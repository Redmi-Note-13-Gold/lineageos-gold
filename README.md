# LineageOS for the Redmi Note 13 5G (`gold`)

Unofficial LineageOS for the Redmi Note 13 5G. Test builds: userdebug, signed with test keys. Not affiliated with Xiaomi, MediaTek or the LineageOS project.

| | |
| --- | --- |
| Downloads | [Releases](https://github.com/Star-caorui/lineageos-gold/releases) |
| How to build | [local_manifests](https://github.com/Star-caorui/local_manifests) |
| Device tree | [android_device_xiaomi_gold](https://github.com/Star-caorui/android_device_xiaomi_gold), a fork of [Dhterech's](https://github.com/Dhterech/android_device_xiaomi_gold) |
| Prebuilt kernel | [android_device_xiaomi_gold-kernel](https://github.com/Star-caorui/android_device_xiaomi_gold-kernel) |
| Proprietary files | [android_vendor_xiaomi_gold](https://github.com/Star-caorui/android_vendor_xiaomi_gold) |

## Builds

| | Android | Latest build | |
| --- | --- | --- | --- |
| LineageOS 24.0 | 17 | [2026101303](https://github.com/Star-caorui/lineageos-gold/releases/tag/LineageOS-gold-Unofficial-24.0-Vanilla-2026101303) | Current |
| LineageOS 23.2 | 16 | [2026101201](https://github.com/Star-caorui/lineageos-gold/releases/tag/LineageOS-gold-Unofficial-23.2-Vanilla-2026101201) | Final, no more updates |

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
| Tested on | China model 2312DRAABC (`gold_cn`), one unit only |

The device tree also carries the configuration for the Indian and Global (`iron`) models. Nobody has tested those.

## Status

The rows follow LineageOS's [device support requirements](https://github.com/LineageOS/charter/blob/main/device-support-requirements.md). "Not tested" means nobody has tried it on that version, not that it is known to be broken.

<table>
  <tr><th></th><th></th><th>24.0</th><th>23.2</th></tr>
  <tr><td>Audio</td><td>Media playback, speaker</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Earpiece</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>In-call audio</td><td colspan="2" align="center">Not tested</td></tr>
  <tr><td></td><td>Wired headset, Bluetooth audio</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Microphone</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>FM radio</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>RIL</td><td>Calls, SMS, mobile data</td><td colspan="2" align="center">Not tested</td></tr>
  <tr><td></td><td>VoLTE, emergency calls</td><td colspan="2" align="center">Not tested</td></tr>
  <tr><td>Encryption</td><td>Hardware-backed, file-based</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>Wi-Fi</td><td>Wi-Fi</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Hotspot</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Same MAC address as on stock</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>USB</td><td>File transfer (MTP)</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>USB tethering</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>GPS</td><td>GPS</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>Bluetooth</td><td>Bluetooth</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Same MAC address as on stock</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Bluetooth tethering</td><td colspan="2" align="center">Not tested</td></tr>
  <tr><td>Camera</td><td>Rear and front photos</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>Video recording</td><td>Video recording</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>Codecs</td><td>Hardware decoding and encoding</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>Display</td><td>Stock resolution, 120 Hz</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Wireless display</td><td colspan="2" align="center">Not tested</td></tr>
  <tr><td>NFC</td><td>NFC</td><td colspan="2" align="center">No hardware</td></tr>
  <tr><td>Fingerprint</td><td>Fingerprint</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>IR</td><td>IR blaster</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>SD card</td><td>SD card</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td></td><td>Adoptable storage</td><td colspan="2" align="center">Not tested</td></tr>
  <tr><td>Sensors</td><td>Accelerometer, gyroscope</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Proximity, light</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Other sensors</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td></td><td>Significant motion</td><td align="center">Not tested</td><td align="center">PASS</td></tr>
  <tr><td>SELinux</td><td>Enforcing</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>Verity</td><td>Off on the system image, as userdebug builds require</td><td colspan="2" align="center">PASS</td></tr>
  <tr><td>Updater</td><td>Updates from the Updater app</td><td align="center">PASS</td><td align="center">No more updates</td></tr>
  <tr><td>FRP</td><td>Factory reset protection</td><td align="center">Not supported</td><td align="center">Not tested</td></tr>
  <tr><td>Recovery</td><td>Installing with Lineage Recovery</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
  <tr><td>Add-ons</td><td>Installing add-on packages from recovery</td><td align="center">PASS</td><td align="center">Not tested</td></tr>
</table>

Measured on 23.2:

- Standby: about 15 mA with the screen off, Wi-Fi connected and no SIM. 1% in three hours.
- Thermal: with all eight cores loaded for about seven minutes the CPU reaches roughly 63°C, is throttled, and settles around 58°C.

## This repository

| | |
| --- | --- |
| `host/` | The build script and a patch for a build host with little RAM, and the script that writes the update lists |
| `updates/` | The lists the Updater app reads, one per published 24.0 build |

A 24.0 build asks for `updates/<its ro.build.version.incremental>.json`. When a build is published, `host/update-lists.py` rewrites the lists of the builds before it: the two most recent are offered an incremental package, older ones the full package.

## Differences from Dhterech's tree

Our commits sit on top of his head, one change each: [the list for 23.2](https://github.com/Star-caorui/android_device_xiaomi_gold/compare/6c5bdc8...lineage-23.2).

| Area | What is different |
| --- | --- |
| Fixes | GPS, FM, a crash when Bluetooth is turned off, 32-bit apps crashing, the hardware codec service crashing now and then, auto-brightness that only went up. Our fixes for offline charging and USB tethering are in his tree now |
| Wi-Fi | Joins an iPhone's hotspot, and Apple devices can join the phone's WPA3 hotspot |
| Added | Double tap, lift and tap to wake, the power-off alarm, charging control, updates from the Updater app, OpenCL and the neural networks accelerator for apps |
| Stock services | The AIDL audio service with the sound trigger HAL, and the IMS stack from this device's own firmware, where the tree ran older stand-ins |
| Smoothness | The GPU frequency is raised while the screen is touched and when an app starts, the display timing is stock's, the UI is drawn with Vulkan as on stock, and the compositor gets CPU time as soon as it has window blur to render |
| Settings | Those that differed from stock without a stated reason are back to stock's or the platform's: refresh rate timers, suspend while the proximity sensor holds the screen off, the recovery pixel format, the graphics driver preloaded in zygote, the low memory killer |
| Stock files | More of the vendor files that the shipped programs ask for by name: the carrier modem configuration, and audio, camera, video and positioning libraries |
| Mainland China | Connectivity checks and time servers that answer from there |
| Choices | Always-on display removed |
| Clean-up | Services and scripts that were never installed or had nothing to run are gone, as are 47 32-bit libraries nothing loads. Tethering hardware offload, which this modem does not provide, is no longer declared |
| Kernel | He keeps the prebuilt files in a repository, and so do we, with a history that starts from the unchanged stock files. Ours adds the `system_dlkm/` directory the device tree needs, and changes one instruction in `hq_charger_sysfs.ko` to stop a thread that only serves MIUI's charging animation |
| Verified boot | His builds skip the whole vbmeta check. Ours only turn off dm-verity, so the bootloader still passes the real patch levels to the secure world |

## Credits

- [Dhterech](https://github.com/Dhterech/android_device_xiaomi_gold) for the device tree, and those he credits: xiaomi-mt6833-dev, aeronruless and linastorvaldz.
- claxten10 and [mt6833-devs](https://github.com/mt6833-devs/android_device_xiaomi_gold). Dhterech's tree is built on theirs, which makes up 204 of its 295 commits.
- [cristidclxvi](https://github.com/cristidclxvi/android_device_xiaomi_camellia) for the camellia device tree, same chip. The way double tap to wake is switched follows it, and so do two Wi-Fi settings.
- [LineageOS](https://lineageos.org), and the maintainers of its MediaTek device trees, which many of our commits follow: [android_device_motorola_mt6768-common](https://github.com/LineageOS/android_device_motorola_mt6768-common) (the stock AIDL audio service, the IMS files, the mtkpower stubs, and the changes for LineageOS 24.0 by Nolen Johnson, Michael Bestas, Nicholas Lim, Elias Gheeraert, Mashopy and Giovanni Ricca), android_device_motorola_mt6879-common, android_device_motorola_lamu, android_device_xiaomi_rosemary and android_device_xiaomi_mt6768-common.
- crDroid's android_device_xiaomi_everpal, same chip, as a reference for what to take from the stock images.
- bengris32, whose patch for Motorola's ImsService ours repeats on this device's build of the app.
- [techyminati](https://github.com/techyminati/android_vendor_mediatek_ims) for the MediaTek IMS package our earlier builds used.
