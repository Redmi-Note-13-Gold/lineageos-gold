#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assemble pinned stock lower partitions with an existing Lineage image set.

Linux/root and existing Android host tools are required for read-only EROFS
mounts. Outputs are built in a fresh directory. This is an incremental image
assembly step, not a clean-source ROM build or a device installation tool.
"""
import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
LEGACY = Path(__file__).resolve().parent
VENDOR_CHANGES = {'etc/selinux/vendor_file_contexts', 'etc/selinux/vendor_sepolicy.cil',
                  'etc/ueventd.rc', 'etc/vintf/manifest.xml'}
CACHE = 'etc/selinux/precompiled_sepolicy'


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        while data := stream.read(8 * 1024 * 1024):
            result.update(data)
    return result.hexdigest()


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@contextmanager
def mounted(image, directory, filesystem='erofs'):
    directory.mkdir()
    # noload avoids journal replay even when inspecting ext4 read-only.
    options = 'loop,ro,noload' if filesystem == 'ext4' else 'loop,ro'
    subprocess.run(['mount', '-t', filesystem, '-o', options, str(image), str(directory)], check=True)
    try:
        yield directory
    finally:
        subprocess.run(['umount', str(directory)], check=True)


def inventory(root):
    result = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        paths = [Path(parent) / name for name in dirs + files]
        if Path(parent) == root:
            paths.insert(0, root)
        for path in paths:
            info = path.lstat()
            result[path.relative_to(root).as_posix()] = {
                'uid': info.st_uid, 'gid': info.st_gid, 'mode': info.st_mode,
                'xattrs': {key: os.getxattr(path, key, follow_symlinks=False).hex()
                          for key in os.listxattr(path, follow_symlinks=False)},
                'link': os.readlink(path) if path.is_symlink() else None,
                'sha256': sha(path) if stat.S_ISREG(info.st_mode) else None,
            }
    return result


def metadata(records, part, output):
    fs, fc = [], []
    for rel, record in sorted(records.items()):
        name = part if rel == '.' else part + '/' + rel
        attrs = {key: bytes.fromhex(value) for key, value in record['xattrs'].items()}
        require(set(attrs) <= {'security.selinux', 'security.capability'}, 'Unsupported xattrs: ' + name)
        require('security.selinux' in attrs, 'Missing SELinux label: ' + name)
        label = attrs['security.selinux'].rstrip(b'\0').decode()
        caps = 0
        if 'security.capability' in attrs:
            cap = attrs['security.capability']
            require(len(cap) in (20, 24), 'Unsupported capability length')
            magic, lo, loi, hi, hii = struct.unpack_from('<5I', cap)
            require(loi == hii == 0 and magic & 1 and
                    (len(cap) == 20 or struct.unpack_from('<I', cap, 20)[0] == 0),
                    'Unsupported capability encoding: ' + name)
            caps = lo + (hi << 32)
        fsname = '' if rel == '.' else name
        fs.append(f"{fsname} {record['uid']} {record['gid']} {stat.S_IMODE(record['mode']):04o} capabilities=0x{caps:x}\n")
        fc.append('/' + re.escape(name) + ('(/.*)?' if rel == '.' else '') + ' ' + label + '\n')
    config = output / (part + '-fs-config.txt')
    contexts = output / (part + '-file-contexts.txt')
    config.write_text(''.join(fs))
    contexts.write_text(''.join(fc))
    return config, contexts


def text(value):
    return value.decode() if isinstance(value, bytes) else value


class Builder:
    def __init__(self, args):
        self.args = args
        self.firmware_lock_path = args.firmware_lock
        self.firmware = json.loads(self.firmware_lock_path.read_text())
        self.output = args.output
        self.images = args.output / 'images'
        self.logs = args.output / 'logs'
        self.h = load('gold_hybrid', LEGACY / 'hybrid_properties.py')
        self.avb = load('gold_avb', args.source / 'external/avb/avbtool.py')
        self.policy = load('gold_policy', LEGACY / 'hybrid_policy.py')
        self.native = self.h.NativeTools(args.source, args.host_bin, self.logs)

    def descriptors(self, path):
        return self.h.parse_avb(self.avb, path)[2]

    def footer(self, image, original, part):
        _, _, descriptors, size, _ = self.h.parse_avb(self.avb, original)
        tree = self.h.partition_descriptor(self.avb, descriptors, part)
        command = ['add_hashtree_footer', '--image', image, '--partition_name', part,
                   '--salt', tree.salt.hex(),
                   '--hash_algorithm', tree.hash_algorithm]
        if part == 'mi_ext':
            # Avoid the conservative fixed-size reservation for this tiny image.
            # Generate real metadata first, then check and restore the stock size.
            command += ['--partition_size', '0']
        else:
            command += ['--partition_size', str(size)]
        if tree.fec_num_roots:
            command += ['--fec_num_roots', str(tree.fec_num_roots)]
        else:
            command += ['--do_not_generate_fec']
        require(tree.flags in (0, 1), 'Unsupported hashtree flags')
        if tree.flags:
            command += ['--do_not_use_ab']
        for descriptor in descriptors:
            if isinstance(descriptor, self.avb.AvbPropertyDescriptor):
                # AVB parses property values as bytes; never serialize Python's b'...' representation.
                command += ['--prop', text(descriptor.key) + ':' + text(descriptor.value)]
            else:
                require(isinstance(descriptor, self.avb.AvbHashtreeDescriptor), 'Unexpected descriptor')
        self.native.run('avbtool', *command, log=part + '-footer.log')
        if part == 'mi_ext':
            require(image.stat().st_size <= size, 'mi_ext exceeds its stock partition')
            self.native.run('avbtool', 'resize_image', '--image', image,
                            '--partition_size', str(size), log='mi_ext-resize.log')
        require(image.stat().st_size == size, 'Partition size changed: ' + part)
        old_props = [d.encode() for d in descriptors if isinstance(d, self.avb.AvbPropertyDescriptor)]
        new_props = [d.encode() for d in self.descriptors(image) if isinstance(d, self.avb.AvbPropertyDescriptor)]
        require(old_props == new_props, 'Stock AVB properties changed: ' + part)

    def repack(self, part, change):
        original = self.args.stock / 'logical' / (part + '.img')
        stage = self.output / ('stage-' + part)
        with mounted(original, self.output / ('original-' + part)) as root:
            before = inventory(root)
            shutil.copytree(root, stage, symlinks=True)
            changed, removed = change(stage)
            expected = {name: record for name, record in before.items() if name not in removed}
            require(set(expected) == set(inventory(stage)), 'Unexpected staging paths: ' + part)
            config, contexts = metadata(expected, part, self.output)
            image = self.images / (part + '.img')
            self.native.run('mkfs.erofs', '-zlz4hc,level=12', '-C65536', '-T1230768000',
                            '--mount-point=' + part, '--fs-config-file=' + str(config),
                            '--file-contexts=' + str(contexts), image, stage, log=part + '-build.log')
            self.footer(image, original, part)
            with mounted(image, self.output / ('rebuilt-' + part)) as rebuilt:
                after = inventory(rebuilt)
                require(set(after) == set(expected), 'Rebuilt path set changed: ' + part)
                actual_changes = set()
                for name, old in expected.items():
                    new = after[name]
                    require({k: v for k, v in old.items() if k != 'sha256'} ==
                            {k: v for k, v in new.items() if k != 'sha256'}, 'Metadata changed: ' + name)
                    if old['sha256'] != new['sha256']:
                        actual_changes.add(name)
                        require(new['sha256'] == sha(stage / name), 'Staged content mismatch: ' + name)
                require(actual_changes == changed, 'Unexpected content delta: ' + repr(actual_changes))
            (self.output / (part + '-audit.json')).write_text(json.dumps({
                'paths': len(after), 'metadata_and_xattrs_preserved': True,
                'modified': sorted(changed), 'removed': sorted(removed)}, indent=2) + '\n')
        print('Rebuilt and audited', part, flush=True)

    def vendor(self, stage):
        patch = LEGACY.parent / 'stock/vendor-compat.patch'
        subprocess.run(['git', 'apply', '--check', str(patch)], cwd=stage, check=True)
        subprocess.run(['git', 'apply', str(patch)], cwd=stage, check=True)
        require((stage / CACHE).is_file(), 'Expected stock precompiled policy cache')
        (stage / CACHE).unlink()
        changed = set(VENDOR_CHANGES)
        if self.firmware['region'] == 'Global':
            self.policy.require_absent_helper(stage)
            for name, repair in [('vendor_sepolicy.cil', self.policy.vendor_policy),
                                 ('plat_pub_versioned.cil', self.policy.public_attributes)]:
                path = stage / 'etc/selinux' / name
                path.write_text(repair(path.read_text()))
                changed.add('etc/selinux/' + name)
        return changed, {CACHE}

    def upper_policy(self, part, repairs):
        """Edit only audited CIL files in a fresh ext4 image; preserve all labels."""
        original = self.args.lineage_images / (part + '.img')
        image = self.images / (part + '.img')
        stage = self.output / ('policy-' + part)
        stage.mkdir()
        with mounted(original, self.output / ('original-' + part), 'ext4') as root:
            self.policy.require_absent_helper(root)
            before = inventory(root)
            commands = []
            def quote(value):
                value = str(value)
                require('\n' not in value and '\r' not in value, 'Invalid debugfs path')
                return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'
            for index, (rel, repair) in enumerate(repairs.items()):
                require(rel in before and stat.S_ISREG(before[rel]['mode']), 'Missing regular policy file')
                require((root / rel).stat().st_nlink == 1, 'Hardlinked policy input requires review')
                data = stage / (str(index) + '.cil')
                data.write_text(repair((root / rel).read_text()))
                name = '/' + rel
                commands += ['rm ' + quote(name), 'write ' + quote(data) + ' ' + quote(name)]
                for field, value in [('uid', before[rel]['uid']), ('gid', before[rel]['gid']),
                                     ('mode', oct(before[rel]['mode']))]:
                    commands.append('set_inode_field ' + quote(name) + ' ' + field + ' ' + str(value))
                for attr, value in before[rel]['xattrs'].items():
                    attr_file = stage / (str(index) + '-' + attr)
                    attr_file.write_bytes(bytes.fromhex(value))
                    commands.append('ea_set -f ' + quote(attr_file) + ' ' + quote(name) + ' ' + attr)
            shutil.copyfile(original, image)
            self.native.run('avbtool', 'erase_footer', '--image', image, log=part + '-erase-footer.log')
            script = stage / 'debugfs.commands'
            script.write_text('\n'.join(commands) + '\n')
            self.native.run('debugfs_static', '-w', '-f', script, image, log=part + '-policy-edit.log')
            self.native.run('e2fsck', '-fn', image, log=part + '-filesystem.log')
            self.footer(image, original, part)
            with mounted(image, self.output / ('rebuilt-' + part), 'ext4') as rebuilt:
                after = inventory(rebuilt)
                require(set(after) == set(before), 'Upper filesystem paths changed: ' + part)
                changed = set()
                for name, record in before.items():
                    require({k: v for k, v in record.items() if k != 'sha256'} ==
                            {k: v for k, v in after[name].items() if k != 'sha256'},
                            'Upper file metadata changed: ' + name)
                    if record['sha256'] != after[name]['sha256']:
                        changed.add(name)
                require(changed == set(repairs), 'Unexpected upper content changes')
                for index, rel in enumerate(repairs):
                    require(sha(rebuilt / rel) == sha(stage / (str(index) + '.cil')),
                            'Policy readback mismatch: ' + rel)
            (self.output / (part + '-audit.json')).write_text(json.dumps({
                'paths': len(after), 'metadata_and_xattrs_preserved': True,
                'modified': sorted(changed), 'removed': []}, indent=2) + '\n')
        print('Rebuilt and audited SELinux policy in', part, flush=True)

    def mi_ext(self, stage):
        if self.firmware['region'] == 'Global':
            # Global mi_ext also contains real OEM/GMS apps, permission XML and
            # six zero-byte app masks. Keep the mount directory skeleton and
            # notices, but none of those application overlays or channel init.
            before = inventory(stage)
            prop = 'etc/build.prop'
            values = {}
            for line in (stage / prop).read_text().splitlines():
                if '=' in line and not line.lstrip().startswith('#'):
                    key, value = line.split('=', 1)
                    require(key not in values, 'Duplicate mi_ext property: ' + key)
                    values[key] = value
            require(values.get('ro.mi.os.version.incremental') == self.firmware['version'],
                    'Unexpected Global mi_ext version')
            require(values.get('ro.product.mod_device') == 'gold_global', 'Unexpected mi_ext device')
            keys = ('ro.product.mod_device', 'ro.miui.build.region', 'ro.vendor.imeisv',
                    'ro.mi.os.flavor', 'ro.mi.os.version.publish', 'ro.mi.os.version.beta',
                    'ro.mi.os.version.code', 'ro.mi.os.version.name',
                    'ro.mi.os.version.incremental', 'ro.build.version.smr_baseversion')
            require(all(key in values for key in keys), 'Missing audited mi_ext property')
            (stage / prop).write_text(''.join(key + '=' + values[key] + '\n' for key in keys))
            keep = {prop, 'etc/NOTICE.xml.gz'}
            require(keep <= set(before), 'Missing mi_ext notice/version inputs')
            removed = set()
            for name, record in before.items():
                if not stat.S_ISDIR(record['mode']) and name not in keep:
                    (stage / name).unlink()
                    removed.add(name)
            require(not list(stage.rglob('*.apk')) and not list(stage.rglob('*.rc')),
                    'OEM app/init survived mi_ext filtering')
            return {prop}, removed
        require(self.firmware['region'] == 'CN', 'Unsupported mi_ext region')
        name = 'product/app/messaging/messaging.apk'
        path = stage / name
        require(path.is_file() and not path.is_symlink() and path.stat().st_size == 0,
                'Expected the audited zero-byte Messaging placeholder')
        path.unlink()
        return set(), {name}

    def parent(self, name, template, child_parts, chains=()):
        _, header, _, size, _ = self.h.parse_avb(self.avb, template)
        require(header.flags == 0, 'Refusing AVB verification-disable flags')
        descriptors = []
        for part in child_parts:
            descriptors.extend(self.descriptors(self.images / (part + '.img')))
        for part, location in chains:
            chain = self.avb.AvbChainPartitionDescriptor()
            chain.partition_name = part
            chain.rollback_index_location = location
            chain.public_key = self.h.parse_avb(self.avb, self.images / (part + '.img'))[4]
            chain.flags = 0
            require(bool(chain.public_key), 'Missing chain key: ' + part)
            descriptors.append(chain)
        blob = self.avb.Avb()._generate_vbmeta_blob(
            algorithm_name='SHA256_RSA4096', key_path=str(self.args.key),
            public_key_metadata_path=None, descriptors=descriptors,
            chain_partitions_use_ab=None, chain_partitions_do_not_use_ab=None,
            rollback_index=header.rollback_index, flags=0,
            rollback_index_location=header.rollback_index_location, props=None,
            props_from_file=None, kernel_cmdlines=None, setup_rootfs_from_kernel=None,
            ht_desc_to_setup=None, include_descriptors_from_image=None, signing_helper=None,
            signing_helper_with_files=None, release_string=header.release_string,
            append_to_release_string=None, required_libavb_version_minor=header.required_libavb_version_minor)
        size = max(size, 65536 if name == 'vbmeta' else 4096)
        require(len(blob) <= size, 'Parent exceeds padded image size')
        image = self.images / (name + '.img')
        image.write_bytes(blob + bytes(size - len(blob)))
        require([d.encode() for d in self.descriptors(image)] == [d.encode() for d in descriptors],
                'Signed descriptor mismatch')

    def fec(self, part):
        image = self.images / (part + '.img')
        tree = self.h.partition_descriptor(self.avb, self.descriptors(image), part)
        if not tree.fec_num_roots:
            return {'roots': 0}
        prefix, encoded = self.output / (part + '-fec-input.tmp'), self.output / (part + '-fec-output.tmp')
        with image.open('rb') as source, prefix.open('xb') as target:
            remaining = tree.fec_offset
            while remaining:
                chunk = source.read(min(remaining, 8 * 1024 * 1024))
                require(chunk, 'Unexpected EOF')
                target.write(chunk)
                remaining -= len(chunk)
        self.native.run('fec', '-e', '-r', str(tree.fec_num_roots), '-j', '8', prefix, encoded,
                        log=part + '-fec.log')
        with image.open('rb') as stream:
            stream.seek(tree.fec_offset)
            stored = stream.read(tree.fec_size)
        with encoded.open('rb') as stream:
            calculated = stream.read(tree.fec_size)
        require(stored == calculated and len(stored) == tree.fec_size, 'FEC mismatch: ' + part)
        prefix.unlink()
        encoded.unlink()
        return {'roots': tree.fec_num_roots, 'bytes': tree.fec_size, 'matches': True}

    def run(self):
        stock_manifest = json.loads((self.args.stock / 'prepared.json').read_text())
        lock = self.firmware
        preparation = load('gold_prepare', REPO / 'tools/prepare-stock.py')
        preparation.verify_prepared(self.args.stock, lock, self.firmware_lock_path)
        require(stock_manifest['archive']['sha256'] == lock['archive']['sha256'], 'Unpinned stock archive')
        for name, record in stock_manifest['images'].items():
            path = self.args.stock / name
            require(path.stat().st_size == record['size'] and sha(path) == record['sha256'],
                    'Changed stock input: ' + name)
        self.output.mkdir()
        self.images.mkdir()
        self.logs.mkdir()
        lineage_inputs = {}
        for part in ('system', 'system_ext', 'product', 'vbmeta_system', 'odm'):
            source = self.args.lineage_odm if part == 'odm' and self.args.lineage_odm else self.args.lineage_images / (part + '.img')
            lineage_inputs[part] = {'size': source.stat().st_size, 'sha256': sha(source)}
            if self.firmware['region'] != 'Global' or part not in ('system', 'system_ext', 'vbmeta_system'):
                (self.images / (part + '.img')).symlink_to(source)
        for part in ('boot', 'vendor_boot', 'dtbo'):
            (self.images / (part + '.img')).symlink_to(self.args.stock / 'physical' / (part + '.img'))
        for part in ('system_dlkm', 'vendor_dlkm', 'odm_dlkm'):
            (self.images / (part + '.img')).symlink_to(self.args.stock / 'logical' / (part + '.img'))
        if self.firmware['region'] == 'Global':
            self.upper_policy('system', {
                'system/etc/selinux/plat_sepolicy.cil': self.policy.platform_policy,
                'system/etc/selinux/mapping/202404.cil': self.policy.mapping_policy})
            self.upper_policy('system_ext', {
                'etc/selinux/system_ext_sepolicy.cil': self.policy.system_ext_policy})
            first_parent = self.output / 'vbmeta_system-after-system.img'
            self.h.resign(self.avb, self.args.lineage_images / 'vbmeta_system.img',
                          self.images / 'system.img', self.args.key, first_parent, 'system')
            self.h.resign(self.avb, first_parent, self.images / 'system_ext.img',
                          self.args.key, self.images / 'vbmeta_system.img', 'system_ext')
        self.repack('vendor', self.vendor)
        self.repack('mi_ext', self.mi_ext)
        self.parent('vbmeta_vendor', self.args.stock / 'physical/vbmeta_vendor.img', ('vendor', 'odm'))
        stock_chains = [d for d in self.descriptors(self.args.stock / 'physical/vbmeta.img')
                        if isinstance(d, self.avb.AvbChainPartitionDescriptor)]
        require({d.partition_name for d in stock_chains} == {'boot', 'vbmeta_system', 'vbmeta_vendor'},
                'Unexpected stock AVB chain layout')
        self.parent('vbmeta', self.args.stock / 'physical/vbmeta.img',
                    ('dtbo', 'vendor_boot', 'mi_ext', 'system_dlkm', 'vendor_dlkm', 'odm_dlkm'),
                    [(d.partition_name, d.rollback_index_location) for d in stock_chains])
        self.native.run('avbtool', 'verify_image', '--image', self.images / 'vbmeta.img',
                        '--follow_chain_partitions', log='full-avb-chain.log')
        fec_parts = ('system', 'system_ext', 'vendor', 'mi_ext') if self.firmware['region'] == 'Global' else ('vendor', 'mi_ext')
        fec = {part: self.fec(part) for part in fec_parts}
        images = {p.name: {'size': p.stat().st_size, 'sha256': sha(p)}
                  for p in sorted(self.images.glob('*.img'))}
        report = {'stock_version': lock['version'], 'region': lock['region'],
                  'firmware_lock_sha256': sha(self.firmware_lock_path),
                  'stock_archive_sha256': lock['archive']['sha256'],
                  'stock_prepared_sha256': sha(self.args.stock / 'prepared.json'),
                  'builder_sha256': sha(Path(__file__)),
                  'vendor_compat_patch_sha256': sha(LEGACY.parent / 'stock/vendor-compat.patch'),
                  'policy_transform_sha256': sha(LEGACY / 'hybrid_policy.py'),
                  'policy_profile': 'global-strict-enforcing' if self.firmware['region'] == 'Global' else 'historical-cn',
                  'mi_ext_profile': 'global-minimal' if lock['region'] == 'Global' else 'cn-messaging-mask-fix', 'lineage_inputs': lineage_inputs, 'images': images,
                  'avb_chain_verified': True, 'top_level_avb_flags': 0, 'fec': fec,
                  'clean_source_build': False, 'device_flashed': False, 'hardware_verified': False}
        (self.output / 'assembly.json').write_text(json.dumps(report, indent=2) + '\n')
        (self.output / 'SHA256SUMS').write_text(''.join(f"{r['sha256']}  images/{n}\n" for n, r in images.items()))
        print('Image assembly and AVB/FEC checks passed; hardware validation remains pending.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('source', 'stock', 'lineage-images', 'output', 'lock'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--firmware-lock', type=Path, default=REPO / 'firmware/gold-global.json')
    parser.add_argument('--host-bin', type=Path)
    parser.add_argument('--key', type=Path)
    parser.add_argument('--lineage-odm', type=Path, help='Matching Lineage-built ODM; stock has no ODM partition')
    args = parser.parse_args()
    require(sys.platform == 'linux' and os.geteuid() == 0, 'Run as root on the Linux build host')
    for name in ('source', 'stock', 'lineage_images', 'output', 'lock', 'firmware_lock'):
        setattr(args, name, getattr(args, name).resolve())
    args.host_bin = (args.host_bin or args.source / 'out/host/linux-x86/bin').resolve()
    if args.lineage_odm:
        args.lineage_odm = args.lineage_odm.resolve()
    args.key = (args.key or args.source / 'external/avb/test/data/testkey_rsa4096.pem').resolve()
    require(not args.output.exists(), 'Output exists; use a fresh directory')
    with args.lock.open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        Builder(args).run()


if __name__ == '__main__':
    main()
