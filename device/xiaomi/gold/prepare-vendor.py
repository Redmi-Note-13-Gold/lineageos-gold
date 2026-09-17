#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare standard Lineage vendor/kernel inputs from the locked Global images.

Run on a native Linux build host with the checkout's extract-utils and host
fsck.erofs/lz4 tools. No stock image is modified. Outputs contain proprietary
material and are not intended for inclusion in this source repository.
"""
from pathlib import Path, PurePosixPath
import argparse
import gzip
import hashlib
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile

DEVICE = Path('device/xiaomi/gold')
VENDOR = Path('vendor/xiaomi/gold')
IMS_SHA256 = '98ca5f5c26293a7c37fafeada31e068d2658adf6813d8b123ebb46529bb292c1'


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(args, **kwargs):
    return subprocess.run([str(x) for x in args], check=True, **kwargs)


def host_tool(tree, name):
    candidates = [tree / 'out/host/linux-x86/bin' / name]
    found = shutil.which(name)
    if found:
        candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise RuntimeError(f'Missing native host tool {name}; build the host tool first')


def extract_fs(tree, image, output, log):
    output.mkdir(parents=True)
    with image.open('rb') as f:
        f.seek(1024)
        magic = f.read(4)
    with log.open('w') as report:
        if magic == bytes.fromhex('e2e1f5e0'):
            run([host_tool(tree, 'fsck.erofs'), f'--extract={output}', image], stdout=report, stderr=report)
        else:
            run([host_tool(tree, 'debugfs'), '-R', f'rdump / {output}', image], stdout=report, stderr=report)
    # debugfs can return success on a bad filesystem; never accept an empty dump.
    require(any(output.iterdir()), f'Empty filesystem extraction: {image}; see {log}')


def extract_modules(tree, archive, output):
    """Read newc directly, retaining only regular module files (no cpio writes)."""
    data = archive.read_bytes()
    if data[:2] == b'\x1f\x8b':
        data = gzip.decompress(data)
    elif data[:6] not in (b'070701', b'070702'):
        data = run([host_tool(tree, 'lz4'), '-d', '-c', archive], stdout=subprocess.PIPE).stdout
    offset = 0
    count = 0
    while offset + 110 <= len(data):
        header = data[offset:offset + 110]
        require(header[:6] in (b'070701', b'070702'), 'Unsupported vendor ramdisk cpio format')
        mode = int(header[14:22], 16)
        size = int(header[54:62], 16)
        namesize = int(header[94:102], 16)
        name_start = offset + 110
        name = data[name_start:name_start + namesize - 1].decode()
        start = (name_start + namesize + 3) & ~3
        end = start + size
        require(end <= len(data), 'Truncated vendor ramdisk')
        offset = (end + 3) & ~3
        if name == 'TRAILER!!!':
            break
        rel = PurePosixPath(name)
        require(not rel.is_absolute() and '..' not in rel.parts, 'Unsafe vendor ramdisk path')
        if str(rel).startswith('lib/modules/') and stat.S_ISREG(mode):
            destination = output / str(rel)
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                require(destination.read_bytes() == data[start:end], f'Conflicting ramdisk module: {name}')
            destination.write_bytes(data[start:end])
            count += 1
    return count


def prepare(args):
    tree = args.tree.resolve()
    stock = args.stock.resolve()
    lock_path = args.lock.resolve()
    require(platform.system() == 'Linux' and platform.machine() == 'x86_64',
            'Run extraction on the native Linux x86_64 Android build host')
    lock = json.loads(lock_path.read_text())
    require(lock['device'] == 'gold' and lock['region_code'] == 'MIXM', 'Expected Gold Global stock lock')
    require(lock['version'] == 'OS3.0.5.0.VNQMIXM', 'Review extraction recipes before changing the stock release')
    for relative, info in lock['images'].items():
        image = stock / relative
        require(image.is_file() and image.stat().st_size == info['size'] and sha(image) == info['sha256'],
                f'Stock image does not match lock: {relative}')
    vendor = tree / VENDOR
    ims = args.ims_apk.resolve() if args.ims_apk else vendor / 'ims/ImsService.apk'
    require(ims.is_file() and sha(ims) == IMS_SHA256,
            'Supply --ims-apk with the pinned 23.2 compatibility APK (see vendor/xiaomi/gold/ims/README.md)')
    require((vendor / 'ims/Android.bp').is_file(), 'IMS source integration is missing from the checkout')
    vendor.mkdir(parents=True, exist_ok=True)
    # Remove the obsolete record left by older preparation scripts.
    (vendor / 'input-receipt.json').unlink(missing_ok=True)
    work_parent = args.work_dir.resolve() if args.work_dir else tree / 'out/gold-vendor-extraction'
    work_parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='prepare-', dir=work_parent) as temporary:
        work = Path(temporary)
        dump = work / 'dump'
        for name in ('vendor', 'system', 'system_dlkm', 'vendor_dlkm', 'odm_dlkm'):
            extract_fs(tree, stock / f'logical/{name}.img', dump / name, work / f'{name}.log')
        # System-as-root: extract-utils expects system/lib64, not system/system/lib64.
        if (dump / 'system/system').is_dir():
            (dump / 'system').rename(dump / 'system-image')
            (dump / 'system').symlink_to(dump / 'system-image/system', target_is_directory=True)
        for line in (tree / DEVICE / 'proprietary-firmware.txt').read_text().splitlines():
            if line and not line.startswith('#'):
                name = line.split(';')[0]
                (dump / name).symlink_to(stock / 'physical' / name)
        env = dict(os.environ, PYTHONPATH=str(tree / 'tools/extract-utils'))
        run([sys.executable, tree / DEVICE / 'extract-files.py', dump], cwd=tree, env=env)
        kernel = vendor / 'proprietary/kernel'
        kernel.mkdir(parents=True)
        unpack = tree / 'system/tools/mkbootimg/unpack_bootimg.py'
        for name in ('boot', 'vendor_boot'):
            run([sys.executable, unpack, '--boot_img', stock / f'physical/{name}.img', '--out', work / name],
                stdout=subprocess.DEVNULL)
        require(sha(work / 'boot/kernel') == lock['kernel']['sha256'], 'Extracted kernel hash mismatch')
        shutil.copyfile(work / 'boot/kernel', kernel / 'kernel')
        shutil.copyfile(stock / 'physical/boot.img', kernel / 'boot.img')
        shutil.copyfile(stock / 'physical/dtbo.img', kernel / 'dtbo.img')
        (kernel / 'dtb').mkdir()
        shutil.copyfile(work / 'vendor_boot/dtb', kernel / 'dtb/gold.dtb')
        for name in ('system_dlkm', 'vendor_dlkm'):
            shutil.copytree(dump / name / 'lib/modules', kernel / name / 'lib/modules')
        total = sum(extract_modules(tree, ramdisk, kernel / 'vendor_ramdisk')
                    for ramdisk in sorted((work / 'vendor_boot').glob('vendor_ramdisk[0-9]*')))
        require(total > 0, 'No vendor ramdisk modules extracted')
        for name in ('modules.load', 'modules.load.recovery'):
            require((kernel / 'vendor_ramdisk/lib/modules' / name).is_file(), f'Missing {name}')
        if ims != vendor / 'ims/ImsService.apk':
            shutil.copyfile(ims, vendor / 'ims/ImsService.apk')
    print(json.dumps({'prepared': True, 'stock_version': lock['version'],
                      'source_build_completed': False, 'device_validated': False}, indent=2))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tree', type=Path, required=True)
    p.add_argument('--lock', type=Path, required=True)
    p.add_argument('--stock', type=Path, required=True)
    p.add_argument('--ims-apk', type=Path)
    p.add_argument('--work-dir', type=Path)
    args = p.parse_args()
    prepare(args)


if __name__ == '__main__':
    try:
        main()
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        sys.exit(f'Gold vendor preparation failed: {error}')
