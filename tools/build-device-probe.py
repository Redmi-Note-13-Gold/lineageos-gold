#!/usr/bin/env python3
"""Build an owned permission-free device probe with the existing Android SDK tools.

This builds only a disposable test APK, never a ROM or a modified system image.
The public AOSP test certificate is used on the build host, not copied elsewhere.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android-root", type=Path, required=True)
    parser.add_argument("--android-out", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--probe", choices=["performance", "hardware"], required=True)
    args = parser.parse_args()
    root, out = args.android_root.resolve(), args.android_out.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    name = {"performance": "GoldPerfProbe", "hardware": "GoldHardwareProbe"}[args.probe]
    source = Path(__file__).resolve().parents[1] / "tests/android" / name
    jdk = root / "prebuilts/jdk/jdk21/linux-x86"
    sdk = root / "prebuilts/sdk/current/public/android.jar"
    host = out / "host/linux-x86/bin"
    env = dict(os.environ, JAVA_HOME=str(jdk), PATH=str(jdk / "bin") + ":" + os.environ["PATH"])
    commands = []

    def run(parts):
        parts = list(map(str, parts))
        commands.append(parts)
        result = subprocess.run(parts, capture_output=True, text=True, env=env)
        (output / ("command-%02d.log" % len(commands))).write_text(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError("command %d failed: %s" % (len(commands), result.stderr))

    classes, dex = output / "classes", output / "dex"
    classes.mkdir()
    dex.mkdir()
    run([jdk / "bin/javac", "--release", "8", "-cp", sdk, "-d", classes, source / "MainActivity.java"])
    run([jdk / "bin/jar", "cf", output / "classes.jar", "-C", classes, "."])
    run([host / "d8", "--min-api", "35", "--lib", sdk, "--output", dex, output / "classes.jar"])
    unsigned = output / "unsigned.apk"
    run([host / "aapt2", "link", "-I", sdk, "--manifest", source / "AndroidManifest.xml", "-o", unsigned])
    with zipfile.ZipFile(unsigned, "a", compression=zipfile.ZIP_STORED) as archive:
        archive.write(dex / "classes.dex", "classes.dex")
    aligned, apk = output / "aligned.apk", output / (name + ".apk")
    run([host / "zipalign", "-p", "4", unsigned, aligned])
    keys = root / "build/make/target/product/security"
    run([host / "apksigner", "sign", "--key", keys / "testkey.pk8", "--cert",
         keys / "testkey.x509.pem", "--out", apk, aligned])
    run([host / "apksigner", "verify", "--verbose", "--print-certs", apk])
    run([host / "aapt2", "dump", "badging", apk])
    result = {
        "apk": str(apk), "apk_sha256": hashlib.sha256(apk.read_bytes()).hexdigest(),
        "source_hashes": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(source.iterdir())},
        "commands": commands, "certificate": "public AOSP testkey", "compiled_and_signature_verified": True,
    }
    (output / "build.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({k: v for k, v in result.items() if k != "commands"}))


if __name__ == "__main__":
    main()
