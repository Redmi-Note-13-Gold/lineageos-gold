#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compile policy and check VINTF against the assembled images, without a phone."""
import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path
import re
import zlib

# Reuse the same image/mount/AVB implementation; no second metadata pipeline.
import importlib.util
spec = importlib.util.spec_from_file_location('stock_build', Path(__file__).with_name('build-stock-base.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--firmware-lock', type=Path, default=b.REPO / 'firmware/gold-global.json')
    parser.add_argument('--assembly', type=Path, required=True)
    parser.add_argument('--apex-root', type=Path, required=True,
                        help='Extracted APEX VINTF inputs matching the Lineage upper images')
    args = parser.parse_args()
    b.require(os.geteuid() == 0, 'Linux root required for read-only image mounts')
    args.source, args.assembly, args.apex_root = (p.resolve() for p in (args.source, args.assembly, args.apex_root))
    out = args.assembly / 'validation'
    out.mkdir()
    logs = out / 'logs'
    logs.mkdir()
    h = b.load('hybrid_check', b.LEGACY / 'hybrid_properties.py')
    native = h.NativeTools(args.source, args.source / 'out/host/linux-x86/bin', logs)
    images = args.assembly / 'images'
    report = json.loads((args.assembly / 'assembly.json').read_text())
    firmware = json.loads(args.firmware_lock.read_text())
    b.require(report['stock_version'] == firmware['version'], 'Firmware version mismatch')
    b.require(report['firmware_lock_sha256'] == b.sha(args.firmware_lock), 'Firmware lock mismatch')
    for name, record in report['images'].items():
        b.require(b.sha(images / name) == record['sha256'], 'Image changed: ' + name)
    boot = out / 'boot'
    native.run('unpack_bootimg', '--boot_img', images / 'boot.img', '--out', boot, log='boot.log')
    kernel = (boot / 'kernel').read_bytes()
    if kernel.startswith(b'\x1f\x8b'):
        kernel = zlib.decompress(kernel, 16 + zlib.MAX_WBITS)
    start = kernel.find(b'IKCFG_ST')
    b.require(start >= 0, 'Kernel lacks embedded configuration')
    config = zlib.decompressobj(16 + zlib.MAX_WBITS).decompress(kernel[start + 8:])
    config_path = out / 'kernel.config'
    config_path.write_bytes(config)
    version = re.search(rb'Linux version (\d+\.\d+\.\d+)[^\x00\n]*', kernel)
    b.require(version is not None, 'Cannot identify official kernel version')
    if 'kernel' in firmware:
        b.require(b.sha(boot / 'kernel') == firmware['kernel']['sha256'], 'Pinned stock kernel mismatch')
    results = {'kernel_sha256': b.sha(boot / 'kernel'), 'kernel_version': version[1].decode(),
               'kernel_config_sha256': b.sha(config_path), 'device_flashed': False}
    with ExitStack() as mounts:
        roots = {}
        for part in ('system', 'system_ext', 'product', 'vendor', 'odm'):
            root = mounts.enter_context(b.mounted(images / (part + '.img'), out / part,
                                                  'ext4' if part in ('system', 'system_ext', 'product') else 'erofs'))
            roots[part.upper()] = root / 'system' if part == 'system' else root
        properties = h.validate(roots, native, out, 'runtime')
        results['runtime_policy_compilation'] = True
        results['property_contexts_valid'] = properties.returncode == 0
        strict = native.run('secilc', *h.policy_files(roots), '-m', '-M', 'true', '-G', '-c', '30',
                            '-o', out / 'strict.sepolicy', '-f', os.devnull, log='strict-policy.log', check=False)
        results['strict_neverallow_pass'] = strict.returncode == 0
        results['strict_neverallow_failures'] = len(re.findall(rb'neverallow check failed', strict.stderr + strict.stdout))
        command = ['--check-compat', '--property', 'ro.product.first_api_level=33',
                   '--kernel', version[1].decode() + ':' + str(config_path)]
        for part, root in roots.items():
            command += ['--dirmap', '/' + part.lower() + ':' + str(root)]
        command += ['--dirmap', '/apex:' + str(args.apex_root)]
        vintf = native.run('checkvintf', *command, log='vintf.log', check=False)
        results['vintf_compatible'] = vintf.returncode == 0
        # Ensure the running Lineage Messaging payload is present independently of mi_ext.
        results['lineage_messaging_present'] = (roots['PRODUCT'] / 'app/messaging/messaging.apk').is_file()
    if firmware['region'] == 'Global':
        with b.mounted(images / 'mi_ext.img', out / 'mi_ext') as root:
            files = [p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() or p.is_symlink()]
            results['global_mi_ext_minimal'] = set(files) == {'etc/build.prop', 'etc/NOTICE.xml.gz'}
            values = dict(line.split('=', 1) for line in (root / 'etc/build.prop').read_text().splitlines())
            results['global_mi_ext_version'] = values.get('ro.mi.os.version.incremental') == firmware['version']
    else:
        results['global_mi_ext_minimal'] = None
        results['global_mi_ext_version'] = None
    (out / 'checks.json').write_text(json.dumps(results, indent=2) + '\n')
    print(json.dumps(results, indent=2), flush=True)
    b.require(results['property_contexts_valid'] and results['vintf_compatible'] and
              results['lineage_messaging_present'] and results['strict_neverallow_pass'] and
              results['global_mi_ext_minimal'] is not False and results['global_mi_ext_version'] is not False, 'Compatibility check failed; inspect validation logs')
    # A runtime policy compile with neverallow disabled cannot satisfy this gate.


if __name__ == '__main__':
    main()
