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
import os
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


def verify_ims_startup_properties(lines):
    # ImsApp returns before constructing the modem backend when ims_support is
    # missing. A bound framework service alone therefore cannot validate this.
    expected = {'persist.vendor.ims_support': '1', 'persist.vendor.volte_support': '1',
                'ro.vendor.md_auto_setup_ims': '1'}
    for name, value in expected.items():
        actual = [line.split('=', 1)[1].strip() for line in lines if line.startswith(name + '=')]
        require(actual == [value], 'Missing, duplicate or incorrect IMS startup property: ' + name)
    return expected


REMOVED_EUICC_IMAGE_PATHS = (
    'priv-app/OpenEUICC',
    'etc/permissions/android.hardware.telephony.euicc.xml',
    'etc/permissions/android.hardware.telephony.euicc.mep.xml',
    'etc/permissions/privapp_whitelist_im.angry.openeuicc.xml',
    'lib/liblpac-jni.so',
    'lib64/liblpac-jni.so',
)


def verify_euicc_removed(archive):
    """Reject stale installed files or feature declarations in an incremental ROM."""
    for name in archive.namelist():
        lower = name.lower()
        require('openeuicc' not in lower and 'liblpac-jni.so' not in lower and
                'android.hardware.telephony.euicc' not in lower,
                'Retired eSIM file still packaged: ' + name)
        if name.endswith('.xml') and ('/etc/permissions/' in name or '/etc/sysconfig/' in name):
            root = ET.fromstring(archive.read(name))
            for node in root.iter():
                feature = node.get('name', '') if node.tag == 'feature' else ''
                require(not (feature == 'android.hardware.telephony.euicc' or
                             feature.startswith('android.hardware.telephony.euicc.')),
                        'Retired eSIM feature still declared: ' + name)
                require(node.get('package') != 'im.angry.openeuicc',
                        'Retired OpenEUICC permission grant: ' + name)
    return {'supported': False, 'packaged_files_absent': True,
            'feature_and_privileged_permission_absent': True}


def verify_euicc_image_removed(image):
    # debugfs can return zero on both a missing path and an unreadable image.
    # Require its specific lookup-miss result, not just a successful process.
    for relative in REMOVED_EUICC_IMAGE_PATHS:
        result = subprocess.run(['debugfs', '-R', 'stat /' + relative, str(image)],
                                capture_output=True, text=True)
        require(result.returncode == 0 and not result.stdout.strip() and
                'File not found by ext2_lookup' in result.stderr,
                'Cannot prove retired eSIM path absent from system_ext image: ' + relative)
    return list(REMOVED_EUICC_IMAGE_PATHS)


def verify_mpeg4_runtime(archive):
    # v3avpud dlopens this ARM library; ELF NEEDED scanning cannot retain it.
    name = 'VENDOR/lib/libmp4enc_sa.ca7.so'
    require(name in archive.namelist(), 'Missing v3avpud MPEG4 runtime: ' + name)
    data = archive.read(name)
    require(data[:6] == b'\x7fELF\x01\x01' and struct.unpack_from('<H', data, 18)[0] == 40,
            'MPEG4 runtime must retain the matched ARM ABI')
    # The locked stock plugin needs the same narrow ARM symbol-version fix
    # as libvcodec_oal. Its code is unchanged; four .gnu.version bytes differ.
    source_sha = 'c12266e17f3c282c7f74f1778cfccc39f607082a30fe7c8c3449fc8a2b30d576'
    expected = 'd3ed8edc612cf7d30523b70230feeae29935b0339f4942782edf5a7bbec2f84b'
    require(sha256(data) == expected, 'MPEG4 runtime differs from reviewed Global compatibility fixup')
    return {'path': name, 'sha256': expected, 'source_sha256': source_sha,
            'stock_version': 'OS3.0.5.0.VNQMIXM',
            'cleared_symbol_versions': ['__aeabi_memclr', '__aeabi_memcpy', '__aeabi_memset',
                                        '__gnu_Unwind_Find_exidx']}


