# LineageOS for the Redmi Note 13 5G (`gold`)

Unofficial LineageOS for the Redmi Note 13 5G. Test builds: userdebug, signed with test keys. Not affiliated with Xiaomi, MediaTek or the LineageOS project.

| | |
| --- | --- |
| Downloads | [Releases](https://github.com/Star-caorui/lineageos-gold/releases) |
| How to build | [local_manifests](https://github.com/Star-caorui/local_manifests) |
| Device tree | [android_device_xiaomi_gold](https://github.com/Star-caorui/android_device_xiaomi_gold), forked from [Dhterech's](https://github.com/Dhterech/android_device_xiaomi_gold) |
| Prebuilt kernel | [android_device_xiaomi_gold-kernel](https://github.com/Star-caorui/android_device_xiaomi_gold-kernel) |
| Kernel source | [android_kernel_xiaomi_gold](https://github.com/Star-caorui/android_kernel_xiaomi_gold) (Android common kernel), with the modules in [android_kernel_xiaomi_gold-modules](https://github.com/Star-caorui/android_kernel_xiaomi_gold-modules) and [android_kernel_xiaomi_gold-mediatek_modules](https://github.com/Star-caorui/android_kernel_xiaomi_gold-mediatek_modules). Off by default |
| Proprietary files | [android_vendor_xiaomi_gold](https://github.com/Star-caorui/android_vendor_xiaomi_gold) |

## Builds

| | Android | Latest build | |
| --- | --- | --- | --- |
| LineageOS 24.0 | 17 | [2026101403](https://github.com/Star-caorui/lineageos-gold/releases/tag/LineageOS-gold-Unofficial-24.0-Vanilla-2026101403) | Current |

## Installing

- Unlock the bootloader first. Do not relock it while this is installed.
- The package also writes the firmware: preloader, lk, tee, modem and seven more partitions, taken from Global `OS3.0.5.0.VNQMIXM`.
- The device has A/B slots. If the new system does not start, the phone returns to the old one.
- If you installed one of our early ROMs, you will very likely need to wipe data.

| Method | Status |
| --- | --- |
| Updater app (OTA) | PASS |
| `update_engine_client` over ADB | PASS |
| Recovery, ADB sideload | PASS |
| Recovery, from an SD card or a USB drive | Not tested |
| First install from the stock ROM | Not tested |

The Updater app does not cross from 23.2 to 24.0. For that step, install the full package by hand.

## Device

| | |
| --- | --- |
| SoC | MediaTek Dimensity 6080 (MT6833) |
| Display | 6.67" AMOLED, 1080x2400, 120 Hz |
| Rear camera | 108 MP main (Samsung HM6) + 2 MP depth |
| Front camera | 16 MP |
| Battery | 5000 mAh |
| Tested on | China model 2312DRAABC (`gold_cn`); Indian model 2312DRAABI (`gold_in_global`) |

The device tree also carries the configuration for the Indian and Global models (`iron`). Their column in the status table holds what `iron` users have reported.

## Status

The rows are the items of LineageOS's [device support requirements](https://github.com/LineageOS/charter/blob/main/device-support-requirements.md), in its order. "Not tested" means nobody has tried it yet, not that it is known to be broken. "Not on stock" means the stock OS does not have it either, so the requirement does not apply.

<table>
  <tr><th></th><th></th><th>gold</th><th>iron</th></tr>
  <tr><td>Audio</td><td>Audio playback for media content</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>In-call audio</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Speaker audio</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Additional audio configuration (echo cancellation, extra mics)</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Other audio outputs of the stock OS: headphone jack, Bluetooth</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Other audio outputs of the stock OS: USB-C</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>FM radio</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>RIL</td><td>Phone calls and data</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Emergency calling with a SIM inserted</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Emergency calling without a SIM inserted</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td>Encryption</td><td>Hardware-backed encryption</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Encryption enabled by default</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Software encryption</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td>Wi-Fi</td><td>Wi-Fi</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Same MAC address as on the stock OS</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Wi-Fi tethering</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>USB</td><td>File access via MTP</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>USB tethering</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>GPS</td><td>GPS</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Bluetooth</td><td>Bluetooth</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Same MAC address as on the stock OS</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Bluetooth tethering</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>aptX</td><td align="center">Not on stock</td><td align="center">Not on stock</td></tr>
  <tr><td>Camera</td><td>Front facing and rear camera</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>All rear cameras (two or more)</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>All front cameras (two or more)</td><td align="center">No hardware</td><td align="center">No hardware</td></tr>
  <tr><td>Video Recording</td><td>Video recording, rear camera</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Video recording, front camera</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td>Codecs</td><td>Hardware encoding and decoding of the codecs the stock OS supports</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Display</td><td>Same resolution as the stock OS</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Same density as the stock OS</td><td align="center">440, stock is 480</td><td align="center">440, stock is 480</td></tr>
  <tr><td></td><td>Additional non-USB display interfaces</td><td align="center">No hardware</td><td align="center">No hardware</td></tr>
  <tr><td></td><td>Display output the stock OS supports (Miracast)</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>HDR10 playback</td><td align="center">Not on stock</td><td align="center">Not on stock</td></tr>
  <tr><td>NFC</td><td>NFC</td><td align="center">No hardware</td><td align="center">PASS</td></tr>
  <tr><td>Fingerprint Sensor</td><td>Fingerprint sensor</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>IR</td><td>IR blaster</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>SD card</td><td>SD cards</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Adoptable storage</td><td align="center">Not tested</td><td align="center">Not tested</td></tr>
  <tr><td>Accelerometer</td><td>Accelerometer</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Gyroscope</td><td>Gyroscope</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Proximity</td><td>Proximity sensor</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Light</td><td>Light sensor</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Other Sensors</td><td>All other sensors of the stock OS</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Accessories</td><td>Proprietary accessories</td><td align="center">No hardware</td><td align="center">No hardware</td></tr>
  <tr><td>SELinux status</td><td>SELinux Enforcing</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Verity</td><td>Verity disabled on the system image for userdebug builds</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Verity on the vendor image</td><td align="center">Not supported</td><td align="center">Not supported</td></tr>
  <tr><td>Updater</td><td>Upgrades via the Updater app and the recovery</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>FRP</td><td>Factory Reset Protection when Google apps are installed</td><td align="center">Not supported</td><td align="center">Not supported</td></tr>
  <tr><td>LineageOS Recovery</td><td>Lineage Recovery works for installation</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Addon packages</td><td>Addon packages can be installed through Lineage Recovery</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
</table>

Measured on 23.2:

- Standby: about 15 mA with the screen off, Wi-Fi connected and no SIM. 1% in three hours.
- Thermal: with all eight cores loaded for about seven minutes the CPU reaches roughly 63°C, is throttled, and settles around 58°C.

## This repository

| | |
| --- | --- |
| `.github/workflows/build.yml`, `ci/` | Build a package from source on a Google Cloud spot VM and make a draft release of it. Started by hand from the Actions tab. Each run keeps the whole log and the build tools' timing data, and its summary shows where the build time went and what it cost |
| `update-lists.py` | Writes the update lists |
| `updates/` | The lists the Updater app reads, one per published 24.0 build |

A 24.0 build asks for `updates/<its ro.build.version.incremental>.json`. When a build is published, `update-lists.py` rewrites the lists of the builds before it, and every one of them is offered the new full package.

Each release built by the workflow carries `manifest-snapshot.xml`, the exact commit of every repository it was built from. Giving its URL to the workflow rebuilds that release.

Its files also carry a signed build provenance attestation: `gh attestation verify <file> -R Star-caorui/lineageos-gold` checks that a file is the one this repository's workflow produced.

## Credits

- [Dhterech](https://github.com/Dhterech/android_device_xiaomi_gold), whose device tree ours was forked from (at `6c5bdc8`), and those he credits: xiaomi-mt6833-dev, aeronruless and linastorvaldz.
- claxten10 and [mt6833-devs](https://github.com/mt6833-devs/android_device_xiaomi_gold). Dhterech's tree is built on theirs, which makes up 204 of its 295 commits.
- [cristidclxvi](https://github.com/cristidclxvi/android_device_xiaomi_camellia) for the camellia device tree, same chip. The way double tap to wake is switched follows it, and so do two Wi-Fi settings.
- [LineageOS](https://lineageos.org), and the maintainers of its MediaTek device trees, which many of our commits follow: [android_device_motorola_mt6768-common](https://github.com/LineageOS/android_device_motorola_mt6768-common) (the stock AIDL audio service, the IMS files, the mtkpower stubs, and the changes for LineageOS 24.0 by Nolen Johnson, Michael Bestas, Nicholas Lim, Elias Gheeraert, Mashopy and Giovanni Ricca), android_device_motorola_mt6879-common, android_device_motorola_lamu, android_device_xiaomi_rosemary and android_device_xiaomi_mt6768-common.
- crDroid's android_device_xiaomi_everpal, same chip, as a reference for what to take from the stock images.
- bengris32, whose patch for Motorola's ImsService ours repeats on this device's build of the app.
- [techyminati](https://github.com/techyminati/android_vendor_mediatek_ims) for the MediaTek IMS package our earlier builds used.
- The testers in the Telegram community, who ran test builds and sent logs: ukriu (call volume, charging, Bluetooth audio, USB OTG), yuuki (call volume, app drawer stutter), affan (5G on an Indonesian carrier), and everyone else who reported a bug.
