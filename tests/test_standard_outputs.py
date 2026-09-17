# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
from pathlib import Path
import struct
import tempfile
import unittest
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

    def fixture(self, timestamp=123, flags=0, partition='system', extra_metadata='', radio=False):
        target, ota = self.root / 'target.zip', self.root / 'ota.zip'
        vbmeta = bytearray(256)
        vbmeta[:4] = b'AVB0'
        vbmeta[120:124] = struct.pack('>I', flags)
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
            archive.writestr('payload.bin', b'fixture payload')
            archive.writestr('payload_properties.txt', 'FILE_SIZE=15\n')
        return target, ota

    def test_small_contract_does_not_claim_signature_verification(self):
        result = CHECK.verify_artifacts(*self.fixture(), 123, ['system', 'vbmeta'])
        self.assertTrue(result['artifact_contract_verified'])
        self.assertNotIn('ota_and_payload_signatures_verified', result)
        self.assertFalse(result['device_accepted'])

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


if __name__ == '__main__':
    unittest.main()
