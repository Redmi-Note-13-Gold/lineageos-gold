#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the partition and metadata contract of completed Android build outputs.

Android's own validators handle VINTF and signatures. This helper does not
inspect source checkouts or generated vendor inputs. Python 3.9+.
"""
import argparse
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
    return {'artifact_contract_verified': True, 'target_files_sha256': digest(target_files), 'ota_sha256': digest(ota),
            'partitions': parts, 'dynamic_partitions': dynamics['dynamic_partition_list'].split(),
            'post_timestamp': timestamp, 'signing_tag': metadata.get('post-build', '').rsplit('/', 1)[-1],
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
