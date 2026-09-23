# SPDX-License-Identifier: Apache-2.0
"""Execute the actual Gold CleanSpec commands in isolated product fixtures."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / 'device/xiaomi/gold/CleanSpec.mk'


class RetiredEuiccCleanupTest(unittest.TestCase):
    def exercise(self, device):
        with tempfile.TemporaryDirectory(prefix='gold-cleanspec-') as temporary:
            root = Path(temporary)
            product = root / 'out/target/product/gold'
            old = product / 'system_ext/priv-app/OpenEUICC'
            (old / 'lib/arm64').mkdir(parents=True)
            external = root / 'external-library'
            external.write_bytes(b'keep external target')
            (old / 'lib/arm64/liblpac-jni.so').symlink_to('/system_ext/lib64/liblpac-jni.so')
            (old / 'must-not-follow').symlink_to(external)
            removed = [
                'system_ext/etc/permissions/android.hardware.telephony.euicc.xml',
                'system_ext/etc/permissions/android.hardware.telephony.euicc.mep.xml',
                'system_ext/etc/permissions/privapp_whitelist_im.angry.openeuicc.xml',
                'system_ext/lib/liblpac-jni.so', 'system_ext/lib64/liblpac-jni.so',
                'system_ext.img', 'installed-files-system_ext.txt',
                'installed-files-system_ext.json',
                'obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip.list',
            ]
            kept = [
                'system_ext/priv-app/ImsService/ImsService.apk',
                'system_ext/overlay/GoldStatusBarOverlay.apk',
                'vendor/lib64/libhardware.so', 'obj/keep-compiled.o',
                'obj/PACKAGING/target_files_intermediates/lineage_gold-target_files.zip',
            ]
            for name in removed + kept:
                path = product / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(name.encode())
            makefile = root / 'Makefile'
            makefile.write_text('TARGET_DEVICE := ' + device + '\nPRODUCT_OUT := ' + str(product) +
                '\ndefine add-clean-step\n$(shell $(1))\nendef\ninclude ' + str(SPEC) +
                '\n.PHONY: verify\nverify:\n\t@true\n')
            for _ in range(2):
                subprocess.run(['make', '--no-print-directory', '-f', str(makefile), 'verify'], check=True)
                self.assertEqual(old.exists(), device != 'gold')
                for name in removed:
                    self.assertEqual((product / name).exists(), device != 'gold', name)
                for name in kept:
                    self.assertEqual((product / name).read_bytes(), name.encode())
                self.assertEqual(external.read_bytes(), b'keep external target')

    def test_gold_removes_dangling_jni_link_and_invalidates_only_affected_outputs(self):
        self.exercise('gold')

    def test_other_device_output_is_untouched(self):
        self.exercise('other')
