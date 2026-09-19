#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Verify pinned official inputs and extract to a fresh staging directory.

Global full Recovery is the default. Pass --lock firmware/gold-cn.json for the
historical CN Fastboot baseline. Uses existing Linux Android host tools, never
installs tools, downloads archives, runs flashing scripts, or touches a device.
"""
import argparse
import base64
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import struct
import subprocess
import sys
import tarfile
import zipfile

LOCK = Path(__file__).resolve().parents[1] / 'firmware/gold-global.json'
PHYSICAL = {
    'boot', 'vendor_boot', 'dtbo', 'vbmeta', 'vbmeta_system', 'vbmeta_vendor',
    'lk', 'md1img', 'tee', 'gz', 'scp', 'sspm', 'spmfw', 'mcupm', 'dpm', 'pi_img',
}
LOGICAL = {'vendor', 'mi_ext', 'system_dlkm', 'vendor_dlkm', 'odm_dlkm'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(path):
    sha, md5 = hashlib.sha256(), hashlib.md5()
    with path.open('rb') as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            sha.update(chunk)
            md5.update(chunk)
    return {'size': path.stat().st_size, 'sha256': sha.hexdigest(), 'md5': md5.hexdigest()}


def check_digest(actual, expected, label):
    for field in ('size', 'sha256', 'md5'):
        if field in expected:
            require(actual[field] == expected[field], label + ' verification failed: ' + field)


def key_values(data):
    values = {}
    for line in data.decode('utf-8').splitlines():
        if not line.strip():
            continue
        require('=' in line, 'Invalid metadata line')
        key, value = line.split('=', 1)
        require(key not in values, 'Duplicate metadata key: ' + key)
        values[key] = value
    return values


def expected_paths(lock):
    if lock.get('archive_format') == 'recovery-full-ota':
        paths = set(lock['images'])
        for rel in paths:
            p = PurePosixPath(rel)
            require(len(p.parts) == 2 and p.parts[0] in ('physical', 'logical')
                    and p.suffix == '.img' and '..' not in p.parts, 'Invalid lock image path')
        return paths
    return {'physical/' + name + '.img' for name in PHYSICAL} | {
        'logical/' + name + '.img' for name in LOGICAL}


def verify_images(output, lock):
    expected = expected_paths(lock)
    actual_paths = {str(p.relative_to(output)) for directory in ('physical', 'logical')
                    for p in (output / directory).iterdir()}
    require(actual_paths == expected, 'Unexpected or missing partition image set')
    images = {}
    for rel in sorted(expected):
        p = output / rel
        require(p.is_file() and not p.is_symlink(), 'Non-regular image: ' + rel)
        images[rel] = digest(p)
        if 'images' in lock:
            check_digest(images[rel], lock['images'][rel], rel)
    return images


def verify_prepared(output, lock, lock_path):
    report = json.loads((output / 'prepared.json').read_text())
    require(report['stock_version'] == lock['version'], 'Prepared stock version mismatch')
    check_digest(report['archive'], lock['archive'], 'Prepared archive record')
    require(report.get('lock_sha256') == digest(lock_path)['sha256'], 'Prepared lock mismatch')
    images = verify_images(output, lock)
    require(images == report['images'], 'Prepared manifest image records changed')
    require(report.get('prepared_only') is True and report.get('phone_commands_executed') is False,
            'Unexpected preparation status')
    return report


def extract_fastboot(archive_path, output, host_bin):
    physical, logical = output / 'physical', output / 'logical'
    wanted = {name + '.img' for name in PHYSICAL} | {'super.img'}
    found = set()
    with tarfile.open(archive_path, mode='r|gz') as archive:
        for entry in archive:
            name = PurePosixPath(entry.name)
            if name.name not in wanted or name.parent.name != 'images':
                continue
            require(entry.isfile() and not name.is_absolute() and '..' not in name.parts,
                    'Unsafe archive member: ' + entry.name)
            require(name.name not in found, 'Duplicate input image: ' + name.name)
            found.add(name.name)
            with archive.extractfile(entry) as source, (physical / name.name).open('xb') as target:
                shutil.copyfileobj(source, target, 8 * 1024 * 1024)
    require(found == wanted, 'Missing official images: ' + repr(sorted(wanted - found)))
    raw = output / 'super.raw.img'
    subprocess.run([str(host_bin / 'simg2img'), str(physical / 'super.img'), str(raw)], check=True)
    command = [str(host_bin / 'lpunpack')]
    for name in sorted(LOGICAL):
        command.extend(['-p', name + '_a'])
    subprocess.run(command + [str(raw), str(logical)], check=True)
    for name in LOGICAL:
        (logical / (name + '_a.img')).rename(logical / (name + '.img'))
    raw.unlink()
    (physical / 'super.img').unlink()
    return {}


def extract_recovery(archive_path, output, host_bin, lock):
    payload = output / 'payload.bin'
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        require(len(names) == len(set(names)), 'Duplicate ZIP entries')
        for info in archive.infolist():
            p = PurePosixPath(info.filename)
            require(not p.is_absolute() and '..' not in p.parts, 'Unsafe ZIP entry')
            require(not info.flag_bits & 1, 'Encrypted ZIP entry')
        metadata = key_values(archive.read('META-INF/com/android/metadata'))
        props = key_values(archive.read('payload_properties.txt'))
        for key, expected in lock['ota_metadata'].items():
            require(metadata.get(key) == expected, 'OTA metadata mismatch: ' + key)
        require(not any(key in metadata for key in ('pre-build', 'pre-build-incremental')),
                'Incremental OTA cannot be a complete stock source')
        require(props == lock['payload_properties'], 'Pinned payload properties mismatch')
        info = archive.getinfo('payload.bin')
        require(info.file_size == int(props['FILE_SIZE']), 'ZIP payload size mismatch')
        with archive.open(info) as source, payload.open('xb') as target:
            shutil.copyfileobj(source, target, 8 * 1024 * 1024)
    actual = digest(payload)
    require(actual['size'] == int(props['FILE_SIZE']), 'Payload length mismatch')
    require(base64.b64encode(bytes.fromhex(actual['sha256'])).decode() == props['FILE_HASH'],
            'Payload SHA-256 mismatch')
    metadata_size = int(props['METADATA_SIZE'])
    require(24 <= metadata_size <= actual['size'], 'Invalid payload metadata size')
    with payload.open('rb') as stream:
        header = stream.read(24)
        magic, major, manifest_size, signature_size = struct.unpack('>4sQQI', header)
        require(magic == b'CrAU' and major == 2 and 24 + manifest_size == metadata_size,
                'Unexpected payload header')
        require(metadata_size + signature_size <= actual['size'], 'Invalid signature extent')
        stream.seek(0)
        h = hashlib.sha256()
        remaining = metadata_size
        while remaining:
            chunk = stream.read(min(8 * 1024 * 1024, remaining))
            require(bool(chunk), 'Short payload metadata')
            h.update(chunk)
            remaining -= len(chunk)
    require(base64.b64encode(h.digest()).decode() == props['METADATA_HASH'],
            'Payload metadata SHA-256 mismatch')
    extracted = output / 'payload-images'
    extracted.mkdir()
    with (output / 'ota-extract.log').open('wb') as log:
        subprocess.run([str(host_bin / 'ota_extractor'), '--payload=' + str(payload),
                        '--output_dir=' + str(extracted)], stdout=log, stderr=subprocess.STDOUT, check=True)
    expected = expected_paths(lock)
    require({p.name for p in extracted.iterdir()} == {PurePosixPath(p).name for p in expected},
            'Unexpected or missing payload partition set')
    for rel in sorted(expected):
        (extracted / PurePosixPath(rel).name).rename(output / rel)
    extracted.rmdir()
    # Payload is a reproducible temporary copy of the retained, verified ZIP.
    payload.unlink()
    return {'ota_metadata': metadata, 'payload_integrity': {
        'file_sha256': actual['sha256'], 'file_size': actual['size'],
        'metadata_sha256': h.hexdigest(), 'metadata_size': metadata_size,
        'signature_trust_chain_verified': False}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host-bin', type=Path)
    parser.add_argument('--lock', type=Path, default=LOCK)
    parser.add_argument('--verify-prepared', action='store_true', help='Rehash a completed staging directory only')
    args = parser.parse_args()
    args.output = args.output.resolve()
    args.lock = args.lock.resolve()
    lock = json.loads(args.lock.read_text())
    require(lock['device'] == 'gold', 'Unexpected device lock')
    if args.verify_prepared:
        verify_prepared(args.output, lock, args.lock)
        print('Verified prepared inputs:', lock['version'])
        return
    if not args.archive or not args.host_bin:
        parser.error('--archive and --host-bin are required for extraction')
    if sys.platform != 'linux':
        parser.error('Run extraction on the Linux Android build host. Verification is portable.')
    args.archive = args.archive.resolve()
    args.host_bin = args.host_bin.resolve()
    require(not args.output.exists(), 'Output already exists; use a fresh staging directory')
    fmt = lock.get('archive_format', 'fastboot-tgz')
    require(fmt in ('fastboot-tgz', 'recovery-full-ota'), 'Unsupported archive format')
    for tool in (('ota_extractor',) if fmt == 'recovery-full-ota' else ('simg2img', 'lpunpack')):
        require((args.host_bin / tool).is_file(), 'Missing existing Android host tool: ' + tool)
    require(args.archive.stat().st_size == lock['archive']['size'], 'Official archive size mismatch')
    actual = digest(args.archive)
    check_digest(actual, lock['archive'], 'Official archive')
    print('Verified official archive', lock['version'], flush=True)
    args.output.mkdir(parents=True)
    (args.output / 'physical').mkdir()
    (args.output / 'logical').mkdir()
    details = (extract_recovery(args.archive, args.output, args.host_bin, lock)
               if fmt == 'recovery-full-ota' else extract_fastboot(args.archive, args.output, args.host_bin))
    images = verify_images(args.output, lock)
    report = {'schema_version': 2, 'stock_version': lock['version'], 'region': lock['region'],
              'archive_format': fmt, 'lock_sha256': digest(args.lock)['sha256'],
              'archive': actual, 'images': images, 'kernel_release': lock.get('kernel', {}).get('release'),
              'phone_commands_executed': False, 'prepared_only': True, 'acceptance': {
                  'archive_integrity': True, 'partition_integrity': 'images' in lock,
                  'signature_trust_chain': False, 'full_build': False, 'device': False}, **details}
    temporary = args.output / 'prepared.json.tmp'
    temporary.write_text(json.dumps(report, indent=2) + '\n')
    temporary.replace(args.output / 'prepared.json')
    print('Prepared', len(images), 'official partition inputs; no device writes.', flush=True)


if __name__ == '__main__':
    main()
