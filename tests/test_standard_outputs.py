# SPDX-License-Identifier: Apache-2.0
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECK = load('check-artifacts')
BUILD = load('build-source')


class OutputContractTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)

    def fixture(self, timestamp=123, flags=0, partition='system', extra_metadata='', radio=False, bad_payload=False):
        target, ota = self.root / 'target.zip', self.root / 'ota.zip'
        vbmeta = bytearray(256)
        vbmeta[:4] = b'AVB0'
        vbmeta[120:124] = struct.pack('>I', flags)
        def varint(value):
            result = bytearray()
            while value > 127:
                result.append((value & 127) | 128)
                value >>= 7
            return bytes(result + bytes([value]))
        def field(number, value):
            if isinstance(value, int):
                return varint(number << 3) + varint(value)
            return varint(number << 3 | 2) + varint(len(value)) + value
        images = {'vbmeta': bytes(vbmeta), partition: b'image'}
        if radio:
            images['lk'] = b'firmware'
        manifest = b''
        for name, data in images.items():
            info = field(1, len(data)) + field(2, hashlib.sha256(data if not bad_payload else b'wrong').digest())
            manifest += field(13, field(1, name.encode()) + field(7, info))
        payload = struct.pack('>4sQQI', b'CrAU', 2, len(manifest), 0) + manifest
        with zipfile.ZipFile(target, 'w') as archive:
            archive.writestr('META/misc_info.txt', 'ab_update=true\navb_enable=true\nuse_dynamic_partitions=true\nvintf_enforce=true\navb_building_vbmeta_image=true\n')
            archive.writestr('META/ab_partitions.txt', 'vbmeta\n' + partition + '\n' + ('lk\n' if radio else ''))
            archive.writestr('META/dynamic_partitions_info.txt', 'dynamic_partition_list=' + partition + '\n')
            archive.writestr('IMAGES/vbmeta.img', vbmeta)
            archive.writestr('IMAGES/' + partition + '.img', b'image')
            if radio:
                archive.writestr('RADIO/lk.img', b'firmware')
        with zipfile.ZipFile(ota, 'w') as archive:
            archive.writestr('META-INF/com/android/metadata', 'ota-type=AB\npre-device=gold\npost-sdk-level=36\npost-timestamp=' + str(timestamp) + '\npost-build=example/test-keys\n' + extra_metadata)
            archive.writestr('META-INF/com/android/metadata.pb', b'fixture')
            archive.writestr('payload.bin', payload)
            archive.writestr('payload_properties.txt', 'FILE_SIZE=' + str(len(payload)) + '\n')
        return target, ota

    def test_small_contract_does_not_claim_signature_verification(self):
        result = CHECK.verify_artifacts(*self.fixture(), 123, ['system', 'vbmeta'])
        self.assertTrue(result['artifact_contract_verified'])
        self.assertNotIn('ota_and_payload_signatures_verified', result)
        self.assertFalse(result['device_accepted'])
        self.assertTrue(result['payload_images_verified'])

    def test_payload_cannot_reference_different_images(self):
        with self.assertRaisesRegex(ValueError, 'differs from target-files'):
            CHECK.verify_artifacts(*self.fixture(bad_payload=True), 123)

    def test_malformed_payload_protobuf_is_rejected(self):
        for data in (b'\x80', b'\x0a\x08x', b'\x00\x01', b'\x0b', b'\xff' * 10):
            with self.subTest(data=data), self.assertRaises(ValueError):
                list(CHECK.protobuf_fields(data))

    def test_duplicate_payload_singular_fields_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'repeated'):
            CHECK.protobuf_single(b'\x08\x01\x08\x02', 1, 0)

    def test_standard_radio_firmware_is_accepted(self):
        result = CHECK.verify_artifacts(*self.fixture(radio=True), 123, ['system', 'vbmeta', 'lk'])
        self.assertEqual(set(result['partitions']), {'system', 'vbmeta', 'lk'})

    def test_reject_stale_timestamp(self):
        with self.assertRaisesRegex(ValueError, 'timestamp'):
            CHECK.verify_artifacts(*self.fixture(), 124)

    def test_reject_wiping_full_package(self):
        with self.assertRaisesRegex(ValueError, 'non-wiping'):
            CHECK.verify_artifacts(*self.fixture(extra_metadata='ota-wipe=yes\n'), 123)

    def test_reject_wrong_product_partition_set(self):
        with self.assertRaisesRegex(ValueError, 'resolved product'):
            CHECK.verify_artifacts(*self.fixture(), 123, ['boot', 'system', 'vbmeta'])

    def test_reject_shared_user_data_partition(self):
        with self.assertRaisesRegex(ValueError, 'unsafe'):
            CHECK.verify_artifacts(*self.fixture(partition='userdata'), 123)

    def test_reject_avb_disabled(self):
        with self.assertRaisesRegex(ValueError, 'disables'):
            CHECK.verify_artifacts(*self.fixture(flags=2), 123)

    def test_cannot_claim_existing_default_or_foreign_output(self):
        tree = self.root / 'android'
        tree.mkdir()
        with self.assertRaisesRegex(ValueError, 'separate'):
            BUILD.claim_output(tree, tree / 'out')
        foreign = tree / 'foreign'
        foreign.mkdir()
        (foreign / 'unique.txt').write_text('preserve')
        with self.assertRaisesRegex(ValueError, 'not owned'):
            BUILD.claim_output(tree, foreign)
        self.assertEqual((foreign / 'unique.txt').read_text(), 'preserve')

    def test_fresh_then_owned_output_has_honest_clean_status(self):
        tree = self.root / 'android'
        tree.mkdir()
        out = tree / 'out-gold-standard'
        self.assertTrue(BUILD.claim_output(tree, out))
        self.assertFalse(BUILD.claim_output(tree, out))

    def test_relative_output_is_resolved_against_source(self):
        tree = self.root / 'android'
        tree.mkdir()
        out = BUILD.output_path(tree, Path('out-gold-standard'))
        self.assertEqual(out, tree.resolve() / 'out-gold-standard')
        self.assertEqual(out.relative_to(tree.resolve()).as_posix(), 'out-gold-standard')
        self.assertFalse(out.exists())  # Planning does not create output.

    def test_external_and_symlink_escape_outputs_are_rejected(self):
        tree = self.root / 'android'
        tree.mkdir()
        outside = self.root / 'source-out'
        with self.assertRaisesRegex(ValueError, 'inside the source tree'):
            BUILD.output_path(tree, outside)
        with self.assertRaisesRegex(ValueError, 'inside the source tree'):
            BUILD.output_path(tree, Path('../source-out'))
        outside.mkdir()
        (outside / 'evidence').write_text('failed build evidence')
        (tree / 'out-link').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'inside the source tree'):
            BUILD.claim_output(tree, tree / 'out-link')
        self.assertEqual((outside / 'evidence').read_text(), 'failed build evidence')
        self.assertFalse((outside / '.gold-source-build.json').exists())

    def test_false_environment_is_not_a_bypass(self):
        self.assertFalse(BUILD.enabled('false'))
        self.assertTrue(BUILD.enabled('true'))

    def test_rebuild_does_not_overwrite_dated_ota_hardlink(self):
        mutable = self.root / 'lineage_gold-ota.zip'
        dated = self.root / 'lineage-previous-gold.zip'
        mutable.write_bytes(b'previous verified OTA')
        os.link(mutable, dated)
        self.assertTrue(BUILD.detach_shared_output(mutable))
        mutable.write_bytes(b'new candidate OTA')
        self.assertEqual(dated.read_bytes(), b'previous verified OTA')
        self.assertEqual(mutable.read_bytes(), b'new candidate OTA')
        self.assertFalse(BUILD.detach_shared_output(mutable))

    def test_missing_ota_needs_no_preservation(self):
        missing = self.root / 'not-built.zip'
        self.assertFalse(BUILD.detach_shared_output(missing))
        self.assertFalse(missing.exists())

    def test_manifest_failure_leaves_unsuccessful_build_record(self):
        tree = self.root / 'android'
        (tree / '.repo').mkdir(parents=True)
        argv = ['build-source', '--tree', str(tree), '--lunch',
                'lineage_gold-bp4a-userdebug', '--execute', '--build-datetime', '123']
        failure = subprocess.CalledProcessError(1, ['repo', 'manifest', '-r'])
        with patch.object(sys, 'argv', argv), \
                patch.object(BUILD.platform, 'system', return_value='Linux'), \
                patch.object(BUILD.platform, 'machine', return_value='x86_64'), \
                patch.object(BUILD.subprocess, 'run', side_effect=failure), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(subprocess.CalledProcessError):
                BUILD.main()
        records = list((tree / 'out-gold-standard/gold-build-records').glob('*/result.json'))
        self.assertEqual(len(records), 1)
        result = json.loads(records[0].read_text())
        self.assertIsNone(result['build_exit_code'])
        self.assertFalse(result['artifact_contract_verified'])
        self.assertFalse(result['android_validators_passed'])
        self.assertIn('manifest', result['error'])


if __name__ == '__main__':
    unittest.main()
