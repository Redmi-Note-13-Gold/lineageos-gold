#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only research-host path guard and persistent mount-unit renderer.

This does not mount, remount, create directories, or repair a mismatched host.
The generic build-source.py remains available for other hosts.
"""
import argparse
import json
from pathlib import Path
import subprocess

CONFIG = Path(__file__).with_name('research-layout.json')


def validate_mounts(layout, mounts):
    by_target = {item['target']: item for item in mounts}
    data = by_target.get(layout['build_mount'])
    if not data or data.get('uuid') != layout['build_mount_uuid'] or data.get('fstype') != 'ext4':
        raise ValueError('Expected the recorded build data disk mounted at ' + layout['build_mount'])
    overlay = by_target.get(layout['source'])
    if not overlay or overlay.get('fstype') != 'overlay':
        raise ValueError('Source must be an exact OverlayFS mount, not its parent filesystem')
    for mount in [data, overlay]:
        if 'rw' not in mount.get('options', '').split(','):
            raise ValueError('Expected a writable mount: ' + mount['target'])
    options = dict(item.split('=', 1) for item in overlay['options'].split(',') if '=' in item)
    for option, key in [('lowerdir', 'lower'), ('upperdir', 'upper'), ('workdir', 'work')]:
        if options.get(option) != layout[key]:
            raise ValueError('Unexpected OverlayFS ' + option + '; inspect before building')
    return {'data': data, 'source': overlay}


def check_paths(layout, source_tree):
    if source_tree.resolve() != Path(layout['source']):
        raise ValueError('The research entry only uses its recorded source; use build-source.py for another host')
    for key in ['workspace', 'project', 'source', 'lower', 'upper', 'work', 'output', 'cache', 'releases']:
        path = Path(layout[key])
        if not path.is_dir() or path.is_symlink():
            raise ValueError('Expected a real directory for ' + key + ': ' + str(path))
    disk = Path(layout['build_mount']).stat().st_dev
    for key in ['lower', 'upper', 'work']:
        if Path(layout[key]).stat().st_dev != disk:
            raise ValueError(key + ' is not on the recorded build disk')
    output = Path(layout['output']).resolve()
    if not output.is_relative_to(source_tree.resolve()):
        raise ValueError('Managed output must stay inside the source tree')
    if output.stat().st_dev != source_tree.stat().st_dev:
        raise ValueError('Managed output must stay on the source overlay')
    for alias, target in layout['aliases'].items():
        link = Path(alias)
        if not link.is_symlink() or not link.exists() or link.resolve() != Path(target).resolve():
            raise ValueError('Missing or mismatched navigation link: ' + alias)
    if not (source_tree / '.repo/repo/repo').is_file():
        raise ValueError('Missing Android Repo launcher')
    if not Path(layout['swap']).is_file() or Path(layout['swap']).is_symlink():
        raise ValueError('Missing physical swap file')


def mount_unit(layout):
    # This host config deliberately uses only simple absolute paths in systemd fields.
    for key in ['build_mount', 'source', 'lower', 'upper', 'work']:
        value = layout[key]
        if not value.startswith('/') or any(c.isspace() or c in ',:%\\' for c in value):
            raise ValueError('Unsupported mount-unit path: ' + value)
    return f"""# Generated from tools/host/research-layout.json; install a regular copy in /etc/systemd/system.
[Unit]
Description=Gold Android source OverlayFS
RequiresMountsFor={layout['lower']} {layout['upper']} {layout['work']}
ConditionPathIsDirectory={layout['lower']}/.repo
ConditionPathIsDirectory={layout['upper']}
ConditionPathIsDirectory={layout['work']}

[Mount]
What=overlay
Where={layout['source']}
Type=overlay
Options=rw,relatime,lowerdir={layout['lower']},upperdir={layout['upper']},workdir={layout['work']},nouserxattr
TimeoutSec=120

[Install]
WantedBy=multi-user.target
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-tree', type=Path)
    parser.add_argument('--print-mount-unit', action='store_true')
    args = parser.parse_args()
    layout = json.loads(CONFIG.read_text())
    if args.print_mount_unit:
        print(mount_unit(layout), end='')
        return
    source = args.source_tree or Path(layout['source'])
    if Path(__file__).resolve().parents[2] != Path(layout['project']):
        raise ValueError('Run this host guard from the recorded mainline project')
    mounts = json.loads(subprocess.check_output(
        ['findmnt', '--json', '--list', '--output', 'TARGET,SOURCE,FSTYPE,OPTIONS,UUID'], text=True))
    checked = validate_mounts(layout, mounts['filesystems'])
    check_paths(layout, source)
    print(json.dumps({'status': 'pass', 'source_tree': str(source.resolve()),
                      'output': layout['output'], 'mounts': checked,
                      'aliases_verified': list(layout['aliases']),
                      'mutated': False}, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error))
