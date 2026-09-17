# SPDX-License-Identifier: Apache-2.0
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


APPLY = load('apply-patches')
PREPARE = load('prepare-stock')


class RestoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'integration'
        self.tree = self.root / 'android'
        self.device = self.tree / 'device/xiaomi/gold'
        self.device.mkdir(parents=True)
        self.git('init', '-q')
        (self.device / 'device.mk').write_text('old\n')
        self.git('add', '.')
        self.git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'baseline')
        revision = self.git('rev-parse', 'HEAD').strip()
        (self.repo / 'patches').mkdir(parents=True)
        (self.repo / 'patches/series.json').write_text(json.dumps([{'path': 'device/xiaomi/gold', 'revision': revision, 'patches': [], 'source': 'device/xiaomi/gold'}]))
        self.local = self.repo / 'device/xiaomi/gold'
        self.local.mkdir(parents=True)
        (self.local / 'device.mk').write_text('new\n')
        (self.local / 'extract-files.py').write_text('source\n')
        (self.local / 'extract-files.py').chmod(0o755)
        vendor = self.repo / 'vendor/xiaomi/gold/ims'
        vendor.mkdir(parents=True)
        (vendor / 'Android.bp').write_text('ims\n')

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.device), *args], text=True)

    def run_restore(self, execute=False):
        with patch.object(APPLY, 'REPOSITORY', self.repo), patch.object(sys, 'argv', ['apply', str(self.tree)] + (['--apply'] if execute else [])), contextlib.redirect_stdout(io.StringIO()):
            APPLY.main()

    def test_check_does_not_mutate_and_apply_copies_full_source(self):
        self.run_restore()
        self.assertEqual((self.device / 'device.mk').read_text(), 'old\n')
        self.assertFalse((self.tree / 'vendor').exists())
        self.run_restore(True)
        self.assertEqual((self.device / 'device.mk').read_text(), 'new\n')
        self.assertEqual((self.device / 'extract-files.py').stat().st_mode & 0o777, 0o755)
        self.assertTrue((self.tree / 'vendor/xiaomi/gold/ims/Android.bp').is_file())

    def test_dirty_tree_is_preserved(self):
        (self.device / 'mine.txt').write_text('unique\n')
        with self.assertRaisesRegex(RuntimeError, 'not clean'):
            self.run_restore(True)
        self.assertEqual((self.device / 'mine.txt').read_text(), 'unique\n')
        self.assertEqual((self.device / 'device.mk').read_text(), 'old\n')

    def test_late_vendor_collision_prevents_device_write(self):
        path = self.tree / 'vendor/xiaomi/gold/ims/Android.bp'
        path.parent.mkdir(parents=True)
        path.write_text('mine\n')
        with self.assertRaisesRegex(RuntimeError, 'overwrite'):
            self.run_restore(True)
        self.assertEqual((self.device / 'device.mk').read_text(), 'old\n')

    def test_ignored_device_input_is_not_overwritten(self):
        (self.device / '.git/info/exclude').write_text('extract-files.py\n')
        (self.device / 'extract-files.py').write_text('unique ignored file\n')
        self.assertEqual(self.git('status', '--porcelain'), '')
        with self.assertRaisesRegex(RuntimeError, 'untracked/ignored'):
            self.run_restore(True)
        self.assertEqual((self.device / 'extract-files.py').read_text(), 'unique ignored file\n')
        self.assertEqual((self.device / 'device.mk').read_text(), 'old\n')

    def test_source_symlink_rejected(self):
        (self.local / 'outside').symlink_to(self.root)
        with self.assertRaisesRegex(RuntimeError, 'symlink'):
            self.run_restore(True)

    def test_explicit_upstream_removal_is_applied(self):
        (self.local / 'device.mk').unlink()
        series_path = self.repo / 'patches/series.json'
        series = json.loads(series_path.read_text())
        series[0]['remove'] = ['device.mk']
        series_path.write_text(json.dumps(series))
        self.run_restore(True)
        self.assertFalse((self.device / 'device.mk').exists())

    def test_upstream_deletion_requires_review(self):
        (self.local / 'device.mk').unlink()
        with self.assertRaisesRegex(RuntimeError, 'omits upstream'):
            self.run_restore(True)


class SourceToolsTest(unittest.TestCase):
    @contextlib.contextmanager
    def stock_fixture(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            names = json.loads((ROOT / 'firmware/gold-global.json').read_text())['images']
            images = {}
            for name in names:
                path = root / name
                path.parent.mkdir(exist_ok=True)
                path.write_bytes(('fixture ' + name).encode())
                images[name] = PREPARE.digest(path)
            archive = {'size': 7, 'sha256': 'a' * 64, 'md5': 'b' * 32}
            lock = root / 'lock.json'
            lock.write_text(json.dumps({'version': 'test', 'archive_format': 'recovery-full-ota',
                                        'archive': archive, 'images': images}))
            record = {'schema_version': 2, 'stock_version': 'test', 'archive': archive,
                      'lock_sha256': PREPARE.digest(lock)['sha256'], 'images': images,
                      'prepared_only': True, 'phone_commands_executed': False}
            (root / 'prepared.json').write_text(json.dumps(record))
            yield root, lock, record

    def test_stock_integrity_and_tamper(self):
        with self.stock_fixture() as (root, lock, record):
            result = PREPARE.verify_prepared(root, json.loads(lock.read_text()), lock)
            self.assertEqual(len(result['images']), 25)
            (root / 'physical/boot.img').write_bytes(b'bad image!')
            with self.assertRaises(ValueError):
                PREPARE.verify_prepared(root, json.loads(lock.read_text()), lock)

    def test_missing_locked_partition_rejected(self):
        with self.stock_fixture() as (root, lock, record):
            del record['images']['physical/boot.img']
            (root / 'physical/boot.img').unlink()
            (root / 'prepared.json').write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'missing partition image set'):
                PREPARE.verify_prepared(root, json.loads(lock.read_text()), lock)

    def test_image_and_prepared_hash_changed_together_rejected(self):
        with self.stock_fixture() as (root, lock, record):
            path = root / 'physical/boot.img'
            path.write_bytes(b'replacement image')
            record['images']['physical/boot.img'] = PREPARE.digest(path)
            (root / 'prepared.json').write_text(json.dumps(record))
            with self.assertRaisesRegex(ValueError, 'physical/boot.img verification failed'):
                PREPARE.verify_prepared(root, json.loads(lock.read_text()), lock)

    def test_wrong_lock_rejected(self):
        with self.stock_fixture() as (root, lock, record):
            record['lock_sha256'] = 'wrong'
            (root / 'prepared.json').write_text(json.dumps(record))
            with self.assertRaises(ValueError):
                PREPARE.verify_prepared(root, json.loads(lock.read_text()), lock)

    def test_plan_never_executes_and_mac_execute_is_rejected(self):
        command = [sys.executable, str(ROOT / 'tools/build-source.py'), '--tree', '/nonexistent/android', '--lunch', 'lineage_gold-test-userdebug']
        result = subprocess.run(command, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        plan = json.loads(result.stdout)
        self.assertFalse(plan['execute'])
        self.assertEqual(plan['targets'], ['bacon', 'target-files-package'])
        self.assertEqual(plan['jobs'], 8)
        self.assertEqual(plan['out_dir_env'], 'out-gold-standard')
        self.assertEqual(plan['out_dir'], '/nonexistent/android/out-gold-standard')
        if sys.platform == 'darwin':
            result = subprocess.run(command + ['--execute', '--build-datetime', '1'], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Linux x86_64', result.stderr)


if __name__ == '__main__':
    unittest.main()
