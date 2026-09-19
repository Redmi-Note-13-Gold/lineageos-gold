# Redmi Note 13 5G (`gold`) device tree

SPDX-FileCopyrightText: The LineageOS Project

SPDX-License-Identifier: Apache-2.0

This tree describes the Global OS3.0.5.0.VNQMIXM / 6.6.118 inputs used by the
standard LineageOS 23.2 build. The original device-tree baseline is
mt6833-devs/android_device_xiaomi_gold at
`d3d941c29395ce770b95b735b27bd28e6a8c6946`; Global extraction references and
reviewed differences are recorded in `proprietary-source.json`.

- `lineage_gold.mk` selects the product and 64-bit application zygote.
- `BoardConfig.mk` owns partition, boot, AVB and kernel-module configuration.
  Native 32-bit vendor components remain supported.
- `device.mk`, init, overlays and manifests declare the installed services.
- `sepolicy/` contains source labels/rules. Stock compiled CIL is not imported.
- `prepare-vendor.py` verifies the locked images, runs standard extract-utils
  and prepares matched boot/kernel/DTB/DTBO/modules under
  `vendor/xiaomi/gold/proprietary/kernel/`.

Stock boot is kernel-only. The standard build re-signs that prebuilt input
and builds vendor_boot with the current generic init ramdisk in its named
`init_boot` fragment, plus the platform and Recovery ramdisks. The standard
build also creates DLKM images and the modules symlinks; no image patcher is
part of this device tree.

Use `lineage_gold-bp4a-user` for release-policy validation and
`lineage_gold-bp4a-userdebug` for development. Development certificates are
not release-key acceptance. Compilation and device validation are reported
separately in the integration repository's `docs/BUILD.md` and `docs/STATUS.md`.
Builds use prepared vendor files directly, without a generated-input receipt
or source preflight scan.

Historical property/CIL/image fixes are retained in the integration
repository under `archive/hybrid/` for tracing previous packages. They are
not part of the standard source build.
