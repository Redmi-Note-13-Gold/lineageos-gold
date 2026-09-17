# Gold vendor inputs

`ims/` contains authored integration sources and must survive extraction. All
other build inputs are generated from the pinned Global stock release by
`device/xiaomi/gold/prepare-vendor.py`. Do not copy a previous vendor tree into a
new checkout or commit extracted Xiaomi binaries here.

On the native Linux Android build host, after preparing the images described by
`firmware/gold-global.json`:

```sh
python3 device/xiaomi/gold/prepare-vendor.py \
  --tree "$PWD" --lock /path/to/gold-global.json \
  --stock /path/to/prepared-stock \
  --ims-apk /path/to/pinned-23.2-compatible/ImsService.apk
```

The stock directory contains `logical/*.img` and `physical/*.img`. The script
checks all 25 image sizes and hashes, extracts the standard proprietary list,
runs the reviewed ELF fixups, generates Android/Soong makefiles, and collects
matching boot, DTB, DTBO and module inputs under `proprietary/kernel/`. Kernel
modules retain their original bytes and both stock ramdisk load lists. Firmware
uses extract-utils' radio rules and the selected list in
`device/xiaomi/gold/proprietary-firmware.txt`: Global `scp` only.
Other stock firmware is left on the device; stock verification images
are excluded. The Android build signs the final images and packages the OTA.

Builds use the prepared vendor files directly. The extra generated-input
receipt and pre-build source comparison have been removed. Keep permanent
fixes in the extraction recipes so the next extraction preserves them.
`extract-files.py` can also be used directly with a normal stock dump; its
cleanup preserves `ims/` and clears only generated blob/radio trees. The
preparation entry additionally collects the matched kernel and IMS inputs.

The IMS compatibility APK is an explicit, SHA-256-pinned prebuilt input, with
source recipe and provenance in `ims/`. Its reconstruction from an arbitrary
stock APK is not yet closed; this remains distinct from a complete standard
build using the pinned input. Preparation does not claim a successful full
source build or real-device validation.

The current firmware selection contains one RADIO image, Global SCP. Older
22-partition packages are historical. Google apps or voice-assistant
compatibility is not established by selecting Global SCP.
