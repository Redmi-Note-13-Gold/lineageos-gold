# Hybrid kernel-module paths

The running hybrid uses a 6.6 GKI kernel and matching partitioned modules.
The legacy source device tree still references a 5.10 prebuilt baseline.
Changing a symlink does not make a mismatched kernel module ABI compatible.

The module-path tool validates and prepares module links and metadata in an
isolated target-files staging tree. Inspect first:

```sh
python3 device/xiaomi/gold/tools/hybrid_modules.py \
  --target-files /path/to/hybrid-target-files --check-only
```

After reviewing the inputs, omit `--check-only` to prepare the staging tree.
Use `--help` for source-root, fs_config and libselinux overrides. Rebuild and
validate the corresponding images separately. The tool does not replace the
kernel, select a modem, flash a phone, or establish hardware acceptance.

The experimental MDDP module is documented separately and is not installed by
this tool or the normal source patch series.

Tests: `python3 -m unittest discover -s device/xiaomi/gold/tools -p 'test_hybrid_modules.py'`.
