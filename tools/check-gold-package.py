#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Inspect Gold-specific target-files contents after Android's validators pass.

Uses the build's native aapt2 and an ELF reader. This checks packaged files and
compiled resources, not installation, overlay activation or physical hardware.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def verify_images(target, host_bin, scratch_parent=None):
    """Compare actual final image contents with the package's checked members."""
    wanted = {
        'vendor': ['lib/hw/mapper.mediatek.so', 'lib/libgpud.so', 'lib/libgralloc_metadata.so',
                   'lib/libgralloctypes_mtk.so', 'lib/arm.graphics-V5-ndk.so',
                   'bin/hw/android.hardware.health-service.gold',
                   'etc/init/android.hardware.health-service.gold.rc', 'etc/init/gold-charger.rc',
                   'etc/vintf/manifest/android.hardware.health-service.gold.xml',
                   'etc/selinux/vendor_file_contexts', 'etc/permissions/android.hardware.telephony.ims.xml',
                   'etc/wifi/wpa_supplicant.conf', 'etc/wifi/wpa_supplicant_overlay.conf',
                   'overlay/FrameworkResOverlayGold.apk',
                   'overlay/SettingsResOverlayGold.apk'],
        'system_ext': ['priv-app/Settings/Settings.apk', 'priv-app/ImsService/ImsService.apk',
                       'etc/permissions/privapp-permissions-com.mediatek.ims.xml'],
    }
    recovery_prefix = 'VENDOR_BOOT/RAMDISK_FRAGMENTS/recovery/RAMDISK/'
    recovery_wanted = ['system/bin/hw/android.hardware.health-service.gold-recovery',
                       'system/etc/init/android.hardware.health-service.gold-recovery.rc',
                       'system/etc/vintf/manifest/android.hardware.health-service.gold.xml',
                       'system/etc/init/init.recovery.mt6833.rc']
    hashes = {}
    with zipfile.ZipFile(target) as archive, tempfile.TemporaryDirectory(
            prefix='gold-image-check-', dir=scratch_parent) as temporary:
        scratch = Path(temporary)

        def run(command):
            result = subprocess.run([str(arg) for arg in command], capture_output=True)
            require(result.returncode == 0, 'Image reader failed: ' + str(command[0]) + ': ' +
                    result.stderr.decode(errors='replace')[-2000:])
            return result.stdout

        def compare(name, data):
            require(name not in hashes, 'Duplicate actual image member: ' + name)
            actual = sha256(data)
            require(actual == sha256(archive.read(name)), 'Actual image/member mismatch: ' + name)
            hashes[name] = actual

        for partition in (*wanted, 'vendor_boot'):
            image = scratch / (partition + '.img')
            with archive.open('IMAGES/' + image.name) as src, image.open('wb') as dst:
                shutil.copyfileobj(src, dst, 8 * 1024 * 1024)
            if partition == 'vendor_boot':
                continue
            extracted = scratch / partition
            if partition == 'vendor':
                run([host_bin / 'fsck.erofs', '--extract=' + str(extracted), '--no-preserve', image])
            else:
                for relative in wanted[partition]:
                    output = extracted / relative
                    output.parent.mkdir(parents=True, exist_ok=True)
                    run(['debugfs', '-R', 'dump /' + relative + ' ' + str(output), image])
                    require(output.is_file(), 'debugfs did not extract ' + relative)
            for relative in wanted[partition]:
                compare(partition.upper() + '/' + relative, (extracted / relative).read_bytes())
            image.unlink()

        boot = scratch / 'boot'
        run([host_bin / 'unpack_bootimg', '--boot_img', scratch / 'vendor_boot.img', '--out', boot])
        for ramdisk in boot.glob('vendor_ramdisk*'):
            if not ramdisk.is_file():
                continue
            raw = ramdisk.read_bytes()
            if raw[:6] not in (b'070701', b'070702'):
                raw = run([host_bin / 'lz4', '-d', '-c', ramdisk])
            offset = 0
            while offset + 110 <= len(raw):
                header = raw[offset:offset + 110]
                require(header[:6] in (b'070701', b'070702'), 'Unsupported Recovery cpio header')
                fields = [int(header[6 + i * 8:14 + i * 8], 16) for i in range(13)]
                size, namesz = fields[6], fields[11]
                start = offset + 110
                require(namesz > 0 and start + namesz <= len(raw), 'Truncated Recovery cpio name')
                name = raw[start:start + namesz - 1].decode()
                start = (start + namesz + 3) & ~3
                require(start + size <= len(raw), 'Truncated Recovery cpio entry')
                if name == 'TRAILER!!!':
                    break
                if name.startswith('./'):
                    name = name[2:]
                if name in recovery_wanted:
                    compare(recovery_prefix + name, raw[start:start + size])
                offset = (start + size + 3) & ~3
        require(all(recovery_prefix + name in hashes for name in recovery_wanted),
                'Missing actual Recovery image members')
    return {'verified': True, 'matched_files': len(hashes), 'members': hashes}


