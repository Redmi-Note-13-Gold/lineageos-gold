# Gold IMS compatibility inputs

This directory contains build registration, privileged permissions, the v5
smali delta, and the 23.2 TelephonyMetrics compatibility source/recipe.
It deliberately does not contain `ImsService.apk` or any signing key.

The smali patch starts from the dependency-bundled v1 tree, not an arbitrary
stock APK. The compatibility rebuild starts from the validated v5 payload:

```sh
python3 vendor/xiaomi/gold/ims/compat/rebuild.py \
  --tree /path/to/android \
  --base-apk /path/to/validated-v5/ImsService.apk \
  --output /path/to/new-compatible-ImsService.apk
```

Input SHA-256 and the upstream compatibility source revision are enforced by
the script and recorded in `compat/provenance.json`. Review the output before
placing it at the `ImsService.apk` path consumed by Android.bp; the product build
performs platform signing. The script does not install or flash anything.

See the repository's `docs/INTEGRATION.md` for the unresolved dependency-bundling
step, carrier scope and runtime validation boundary. Do not treat this recipe
as a complete stock-to-working-IMS pipeline.
