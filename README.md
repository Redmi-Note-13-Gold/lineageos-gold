# LineageOS 23.2 for the Redmi Note 13 5G (`gold`)

Unofficial LineageOS 23.2 (Android 16) for the Redmi Note 13 5G. Test builds, userdebug, test-keys. Not affiliated with Xiaomi, MediaTek or the LineageOS project.

- Downloads: [Releases](https://github.com/Redmi-Note-13-Gold/lineageos-gold/releases)
- Device tree: [android_device_xiaomi_gold](https://github.com/Redmi-Note-13-Gold/android_device_xiaomi_gold), forked from [Dhterech](https://github.com/Dhterech/android_device_xiaomi_gold)

## Device

| | |
| --- | --- |
| SoC | MediaTek Dimensity 6080 (MT6833) |
| Display | 6.67" AMOLED, 1080x2400, 120 Hz |
| Rear camera | 108 MP main (Samsung HM6) + 2 MP depth |
| Front camera | 16 MP |
| Battery | 5000 mAh |
| Tested on | China model 2312DRAABC (`gold_cn`), one unit only |

The device tree also carries the configuration for the Indian and Global (`iron`) models. Nobody has tested those.

## Status

| Feature | Status |
| --- | --- |
| Calls, SMS, 4G/5G data | Works (China Unicom and China Mobile SIMs; China Telecom not tried) |
| Wi-Fi, hotspot | Works, including WPA3; Apple devices can join |
| Bluetooth | Works (headset, calls, file transfer) |
| GPS | Works |
| Camera | Photo and video work. The rear camera outputs 12 MP, the front 4 MP |
| Hardware codecs | H.264, HEVC and VP9 decoding; H.264 and HEVC encoding |
| Sensors, fingerprint | Work |
| Display | 120 Hz, auto-brightness, high brightness mode in sunlight |
| Double tap to wake, lift to wake, tap to wake | Work |
| Charging | USB, fast charging, offline charging, power-off alarm |
| USB | File transfer (MTP), USB tethering |
| System updates | Straight from the Updater app, since the 2026-10-09 build |
| FM radio | Works, with a wired headset as the antenna |
| Wired headset | Playback and the play/pause button work; the headset microphone has not been tried |
| OTG, SD card, IR blaster, wireless display | Not tested |
| NFC | This model has no NFC hardware |

Not possible, or not done:

- 108 MP, portrait and 16 MP front photos. The camera HAL only offers them to the stock camera app.
- Video stabilisation is weak. It takes a patch to the camera app to make it effective, and we do not carry one.
- No always-on display. With this panel the system cannot suspend while it is showing, about 290 mA, so it was removed in favour of lift and tap to wake.
- While connected to 5 GHz Wi-Fi the hotspot can only use the same channel. There is a single Wi-Fi radio.

Measured:

- Standby: about 15 mA with the screen off, Wi-Fi connected and no SIM; 1% in three hours.
- Thermal: with all eight cores loaded for about seven minutes the CPU reaches roughly 63°C, is throttled, and settles around 58°C.

## Before installing

- Unlock the bootloader first. Do not relock it while this is installed.
- The package does not carry preloader, lk, tee or modem firmware, only `scp`. Everything else stays as it is on the phone. Our test unit has the firmware of China `OS3.0.10.0.VNQCNXM`.
- We have only installed it two ways: updating from an earlier build of this tree with the Updater app, or with `update_engine`. A first install from the stock ROM has not been tested.
- Builds from 2026-09-30 and earlier come from the old structure, and moving from them needs a data wipe. That code is in this repository's tag `pre-restructure` and the device tree's tag [`gold-r7`](https://github.com/Redmi-Note-13-Gold/android_device_xiaomi_gold/tree/gold-r7).

## What is in this repository

| File | Purpose |
| --- | --- |
| `local_manifests/gold.xml` | Local manifest: the device tree, the common MediaTek and Xiaomi repositories, IMS |
| `extract-kernel.sh` | Takes the kernel, DTB and kernel modules out of the stock package |
| `host/` | Build script and two patches for a build host with little RAM |
| `updates.json` | The list of builds the Updater app reads |

The kernel and the vendor blobs are not in any repository. Both are extracted from the same stock package.

## Building

You need `repo`, `git-lfs`, `erofs-utils`, `lz4`, `cpio` and `unzip`, plus the usual [LineageOS build dependencies](https://wiki.lineageos.org/devices/).

```sh
repo init -u https://github.com/LineageOS/android.git -b lineage-23.2 --git-lfs
mkdir -p .repo/local_manifests
curl -o .repo/local_manifests/gold.xml \
  https://raw.githubusercontent.com/Redmi-Note-13-Gold/lineageos-gold/main/local_manifests/gold.xml
repo sync -c
```

Extract the kernel and the vendor blobs. Both take the stock full OTA `gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip` (SHA-256 `35c9f1d98b28538ac10c319ad4cba993cd5a632960d9111162e3efa494dae5c9`). `extract-kernel.sh` checks that checksum and stops on any other package; set `ANY_OTA=1` to try one anyway.

```sh
curl -O https://raw.githubusercontent.com/Redmi-Note-13-Gold/lineageos-gold/main/extract-kernel.sh
bash extract-kernel.sh /path/to/gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip
cd device/xiaomi/gold
./extract-files.py /path/to/gold_global-ota_full-OS3.0.5.0.VNQMIXM-user-15.0-df9ff3aa93.zip
cd -
```

Build:

```sh
source build/envsetup.sh
breakfast gold userdebug
m bacon
```

The output is in `out/target/product/gold/`.

### Build hosts with little RAM

`host/build.sh` is what we use on an 8-core, 14 GB machine. Run it from the top of the Android tree, or set `SOURCE_TREE`. It does the same as the steps above, turns on ccache if it is installed, and applies two local patches. A host with enough memory does not need it.

- `soong-memory-env.patch` (`build/soong`): passes `GOGC` and `GOMEMLIMIT` through to soong_build.
- `lineage-build-date.patch` (`vendor/lineage`): lets the date in the version string be fixed. When the date changes Soong redoes its whole analysis, which takes hours on that machine. The script keeps the date the current `out/` was first built with; set `LINEAGE_BUILD_DATE` to change it.

Restore both projects before `repo sync`: `git -C build/soong checkout . && git -C vendor/lineage checkout .`

## Differences from Dhterech's tree

Device tree: our commits sit on top of his head, one change each. [Here is the list.](https://github.com/Redmi-Note-13-Gold/android_device_xiaomi_gold/compare/727b728...lineage-23.2) Roughly:

- Things that did not work on his tree: offline charging, GPS, FM, USB tethering, a crash when Bluetooth is turned off, 32-bit apps crashing, the hardware codec service crashing now and then, auto-brightness that only went up.
- Wi-Fi: joins an iPhone's hotspot, and Apple devices can join the phone's WPA3 hotspot.
- Added: double tap to wake, lift to wake, tap to wake, power-off alarm, updates from the Updater app.
- Networks in mainland China: connectivity checks and time servers that answer from there.
- Choices: always-on display removed, window blur off.
- Clean-up: services and scripts that were never installed or had nothing to run are gone, and tethering hardware offload, which this modem does not provide, is no longer declared.

Kernel: he keeps the prebuilt files in a repository. We generate the same directory straight from the stock package with `extract-kernel.sh`, so the origin of every file can be checked by running it again. Compared with his repository the result:

- Has a `system_dlkm/` directory. His repository only committed the image, the device tree wants the directory, and without it there is no zram and the Wi-Fi driver does not load.
- Changes one instruction in `hq_charger_sysfs.ko` to stop a thread that only serves MIUI's charging animation. On a computer's USB port it sent ten battery events a second.
- Is otherwise byte for byte the same in every file the build uses.

Firmware: his package writes eleven firmware partitions. The packages we have released write only `scp`.

## Credits

- [Dhterech](https://github.com/Dhterech/android_device_xiaomi_gold) for the device tree, and those he credits: xiaomi-mt6833-dev, aeronruless and linastorvaldz.
- claxten10 and [mt6833-devs](https://github.com/mt6833-devs/android_device_xiaomi_gold). Dhterech's tree is built on theirs, which makes up 204 of its 295 commits, and our old structure was based on it too.
- [techyminati](https://github.com/techyminati/android_vendor_mediatek_ims) for MediaTek IMS.
- [cristidclxvi](https://github.com/cristidclxvi/android_device_xiaomi_camellia) for the camellia device tree, same chip. Two Wi-Fi overlay values follow it: the 2.4 GHz hotspot stays on channels 1 to 11, and Wi-Fi is not dropped to apply the country code.
- [LineageOS](https://lineageos.org).
