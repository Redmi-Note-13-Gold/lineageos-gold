#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the partition and metadata contract of completed Android build outputs.

Android's own validators handle VINTF and signatures. This helper does not
inspect source checkouts or generated vendor inputs. Python 3.9+.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import struct
import zipfile


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for data in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(data)
    return h.hexdigest()


def key_values(text):
    return dict(line.split('=', 1) for line in text.splitlines() if '=' in line and not line.startswith('#'))


def protobuf_fields(data):
    """Read only protobuf wire values; reject truncation and malformed varints."""
    offset = 0

    def varint():
        nonlocal offset
        value = 0
        for shift in range(0, 70, 7):
            if offset >= len(data):
                raise ValueError('Truncated payload protobuf varint')
            byte = data[offset]
            offset += 1
            if shift == 63 and byte > 1:
                raise ValueError('Oversized payload protobuf varint')
            value |= (byte & 127) << shift
            if not byte & 128:
                return value
        raise ValueError('Oversized payload protobuf varint')

    while offset < len(data):
        key = varint()
        field, wire = key >> 3, key & 7
        if not 0 < field < (1 << 29):
            raise ValueError('Invalid payload protobuf field number')
        if wire == 0:
            value = varint()
        elif wire in (1, 2, 5):
            length = varint() if wire == 2 else (8 if wire == 1 else 4)
            if length > len(data) - offset:
                raise ValueError('Truncated payload protobuf field')
            value = data[offset:offset + length]
            offset += length
        else:
            raise ValueError('Unsupported payload protobuf wire type')
        yield field, wire, value


def protobuf_single(data, number, wire):
    values = [(kind, value) for field, kind, value in protobuf_fields(data) if field == number]
    if len(values) != 1 or values[0][0] != wire:
        raise ValueError('Missing, repeated or incorrectly typed payload field: ' + str(number))
    return values[0][1]


def verify_payload_images(target, package, parts):
    # CrAU v2, DeltaArchiveManifest.partitions=13, PartitionUpdate name=1 /
    # new_partition_info=7, PartitionInfo size=1/hash=2 follow the pinned
    # system/update_engine/update_metadata.proto. Signatures are checked by
    # Android's verifier separately. This binds its signed final hashes to
    # actual target-files images, not mutable loose images or older artifacts.
    with package.open('payload.bin') as payload:
        header = payload.read(24)
        if len(header) != 24:
            raise ValueError('Truncated payload header')
        magic, version, length, signatures = struct.unpack('>4sQQI', header)
        if magic != b'CrAU' or version != 2 or not 0 < length < 16 * 1024 * 1024:
            raise ValueError('Unsupported payload header')
        if length + signatures + 24 > package.getinfo('payload.bin').file_size:
            raise ValueError('Truncated payload manifest/signatures')
        manifest = payload.read(length)
    rows = []
    names = set()
    for field, wire, data in protobuf_fields(manifest):
        if field != 13:
            continue
        if wire != 2:
            raise ValueError('Invalid payload partition field type')
        name = protobuf_single(data, 1, 2).decode('ascii')
        if name not in parts or name in names:
            raise ValueError('Unexpected or repeated payload partition: ' + name)
        names.add(name)
        info = protobuf_single(data, 7, 2)
        size, expected = protobuf_single(info, 1, 0), protobuf_single(info, 2, 2)
        if size <= 0 or len(expected) != 32:
            raise ValueError('Invalid payload partition size/hash: ' + name)
        candidates = [p for p in ('IMAGES/' + name + '.img', 'RADIO/' + name + '.img')
                      if p in target.namelist()]
        if len(candidates) != 1:
            raise ValueError('Ambiguous target-files partition image: ' + name)
        member = candidates[0]
        actual = hashlib.sha256()
        with target.open(member) as stream:
            for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                actual.update(block)
        if target.getinfo(member).file_size != size or actual.digest() != expected:
            raise ValueError('Payload partition differs from target-files image: ' + name)
        rows.append({'partition': name, 'entry': member, 'bytes': size, 'sha256': actual.hexdigest()})
    if names != set(parts):
        raise ValueError('Payload is missing target-files partitions')
    return rows


def verify_lineage_dates(target, timestamp):
    """Bind Lineage's product and Recovery version dates to the build epoch."""
    utc = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    dates = {utc.strftime('%Y%m%d'), utc.strftime('%Y%m%d_%H%M%S')}
    versions = None
    for member in ('PRODUCT/etc/build.prop', 'VENDOR_BOOT/RAMDISK_FRAGMENTS/recovery/RAMDISK/prop.default'):
        props = key_values(target.read(member).decode())
        values = {name: props.get(name, '') for name in
                  ('ro.lineage.version', 'ro.lineage.display.version')}
        for value in values.values():
            fields = value.split('-')
            if len(fields) < 3 or fields[1] not in dates:
                raise ValueError('Lineage version date differs from build timestamp: ' + member)
        if versions is not None and values != versions:
            raise ValueError('Product and Recovery Lineage versions differ')
        versions = values
    return versions


