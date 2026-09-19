#!/usr/bin/env -S PYTHONPATH=../../../tools/extract-utils python3
#
# SPDX-FileCopyrightText: 2024 The LineageOS Project
# SPDX-License-Identifier: Apache-2.0
#

from pathlib import Path
import shutil

from extract_utils.fixups_blob import (
    blob_fixup,
    blob_fixups_user_type,
)

from extract_utils.main import (
    ExtractUtils,
    ExtractUtilsModule,
)

namespace_imports = [
    'device/xiaomi/gold',
    'hardware/mediatek',
    'hardware/mediatek/libmtkperf_client',
    'hardware/xiaomi',
]

blob_fixups: blob_fixups_user_type = {

    # Keep modem runtime files in a vendor-owned, non-user directory.
    'vendor/bin/ccci_mdinit': blob_fixup()
        .binary_regex_replace(br'/data/vendor_de/md\x00', b'/data/vendor/md\x00\x00\x00\x00'),

    'vendor/etc/init/init.cccimdinit.rc': blob_fixup()
        .regex_replace(r'/data/vendor_de/md', '/data/vendor/md'),

    # The camera HAL owns this calibration-status property in the vendor namespace.
    'vendor/lib64/libcameracustom.so': blob_fixup()
        .binary_regex_replace(br'persist\.camera\.dualcal\.state\x00', b'persist.vendor.cam.dualcal\x00\x00\x00'),


    'vendor/lib64/hw/fingerprint.fpc.default.so': blob_fixup()
        .binary_regex_replace(
            br'fingerprint\.fpc\x00',
            b'fingerprint\x00\x00\x00\x00\x00',
        ),

    'vendor/lib64/hw/fingerprint.goodix.default.so': blob_fixup()
        .binary_regex_replace(
            br'fingerprint\.goodix\x00',
            b'fingerprint\x00\x00\x00\x00\x00\x00\x00\x00',
        ),

    'vendor/lib64/libgoodixhwfingerprint.so': blob_fixup()
        .replace_needed('libvendor.xiaomi.hardware.fx.tunnel@1.0.so', 'vendor.xiaomi.hardware.fx.tunnel@1.0.so'),

    ('vendor/bin/mnld',
     'vendor/lib64/libcam.utils.sensorprovider.so',
     'vendor/lib64/libaalservice.so'): blob_fixup()
        .replace_needed(
            'android.hardware.sensors-V2-ndk.so',
            'android.hardware.sensors-V3-ndk.so',
        ),

    # From device_xiaomi_duchamp
    'vendor/bin/hw/android.hardware.security.keymint@3.0-service.mitee': blob_fixup()
        .replace_needed(
            'android.hardware.security.keymint-V3-ndk.so',
            'android.hardware.security.keymint-V3-ndk-prebuilt.so',
        ),


    # From device_xiaomi_duchamp
    'vendor/lib64/libmtkcam_hal_aidl_common.so': blob_fixup()
        .replace_needed('android.hardware.camera.common-V2-ndk.so', 'android.hardware.camera.common-V1-ndk.so'),

    # Android 15 vendor AIDL interfaces against the Lineage 23.2 platform.
    ('vendor/lib64/hw/mapper.mediatek.so',
     'vendor/lib64/egl/libGLES_mali.so',
     'vendor/bin/hw/android.hardware.graphics.allocator-V2-service-mediatek',
     'vendor/lib64/vendor.mediatek.hardware.camera.isphal-V1-ndk.so',
     'vendor/lib64/hw/android.hardware.graphics.allocator-V2-mediatek.so',
     'vendor/lib64/vendor.mediatek.hardware.pq_aidl-V4-ndk.so',
     'vendor/lib/vendor.mediatek.hardware.pq_aidl-V4-ndk.so',
     'vendor/lib64/vendor.mediatek.hardware.pq_aidl-V2-ndk.so',
     'vendor/lib/vendor.mediatek.hardware.pq_aidl-V2-ndk.so',
     'vendor/lib64/libmtkcam_grallocutils.so',
     'vendor/lib64/libcodec2_fsr.so',
     'vendor/lib/libcodec2_fsr.so',
     'vendor/lib64/libgpud.so'): blob_fixup()
        .replace_needed('android.hardware.graphics.common-V5-ndk.so', 'android.hardware.graphics.common-V7-ndk.so'),

    # From android_device_xiaomi_rosemary
    ('vendor/lib64/libMiVideoFilter.so'): blob_fixup()
        .clear_symbol_version('AHardwareBuffer_allocate')
        .clear_symbol_version('AHardwareBuffer_describe')
        .clear_symbol_version('AHardwareBuffer_lock')
        .clear_symbol_version('AHardwareBuffer_lockPlanes')
        .clear_symbol_version('AHardwareBuffer_release')
        .clear_symbol_version('AHardwareBuffer_unlock'),

    'vendor/lib/libvcodec_oal.so': blob_fixup()
        .clear_symbol_version('__aeabi_memcpy')
        .clear_symbol_version('__aeabi_memset')
        .clear_symbol_version('__gnu_Unwind_Find_exidx'),

    # libtinyxml
    ('vendor/lib64/libsilkybrightnesscore.so',
     'vendor/lib64/hw/vendor.mediatek.hardware.pq_aidl-impl.so',
     'vendor/lib64/libpqxmlparser.so'): blob_fixup()
        .replace_needed(
            'libtinyxml2.so',
            'libtinyxml2-v34.so',
        ),

    # Keep all composer changes in one key: duplicate dict keys silently lose fixups.
    'vendor/lib64/hw/hwcomposer.mtk_common.so': blob_fixup()
        .replace_needed('android.hardware.graphics.common-V5-ndk.so', 'android.hardware.graphics.common-V7-ndk.so')
        .replace_needed('libtinyxml2.so', 'libtinyxml2-v34.so')
        .add_needed('libprocessgroup_shim.so'),

    # mtk pq
    'vendor/lib64/vendor.mediatek.hardware.pq_aidl-V7-ndk.so': blob_fixup()
        .replace_needed('android.hardware.graphics.common-V4-ndk.so',
        'android.hardware.graphics.common-V7-ndk.so')


}  # fmt: skip

