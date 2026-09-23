#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Print an inventory of frozen candidates without changing packages or acceptance.

Navigation links are followed, and the physical storage path is always recorded.
Use --verify-hashes for explicit package-byte verification. A directory name or
candidate.json never substitutes for installation or hardware acceptance.
"""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import re


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def candidate(path, verify_hashes=False):
    record_path = path / 'candidate.json'
    metadata = json.loads(record_path.read_text()) if record_path.is_file() else {}
    result = metadata.get('result', {})
    artifacts = []
    for artifact in sorted(path.glob('*.zip')):
        kind = 'target_files' if 'target_files' in artifact.name else 'ota'
        recorded = metadata.get(kind, {})
        if not isinstance(recorded, dict):
            recorded = {}
        expected_hash = recorded.get('sha256') or result.get(kind + '_sha256')
        expected_size = recorded.get('bytes')
        size = artifact.stat().st_size
        if expected_size is not None and expected_size != size:
            raise ValueError('Recorded package size mismatch: ' + str(artifact))
        actual = digest(artifact) if verify_hashes else None
        if actual and expected_hash and actual != expected_hash:
            raise ValueError('Recorded package hash mismatch: ' + str(artifact))
        artifacts.append({'name': artifact.name, 'kind': kind, 'bytes': size,
                          'sha256_recorded': expected_hash,
                          'sha256_computed_now': actual,
                          'recorded_hash_verified_now': (actual == expected_hash) if actual and expected_hash else None})
    if not artifacts:
        raise ValueError('Candidate has no ZIP packages: ' + str(path))
    return {'id': path.name, 'path': str(path.absolute()), 'storage_path': str(path.resolve()),
            'record': str(record_path.resolve()) if record_path.is_file() else None,
            'record_sha256': digest(record_path) if record_path.is_file() else None,
            'source_revision_recorded': metadata.get('source_revision', metadata.get('commit')),
            'package_checks_recorded': metadata.get('validation_completed', result.get('android_validators_passed')),
            'artifacts': artifacts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--verify-hashes', action='store_true')
    args = parser.parse_args()
    if not args.directory.is_dir():
        parser.error('Candidate directory does not exist')
    candidates = []
    for path in sorted(args.directory.iterdir()):
        if re.fullmatch(r'[0-9]{8}-[0-9]{6}-[0-9a-f]{7,40}', path.name):
            if not path.is_dir():
                raise ValueError('Broken candidate navigation entry: ' + str(path))
            candidates.append(candidate(path, args.verify_hashes))
    print(json.dumps({'schema_version': 1, 'generated_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                      'root': str(args.directory.absolute()), 'package_hashes_read_now': args.verify_hashes,
                      'acceptance_source': 'project/docs/STATUS.md and project/validation; this index does not assign device acceptance',
                      'candidates': candidates}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError) as error:
        raise SystemExit(str(error))