def verify(target, aapt2, readelf, profile):
    with zipfile.ZipFile(target) as archive, tempfile.TemporaryDirectory(prefix='gold-package-') as scratch:
        members = set(archive.namelist())

        def unpack(name):
            destination = Path(scratch) / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
            return destination

        def dump(name, *arguments):
            return subprocess.check_output([str(aapt2), 'dump', *arguments, str(unpack(name))], text=True)

        graphics = {}
        for relative in ('hw/mapper.mediatek.so', 'libgpud.so', 'libgralloc_metadata.so',
                         'libgralloctypes_mtk.so', 'arm.graphics-V5-ndk.so'):
            name = 'VENDOR/lib/' + relative
            data = archive.read(name)
            require(data[:6] == b'\x7fELF\x01\x01' and struct.unpack_from('<H', data, 18)[0] == 40,
                    'Expected ARM ELF32: ' + name)
            dynamic = subprocess.check_output([str(readelf), '-d', str(unpack(name))], text=True)
            needed = re.findall(r'\(NEEDED\).*\[([^]]+)\]', dynamic)
            if relative in ('hw/mapper.mediatek.so', 'libgpud.so'):
                require('android.hardware.graphics.common-V7-ndk.so' in needed,
                        'Missing graphics-common V7 fixup: ' + name)
                require('android.hardware.graphics.common-V5-ndk.so' not in needed,
                        'Stale graphics-common V5 dependency: ' + name)
            graphics[name] = {'sha256': sha256(data), 'needed': needed}
        require('VENDOR/lib/android.hardware.graphics.common-V7-ndk.so' in members,
                'Missing packaged ARM graphics-common V7 dependency')

        recovery = 'VENDOR_BOOT/RAMDISK_FRAGMENTS/recovery/RAMDISK/'
        health = {}
        for prefix, suffix in (('VENDOR/', ''), (recovery + 'system/', '-recovery')):
            binary = prefix + 'bin/hw/android.hardware.health-service.gold' + suffix
            data = archive.read(binary)
            require(data[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', data, 18)[0] == 183,
                    'Expected AArch64 Health service: ' + binary)
            rc_name = prefix + 'etc/init/android.hardware.health-service.gold' + suffix + '.rc'
            rc = archive.read(rc_name).decode()
            runtime_binary = ('/system/' if suffix else '/vendor/') + binary.split(prefix, 1)[1]
            require('service vendor.health-gold ' + runtime_binary in rc, 'Wrong Health init service')
            if suffix:
                require('seclabel u:r:hal_health_default:s0' in rc, 'Missing Recovery Health domain')
            health[binary] = {'sha256': sha256(data), 'init': rc_name}

        contexts = archive.read('VENDOR/etc/selinux/vendor_file_contexts').decode().splitlines()
        require(any(len(parts := line.split()) >= 2 and parts[-1] == 'u:object_r:hal_health_default_exec:s0'
                    and re.fullmatch(parts[0], '/vendor/bin/hw/android.hardware.health-service.gold')
                    for line in contexts if line and not line.startswith('#')), 'Missing Health executable label')
        require(not any('android.hardware.health-service.mediatek' in name and
                        ('/bin/' in name or name.endswith(('.rc', '.xml'))) for name in members),
                'Old MediaTek Health service still packaged')

        declarations = {'android': [], 'recovery': []}
        chargers = {'android': [], 'recovery': []}
        for name in sorted(members):
            environment = 'recovery' if name.startswith(recovery) else 'android'
            if '/etc/vintf/' in name and name.endswith('.xml'):
                manifest = ET.fromstring(archive.read(name))
                # Compatibility matrices describe requirements, not services.
                for hal in manifest.findall('hal') if manifest.tag == 'manifest' else ():
                    if hal.findtext('name') == 'android.hardware.health':
                        require(hal.findtext('version') == '4', 'Expected Health AIDL V4')
                        declarations[environment].append(name)
            if name.endswith('.rc'):
                for line in archive.read(name).decode().splitlines():
                    if re.match(r'^service\s+(?:vendor\.)?charger\s', line):
                        chargers[environment].append({'file': name, 'service': line})
        require(all(len(items) == 1 for items in declarations.values()), 'Duplicate or missing Health VINTF declaration')
        require(chargers['android'] == [{'file': 'VENDOR/etc/init/gold-charger.rc',
                'service': 'service vendor.charger /vendor/bin/hw/android.hardware.health-service.gold --charger'}],
                'Expected exactly one normal-system charger definition')

        ims_feature = 'VENDOR/etc/permissions/android.hardware.telephony.ims.xml'
        require(ims_feature in members,
                'Missing IMS feature: the framework would skip ImsResolver and ImsPhone initialization')
        permissions = ET.fromstring(archive.read(ims_feature))
        require(permissions.tag == 'permissions' and any(
            feature.get('name') == 'android.hardware.telephony.ims'
            for feature in permissions.findall('feature')),
            'Missing IMS feature: the framework would skip ImsResolver and ImsPhone initialization')

        ims_root = Path(__file__).resolve().parents[1] / 'vendor/xiaomi/gold/ims'
        ims_input = json.loads((ims_root / 'input.json').read_text())
        original = (ims_root / ims_input['file']).read_bytes()
        require(sha256(original) == ims_input['sha256'] and len(original) == ims_input['size'],
                'The mainline IMS prebuilt differs from its explicit input lock')
        ims_name = 'SYSTEM_EXT/priv-app/ImsService/ImsService.apk'
        with zipfile.ZipFile(io.BytesIO(original)) as source_apk, \
                zipfile.ZipFile(io.BytesIO(archive.read(ims_name))) as signed_apk:
            payload = [name for name in source_apk.namelist() if not name.startswith('META-INF/')]
            require(len(payload) == len(set(payload)), 'Duplicate IMS payload entries')
            require(set(payload) == {name for name in signed_apk.namelist() if not name.startswith('META-INF/')},
                    'Signed IMS package has a different dependency payload')
            require(all(source_apk.read(name) == signed_apk.read(name) for name in payload),
                    'Signed IMS dependency payload differs from the mainline prebuilt')
        apkcerts = archive.read('META/apkcerts.txt').decode()
        ims_cert = [line for line in apkcerts.splitlines() if 'name="ImsService.apk"' in line]
        require(len(ims_cert) == 1 and '/platform.x509.pem"' in ims_cert[0],
                'ImsService must use the product platform certificate')
        ims_permissions_name = 'SYSTEM_EXT/etc/permissions/privapp-permissions-com.mediatek.ims.xml'
        require(archive.read(ims_permissions_name) == (ims_root / Path(ims_permissions_name).name).read_bytes(),
                'Packaged IMS privileged permission allowlist differs from mainline')

        vendor_properties = archive.read('VENDOR/build.prop').decode().splitlines()
        zygote = [line.split('=', 1)[1].strip() for line in vendor_properties if line.startswith('ro.zygote=')]
        require(zygote == ['zygote64'], 'Gold supports 64-bit applications only')
        require('service zygote /system/bin/app_process64 ' in archive.read(
            'SYSTEM/etc/init/hw/init.zygote64.rc').decode(), 'Missing selected zygote RC')
        for name, destination in [('SYSTEM/lib/modules', b'/system_dlkm/lib/modules'),
                                  ('VENDOR/lib/modules', b'/vendor_dlkm/lib/modules')]:
            require((archive.getinfo(name).external_attr >> 16) & 0o170000 == 0o120000
                    and archive.read(name) == destination, 'Wrong standard kernel module link: ' + name)
        for wifi_name in ('VENDOR/etc/wifi/wpa_supplicant.conf',
                          'VENDOR/etc/wifi/wpa_supplicant_overlay.conf'):
            wifi_pmf = [line.strip() for line in archive.read(wifi_name).decode().splitlines()
                        if line.strip().startswith('pmf=')]
            require(wifi_pmf == ['pmf=1'],
                    'Wi-Fi PMF default must apply to fresh installs and upgrades: ' + wifi_name)

        recovery_rc_name = ('VENDOR_BOOT/RAMDISK_FRAGMENTS/recovery/RAMDISK/'
                            'system/etc/init/init.recovery.mt6833.rc')
        recovery_rc = archive.read(recovery_rc_name)
        recovery_source = (profile.parents[4] / 'init/init.recovery.mt6833.rc').read_bytes()
        require(recovery_rc == recovery_source, 'Recovery USB configuration differs from mainline')
        require(b'on init && property:ro.build.type=userdebug\n'
                b'    setprop ro.adb.secure.recovery 0\n' in recovery_rc,
                'Debug Recovery must enable its own ADB access before userdata is available')

        settings_name = 'SYSTEM_EXT/priv-app/Settings/Settings.apk'
        settings = dump(settings_name, 'resources')

        def resource(text, name):
            match = re.search(r'^\s*resource (0x[0-9a-f]+) ' + re.escape(name) + r'\n(.*?)(?=^\s*resource |^  type |\Z)',
                              text, re.M | re.S)
            require(match is not None, 'Missing compiled resource: ' + name)
            return match.group(1), match.group(2)

        name_id, name_values = resource(settings, 'string/device_maintainer_name')
        title_id, title_values = resource(settings, 'string/device_maintainer_title')
        require('() "Betterr"' in name_values, 'Incorrect maintainer value')
        for value in ('() "Device maintainer"', '(zh-rCN) "设备维护者"', '(zh-rTW) "裝置維護者"'):
            require(value in title_values, 'Missing maintainer translation: ' + value)
        page = dump(settings_name, 'xmltree', '--file', 'res/xml/my_device_info.xml')
        require('"device_maintainer"' in page and '@' + name_id in page and '@' + title_id in page,
                'Maintainer resources not referenced by About-phone page')
        settings_overlay = dump('VENDOR/overlay/SettingsResOverlayGold.apk', 'resources')
        require('() true' in resource(settings_overlay, 'bool/config_show_peak_refresh_rate_switch')[1],
                'Peak-refresh selector not enabled in Gold overlay')

        framework_name = 'VENDOR/overlay/FrameworkResOverlayGold.apk'
        framework = dump(framework_name, 'resources')
        require('() false' in resource(framework, 'bool/config_sustainedPerformanceModeSupported')[1],
                'Untuned sustained-performance capability still advertised')
        compiled_profile = dump(framework_name, 'xmltree', '--file', 'res/xml/power_profile.xml')
        actual = {}
        for block in re.split(r'^    E: (?:item|array) .*\n', compiled_profile, flags=re.M)[1:]:
            key = re.search(r'A: name="([^"]+)"', block)
            require(key is not None, 'Malformed compiled power profile')
            require(key[1] not in actual, 'Duplicate compiled power-profile key')
            actual[key[1]] = re.findall(r"T: '([^']*)'", block)
        expected = {node.attrib['name']: [v.text.strip() for v in node] if node.tag == 'array'
                    else [node.text.strip()] for node in ET.parse(profile).getroot()}
        require(actual == expected, 'Compiled power profile differs from checked-in profile')
        require('cpu.core_power.cluster1' in actual and 'u.core_power.cluster1' not in actual,
                'Incorrect big-core power key')
        return {'gold_package_contents_verified': True, 'graphics_32bit': graphics,
                'health': health, 'health_vintf': declarations, 'charger_definitions': chargers,
                'ims': {'feature_permission': ims_feature, 'feature_declared': True,
                        'input_sha256': ims_input['sha256'], 'packaged_sha256': sha256(archive.read(ims_name)),
                        'dependency_payload_matches': True, 'payload_entries': len(payload),
                        'platform_signing_selected': True, 'privileged_permissions_match': True,
                        'registration_verified': False},
                'settings': {'sha256': sha256(archive.read(settings_name)), 'maintainer_page_verified': True,
                             'languages': ['default', 'zh-rCN', 'zh-rTW'], 'peak_refresh_overlay': True},
                'power_profile': {'named_entries': len(actual), 'matches_source': True,
                                  'source_sha256': sha256(profile.read_bytes()), 'big_core_key_corrected': True},
                'sustained_performance_advertised': False,
                'zygote': 'zygote64', 'standard_module_links_verified': True,
                'wifi_pmf_default': 1, 'wifi_pmf_upgrade_overlay': True,
                'recovery_debug_adb_config_verified': True,
                'wifi_association_verified': False,
                'limitations': ['Checks target-files members; Android validators check image/AVB contracts.',
                                'Does not prove runtime overlay activation or hardware behavior.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-files', required=True, type=Path)
    parser.add_argument('--aapt2', required=True, type=Path)
    parser.add_argument('--readelf', default='readelf')
    parser.add_argument('--image-tools', type=Path,
                        help='Also inspect final images using this build host-bin directory and debugfs')
    parser.add_argument('--scratch-parent', type=Path,
                        help='Temporary image extraction directory; removed after checking')
    args = parser.parse_args()
    profile = Path(__file__).resolve().parents[1] / 'device/xiaomi/gold/overlay/FrameworksResOverlayGold/res/xml/power_profile.xml'
    result = verify(args.target_files, args.aapt2, args.readelf, profile)
    if args.image_tools:
        result['actual_images'] = verify_images(args.target_files, args.image_tools, args.scratch_parent)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, ET.ParseError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
