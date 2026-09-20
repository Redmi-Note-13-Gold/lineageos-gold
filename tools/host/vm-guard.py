#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Temporarily enable bounded reclaim for one research build, then restore it.

The build runs in its existing protected systemd cgroup. This guard is a small
separate service so an OOM in the build cannot prevent restoration. It never
changes swap files, capacities or persistent kernel configuration.
"""
import argparse
import json
from pathlib import Path
import re
import signal
import time

SETTINGS = [('/proc/sys/vm/swappiness', '60'),
            ('/sys/module/zswap/parameters/zpool', 'zsmalloc'),
            ('/sys/module/zswap/parameters/enabled', 'Y'),
            ('/sys/module/zswap/parameters/shrinker_enabled', 'N')]


def save(record, state):
    temp = record.with_suffix('.tmp')
    temp.write_text(json.dumps(state, indent=2) + '\n')
    temp.replace(record)


def restore(record):
    if not record.exists():
        return
    state = json.loads(record.read_text())
    if [(item['path'], item['temporary']) for item in state['settings']] != SETTINGS:
        raise ValueError('Unexpected VM restoration record')
    for item in reversed(state['settings']):
        if item.get('restore_result'):
            continue
        path = Path(item['path'])
        current = path.read_text().strip()
        if current == item['temporary']:
            path.write_text(item['original'])
            item['restore_result'] = 'restored' if path.read_text().strip() == item['original'] else 'failed'
        elif current == item['original']:
            item['restore_result'] = 'already_original'
        else:
            item['restore_result'] = 'preserved_external_change'
        save(record, state)
    state['restored_at'] = time.time()
    state['status'] = 'failed' if any(i['restore_result'] == 'failed' for i in state['settings']) else 'restored'
    save(record, state)
    if state['status'] != 'restored':
        raise RuntimeError('VM settings did not restore; inspect the record')
    print('Temporary VM settings restored; existing swap retained.', flush=True)


def terminate(_signum, _frame):
    raise SystemExit(0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--restore-only', action='store_true')
    args = parser.parse_args()
    if not re.fullmatch(r'gold-[A-Za-z0-9_.-]+\.service', args.unit):
        parser.error('Expected one explicit Gold systemd service name')
    if args.restore_only:
        restore(args.record)
        return
    cgroup = Path('/sys/fs/cgroup/system.slice') / args.unit / 'cgroup.procs'
    if not cgroup.exists() or not cgroup.read_text().strip():
        raise RuntimeError('Build no longer active')
    if args.record.exists():
        raise RuntimeError('Refuse to replace an existing restoration record')
    state = {'build_unit': args.unit, 'started_at': time.time(), 'status': 'applying',
             'settings': [dict(path=p, original=Path(p).read_text().strip(), temporary=v) for p, v in SETTINGS]}
    save(args.record, state)
    signal.signal(signal.SIGTERM, terminate)
    signal.signal(signal.SIGINT, terminate)
    try:
        for item in state['settings']:
            path = Path(item['path'])
            path.write_text(item['temporary'])
            if path.read_text().strip() != item['temporary']:
                raise RuntimeError('Temporary setting did not apply: ' + item['path'])
        state['status'] = 'active'
        save(args.record, state)
        print('Temporary swap reclaim and zswap active; restoration guard running.', flush=True)
        while cgroup.exists() and cgroup.read_text().strip():
            time.sleep(20)
    finally:
        restore(args.record)


if __name__ == '__main__':
    main()
