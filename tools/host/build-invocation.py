#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Record each systemd execution of the existing build entry, including signals."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import time


def write_record(path, state, *, create=False):
    target = path if create else path.with_suffix('.tmp')
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW |
                 (os.O_EXCL if create else os.O_TRUNC), 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    if not create:
        target.replace(path)


def run(command, records, invocation):
    if not re.fullmatch('[0-9a-f]{32}', invocation or ''):
        raise ValueError('Expected the current systemd INVOCATION_ID')
    if not command:
        raise ValueError('Missing build entry command')
    if not records.is_absolute() or records.is_symlink() or records.parent.resolve() != records.parent:
        raise ValueError('Use an absolute real invocation directory')
    records.mkdir(mode=0o700, exist_ok=True)
    stat = records.stat()
    if stat.st_uid != os.geteuid() or stat.st_mode & 0o077:
        raise ValueError('Invocation directory must be private and owned by the caller')
    path = records / (invocation + '.json')
    state = {'invocation_id': invocation, 'started_at': time.time(), 'status': 'running',
             'entry_exit_code': None, 'command': command, 'external_signals': [],
             'device_accepted': False}
    write_record(path, state, create=True)  # Never overwrite a previous execution.
    env = os.environ.copy()
    env.update(GOLD_RECORDED_INVOCATION=invocation, GOLD_HOST_INVOCATION_RECORD=str(path))
    child = None
    previous = {}
    def interrupted(signum, _frame):
        state['external_signals'].append({'signal': signum, 'at': time.time()})
        if child is not None:
            try:
                os.killpg(child.pid, signum)
            except ProcessLookupError:
                pass
    try:
        for sig in (signal.SIGTERM, signal.SIGINT):
            previous[sig] = signal.signal(sig, interrupted)
        child = subprocess.Popen(command, env=env, start_new_session=True)
        if state['external_signals']:
            interrupted(state['external_signals'][-1]['signal'], None)
        state['entry_pid'] = child.pid
        write_record(path, state)
        code = child.wait()
        state['child_returncode'] = code
        if state['external_signals']:
            code = 128 + state['external_signals'][-1]['signal']
            state['status'] = 'interrupted'
        else:
            code = code if code >= 0 else 128 - code
            state['status'] = 'passed' if code == 0 else 'failed'
        state['entry_exit_code'] = code
        return code
    except BaseException as error:
        state.update(status='failed', error=repr(error))
        raise
    finally:
        state['finished_at'] = time.time()
        write_record(path, state)
        for sig, handler in previous.items():
            signal.signal(sig, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--records', required=True, type=Path)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    return run(command, args.records, os.environ.get('INVOCATION_ID'))


if __name__ == '__main__':
    raise SystemExit(main())
