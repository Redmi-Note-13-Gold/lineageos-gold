# SPDX-License-Identifier: Apache-2.0
import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


host = load('research_layout', 'tools/host/check-research-layout.py')
index = load('candidate_index', 'tools/index-candidates.py')


class ResearchMountTests(unittest.TestCase):
    def setUp(self):
        self.layout = json.loads((ROOT / 'tools/host/research-layout.json').read_text())
        c = self.layout
        self.mounts = [
            {'target': c['build_mount'], 'fstype': 'ext4', 'uuid': c['build_mount_uuid'], 'options': 'rw,noatime'},
            {'target': c['source'], 'fstype': 'overlay', 'options':
             f"rw,relatime,lowerdir={c['lower']},upperdir={c['upper']},workdir={c['work']},nouserxattr"}]

    def test_expected_mounts(self):
        self.assertEqual(host.validate_mounts(self.layout, self.mounts)['source']['fstype'], 'overlay')

    def test_missing_overlay_does_not_accept_parent_disk(self):
        with self.assertRaisesRegex(ValueError, 'exact OverlayFS'):
            host.validate_mounts(self.layout, self.mounts[:1])

    def test_wrong_data_disk_rejected(self):
        self.mounts[0]['uuid'] = 'different-disk'
        with self.assertRaisesRegex(ValueError, 'data disk'):
            host.validate_mounts(self.layout, self.mounts)

    def test_each_stale_overlay_layer_rejected(self):
        for key in ['lower', 'upper', 'work']:
            with self.subTest(layer=key):
                mounts = copy.deepcopy(self.mounts)
                mounts[1]['options'] = mounts[1]['options'].replace(self.layout[key], '/old-layer')
                with self.assertRaisesRegex(ValueError, 'Unexpected OverlayFS'):
                    host.validate_mounts(self.layout, mounts)

    def test_read_only_mount_rejected(self):
        for n in [0, 1]:
            with self.subTest(mount=n):
                mounts = copy.deepcopy(self.mounts)
                mounts[n]['options'] = mounts[n]['options'].replace('rw,', 'ro,')
                with self.assertRaisesRegex(ValueError, 'writable mount'):
                    host.validate_mounts(self.layout, mounts)


class CandidateInventoryTests(unittest.TestCase):
    def test_directory_name_does_not_imply_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'lineage_gold-ota.zip').write_bytes(b'synthetic-package')
            found = index.candidate(root)
            self.assertIsNone(found['package_checks_recorded'])
            self.assertIsNone(found['artifacts'][0]['recorded_hash_verified_now'])

    def test_corrupt_frozen_package_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / 'lineage_gold-ota.zip'
            artifact.write_bytes(b'original')
            record = {'ota': {'bytes': 8, 'sha256': index.digest(artifact)}}
            (root / 'candidate.json').write_text(json.dumps(record))
            artifact.write_bytes(b'changed!')
            with self.assertRaisesRegex(ValueError, 'hash mismatch'):
                index.candidate(root, verify_hashes=True)

    def test_missing_package_is_not_a_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ValueError, 'no ZIP'):
                index.candidate(Path(tmp))

    def test_navigation_preserves_physical_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            physical = Path(tmp) / 'physical'
            physical.mkdir()
            (physical / 'lineage_gold-ota.zip').write_bytes(b'synthetic-package')
            alias = Path(tmp) / 'link'
            alias.symlink_to(physical, target_is_directory=True)
            found = index.candidate(alias)
            self.assertEqual(found['path'], str(alias))
            self.assertEqual(found['storage_path'], str(physical.resolve()))


if __name__ == '__main__':
    unittest.main()
