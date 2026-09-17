#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Plan or run the pinned standard Android product and full OTA build.

Default is a plan. Execution builds bacon and target-files-package together,
then validates their final partition contract. No post-build image rewriting,
release signing, publishing or device operations. Linux x86_64 host only.
"""
import argparse
import fcntl
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import time
import zipfile

REPO = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('gold_artifacts', REPO / 'tools/check-artifacts.py')
CHECK = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CHECK)
CONFIG_VARS = ('TARGET_PRODUCT', 'TARGET_BUILD_VARIANT', 'AB_OTA_UPDATER', 'AB_OTA_PARTITIONS',
               'PRODUCT_USE_DYNAMIC_PARTITIONS', 'BOARD_AVB_ENABLE', 'DEFAULT_SYSTEM_DEV_CERTIFICATE', 'BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS',
               'BOARD_KERNEL_CMDLINE', 'SELINUX_IGNORE_NEVERALLOWS', 'ALLOW_MISSING_DEPENDENCIES',
               'BUILD_BROKEN_ELF_PREBUILT_PRODUCT_COPY_FILES')


def enabled(value):
    return value.strip().lower() not in ('', '0', 'false', 'no')


def verify_config(config, variant):
    if config['TARGET_PRODUCT'] != 'lineage_gold' or config['TARGET_BUILD_VARIANT'] != variant:
        raise ValueError('Resolved product/variant differs from requested lunch')
    for name in ('AB_OTA_UPDATER', 'PRODUCT_USE_DYNAMIC_PARTITIONS', 'BOARD_AVB_ENABLE'):
        if config[name] != 'true':
            raise ValueError('Standard full OTA requires ' + name + '=true')
    for name in ('SELINUX_IGNORE_NEVERALLOWS', 'ALLOW_MISSING_DEPENDENCIES', 'BUILD_BROKEN_ELF_PREBUILT_PRODUCT_COPY_FILES'):
        if enabled(config[name]):
            raise ValueError('Build bypass is enabled in resolved configuration: ' + name)
    args = config['BOARD_AVB_MAKE_VBMETA_IMAGE_ARGS'].split()
    if ('--set_hashtree_disabled_flag' in args or
            '--flags' in args and (args.index('--flags') + 1 == len(args) or args[args.index('--flags') + 1] != '0')):
        raise ValueError('Resolved configuration disables AVB verification/hashtree')
    if 'androidboot.selinux=permissive' in config['BOARD_KERNEL_CMDLINE']:
        raise ValueError('Resolved kernel command line makes the complete device permissive')
    if not config['AB_OTA_PARTITIONS'].split():
        raise ValueError('No A/B OTA partitions in resolved product')


def output_path(tree, requested=None):
    # This pinned Soong tree feeds host output paths into module-relative data
    # paths. Keep OUT_DIR inside the source tree and pass its relative spelling.
    tree = tree.resolve()
    requested = requested or Path('out-gold-standard')
    out = (requested if requested.is_absolute() else tree / requested).resolve()
    if not out.is_relative_to(tree):
        raise ValueError('OUT_DIR must resolve inside the source tree; external output directories are unsupported')
    if out == tree / 'out' or out == tree or out.is_relative_to(tree / '.repo'):
        raise ValueError('Use a separate standard-build OUT_DIR, not the existing default out or .repo')
    return out


def claim_output(tree, out):
    tree = tree.resolve()
    out = output_path(tree, out)
    marker = out / '.gold-source-build.json'
    if out.exists() and any(out.iterdir()):
        if not marker.is_file() or json.loads(marker.read_text()).get('source_tree') != str(tree):
            raise ValueError('OUT_DIR is nonempty and is not owned by this source build entry')
        clean = False
    else:
        out.mkdir(parents=True, exist_ok=True)
        marker.write_text(json.dumps({'schema_version': 1, 'source_tree': str(tree)}) + '\n')
        clean = True
    return clean


def single(paths, description):
    paths = list(paths)
    if len(paths) != 1:
        raise ValueError('Expected exactly one ' + description + ', found ' + str(len(paths)))
    return paths[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tree', required=True, type=Path)
    parser.add_argument('--lunch', required=True, help='lineage_gold-<release_config>-user or -userdebug')
    parser.add_argument('--jobs', type=int, default=8)
    parser.add_argument('--build-datetime', type=int, help='Fixed Unix timestamp; required for execution')
    parser.add_argument('--out', type=Path, help='Managed output inside source; relative paths are relative to TREE; default out-gold-standard')
    parser.add_argument('--execute', action='store_true')
    args = parser.parse_args()
    match = re.fullmatch(r'lineage_gold-[A-Za-z0-9_]+-(user|userdebug)', args.lunch)
    if not match or args.jobs < 1:
        parser.error('Use lineage_gold-<release_config>-user or -userdebug and positive --jobs')
    tree = args.tree.resolve()
    out = output_path(tree, args.out)
    plan = {'source_tree': str(tree), 'out_dir': str(out), 'out_dir_env': out.relative_to(tree).as_posix(), 'lunch': args.lunch, 'jobs': args.jobs,
            'build_datetime': args.build_datetime,
            'targets': ['bacon', 'target-files-package'], 'execute': args.execute,
            'output_role': 'standard Android target-files and full A/B OTA',
            'release_signing_verified': False, 'device_accepted': False}
    print(json.dumps(plan, indent=2), flush=True)
    if not args.execute:
        return
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        parser.error('Execute only on a Linux x86_64 Android build host')
    if args.build_datetime is None or args.build_datetime <= 0:
        parser.error('--execute requires a positive --build-datetime')
    if not (tree / '.repo').is_dir():
        parser.error('--tree must be a Repo-managed Android source tree')
    for name in ('SELINUX_IGNORE_NEVERALLOWS', 'ALLOW_MISSING_DEPENDENCIES', 'BUILD_BROKEN_ELF_PREBUILT_PRODUCT_COPY_FILES'):
        if enabled(os.environ.get(name, '')):
            parser.error('Remove build bypass environment flag: ' + name)
    with (tree / '.repo/gold-source-build.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            parser.error('Another standard Gold build holds this source-tree lock')
        plan['clean_output_directory'] = claim_output(tree, out)
        record_dir = out / 'gold-build-records' / str(time.time_ns())
        config_dir = record_dir / 'config'
        config_dir.mkdir(parents=True)
        (record_dir / 'inputs.json').write_text(json.dumps(plan, indent=2) + '\n')
        with (record_dir / 'manifest.xml').open('w') as manifest:
            subprocess.run(['repo', 'manifest', '-r'], cwd=tree, stdout=manifest, check=True)
        env = os.environ.copy()
        env.update(OUT_DIR=plan['out_dir_env'], BUILD_DATETIME=str(args.build_datetime), SOURCE_DATE_EPOCH=str(args.build_datetime))
        env.pop('OUT_DIR_COMMON_BASE', None)
        result_record = {'build_exit_code': None, 'artifact_contract_verified': False, 'android_validators_passed': False,
                         'release_signing_verified': False, 'device_accepted': False}
        try:
            configure = 'set -e; source build/envsetup.sh; lunch "$1"; config_dir="$2"; shift 2; for name in "$@"; do get_build_var "$name" > "$config_dir/$name"; done'
            subprocess.run(['bash', '-c', configure, 'gold-config', args.lunch, str(config_dir), *CONFIG_VARS], cwd=tree, env=env, check=True)
            config = {name: (config_dir / name).read_text().strip() for name in CONFIG_VARS}
            verify_config(config, match.group(1))
            plan['resolved_config'] = config
            (record_dir / 'inputs.json').write_text(json.dumps(plan, indent=2) + '\n')
            command = 'set -e; source build/envsetup.sh; lunch "$1"; jobs="$2"; shift 2; m -j"$jobs" "$@"'
            result = subprocess.run(['bash', '-c', command, 'gold-build', args.lunch, str(args.jobs), *plan['targets']], cwd=tree, env=env)
            result_record['build_exit_code'] = result.returncode
            if result.returncode:
                raise ValueError('Android product build failed: ' + str(result.returncode))
            product = out / 'target/product/gold'
            target = single((product / 'obj/PACKAGING/target_files_intermediates').glob('*-target_files.zip'), 'target-files archive')
            ota = single(product.glob('lineage_gold*-ota.zip'), 'standard OTA archive')
            result_record.update(CHECK.verify_artifacts(target, ota, args.build_datetime, config['AB_OTA_PARTITIONS'].split()))
            host_bin = out / 'host/linux-x86/bin'
            verify_env = env.copy()
            verify_env['PATH'] = str(host_bin) + os.pathsep + env.get('PATH', '')
            cert = Path(config['DEFAULT_SYSTEM_DEV_CERTIFICATE'] + '.x509.pem')
            if not cert.is_absolute():
                cert = tree / cert
            if not cert.is_file():
                raise ValueError('Resolved OTA certificate is missing')
            result_record['ota_certificate_sha256'] = CHECK.digest(cert)
            validators = [
                ('validate_target_files', [str(target)]),
                ('check_target_files_vintf', [str(target)]),
                ('check_ota_package_signature', [str(cert), str(ota)]),
            ]
            for tool, arguments in validators:
                with (record_dir / (tool + '.log')).open('w') as log:
                    subprocess.run([str(host_bin / tool), *arguments], cwd=tree, env=verify_env, stdout=log, stderr=subprocess.STDOUT, check=True)
            # Analyze the compiled policy actually packaged for the device,
            # not a stale monolithic policy from a legacy output directory.
            with zipfile.ZipFile(target) as archive:
                policies = [name for name in ('VENDOR/etc/selinux/precompiled_sepolicy', 'ODM/etc/selinux/precompiled_sepolicy') if name in archive.namelist()]
                if len(policies) != 1:
                    raise ValueError('Expected one actual packaged precompiled SELinux policy')
                policy = record_dir / 'packaged-sepolicy'
                policy.write_bytes(archive.read(policies[0]))
            result_record['packaged_policy_sha256'] = CHECK.digest(policy)
            permissive = subprocess.check_output([str(host_bin / 'sepolicy-analyze'), str(policy), 'permissive'], cwd=tree, env=verify_env, text=True).split()
            result_record['permissive_domains'] = permissive
            if match.group(1) == 'user' and permissive:
                raise ValueError('Release user policy contains permissive domains: ' + ', '.join(permissive))
            result_record['android_validators_passed'] = True
            result_record['ota_and_payload_signatures_verified'] = True
            result_record.update(target_files=str(target), ota=str(ota))
        except (ValueError, OSError, KeyError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
            result_record['error'] = str(error)
            raise
        finally:
            (record_dir / 'result.json').write_text(json.dumps(result_record, indent=2) + '\n')
            print('Build record:', record_dir)
        print('Standard OTA/target-files passed Android validators. Certificate identity is recorded; release-key trust and device acceptance remain separate.')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
