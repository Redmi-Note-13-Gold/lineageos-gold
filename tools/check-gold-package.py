#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Inspect Gold-specific target-files contents after Android's validators pass.

Uses the build's native aapt2 and an ELF reader. This checks packaged files and
compiled resources, not installation, overlay activation or physical hardware.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
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
                        'registration_verified': False},
                'settings': {'sha256': sha256(archive.read(settings_name)), 'maintainer_page_verified': True,
                             'languages': ['default', 'zh-rCN', 'zh-rTW'], 'peak_refresh_overlay': True},
                'power_profile': {'named_entries': len(actual), 'matches_source': True,
                                  'source_sha256': sha256(profile.read_bytes()), 'big_core_key_corrected': True},
                'sustained_performance_advertised': False,
                'limitations': ['Checks target-files members; Android validators check image/AVB contracts.',
                                'Does not prove runtime overlay activation or hardware behavior.']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-files', required=True, type=Path)
    parser.add_argument('--aapt2', required=True, type=Path)
    parser.add_argument('--readelf', default='readelf')
    args = parser.parse_args()
    profile = Path(__file__).resolve().parents[1] / 'device/xiaomi/gold/overlay/FrameworksResOverlayGold/res/xml/power_profile.xml'
    print(json.dumps(verify(args.target_files, args.aapt2, args.readelf, profile), indent=2, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, ET.ParseError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
