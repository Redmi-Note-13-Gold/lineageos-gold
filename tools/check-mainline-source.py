#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare the actual merged Android inputs with mainline without modifying them.

Reconstruct only patched files from pinned Git objects. This detects an old
OverlayFS upper file shadowing the intended source without copying a checkout.
It does not validate vendor provenance, build a product, or access a device.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gold_apply', ROOT / 'tools/apply-patches.py')
APPLY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APPLY)


def git_result(tree, *args, check=True):
    # Explicitly requested, pinned trees can retain their original build UID.
    # Trust only this exact path for this read, without changing global config.
    tree = Path(tree).resolve()
    result = subprocess.run(['git', '-c', 'safe.directory=' + str(tree), '-C', str(tree), *args],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode:
        raise RuntimeError(result.stderr.decode(errors='replace'))
    return result


APPLY.git = git_result


def git(tree, *args):
    return git_result(tree, *args).stdout


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check(tree):
    result = {'project_commit': git(ROOT, 'rev-parse', 'HEAD').decode().strip(),
              'tree': str(tree), 'projects': {}, 'files': {}, 'failures': []}

    def compare(path, expected, execute=None):
        actual = tree / path
        if expected is None:
            if actual.exists() or actual.is_symlink():
                result['failures'].append('Unexpected retained source: ' + path)
            return
        if actual.is_symlink() or not actual.is_file():
            result['failures'].append('Missing or symlinked input: ' + path)
            return
        data = actual.read_bytes()
        result['files'][path] = digest(data)
        if data != expected or execute is not None and bool(actual.stat().st_mode & 0o111) != bool(execute):
            result['failures'].append('Merged source differs: ' + path)

    for retired in ('external/openeuicc', 'external/openeuicc-deps'):
        if (tree / retired).exists() or (tree / retired).is_symlink():
            result['failures'].append('Retired eSIM source still present: ' + retired)

    for entry in json.loads((ROOT / 'patches/series.json').read_text()):
        path = entry['path']
        project = tree / path
        head = git(project, 'rev-parse', 'HEAD').decode().strip()
        result['projects'][path] = head
        if head != entry['revision']:
            result['failures'].append('Wrong pinned revision: ' + path)
            continue
        patches = [ROOT / name for name in entry['patches']]
        if path == 'build/soong':
            patches.append(ROOT / 'tools/host/soong-memory-env.patch')
        expected = APPLY.validate_series(project, patches)
        for name, content in expected.items():
            compare(path + '/' + name, None if content is None else content[0],
                    None if content is None else content[1])
        allowed = set(expected)
        if 'source' in entry:
            source = ROOT / entry['source']
            for own in APPLY.source_files(source):
                name = own.relative_to(source).as_posix()
                allowed.add(name)
                compare(path + '/' + name, own.read_bytes(), own.stat().st_mode & 0o111)
            for name in entry.get('remove', []):
                allowed.add(name)
                compare(path + '/' + name, None)
        changed = git(project, 'diff', 'HEAD', '--name-only').decode().splitlines()
        untracked = git(project, 'ls-files', '--others', '--exclude-standard').decode().splitlines()
        submodules = entry.get('submodules', {})
        extra = set(changed + untracked) - allowed - set(submodules)
        for name in sorted(extra):
            result['failures'].append('Unmanaged source change: ' + path + '/' + name)
        for name, revision in submodules.items():
            if git(project / name, 'rev-parse', 'HEAD').decode().strip() != revision:
                result['failures'].append('Wrong submodule: ' + path + '/' + name)
    for own in APPLY.source_files(ROOT / 'vendor/xiaomi/gold/ims'):
        compare(own.relative_to(ROOT).as_posix(), own.read_bytes())
    result['merged_inputs_match_mainline'] = not result['failures']
    result['archive_hybrid_executed'] = False
    result['device_accepted'] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = check(args.tree.resolve())
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as error:
        result = {'merged_inputs_match_mainline': False, 'failures': [str(error)]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['merged_inputs_match_mainline'] else 1)


if __name__ == '__main__':
    main()
