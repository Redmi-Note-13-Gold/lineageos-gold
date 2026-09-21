# SPDX-License-Identifier: Apache-2.0
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location(
    'gold_package', Path(__file__).resolve().parents[1] / 'tools/check-gold-package.py')
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class VintfFragmentTest(unittest.TestCase):
    assembled = b'''<!-- Input: /absolute/mainline/power.xml -->
<manifest version="9.0" type="device">
    <hal format="aidl"><name>android.hardware.power</name><version>6</version>
        <fqname>IPower/default</fqname></hal>
</manifest>'''

    def verify(self, actual):
        with patch.object(package.subprocess, 'check_output', return_value=self.assembled) as run:
            package.verify_vintf_fragment(actual, Path('/source/power.xml'), Path('/host/assemble_vintf'))
        self.assertEqual(run.call_args.args[0], ['/host/assemble_vintf', '-i', '/source/power.xml'])
        self.assertEqual(run.call_args.kwargs['env']['VINTF_IGNORE_TARGET_FCM_VERSION'], 'true')

    def test_assembled_schema_and_source_comment_are_handled(self):
        self.verify(self.assembled.replace(b'/absolute/mainline/power.xml', b'device/power.xml'))
        self.verify(self.assembled.replace(b'\n', b'').replace(b'    ', b''))

    def test_interface_version_instance_and_transport_changes_are_rejected(self):
        for old, new in [(b'<version>6</version>', b'<version>5</version>'),
                         (b'IPower/default', b'IPower/other'), (b'format="aidl"', b'format="hidl"')]:
            with self.subTest(change=new), self.assertRaises(ValueError):
                self.verify(self.assembled.replace(old, new))

    def test_extra_missing_and_duplicate_declarations_are_rejected(self):
        for actual in [self.assembled.replace(b'<hal ', b'<hal override="true" '),
                       self.assembled.replace(b'<fqname>IPower/default</fqname>', b''),
                       self.assembled.replace(b'</manifest>', b'<hal format="aidl"><name>extra</name></hal></manifest>'),
                       self.assembled.replace(b'</hal>', b'<fqname>IPower/default</fqname></hal>')]:
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                self.verify(actual)

    def test_root_schema_and_target_level_still_must_match_build_tool(self):
        for actual in [self.assembled.replace(b'version="9.0"', b'version="1.0"'),
                       self.assembled.replace(b'type="device"', b'type="framework"'),
                       self.assembled.replace(b'type="device"', b'type="device" target-level="legacy"')]:
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                self.verify(actual)


class ImsStartupTest(unittest.TestCase):
    defaults = ['persist.vendor.ims_support=1', 'persist.vendor.volte_support=1',
                'ro.vendor.md_auto_setup_ims=1']

    def test_locked_modem_startup_contract(self):
        result = package.verify_ims_startup_properties(self.defaults + ['persist.vendor.mims_support=2'])
        self.assertEqual(result['persist.vendor.ims_support'], '1')

    def test_previous_candidate_mims_count_does_not_initialize_backend(self):
        with self.assertRaisesRegex(ValueError, 'persist.vendor.ims_support'):
            package.verify_ims_startup_properties(['persist.vendor.mims_support=2'])

    def test_disabled_or_missing_required_switch_is_rejected(self):
        for index in range(len(self.defaults)):
            for changed in [self.defaults[:index] + self.defaults[index + 1:],
                            [line if i != index else line[:-1] + '0'
                             for i, line in enumerate(self.defaults)]]:
                with self.subTest(index=index, changed=changed), self.assertRaises(ValueError):
                    package.verify_ims_startup_properties(changed)

    def test_duplicate_even_identical_value_is_rejected(self):
        with self.assertRaises(ValueError):
            package.verify_ims_startup_properties(self.defaults + [self.defaults[0]])


class OpenEuiccManifestTest(unittest.TestCase):
    # Captured with the candidate's actual aapt2, including namespace indentation.
    manifest = (Path(__file__).parent / 'fixtures/openeuicc-aapt2-manifest.txt').read_text()

    def test_real_compiled_manifest_and_shifted_indentation(self):
        package.verify_openeuicc_manifest(self.manifest)
        shifted = ''.join('  ' + line for line in self.manifest.splitlines(keepends=True))
        package.verify_openeuicc_manifest(shifted)

    def test_permission_from_adjacent_service_cannot_satisfy_activity(self):
        # aapt2 prints each string twice (decoded and Raw); replace only main's pair.
        changed = self.manifest.replace('android.permission.BIND_EUICC_SERVICE',
                                        'android.permission.WRONG_PERMISSION', 2)
        self.assertIn('android.permission.BIND_EUICC_SERVICE', changed)
        with self.assertRaisesRegex(ValueError, 'entry points'):
            package.verify_openeuicc_manifest(changed)

    def test_wrong_route_or_launcher_is_rejected(self):
        changes = [
            ('MANAGE_EMBEDDED_SUBSCRIPTIONS', 'WRONG_MANAGEMENT_ACTION', 2),
            ('PROVISION_EMBEDDED_SUBSCRIPTION', 'MANAGE_EMBEDDED_SUBSCRIPTIONS', 2),
            ('android.intent.category.DEFAULT', 'android.intent.category.LAUNCHER', 2),
        ]
        for old, new, count in changes:
            with self.subTest(change=new), self.assertRaises(ValueError):
                package.verify_openeuicc_manifest(self.manifest.replace(old, new, count))

    def test_missing_duplicate_and_alias_activity_are_rejected(self):
        block = next(x for x in package.aapt_element_blocks(self.manifest, 'activity')
                     if '.ui.PrivilegedMainActivity"' in x)
        for changed in [self.manifest.replace(block, ''),
                        self.manifest.replace(block, block + block),
                        self.manifest.replace(block, block.replace('E: activity ', 'E: activity-alias ', 1))]:
            with self.subTest(), self.assertRaises(ValueError):
                package.verify_openeuicc_manifest(changed)

    def test_last_activity_at_end_of_dump_is_kept(self):
        blocks = package.aapt_element_blocks(self.manifest, 'activity')
        main = next(x for x in blocks if '.ui.PrivilegedMainActivity"' in x)
        lui = next(x for x in blocks if '.ui.LuiActivity"' in x)
        package.verify_openeuicc_manifest(main + lui)
