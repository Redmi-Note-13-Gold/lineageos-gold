# Hybrid zygote consistency

The OS3 vendor requests a particular `ro.zygote` mode. The matching init RCs,
32/64-bit app_process binaries, libraries, metadata and selected property must
agree in the assembled image. Adding a single property does not restore a
missing secondary runtime.

Run the tool against an isolated target-files staging tree, with the actual
vendor property file from that same image set:

```sh
python3 device/xiaomi/gold/tools/hybrid_zygote.py \
  --target-files /path/to/hybrid-target-files \
  --zygote-property-file /path/to/hybrid-target-files/VENDOR/build.prop
```

Use `--help` for source-root and Android host fs_config overrides. Review the
script's validation result before rebuilding images. This operates on staging
files; it does not flash, format or boot a phone. It is one component of hybrid
assembly and is not automatically called by ordinary `bacon`.

Tests: `python3 -m unittest discover -s device/xiaomi/gold/tools -p 'test_hybrid_zygote.py'`.
