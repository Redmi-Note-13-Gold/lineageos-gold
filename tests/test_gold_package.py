# SPDX-License-Identifier: Apache-2.0
import importlib.util
import io
import subprocess
import zipfile
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


class RemovedEuiccTest(unittest.TestCase):
    def verify(self, members):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            for name, data in members.items():
                archive.writestr(name, data)
        with zipfile.ZipFile(buffer) as archive:
            return package.verify_euicc_removed(archive)

    def test_regular_dual_sim_ims_and_platform_apis_remain_allowed(self):
        result = self.verify({'SYSTEM_EXT/priv-app/ImsService/ImsService.apk': b'ims',
                              'SYSTEM/framework/framework.jar': b'EuiccManager API',
                              'VENDOR/etc/permissions/phone.xml':
                              b'<permissions><feature name="android.hardware.telephony.ims"/></permissions>'})
        self.assertFalse(result['supported'])

    def test_stale_apk_compiled_code_library_and_permission_files_are_rejected(self):
        for name in ['SYSTEM_EXT/priv-app/OpenEUICC/OpenEUICC.apk',
                     'SYSTEM_EXT/priv-app/OpenEUICC/oat/arm64/OpenEUICC.odex',
                     'SYSTEM_EXT/etc/permissions/privapp_whitelist_im.angry.openeuicc.xml',
                     'SYSTEM_EXT/lib64/liblpac-jni.so',
                     'PRODUCT/lib/liblpac-jni.so',
                     'PRODUCT/etc/permissions/android.hardware.telephony.euicc.mep.xml']:
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'still packaged'):
                self.verify({name: b'residual'})

    def test_renamed_feature_xml_is_rejected(self):
        for feature in ['android.hardware.telephony.euicc', 'android.hardware.telephony.euicc.mep']:
            with self.subTest(feature=feature), self.assertRaisesRegex(ValueError, 'feature still declared'):
                self.verify({'VENDOR/etc/permissions/phone.xml':
                             '<permissions><feature name="' + feature + '"/></permissions>'})

    def test_renamed_privileged_permission_xml_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'permission grant'):
            self.verify({'SYSTEM_EXT/etc/permissions/privileged.xml':
                         '<permissions><privapp-permissions package="im.angry.openeuicc"/></permissions>'})

    def test_image_lookup_miss_proves_paths_absent(self):
        missing = subprocess.CompletedProcess([], 0, '', 'File not found by ext2_lookup')
        with patch.object(package.subprocess, 'run', return_value=missing):
            self.assertEqual(package.verify_euicc_image_removed(Path('/system_ext.img')),
                             list(package.REMOVED_EUICC_IMAGE_PATHS))

    def test_existing_image_entry_and_reader_failure_cannot_pass_absence_check(self):
        for result in [subprocess.CompletedProcess([], 0, 'Inode: 41 Type: regular', ''),
                       subprocess.CompletedProcess([], 0, '', 'Bad magic number in super-block'),
                       subprocess.CompletedProcess([], 1, '', 'File not found by ext2_lookup')]:
            with self.subTest(result=result), patch.object(package.subprocess, 'run', return_value=result), self.assertRaises(ValueError):
                package.verify_euicc_image_removed(Path('/system_ext.img'))