def verify_vintf_fragment(packaged, source, assembler):
    # Soong's android/defs.go processes fragments with this flag. Rebuild the
    # expected XML with the same host tool: its schema version is not the HAL
    # interface version, and source comments/paths are not runtime declarations.
    env = os.environ.copy()
    env['VINTF_IGNORE_TARGET_FCM_VERSION'] = 'true'
    expected = subprocess.check_output([str(assembler), '-i', str(source)], env=env)

    def identity(node):
        return (node.tag, tuple(sorted(node.attrib.items())),
                (node.text or '').strip(), (node.tail or '').strip(),
                tuple(identity(child) for child in node))

    require(identity(ET.fromstring(packaged)) == identity(ET.fromstring(expected)),
            'Power VINTF declaration differs from assembled mainline: ' + str(source))


def verify_images(target, host_bin, scratch_parent=None):
    """Compare actual final image contents with the package's checked members."""
    wanted = {
        'vendor': ['build.prop', 'etc/selinux/vendor_property_contexts',
                   'lib/hw/mapper.mediatek.so', 'lib/libgpud.so', 'lib/libgralloc_metadata.so',
                   'lib/libgralloctypes_mtk.so', 'lib/arm.graphics-V5-ndk.so',
                   'lib/libmp4enc_sa.ca7.so',
                   'lib64/com.xiaomi.plugin.capbokeh.so', 'lib64/libwa_dof.so',
                   'bin/hw/android.hardware.health-service.gold',
                   'etc/init/android.hardware.health-service.gold.rc', 'etc/init/gold-charger.rc',
                   'bin/batterysecret', 'etc/init/init.batterysecret.rc',
                   'etc/vintf/manifest/android.hardware.health-service.gold.xml',
                   'etc/selinux/vendor_file_contexts', 'etc/permissions/android.hardware.telephony.ims.xml',
                   'etc/wifi/wpa_supplicant.conf', 'etc/wifi/wpa_supplicant_overlay.conf',
                   'bin/hw/android.hardware.power-service.gold',
                   'etc/init/android.hardware.power-service.gold.rc',
                   'etc/vintf/manifest/android.hardware.power-service.gold.xml',
                   'lib/libmtkperf_client_vendor.so', 'lib64/libmtkperf_client_vendor.so',
                   'bin/hw/android.hardware.media.c2-mediatek',
                   'etc/init/android.hardware.media.c2-mediatek.rc',
                   'etc/vintf/manifest/manifest_media_c2_default.xml',
                   'etc/seccomp_policy/android.hardware.media.c2@1.2-mediatek-seccomp-policy',
                   'etc/seccomp_policy/android.hardware.media.c2@1.2-extended-seccomp-policy',
                   'etc/seccomp_policy/gold-codec2-crash.policy',
                   'overlay/FrameworkResOverlayGold.apk',
                   'overlay/GoldNetworkStackOverlay.apk',
                   'overlay/WifiOverlay/WifiOverlay.apk',
                   'overlay/SettingsResOverlayGold.apk'],
        'system_ext': ['priv-app/Settings/Settings.apk', 'priv-app/ImsService/ImsService.apk',
                       'app/Aperture/Aperture.apk', 'lib64/libcamera_algoup_jni.xiaomi.so',
                       'etc/public.libraries-xiaomi.txt', 'etc/permissions/gold-aperture-camera-data.xml',
                       'etc/selinux/system_ext_seapp_contexts', 'etc/selinux/system_ext_mac_permissions.xml',
                       'overlay/GoldStatusBarOverlay.apk',
                       'priv-app/SystemUI/SystemUI.apk',
                       'etc/permissions/privapp-permissions-com.mediatek.ims.xml'],
        'product': ['etc/displayconfig/display_id_4627039422300187648.xml'],
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
            if partition == 'system_ext':
                euicc_absent = verify_euicc_image_removed(image)
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
    return {'verified': True, 'matched_files': len(hashes), 'members': hashes,
            'retired_euicc_paths_absent': euicc_absent}


def verify(target, aapt2, readelf, profile):
    with zipfile.ZipFile(target) as archive, tempfile.TemporaryDirectory(prefix='gold-package-') as scratch:
        members = set(archive.namelist())
        euicc = verify_euicc_removed(archive)

        # One unresolved signer alias makes SELinuxMMAC discard every seinfo policy.
        for name in members:
            if '/etc/selinux/' not in name or not name.endswith('_mac_permissions.xml'):
                continue
            root = ET.fromstring(archive.read(name))
            for signer in root.findall('signer'):
                certs = [signer.get('signature')] + [cert.get('signature') for cert in signer.findall('cert')]
                certs = [cert for cert in certs if cert is not None]
                require(certs and all(re.fullmatch(r'(?:[0-9A-Fa-f]{2})+', cert) for cert in certs),
                        'Unexpanded or invalid SELinux signer certificate: ' + name)

        def unpack(name):
            destination = Path(scratch) / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(name))
            return destination

        def dump(name, *arguments):
            return subprocess.check_output([str(aapt2), 'dump', *arguments, str(unpack(name))], text=True)

        # The bridge stays byte-exact; these hashes do not establish runtime JNI ABI compatibility.
        portrait = {
            'SYSTEM_EXT/lib64/libcamera_algoup_jni.xiaomi.so': 'd0d4ee4a31ced39df1661f0e3950c13245b715c30ed7c30e323095991c24a438',
            'VENDOR/lib64/com.xiaomi.plugin.capbokeh.so': '79438946cd668d2f9de29a0ff0966bf8d8939a5611afb6720d517bccbbbc2ad2',
            'VENDOR/lib64/libwa_dof.so': 'bbcba825cb102e61fc6cb8959e10efa3663fe249941b62e9e0c7e6f9bd822fe2',
        }
        for name, expected_sha in portrait.items():
            require(sha256(archive.read(name)) == expected_sha, 'Unexpected original portrait library: ' + name)
        require(not any(name.startswith('PRODUCT/app/Aperture/') for name in members),
                'Old product Aperture remains after system_ext migration')
        require(archive.read('SYSTEM_EXT/etc/public.libraries-xiaomi.txt').decode().splitlines() ==
                ['libcamera_algoup_jni.xiaomi.so'], 'Incorrect portrait public library declaration')
        aperture_manifest = dump('SYSTEM_EXT/app/Aperture/Aperture.apk', 'xmltree', '--file', 'AndroidManifest.xml')
        require('libcamera_algoup_jni.xiaomi.so' in aperture_manifest and
                'org.lineageos.aperture.permission.CAMERA_CALIBRATION' in aperture_manifest,
                'Missing Aperture native library or calibration permission declaration')

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
        ims_startup = verify_ims_startup_properties(vendor_properties)
        aod_support = [line.split('=', 1)[1].strip() for line in vendor_properties
                       if line.startswith('ro.vendor.mtk_aod_support=')]
        require(aod_support == ['1'], 'MTK composer must accept native DOZE modes')
        camera_clients = [line.split('=', 1)[1].strip() for line in vendor_properties
                          if line.startswith('persist.vendor.camera.privapp.list=')]
        require(camera_clients == ['org.lineageos.aperture'], 'Aperture must retain OEM private stream sizes')
        property_contexts = archive.read('VENDOR/etc/selinux/vendor_property_contexts').decode()
        require(re.search(r'^persist\.vendor\.camera\.privapp\.list\s+'
                          r'u:object_r:vendor_mtk_camera_prop:s0\s+exact\s+string\s*$',
                          property_contexts, re.M), 'Missing exact camera private-stream property label')
        for name, context in [('persist.vendor.ims_support', 'vendor_mtk_ims_prop'),
                              ('ro.vendor.md_auto_setup_ims', 'vendor_mtk_ims_prop'),
                              ('persist.vendor.volte_support', 'vendor_mtk_volte_support_prop')]:
            require(re.search(r'^' + re.escape(name) + r'\s+u:object_r:' + context + r':s0(?:\s|$)',
                              property_contexts, re.M), 'Missing IMS property label: ' + name)
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

        for packaged, source in [
            ('VENDOR/etc/init/init.batterysecret.rc', 'init/init.batterysecret.rc'),
            ('PRODUCT/etc/displayconfig/display_id_4627039422300187648.xml',
             'configs/display/display_id_4627039422300187648.xml'),
        ]:
            require(archive.read(packaged) == (profile.parents[4] / source).read_bytes(),
                    'Packaged stock device configuration differs from mainline: ' + packaged)

        power_rc = 'VENDOR/etc/init/android.hardware.power-service.gold.rc'
        power_xml = 'VENDOR/etc/vintf/manifest/android.hardware.power-service.gold.xml'
        power_root = profile.parents[4] / 'power'
        require(archive.read(power_rc) == (power_root / Path(power_rc).name).read_bytes(),
                'Power service definition differs from mainline: ' + power_rc)
        verify_vintf_fragment(archive.read(power_xml), power_root / Path(power_xml).name,
                              Path(aapt2).with_name('assemble_vintf'))
        power_services = []
        for name in members:
            if not name.startswith(('VENDOR/', 'SYSTEM/', 'SYSTEM_EXT/')):
                continue
            if name.endswith('.rc'):
                for line in archive.read(name).decode(errors='replace').splitlines():
                    if re.match(r'^service\s+\S+\s+\S*(?:android\.hardware\.power-service|mtkpower@)', line):
                        power_services.append((name, line))
        require(len(power_services) == 1 and power_services[0][0] == power_rc,
                'Multiple or stale Power resource owners in packaged init')
        require('VENDOR/etc/powerhint.json' not in members,
                'Obsolete independent libperfmgr policy still packaged')
        clients = {}
        for directory, elf_class in [('lib', 1), ('lib64', 2)]:
            name = 'VENDOR/' + directory + '/libmtkperf_client_vendor.so'
            data = archive.read(name)
            require(data[:5] == b'\x7fELF' + bytes([elf_class]), 'Wrong native perf client ABI: ' + name)
            output = subprocess.check_output([str(readelf), '-d', '-Ws', str(unpack(name))], text=True)
            require('Shared library: [vendor.mediatek.hardware.mtkpower@1.2.so]' in output,
                    'Perf client does not forward to the synchronous 1.2 service: ' + name)
            for symbol in ('perf_lock_acq', 'perf_lock_rel', 'perf_cus_lock_hint'):
                require(re.search(r'\bGLOBAL\s+DEFAULT\s+\d+\s+' + symbol + r'\b', output),
                        'Missing public C perf ABI: ' + symbol)
            clients[name] = sha256(data)

        codec_name = 'VENDOR/bin/hw/android.hardware.media.c2-mediatek'
        codec = archive.read(codec_name)
        require(codec[:6] == b'\x7fELF\x02\x01' and struct.unpack_from('<H', codec, 18)[0] == 183,
                'Codec2 frontend must use the matched native AArch64 ABI')
        require(b'Gold Codec2 bridge: platform ComponentStore size=' in codec,
                'Stale stock Codec2 entrypoint with incompatible platform object allocation')
        codec_dynamic = subprocess.check_output([str(readelf), '-d', str(unpack(codec_name))], text=True)
        for library in ('libcodec2_aidl.so', 'libcodec2_mtk_c2store.so'):
            require('Shared library: [' + library + ']' in codec_dynamic,
                    'Missing actual Codec2 frontend dependency: ' + library)
        codec_services = []
        codec_hals = []
        for name in members:
            if name.startswith('VENDOR/') and name.endswith('.rc'):
                codec_services.extend(line for line in archive.read(name).decode(errors='replace').splitlines()
                                      if re.match(r'^service\s+\S+\s+\S*android\.hardware\.media\.c2-', line))
            if name.startswith(('VENDOR/etc/vintf/', 'ODM/etc/vintf/')) and name.endswith('.xml'):
                for hal in ET.fromstring(archive.read(name)).findall('hal'):
                    if hal.findtext('name') == 'android.hardware.media.c2':
                        codec_hals.append((hal.get('format'), hal.findtext('version'), hal.findtext('fqname')))
        require(codec_services == ['service android-hardware-media-c2-hal /vendor/bin/hw/android.hardware.media.c2-mediatek'],
                'Duplicate or stale vendor Codec2 init service')
        require(codec_hals == [('aidl', '1', 'IComponentStore/default')],
                'Vendor Codec2 must retain its single AIDL instance')
        codec_policy = 'VENDOR/etc/seccomp_policy/gold-codec2-crash.policy'
        require(archive.read(codec_policy) == (profile.parents[4] / 'codec2/gold-codec2-crash.policy').read_bytes(),
                'Codec2 crash-report syscall addition differs from mainline')

        mpeg4_runtime = verify_mpeg4_runtime(archive)

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
        require('() true' in resource(framework, 'bool/config_supportDoubleTapWake')[1],
                'Double-tap wake not exposed by the Gold framework overlay')
        require('com.android.systemui/com.android.systemui.doze.DozeService' in
                resource(framework, 'string/config_dozeComponent')[1],
                'Gold ambient display service component is missing')
        doze_overlay = dump('SYSTEM_EXT/overlay/GoldStatusBarOverlay.apk', 'resources')
        for name in ('doze_display_state_supported', 'doze_suspend_display_state_supported'):
            require('() true' in resource(doze_overlay, 'bool/' + name)[1],
                    'Gold AOD low-power display state is disabled: ' + name)
        require(b'double-tap wake request failed' in archive.read(
                'VENDOR/bin/hw/android.hardware.power-service.gold'), 'Missing touch wake Power HAL path')
        require(any(len(parts := line.split()) >= 2 and parts[0] == '/dev/xiaomi-touch'
                    and parts[-1] == 'u:object_r:vendor_gold_touch_device:s0' for line in contexts),
                'Missing narrowly typed touch control device')
        attestation = {'ro.product.name_for_attestation': 'vnd_gold',
                       'ro.product.model_for_attestation': 'gold'}
        for name, value in attestation.items():
            require([x.split('=', 1)[1] for x in vendor_properties if x.startswith(name + '=')] == [value],
                    'Original vendor attestation identity missing or duplicated: ' + name)
        wifi_overlay = dump('VENDOR/overlay/WifiOverlay/WifiOverlay.apk', 'resources')
        require('() true' in resource(wifi_overlay, 'bool/config_wifi_softap_sae_supported')[1],
                'WPA3-SAE SoftAP capability absent from Gold Wi-Fi overlay')
        network_name = 'VENDOR/overlay/GoldNetworkStackOverlay.apk'
        network = dump(network_name, 'resources')
        urls = ['https://www.google.com/generate_204',
                'https://connectivitycheck.gstatic.com/generate_204']
        actual_urls = re.findall(r'"(https?://[^"\s]+)"',
                                resource(network, 'array/config_captive_portal_https_urls')[1])
        require(actual_urls == urls, 'Unexpected captive-portal HTTPS probe configuration')
        network_manifest = dump(network_name, 'xmltree', '--file', 'AndroidManifest.xml')
        require('"com.android.networkstack"' in network_manifest and
                '"NetworkStackConfig"' in network_manifest, 'Incorrect NetworkStack overlay target')
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
                'portrait': {'original_libraries': portrait, 'aperture_partition': 'system_ext',
                             'private_stream_client': camera_clients[0],
                             'runtime_verified': False},
                'health': health, 'health_vintf': declarations, 'charger_definitions': chargers,
                'ims': {'feature_permission': ims_feature, 'feature_declared': True,
                        'input_sha256': ims_input['sha256'], 'packaged_sha256': sha256(archive.read(ims_name)),
                        'dependency_payload_matches': True, 'payload_entries': len(payload),
                        'platform_signing_selected': True, 'privileged_permissions_match': True,
                        'startup_properties': ims_startup, 'startup_property_labels_verified': True,
                        'registration_verified': False},
                'settings': {'sha256': sha256(archive.read(settings_name)), 'maintainer_page_verified': True,
                             'languages': ['default', 'zh-rCN', 'zh-rTW'], 'peak_refresh_overlay': True},
                'power_profile': {'named_entries': len(actual), 'matches_source': True,
                                  'source_sha256': sha256(profile.read_bytes()), 'big_core_key_corrected': True},
                'sustained_performance_advertised': False,
                'zygote': 'zygote64', 'standard_module_links_verified': True,
                'wifi_pmf_default': 1, 'wifi_pmf_upgrade_overlay': True,
                'wifi_softap_sae_overlay': True, 'wifi_softap_runtime_verified': False,
                'recovery_debug_adb_config_verified': True,
                'power': {'single_resource_owner': True, 'native_clients': clients,
                          'runtime_verified': False, 'performance_benefit_verified': False},
                'codec2': {'source_frontend_marker_verified': True, 'sha256': sha256(codec),
                           'mpeg4_runtime': mpeg4_runtime,
                           'single_vendor_service': True, 'matched_vendor_store_retained': True,
                           'runtime_verified': False},
                'touch_wake': {'framework_switch': True, 'power_path': True,
                               'typed_control_device': True, 'runtime_verified': False},
                'aod': {'doze_component': True, 'display_doze_supported': True,
                        'display_doze_suspend_supported': True, 'mtk_composer_doze_enabled': True,
                        'runtime_verified': False},
                'attestation_identity': {'properties': attestation, 'tee_acceptance_verified': False},
                'network_probes': {'https_urls': urls, 'runtime_validated': False},
                'euicc': euicc,
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