class GoldModule(ExtractUtilsModule):
    def cleanup(self):
        # extract-utils normally clears the whole vendor tree. IMS recipes here
        # are authored inputs, so only clear directories owned by extraction.
        vendor = Path(self.vendor_path)
        for name in ('proprietary', 'radio'):
            directory = vendor / name
            if directory.is_symlink():
                raise RuntimeError(f'Refusing symlink extraction output: {directory}')
            if directory.exists():
                shutil.rmtree(directory)
            directory.mkdir(parents=True)
        (vendor / 'input-receipt.json').unlink(missing_ok=True)


def write_odm_sku_manifests(ctx, _packages):
    # android-info.mk owns SKU module creation, assembly and ODM installation.
    # Keep these as EXTRACT_ONLY inputs so no copied VINTF metadata or duplicate
    # Soong module competes with the platform's odm_manifest_<sku>.xml module.
    skus = ('iron_gl', 'iron_p_gl')
    ctx.board_config_mk_out.write('\nODM_MANIFEST_SKUS += ' + ' '.join(skus) + '\n')
    for sku in skus:
        ctx.board_config_mk_out.write(
            f'ODM_MANIFEST_{sku.upper()}_FILES := '
            f'vendor/xiaomi/gold/proprietary/vendor/odm/etc/vintf/manifest_{sku}.xml\n'
        )


module = GoldModule(
    'gold',
    'xiaomi',
    blob_fixups=blob_fixups,
    namespace_imports=namespace_imports,
    add_firmware_proprietary_file=True,
)

# The main proprietary list is registered after the firmware list.
module.proprietary_files[-1].add_post_makefile_generation_fn(write_odm_sku_manifests)

if __name__ == '__main__':
    utils = ExtractUtils.device(module)
    utils.run()
