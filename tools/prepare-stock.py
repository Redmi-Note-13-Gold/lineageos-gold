#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify and unpack the pinned official firmware on a Linux build host.

Uses existing Android host tools. Never runs vendor flashing scripts or adb.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import tarfile

LOCK = Path(__file__).resolve().parents[1] / 'firmware/gold-cn.json'
PHYSICAL = {
    'boot', 'vendor_boot', 'dtbo', 'vbmeta', 'vbmeta_system', 'vbmeta_vendor',
    'lk', 'md1img', 'tee', 'gz', 'scp', 'sspm', 'spmfw', 'mcupm', 'dpm', 'pi_img',
}
LOGICAL = {'vendor', 'mi_ext', 'system_dlkm', 'vendor_dlkm', 'odm_dlkm'}


def digest(path):
    sha = hashlib.sha256()
    md5 = hashlib.md5()
    with path.open('rb') as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            sha.update(chunk)
            md5.update(chunk)
    return {'size': path.stat().st_size, 'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}


def finish_extraction(output, host_bin, actual, lock):
    raw = output / 'super.raw.img'
    physical = output / 'physical'
    logical = output / 'logical'
    logical.mkdir(exist_ok=True)
    command = [str(host_bin / 'lpunpack')]
    for name in sorted(LOGICAL):
        command.extend(['-p', name + '_a'])
    subprocess.run(command + [str(raw), str(logical)], check=True)
    for name in LOGICAL:
        (logical / (name + '_a.img')).rename(logical / (name + '.img'))
    images = {}
    for directory in (physical, logical):
        for path in sorted(directory.glob('*.img')):
            if path.name != 'super.img':
                images[str(path.relative_to(output))] = digest(path)
    report = {'stock_version': lock['version'], 'archive': actual, 'images': images,
              'phone_commands_executed': False, 'prepared_only': True}
    (output / 'prepared.json').write_text(json.dumps(report, indent=2) + '\n')
    # Raw/sparse super are reproducible temporary copies of the retained archive.
    # Keep only the needed partition images once extraction and hashing succeed.
    raw.unlink()
    (physical / 'super.img').unlink()
    print('Prepared', len(images), 'official partition inputs; no device writes.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host-bin', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run this tool on the Linux Android build host.')
    lock = json.loads(LOCK.read_text())
    actual = digest(args.archive)
    for field in ('size', 'sha256', 'md5'):
        if actual[field] != lock['archive'][field]:
            raise SystemExit('Official archive verification failed: ' + field)
    print('Verified official archive', lock['version'], flush=True)
    if args.output.exists():
        raise SystemExit('Output already exists; use a fresh staging directory.')
    for tool in ('simg2img', 'lpunpack'):
        if not (args.host_bin / tool).is_file():
            raise SystemExit('Missing existing Android host tool: ' + tool)
    args.output.mkdir(parents=True)
    physical = args.output / 'physical'
    physical.mkdir()
    wanted = {name + '.img' for name in PHYSICAL} | {'super.img'}
    found = set()
    with tarfile.open(args.archive, mode='r|gz') as archive:
        for entry in archive:
            name = PurePosixPath(entry.name)
            if name.name not in wanted or name.parent.name != 'images':
                continue
            if not entry.isfile() or name.is_absolute() or '..' in name.parts:
                raise SystemExit('Unsafe archive member: ' + entry.name)
            if name.name in found:
                raise SystemExit('Duplicate input image: ' + name.name)
            found.add(name.name)
            with archive.extractfile(entry) as source, (physical / name.name).open('xb') as target:
                shutil.copyfileobj(source, target, 8 * 1024 * 1024)
    if found != wanted:
        raise SystemExit('Missing official images: ' + repr(sorted(wanted - found)))
    raw = args.output / 'super.raw.img'
    subprocess.run([str(args.host_bin / 'simg2img'), str(physical / 'super.img'), str(raw)], check=True)
    finish_extraction(args.output, args.host_bin, actual, lock)


if __name__ == '__main__':
    main()
