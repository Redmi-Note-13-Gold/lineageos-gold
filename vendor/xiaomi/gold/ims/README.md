# Gold IMS compatibility inputs

This directory owns the exact proprietary `ImsService.apk` input, its
`input.json` lock, build registration, privileged permissions, the v5 smali
delta, and the 23.2 TelephonyMetrics compatibility source/recipe. The APK is
a regular tracked Git blob: a mainline checkout or Git bundle includes it.
No old checkout, hybrid image, temporary directory or signing key is needed.

The original stock APK provenance and dependency-bundling recipe have not
been fully recovered. This is an explicitly managed proprietary prebuilt,
not a complete stock-to-IMS source build. The smali patch documents the delta
from the former dependency-bundled v1 tree; it is not a normal preparation
step and must not be applied to an arbitrary stock APK. The optional metrics
rebuild accepts the mainline prebuilt as its payload source:

```sh
python3 vendor/xiaomi/gold/ims/compat/rebuild.py \
  --tree /path/to/android \
  --base-apk vendor/xiaomi/gold/ims/ImsService.apk \
  --output /path/to/new-compatible-ImsService.apk
```

Input SHA-256 and the upstream compatibility source revision are enforced by
the script and recorded in `compat/provenance.json`. Review the output before
placing it at the `ImsService.apk` path consumed by Android.bp; the product build
performs platform signing. ZIP compression metadata can differ between host
versions even when the regenerated dex and every payload entry are identical.
The report distinguishes payload equality from full APK byte equality. A
different complete APK hash requires an explicit input-lock update before
`prepare-vendor.py` accepts it. The script does not install or flash anything.

See `input.json` for source limitations and `docs/ADAPTATION.md` for carrier
scope and the separate runtime acceptance boundary. Retaining the binary
does not demonstrate IMS registration, calling, or permission to redistribute
vendor software. No public publication is performed by these tools.

The standard Global preparation path currently accepts the explicit 23.2
compatibility APK with SHA-256
`98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1`.
`apply-patches.py --apply` copies it into the Android tree with its integration
files. `prepare-vendor.py` then uses that local input by default; `--ims-apk`
may select another byte-identical copy. Its bytes are verified before any
vendor preparation. This
pin identifies the previous compatibility input, not a claim that IMS on the
new Global firmware has passed runtime acceptance. The final package validator
compares all non-signature APK entries against this input and verifies the
platform-signing selection, privileged allowlist and IMS feature declaration.
