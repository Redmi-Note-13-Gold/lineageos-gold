#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Rebuild selected APKs using a verified existing Gold Ninja graph.

Only edits to already-present sources/resources are allowed. A product, build
recipe, file-list or toolchain change must use the normal Soong build instead.
This creates module artifacts, never a ROM acceptance or a reboot requirement.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import os
import shutil
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
MODULES = {
    'DeviceDiagnostics': ('packages/apps/DeviceDiagnostics/app/src/main/DeviceDiagnostics/android_common/DeviceDiagnostics.apk', {
        'packages/apps/DeviceDiagnostics/DeviceDiagnosticsLib/src/main/java/com/android/devicediagnostics/BatteryActivity.kt',
        'packages/apps/DeviceDiagnostics/DeviceDiagnosticsLib/src/main/java/com/android/devicediagnostics/evaluated/BatteryUtilities.kt'}),
    'FrameworkResOverlayGold': ('device/xiaomi/gold/overlay/FrameworksResOverlayGold/FrameworkResOverlayGold/android_common/signed/FrameworkResOverlayGold.apk', {
        'device/xiaomi/gold/overlay/FrameworksResOverlayGold/res/values/config.xml'}),
}

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''): h.update(block)
    return h.hexdigest()


def verify_delta(before, after, modules):
    if not before.get('merged_inputs_match_mainline') or not after.get('merged_inputs_match_mainline'):
        raise ValueError('Both source audits must pass')
    if before['projects'] != after['projects']:
        raise ValueError('Pinned project revisions changed; regenerate the graph')
    allowed = set().union(*(MODULES[name][1] for name in modules))
    changed = {name for name in before['files'].keys() | after['files'].keys()
               if before['files'].get(name) != after['files'].get(name)}
    if not changed or changed - allowed:
        raise ValueError('No supported source-only delta, or unrelated inputs changed: ' + repr(sorted(changed)))
    return sorted(changed)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', type=Path, required=True)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('modules', nargs='+', choices=sorted(MODULES))
    args = parser.parse_args()
    tree = args.tree.resolve(); out = tree / 'out-gold-standard'
    with (tree / '.repo/gold-source-build.lock').open('a') as source_lock, (out / '.lock').open('a') as output_lock:
        fcntl.flock(source_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(output_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        subprocess.run(['python3', ROOT / 'tools/host/check-research-layout.py', '--source-tree', tree], check=True, stdout=subprocess.DEVNULL)
        marker = json.loads((out / '.gold-source-build.json').read_text())
        if marker.get('source_tree') != str(tree) or (out / '.top').read_text().strip() != str(tree):
            raise ValueError('Output ownership/top mismatch')
        spec = importlib.util.spec_from_file_location('gold_audit', ROOT / 'tools/check-mainline-source.py')
        audit = importlib.util.module_from_spec(spec); spec.loader.exec_module(audit)
        actual = audit.check(tree); baseline = json.loads(args.baseline.read_text())
        changed = verify_delta(baseline, actual, args.modules)
        # Every newly audited input must already exist in its pinned source revision.
        for path in set(actual['files']) - set(baseline['files']):
            project = max((p for p in actual['projects'] if path.startswith(p + '/')), key=len)
            subprocess.run(['git', '-C', tree / project, 'cat-file', '-e', 'HEAD:' + path[len(project)+1:]], check=True)
        args.record.mkdir(parents=True, exist_ok=False)
        (args.record / 'source-inputs.json').write_text(json.dumps(actual, indent=2) + '\n')
        env_file = out / 'soong/ninja.environment'
        env = {item['Key']: item['Value'] for item in json.loads(env_file.read_text())}
        if env.get('PWD') != str(tree) or env.get('OUT_DIR') != out.name or env.get('TARGET_PRODUCT') != 'lineage_gold':
            raise ValueError('Ninja environment does not match the managed output')
        env.update(GOGC='50', GOMEMLIMIT='10GiB', GOMAXPROCS='4')
        graphs = [out / 'combined-lineage_gold.ninja', out / 'build-lineage_gold.ninja',
                  out / 'build-lineage_gold-package.ninja', out / 'soong/build.lineage_gold.ninja']
        targets = [str((out / 'soong/.intermediates' / MODULES[name][0]).relative_to(tree)) for name in args.modules]
        record = {'kind': 'incremental_apks_existing_graph', 'rom_built': False, 'device_accepted': False,
                  'started_at': time.time(), 'systemd_invocation_id': os.environ.get('INVOCATION_ID'),
                  'baseline': str(args.baseline), 'changed_sources': changed, 'modules': args.modules,
                  'graph_sha256': {str(p.relative_to(tree)): digest(p) for p in graphs},
                  'ninja_environment_sha256': digest(env_file), 'build_datetime': (out / 'build_date.txt').read_text().strip(),
                  'output_inode': out.stat().st_ino, 'jobs': 2, 'artifacts': {}}
        (args.record / 'inputs.json').write_text(json.dumps(record, indent=2) + '\n')
        try:
            command = [str(tree / 'prebuilts/build-tools/linux-x86/bin/ninja'), '-j2', '-f', str(graphs[0].relative_to(tree)), *targets]
            record['command'] = command
            result = subprocess.run(command, cwd=tree, env=env)
            record['exit_code'] = result.returncode
            if result.returncode: raise RuntimeError('Incremental APK compilation failed')
            host = out / 'host/linux-x86/bin'
            for name, target in zip(args.modules, targets):
                path = tree / target
                check_env = dict(env, PATH=str(tree / 'prebuilts/jdk/jdk21/linux-x86/bin') + ':' + env['PATH'])
                checked = subprocess.run([host / 'apksigner', 'verify', '--verbose', '--print-certs', path], env=check_env, capture_output=True, text=True)
                (args.record / (name + '-signature.txt')).write_text(checked.stdout + checked.stderr)
                if checked.returncode: raise RuntimeError(name + ' APK signature failed')
                frozen = args.record / (name + '.apk')
                shutil.copyfile(path, frozen)
                with frozen.open('rb') as stream: os.fsync(stream.fileno())
                if digest(frozen) != digest(path): raise RuntimeError('APK copy hash mismatch')
                record['artifacts'][name] = {'path': str(frozen), 'source_output': str(path), 'bytes': frozen.stat().st_size, 'sha256': digest(frozen), 'signature_verified': True}
            record['module_build_passed'] = True
        except BaseException as error:
            record['module_build_passed'] = False; record['error'] = str(error)
            raise
        finally:
            record['finished_at'] = time.time()
            (args.record / 'result.json').write_text(json.dumps(record, indent=2) + '\n')

if __name__ == '__main__': main()
