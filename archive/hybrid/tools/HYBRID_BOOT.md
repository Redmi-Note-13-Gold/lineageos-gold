# Hybrid property-context validation

The original OS3.0.9.0.VNQCNXM investigation found that vendor and LineageOS system_ext both declare the prefixes
`persist.vendor.pco5.radio.ctrl` and `vendor.camera.aux.packagelist`. The merged
property trie rejects duplicates, even when their labels agree. This aborts
`PropertyInit()` before ADB starts. A successful CIL compile alone does not test
property-trie construction.

Use Python 3.11+ and built Android host tools. Run from the Android source root
on an isolated, extracted hybrid target-files staging tree:

```sh
python3 device/xiaomi/gold/tools/hybrid_properties.py check \
  --target-files /path/to/hybrid-target-files
python3 device/xiaomi/gold/tools/hybrid_properties.py build \
  --target-files /path/to/hybrid-target-files \
  --output /path/to/new-repair-output
```

The builder keeps the vendor definitions, removes only the two audited
system_ext duplicates, and rebuilds system_ext and its vbmeta descriptor using
existing image size, filesystem metadata, and chain keys. Existing output
folders are refused. Read `--help` for explicit source, host-tool, key, system
and overlay-image inputs. Do not mix staging files from different image sets.

This is a component repair tool, not the full 23.2 hybrid assembly pipeline.
It does not invoke adb/fastboot or write a device. Generated images and local
logs need independent image, boot, and hardware validation; they are not OTA
packages. The device's active slot and fallback slot must be handled by a
separate, reviewed deployment process.

## Read-only boot observation

`capture_boot.py` uses Python 3.9+, installed adb/fastboot, and an explicit
serial and target slot. It does not request root, reboot, change slots or flash.

```sh
python3 device/xiaomi/gold/tools/capture_boot.py \
  --serial EXAMPLE_GOLD_SERIAL --slot a \
  --output /path/to/new-private-capture --timeout 240 --stable-seconds 15
```

Normal Android mode, the expected slot, boot completion and a stable boot ID
must agree over the observation window. Recovery, unauthorized USB and unknown
states do not count as boot success. Raw captures can contain personal data;
keep them private and publish only redacted findings.

Host tests (no phone needed):

```sh
python3 -m unittest discover -s device/xiaomi/gold/tools -p 'test_*.py'
```

The new integration input is Global full Recovery OS3.0.5.0.VNQMIXM; the published CN R1 remains OS3.0.10.0.VNQCNXM. See the repository `docs/STOCK_BASE.md` for the stock-input and incremental assembly workflow; the historical examples here do not select a firmware version.
