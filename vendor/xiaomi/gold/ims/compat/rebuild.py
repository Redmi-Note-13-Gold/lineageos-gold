#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rebuild the metrics dex using the mainline proprietary dependency payload.

This intentionally does not claim to rebuild the proprietary dependency bundle
from stock. Run on native Linux x86_64 with this checkout's JDK and D8.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile
import zipfile


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--base-apk', type=Path, default=Path(__file__).resolve().parents[1] / 'ImsService.apk')
    parser.add_argument('--out', type=Path, default=Path('out-gold-standard'))
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64',
            'Use the native Linux x86_64 Android build host')
    require(not args.output.exists(), 'Output already exists')
    own = Path(__file__).resolve().parent
    lock = json.loads((own.parent / 'input.json').read_text())
    provenance = json.loads((own / 'provenance.json').read_text())
    require(sha(args.base_apk) == lock['sha256'], 'Requires the pinned mainline proprietary payload')
    source = own / 'TelephonyMetrics.java'
    require(sha(source) == provenance['compat_source_sha256'], 'Compatibility source hash changed')
    java = args.tree / 'prebuilts/jdk/jdk21/linux-x86/bin'
    out = args.out if args.out.is_absolute() else args.tree / args.out
    d8 = out / 'host/linux-x86/framework/d8.jar'
    require(d8.is_file(), 'Build the d8 host target in the selected OUT_DIR first')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='gold-ims-compat-', dir=args.output.parent) as td:
        work = Path(td)
        classes, dex = work / 'classes', work / 'dex'
        classes.mkdir()
        dex.mkdir()
        subprocess.run([str(java / 'javac'), '--release', '8', '-d', str(classes), str(source)], check=True)
        subprocess.run([str(java / 'java'), '-cp', str(d8), 'com.android.tools.r8.D8',
                        '--min-api', '26', '--output', str(dex),
                        *[str(p) for p in sorted(classes.rglob('*.class'))]], check=True)
        require(sha(dex / 'classes.dex') == provenance['added_dex_sha256'],
                'Regenerated metrics dex differs; review compiler/input drift before accepting')
        staged = work / 'ImsService.apk'
        with zipfile.ZipFile(args.base_apk) as src, zipfile.ZipFile(staged, 'w') as dst:
            require(len(src.namelist()) == len(set(src.namelist())), 'Duplicate APK entries')
            for info in src.infolist():
                if info.filename.startswith('META-INF/') or info.filename == 'classes2.dex':
                    continue
                dst.writestr(info, src.read(info.filename))
            info = zipfile.ZipInfo('classes2.dex', (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            dst.writestr(info, (dex / 'classes.dex').read_bytes())
        with zipfile.ZipFile(args.base_apk) as original, zipfile.ZipFile(staged) as rebuilt:
            names = {name for name in original.namelist() if not name.startswith('META-INF/')}
            require(names == set(rebuilt.namelist()), 'Rebuilt APK dependency entry set changed')
            require(all(original.read(name) == rebuilt.read(name) for name in names),
                    'Rebuilt APK dependency payload changed')
        # Exclusive publication: never replace an existing user output.
        os.link(staged, args.output)
    print(json.dumps({'input_sha256': sha(args.base_apk), 'output_sha256': sha(args.output),
                      'metrics_dex_rebuilt': True, 'proprietary_payload_preserved': True,
                      'apk_byte_identical': sha(args.output) == lock['sha256'],
                      'stock_dependency_bundle_rebuilt': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
