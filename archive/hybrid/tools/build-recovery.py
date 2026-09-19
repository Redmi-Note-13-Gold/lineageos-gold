#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Combine Lineage Recovery with the verified OS3 vendor-boot platform inputs.

Only the named recovery ramdisk is replaced. This creates an offline candidate,
not proof of Recovery boot, data formatting, sideload or installed-system boot.
"""
import argparse
import fcntl
import importlib.util
import json
from pathlib import Path
import shlex
import shutil


def load(path):
    spec = importlib.util.spec_from_file_location('stock_builder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fragments(args):
    result = []
    kind, name = None, None
    for index, option in enumerate(args):
        if option == '--ramdisk_type':
            kind = int(args[index + 1])
        elif option == '--ramdisk_name':
            name = args[index + 1]
        elif option == '--vendor_ramdisk_fragment':
            result.append((kind, name, Path(args[index + 1]), index + 1))
            kind, name = None, None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'assembly', 'lineage-vendor-boot', 'output', 'lock'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--firmware-lock', type=Path, default=Path(__file__).resolve().parents[3] / 'firmware/gold-global.json')
    parser.add_argument('--key', type=Path)
    args = parser.parse_args()
    for name in ('source', 'assembly', 'lineage_vendor_boot', 'output', 'lock', 'firmware_lock'):
        setattr(args, name, getattr(args, name).resolve())
    args.host_bin = args.source / 'out/host/linux-x86/bin'
    args.key = (args.key or args.source / 'external/avb/test/data/testkey_rsa4096.pem').resolve()
    b = load(Path(__file__).with_name('build-stock-base.py'))
    b.require(not args.output.exists(), 'Use a fresh output directory')
    with args.lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest = json.loads((args.assembly / 'assembly.json').read_text())
        firmware = json.loads(args.firmware_lock.read_text())
        b.require(manifest['stock_version'] == firmware['version'], 'Unexpected firmware baseline')
        b.require(manifest['firmware_lock_sha256'] == b.sha(args.firmware_lock), 'Firmware lock changed')
        b.require(manifest['stock_archive_sha256'] == firmware['archive']['sha256'], 'Stock archive changed')
        for name, record in manifest['images'].items():
            b.require(b.sha(args.assembly / 'images' / name) == record['sha256'], 'Changed input: ' + name)
        args.output.mkdir()
        builder = b.Builder(args)
        builder.logs.mkdir()
        builder.images.mkdir()
        stock = args.assembly / 'images/vendor_boot.img'
        unpacked = {}
        for kind, image in [('stock', stock), ('lineage', args.lineage_vendor_boot)]:
            target = args.output / (kind + '-unpacked')
            value = builder.native.run('unpack_bootimg', '--boot_img', image, '--out', target,
                                       '--format=mkbootimg', log=kind + '-unpack.log')
            unpacked[kind] = shlex.split(value.stdout.decode())
        original = fragments(unpacked['stock'])
        lineage = fragments(unpacked['lineage'])
        b.require([(t, n) for t, n, _, _ in original] == [(1, ''), (2, 'recovery'), (1, 'init_boot')],
                  'Unexpected official ramdisk layout')
        candidates = [p for t, n, p, _ in lineage if t == 2 and n == 'recovery']
        b.require(len(candidates) == 1, 'Expected one Lineage recovery ramdisk')
        command = unpacked['stock'][:]
        command[original[1][3]] = str(candidates[0])
        output = builder.images / 'vendor_boot.img'
        builder.native.run('mkbootimg', *command, '--vendor_boot', output, log='repack.log')
        _, header, descriptors, size, _ = builder.h.parse_avb(builder.avb, stock)
        hashes = [d for d in descriptors if isinstance(d, builder.avb.AvbHashDescriptor)]
        b.require(len(hashes) == 1 and hashes[0].partition_name == 'vendor_boot', 'Unexpected AVB hash')
        desc = hashes[0]
        footer = ['add_hash_footer', '--image', output, '--partition_name', 'vendor_boot',
                  '--partition_size', str(size), '--hash_algorithm', desc.hash_algorithm,
                  '--salt', desc.salt.hex(), '--algorithm', 'SHA256_RSA4096', '--key', args.key,
                  '--rollback_index', str(header.rollback_index),
                  '--rollback_index_location', str(header.rollback_index_location)]
        for item in descriptors:
            if isinstance(item, builder.avb.AvbPropertyDescriptor):
                footer += ['--prop', b.text(item.key) + ':' + b.text(item.value)]
        builder.native.run('avbtool', *footer, log='vendor-boot-avb.log')
        for name in manifest['images']:
            if name not in ('vendor_boot.img', 'vbmeta.img'):
                (builder.images / name).symlink_to((args.assembly / 'images' / name).resolve())
        chains = [d for d in builder.descriptors(args.assembly / 'images/vbmeta.img')
                  if isinstance(d, builder.avb.AvbChainPartitionDescriptor)]
        b.require({d.partition_name for d in chains} == {'boot', 'vbmeta_system', 'vbmeta_vendor'},
                  'Unexpected AVB chain layout')
        builder.parent('vbmeta', args.assembly / 'images/vbmeta.img',
                       ['dtbo', 'vendor_boot', 'mi_ext', 'system_dlkm', 'vendor_dlkm', 'odm_dlkm'],
                       [(d.partition_name, d.rollback_index_location) for d in chains])
        builder.native.run('avbtool', 'verify_image', '--image', builder.images / 'vbmeta.img',
                           '--follow_chain_partitions', log='avb-chain.log')
        check = args.output / 'verified-unpacked'
        result = builder.native.run('unpack_bootimg', '--boot_img', output, '--out', check,
                                    '--format=mkbootimg', log='verify-unpack.log')
        final = fragments(shlex.split(result.stdout.decode()))
        b.require(len(final) == len(original), 'Ramdisk count changed')
        for before, after in zip(original, final):
            b.require(before[:2] == after[:2], 'Ramdisk order/type/name changed')
            expected = candidates[0] if before[1] == 'recovery' else before[2]
            b.require(b.sha(expected) == b.sha(after[2]), 'Ramdisk content mismatch')
        for name in ('dtb', 'bootconfig'):
            b.require(b.sha(args.output / 'stock-unpacked' / name) == b.sha(check / name), name + ' changed')
        report = dict(manifest)
        report['images'] = {p.name: {'size': p.stat().st_size, 'sha256': b.sha(p)}
                            for p in sorted(builder.images.glob('*.img'))}
        report['recovery'] = {'lineage_vendor_boot_sha256': b.sha(args.lineage_vendor_boot),
                              'lineage_recovery_fragment_sha256': b.sha(candidates[0]),
                              'stock_platform_and_init_boot_preserved': True,
                              'stock_dtb_preserved': True, 'device_tested': False}
        (args.output / 'assembly.json').write_text(json.dumps(report, indent=2) + '\n')
        (args.output / 'SHA256SUMS').write_text(''.join(
            f"{entry['sha256']}  images/{name}\n" for name, entry in report['images'].items()))
        print('Recovery candidate built and AVB/ramdisk integrity verified; device testing pending.')


if __name__ == '__main__':
    main()
