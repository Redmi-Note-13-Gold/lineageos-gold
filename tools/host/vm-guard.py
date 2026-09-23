#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Guard temporary VM settings for one Gold service, including guard restarts.

Prepare exact needrestart exclusions before launching the build. Restoration and
removal require an idle service/cgroup and the shared source lock. No swap files,
Android outputs, package-manager policy or unrelated services are changed.
"""
import argparse
import contextlib
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time

SETTINGS = [('/proc/sys/vm/swappiness', '60'),
            ('/sys/module/zswap/parameters/zpool', 'zsmalloc'),
            ('/sys/module/zswap/parameters/enabled', 'Y'),
            ('/sys/module/zswap/parameters/shrinker_enabled', 'N')]
GUARD_LOCK = Path('/run/lock/gold-vm-guard.lock')
RESTART_DIR = Path('/etc/needrestart/conf.d')
CGROUP_ROOT = Path('/sys/fs/cgroup')


def save(record, state):
    if record.is_symlink():
        raise ValueError('Record must not be a symlink')
    temp = record.with_suffix('.tmp')
    fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    temp.replace(record)


def valid_unit(unit):
    if not re.fullmatch(r'gold-[A-Za-z0-9_.-]+\.service', unit):
        raise ValueError('Expected one explicit Gold systemd service name')
    return unit


@contextlib.contextmanager
def exclusive(path):
    fd = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'r+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def service_state(unit):
    text = subprocess.check_output(['systemctl', 'show', valid_unit(unit),
                                   '-p', 'LoadState', '-p', 'ActiveState',
                                   '-p', 'ControlGroup', '-p', 'InvocationID'], text=True)
    result = dict(line.split('=', 1) for line in text.splitlines() if '=' in line)
    if 'ActiveState' not in result or 'LoadState' not in result:
        raise RuntimeError('Cannot establish service state')
    group = result.get('ControlGroup') or '/system.slice/' + unit
    path = CGROUP_ROOT / group.lstrip('/')
    if '..' in Path(group).parts:
        raise ValueError('Unexpected cgroup path')
    events = path / 'cgroup.events'
    # populated includes descendant processes, unlike cgroup.procs alone.
    populated = events.exists() and 'populated 1' in events.read_text().splitlines()
    result['busy'] = (result['ActiveState'] not in ('inactive', 'failed') or populated)
    return result


def validate_state(state, unit=None):
    if unit is not None and state.get('build_unit') != unit:
        raise ValueError('VM record belongs to another build')
    if [(i['path'], i['temporary']) for i in state['settings']] != SETTINGS:
        raise ValueError('Unexpected VM restoration record')
    if any(not isinstance(i.get('original'), str) or not i['original'] for i in state['settings']):
        raise ValueError('Missing original VM values')


def acquire_state(record, unit):
    if record.exists():
        state = json.loads(record.read_text())
        validate_state(state, unit)
        if state['status'] not in ('applying', 'active') or any(i.get('restore_result') for i in state['settings']):
            raise ValueError('Refuse to reuse a completed or partially restored VM record')
        state['adoptions'] = state.get('adoptions', 0) + 1
    else:
        state = {'build_unit': unit, 'started_at': time.time(), 'status': 'applying',
                 'settings': [dict(path=p, original=Path(p).read_text().strip(), temporary=v) for p, v in SETTINGS]}
    # An external policy change needs investigation; do not silently adopt it.
    for item in state['settings']:
        if Path(item['path']).read_text().strip() not in (item['original'], item['temporary']):
            raise RuntimeError('VM setting changed outside this build: ' + item['path'])
    state.setdefault('guard_invocations', []).append(
        {'invocation_id': os.environ.get('INVOCATION_ID'), 'pid': os.getpid(), 'started_at': time.time()})
    save(record, state)  # Save originals before the first temporary write.
    return state


def restore(record):
    if not record.exists():
        return
    state = json.loads(record.read_text())
    validate_state(state)
    for item in reversed(state['settings']):
        path = Path(item['path'])
        current = path.read_text().strip()
        if current == item['original']:
            item['restore_result'] = 'already_original'
        elif current == item['temporary']:
            path.write_text(item['original'])
            item['restore_result'] = 'restored' if path.read_text().strip() == item['original'] else 'failed'
        else:
            item['restore_result'] = 'preserved_external_change'
        save(record, state)
    state['restored_at'] = time.time()
    state['status'] = ('restored' if all(Path(i['path']).read_text().strip() == i['original']
                                       for i in state['settings']) else 'restore_incomplete')
    save(record, state)
    if state['status'] != 'restored':
        raise RuntimeError('VM restoration incomplete; external changes preserved')
    print('Original VM settings verified; existing swap retained.', flush=True)


def restart_content(units):
    return ('# Temporary Gold build protection; other services keep their policy.\n' +
            ''.join('$nrconf{override_rc}->{qr(\\A' + re.escape(valid_unit(u)) + '\\z)} = 0;\n'
                    for u in units))


def prepare_restart(record, unit, guard):
    if unit == guard:
        raise ValueError('The restoration guard must be a separate unit')
    units = [valid_unit(unit), valid_unit(guard)]
    if record.exists() or record.is_symlink():
        raise ValueError('Restart protection record already exists')
    path = RESTART_DIR / ('99-' + unit.removesuffix('.service') + '-temporary.conf')
    data = restart_content(units).encode()
    state = {'build_unit': unit, 'guard_unit': guard, 'path': str(path),
             'sha256': hashlib.sha256(data).hexdigest(), 'status': 'prepared'}
    if path.exists() or path.is_symlink():
        raise ValueError('Refuse to replace an existing needrestart configuration')
    save(record, state)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    return state


def remove_restart(record, unit):
    state = json.loads(record.read_text())
    guard = valid_unit(state['guard_unit'])
    expected = RESTART_DIR / ('99-' + valid_unit(unit).removesuffix('.service') + '-temporary.conf')
    data = restart_content([unit, guard]).encode()
    if (state.get('build_unit') != unit or state['path'] != str(expected) or
            state['sha256'] != hashlib.sha256(data).hexdigest()):
        raise ValueError('Unexpected restart protection record')
    if expected.is_symlink():
        raise ValueError('Restart protection became a symlink')
    if expected.exists():
        stat = expected.stat()
        if stat.st_uid != os.geteuid() or stat.st_mode & 0o077 or expected.read_bytes() != data:
            raise ValueError('Restart protection changed externally; preserve it')
        expected.unlink()
    state.update(status='removed', removed_at=time.time(), absent=not expected.exists())
    save(record, state)


def finish_when_idle(unit, record, source_lock, protection=None):
    if service_state(unit)['busy']:
        return False
    try:
        with exclusive(source_lock):
            if service_state(unit)['busy']:
                return False
            if record.exists():
                state = json.loads(record.read_text())
                validate_state(state, unit)
                restore(record)
            if protection:
                remove_restart(protection, unit)
            return True
    except BlockingIOError:
        return False


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--record', required=True, type=Path)
    parser.add_argument('--source-tree', type=Path, default=Path(__file__).resolve().parents[3] / 'source')
    parser.add_argument('--restore-only', action='store_true')
    parser.add_argument('--prepare-restart-protection', action='store_true')
    parser.add_argument('--guard-unit')
    parser.add_argument('--protection-record', type=Path)
    args = parser.parse_args()
    valid_unit(args.unit)
    for record in (args.record, args.protection_record):
        if record and (not record.is_absolute() or record.is_symlink() or
                       record.parent.resolve() != record.parent or not record.parent.is_dir()):
            parser.error('Use absolute records in an existing real job directory')
    source_lock = args.source_tree.resolve() / '.repo/gold-source-build.lock'
    with exclusive(GUARD_LOCK):
        if args.prepare_restart_protection:
            if args.restore_only or not args.guard_unit or not args.protection_record:
                parser.error('Preparation requires --guard-unit and --protection-record')
            if service_state(args.unit)['busy'] or service_state(args.guard_unit)['busy']:
                raise RuntimeError('Prepare protection before starting either service')
            with exclusive(source_lock):
                prepare_restart(args.protection_record, args.unit, args.guard_unit)
            return
        if args.restore_only:
            if not finish_when_idle(args.unit, args.record, source_lock, args.protection_record):
                raise RuntimeError('Build/service/source lock is still active; no restoration performed')
            return
        if not service_state(args.unit)['busy']:
            if finish_when_idle(args.unit, args.record, source_lock, args.protection_record):
                return
            raise RuntimeError('Build no longer active; no new VM values applied')
        state = acquire_state(args.record, args.unit)
        pending_signals = []
        # A service-manager SIGTERM must not restore global VM settings while the
        # build survives. SIGKILL is recovered by adopting the same durable record.
        def defer_signal(signum, _frame):
            pending_signals.append({'signal': signum, 'at': time.time()})
        signal.signal(signal.SIGTERM, defer_signal)
        signal.signal(signal.SIGINT, defer_signal)
        for item in state['settings']:
            path = Path(item['path'])
            path.write_text(item['temporary'])
            if path.read_text().strip() != item['temporary']:
                raise RuntimeError('Temporary setting did not apply: ' + item['path'])
        state['status'] = 'active'
        save(args.record, state)
        print('Temporary VM settings active; independent guard is watching.', flush=True)
        while True:
            service = service_state(args.unit)
            invocation = service.get('InvocationID')
            changed = False
            if invocation and invocation not in state.setdefault('build_invocations', []):
                state['build_invocations'].append(invocation)
                changed = True
            if pending_signals:
                state.setdefault('deferred_signals', []).extend(pending_signals)
                pending_signals.clear()
                changed = True
            if changed:
                save(args.record, state)
            if not service['busy']:
                time.sleep(3)
                if finish_when_idle(args.unit, args.record, source_lock, args.protection_record):
                    return
            time.sleep(5)


if __name__ == '__main__':
    main()