def verify_artifacts(target_files, ota, timestamp, expected_parts=None):
    """Small product contract check; Android's own tools validate images/signatures."""
    with zipfile.ZipFile(target_files) as target, zipfile.ZipFile(ota) as package:
        if len(target.namelist()) != len(set(target.namelist())) or len(package.namelist()) != len(set(package.namelist())):
            raise ValueError('Duplicate ZIP entries')
        misc = key_values(target.read('META/misc_info.txt').decode())
        parts = target.read('META/ab_partitions.txt').decode().split()
        dynamics = key_values(target.read('META/dynamic_partitions_info.txt').decode())
        metadata = key_values(package.read('META-INF/com/android/metadata').decode())
        if expected_parts is not None and set(parts) != set(expected_parts):
            raise ValueError('Final AB partitions differ from resolved product configuration')
        if not parts or len(parts) != len(set(parts)) or any(p in parts for p in ('userdata', 'metadata', 'persist', 'nvram', 'nvdata')):
            raise ValueError('Invalid or unsafe AB partition list')
        if not set(dynamics.get('dynamic_partition_list', '').split()) <= set(parts):
            raise ValueError('Dynamic partitions missing from AB list')
        if misc.get('ab_update') != 'true' or misc.get('avb_enable') != 'true' or misc.get('use_dynamic_partitions') != 'true':
            raise ValueError('Expected A/B, AVB and dynamic partitions in final target-files')
        if misc.get('vintf_enforce') != 'true' or misc.get('avb_building_vbmeta_image') != 'true':
            raise ValueError('Final target-files would skip VINTF or AVB validation')
        if metadata.get('ota-type') != 'AB' or metadata.get('pre-device', '').split('|') != ['gold']:
            raise ValueError('Wrong OTA type/device')
        if int(metadata.get('post-timestamp', 0)) != timestamp:
            raise ValueError('OTA timestamp differs from requested source build')
        if any(key in metadata for key in ('ota-wipe', 'ota-downgrade', 'spl-downgrade', 'pre-build', 'pre-build-incremental')):
            raise ValueError('Expected full non-wiping non-downgrade OTA')
        if int(metadata.get('post-sdk-level', 0)) != 36:
            raise ValueError('Expected Android 16 / SDK 36')
        package.getinfo('META-INF/com/android/metadata.pb')
        payload = package.getinfo('payload.bin')
        if payload.compress_type != zipfile.ZIP_STORED:
            raise ValueError('payload.bin must be stored for A/B installation')
        props = key_values(package.read('payload_properties.txt').decode())
        if int(props.get('FILE_SIZE', 0)) != payload.file_size:
            raise ValueError('Payload size/properties mismatch')
        for name in parts:
            # Match pinned releasetools CheckAbOtaImages: standard firmware
            # added with add-radio-file may live only in RADIO/.
            candidates = ('IMAGES/' + name + '.img', 'RADIO/' + name + '.img')
            if not any(candidate in target.namelist() for candidate in candidates):
                raise ValueError('Missing A/B partition image in IMAGES/ or RADIO/: ' + name)
        vbmeta = target.read('IMAGES/vbmeta.img')
        if vbmeta[:4] != b'AVB0' or len(vbmeta) < 124 or struct.unpack('>I', vbmeta[120:124])[0] != 0:
            raise ValueError('Top-level AVB image disables verification/hashtree or is invalid')
        lineage_versions = verify_lineage_dates(target, timestamp)
        payload_images = verify_payload_images(target, package, parts)
    return {'artifact_contract_verified': True, 'target_files_sha256': digest(target_files), 'ota_sha256': digest(ota),
            'partitions': parts, 'dynamic_partitions': dynamics['dynamic_partition_list'].split(),
            'post_timestamp': timestamp, 'signing_tag': metadata.get('post-build', '').rsplit('/', 1)[-1],
            'payload_images_verified': True, 'payload_images': payload_images,
            'lineage_version_date_verified': True, 'lineage_versions': lineage_versions,
            'device_accepted': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-files', type=Path, required=True)
    parser.add_argument('--ota', type=Path, required=True)
    parser.add_argument('--build-datetime', type=int, required=True)
    args = parser.parse_args()
    result = verify_artifacts(args.target_files, args.ota, args.build_datetime)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit(str(error))
