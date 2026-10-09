#!/bin/bash
# Fill device/xiaomi/gold-kernel with the stock kernel, device trees and kernel modules.
# Usage, from the top of the Android tree: extract-kernel.sh <official full OTA zip> [output dir]
#
# Everything is taken unchanged from the OTA, except for the two edits marked EDIT below.
# Needs unzip, cpio, lz4 and erofs-utils on the host.
set -euo pipefail

ota=$(readlink -f -- "$1")
out=${2:-device/xiaomi/gold-kernel}

[ -x prebuilts/extract-tools/linux-x86/bin/ota_extractor ] || {
    echo "Run this from the top of the Android tree." >&2
    exit 1
}
top=$PWD
for tool in unzip cpio lz4 fsck.erofs sha256sum; do
    command -v "$tool" >/dev/null || { echo "$tool is missing" >&2; exit 1; }
done

# The package everything below was checked against: gold global OS3.0.5.0.VNQMIXM.
expected=35c9f1d98b28538ac10c319ad4cba993cd5a632960d9111162e3efa494dae5c9
if [ -z "${ANY_OTA:-}" ] && [ "$(sha256sum "$ota" | cut -d' ' -f1)" != "$expected" ]; then
    echo "$(basename -- "$ota") is not the OS3.0.5.0.VNQMIXM full OTA (SHA-256 $expected)." >&2
    echo "Set ANY_OTA=1 to try another package anyway." >&2
    exit 1
fi

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

unzip -q "$ota" payload.bin -d "$work"
"$top/prebuilts/extract-tools/linux-x86/bin/ota_extractor" --payload "$work/payload.bin" \
    --output_dir "$work" --partitions boot,vendor_boot,dtbo,vendor_dlkm,system_dlkm \
    >"$work/extract.log" 2>&1 || { cat "$work/extract.log" >&2; exit 1; }
rm "$work/payload.bin"

python3 "$top/system/tools/mkbootimg/unpack_bootimg.py" \
    --boot_img "$work/boot.img" --out "$work/boot" >/dev/null
python3 "$top/system/tools/mkbootimg/unpack_bootimg.py" \
    --boot_img "$work/vendor_boot.img" --out "$work/vendor_boot" >/dev/null
mkdir "$work/ramdisk"
for fragment in "$work"/vendor_boot/vendor_ramdisk0*; do
    lz4 -dc "$fragment" | (cd "$work/ramdisk" && cpio -idmu --quiet)
done
fsck.erofs --extract="$work/vendor_dlkm" "$work/vendor_dlkm.img" >/dev/null
fsck.erofs --extract="$work/system_dlkm" "$work/system_dlkm.img" >/dev/null
# The partition image is the DTBO padded to the partition size, with an AVB footer.
python3 "$top/external/avb/avbtool.py" erase_footer --image "$work/dtbo.img"

rm -rf "$out"
mkdir -p "$out/dtb" "$out/vendor_ramdisk" "$out/vendor_dlkm" "$out/system_dlkm/lib"
cp "$work/boot/kernel" "$out/kernel"
cp "$work/vendor_boot/dtb" "$out/dtb/gold.dtb"
cp "$work/dtbo.img" "$out/dtbo.img"
cp "$work"/ramdisk/lib/modules/*.ko "$out/vendor_ramdisk/"
cp "$work/ramdisk/lib/modules/modules.load" "$out/modules.load.vendor_ramdisk"
cp "$work/ramdisk/lib/modules/modules.load.recovery" "$out/modules.load.recovery"
cp "$work"/vendor_dlkm/lib/modules/*.ko "$out/vendor_dlkm/"
# The image's own etc/ is left out because the build generates that.
cp -r "$work/system_dlkm/lib/modules" "$out/system_dlkm/lib/"

# EDIT 1: load wmt_drv.ko, which the Wi-Fi, Bluetooth, GPS and FM drivers all depend on.
# Stock loads it from /vendor/etc/init/init.wmt_drv.rc, which the device tree does not carry.
sed '/^ccci_fsm_scp\.ko$/a wmt_drv.ko' "$work/vendor_dlkm/lib/modules/modules.load" \
    > "$out/modules.load.vendor"
grep -qx 'wmt_drv.ko' "$out/modules.load.vendor"

# EDIT 2: stop the soc_decimal uevent thread in hq_charger_sysfs.ko.
# While a USB, DCP or CDP charger is attached, soc_decimal_threadfn sends a battery uevent
# every 100 ms carrying POWER_SUPPLY_SOC_DECIMAL for MIUI's charging animation. Nothing
# outside MIUI reads it, and each event makes the kernel read every battery property and
# ueventd reapply its sysfs rules: about a third of a core for as long as the phone charges.
# The thread only runs while quick_chr_type_noti has set a flag in the driver data; make
# that store write 0 so the thread stays asleep:
#   .text+0x228 (file offset 0x1228)   mov w9, #1  ->  mov w9, #0
module=$out/vendor_dlkm/hq_charger_sysfs.ko
echo "69fad2943a9500d01cf4f1ed7de6176684d7bf7bedeb5c482cfba8db61fd6daf  $module" | sha256sum -c --quiet
printf '\x09' | dd of="$module" bs=1 seek=$((0x1228)) conv=notrunc status=none
echo "1360d2c793475eec564fbc60d3fb6866d17a51a2478cca23101ec7340705e554  $module" | sha256sum -c --quiet

echo "Wrote $out from $(basename -- "$ota")"
