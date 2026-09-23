# SPDX-License-Identifier: Apache-2.0
import importlib.util
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tools/host' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


guard = load('vm-guard')
invocation = load('build-invocation')


class GuardLifecycleTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.record = self.root / 'vm.json'
        self.source_lock = self.root / 'source.lock'
        self.unit = 'gold-fixture.service'
        self.protection = self.root / 'protection.json'
        self.values = ['0', 'zbud', 'N', 'Y']
        self.settings = []
        for i, ((_, temporary), original) in enumerate(zip(guard.SETTINGS, self.values)):
            path = self.root / str(i)
            path.write_text(original)
            self.settings.append((str(path), temporary))
        self.patch_settings = patch.object(guard, 'SETTINGS', self.settings)
        self.patch_settings.start()
        self.addCleanup(self.patch_settings.stop)

    def activate(self):
        state = guard.acquire_state(self.record, self.unit)
        for path, value in self.settings:
            Path(path).write_text(value)
        state['status'] = 'active'
        guard.save(self.record, state)
        return state

    def test_replacement_guard_preserves_originals_after_partial_or_full_apply(self):
        original = guard.acquire_state(self.record, self.unit)
        Path(self.settings[0][0]).write_text(self.settings[0][1])
        adopted = guard.acquire_state(self.record, self.unit)
        self.assertEqual(adopted['settings'], original['settings'])
        self.activate()
        adopted = guard.acquire_state(self.record, self.unit)
        self.assertEqual([i['original'] for i in adopted['settings']], self.values)
        guard.restore(self.record)
        self.assertEqual([Path(p).read_text() for p, _ in self.settings], self.values)

    def test_record_for_different_unit_or_completed_restore_is_not_adopted(self):
        self.activate()
        with self.assertRaisesRegex(ValueError, 'another build'):
            guard.acquire_state(self.record, 'gold-other.service')
        guard.restore(self.record)
        with self.assertRaisesRegex(ValueError, 'completed'):
            guard.acquire_state(self.record, self.unit)

    def test_live_service_or_source_lock_prevents_restoration(self):
        self.activate()
        with patch.object(guard, 'service_state', return_value={'busy': True}):
            self.assertFalse(guard.finish_when_idle(self.unit, self.record, self.source_lock))
        with guard.exclusive(self.source_lock), patch.object(guard, 'service_state', return_value={'busy': False}):
            self.assertFalse(guard.finish_when_idle(self.unit, self.record, self.source_lock))
        self.assertEqual([Path(p).read_text() for p, _ in self.settings], [v for _, v in self.settings])
        with patch.object(guard, 'service_state', return_value={'busy': False}):
            self.assertTrue(guard.finish_when_idle(self.unit, self.record, self.source_lock))

    def test_live_descendant_cgroup_prevents_false_idle(self):
        cgroup = self.root / 'system.slice' / self.unit
        cgroup.mkdir(parents=True)
        (cgroup / 'cgroup.events').write_text('populated 1\nfrozen 0\n')
        with patch.object(guard, 'CGROUP_ROOT', self.root), patch.object(guard.subprocess, 'check_output',
                return_value='LoadState=not-found\nActiveState=inactive\nControlGroup=\nInvocationID=\n'):
            self.assertTrue(guard.service_state(self.unit)['busy'])
            (cgroup / 'cgroup.events').write_text('populated 0\n')
            self.assertFalse(guard.service_state(self.unit)['busy'])

    def test_external_vm_change_is_preserved_and_not_reported_restored(self):
        self.activate()
        path = Path(self.settings[0][0]); path.write_text('42')
        with self.assertRaisesRegex(RuntimeError, 'outside'):
            guard.acquire_state(self.record, self.unit)
        with self.assertRaisesRegex(RuntimeError, 'incomplete'):
            guard.restore(self.record)
        self.assertEqual(path.read_text(), '42')
        self.assertEqual(json.loads(self.record.read_text())['status'], 'restore_incomplete')

    def test_singleton_rejects_second_guard(self):
        with guard.exclusive(self.root / 'guard.lock'):
            with self.assertRaises(BlockingIOError), guard.exclusive(self.root / 'guard.lock'):
                pass

    def test_restart_regex_scopes_only_two_exact_units_and_cleanup_checks_bytes(self):
        with patch.object(guard, 'RESTART_DIR', self.root):
            state = guard.prepare_restart(self.protection, self.unit, 'gold-fixture-guard.service')
            config = Path(state['path'])
            perl = r'''our %nrconf; do $ARGV[0]; die $@ if $@;
for my $i (1..$#ARGV) { my $matches = 0; for my $r (keys %{$nrconf{override_rc}}) {
  $matches++ if $ARGV[$i] =~ $r && $nrconf{override_rc}->{$r} == 0;
} print "$matches\n"; }'''
            output = subprocess.check_output(['perl', '-e', perl, str(config), self.unit,
                'gold-fixture-guard.service', 'gold-fixtureXservice', 'gold-fixture.service.extra',
                'ssh.service', self.unit + '\n'], text=True)
            self.assertEqual(output.splitlines(), ['1', '1', '0', '0', '0', '0'])
            original = config.read_text(); config.write_text(original + '# other administrator\n')
            with self.assertRaisesRegex(ValueError, 'externally'):
                guard.remove_restart(self.protection, self.unit)
            self.assertTrue(config.exists())
            config.write_text(original)
            guard.remove_restart(self.protection, self.unit)
            self.assertFalse(config.exists())
            self.assertTrue(json.loads(self.protection.read_text())['absent'])

    def test_dangling_restart_symlink_and_existing_record_are_rejected(self):
        with patch.object(guard, 'RESTART_DIR', self.root):
            config = self.root / '99-gold-fixture-temporary.conf'
            config.symlink_to(self.root / 'missing')
            with self.assertRaises(ValueError):
                guard.prepare_restart(self.protection, self.unit, 'gold-fixture-guard.service')
            self.assertTrue(config.is_symlink())

    def test_short_job_without_vm_application_can_remove_its_protection(self):
        with patch.object(guard, 'RESTART_DIR', self.root), patch.object(guard, 'service_state', return_value={'busy': False}):
            guard.prepare_restart(self.protection, self.unit, 'gold-fixture-guard.service')
            self.assertTrue(guard.finish_when_idle(self.unit, self.record, self.source_lock, self.protection))
        self.assertFalse(self.record.exists())
        self.assertEqual([Path(p).read_text() for p, _ in self.settings], self.values)


class InvocationTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.records = self.root / 'invocations'

    def test_exit_codes_have_separate_immutable_invocation_identities(self):
        for char, code in [('a', 0), ('b', 7)]:
            invocation_id = char * 32
            result = invocation.run([sys.executable, '-c', f'raise SystemExit({code})'], self.records, invocation_id)
            self.assertEqual(result, code)
            state = json.loads((self.records / (invocation_id + '.json')).read_text())
            self.assertEqual(state['status'], 'passed' if code == 0 else 'failed')
            self.assertEqual(state['entry_exit_code'], code)
            self.assertLessEqual(state['started_at'], state['finished_at'])
        with self.assertRaises(FileExistsError):
            invocation.run([sys.executable, '-c', 'pass'], self.records, 'a' * 32)
        self.assertEqual(len(list(self.records.glob('*.json'))), 2)

    def test_external_termination_is_interrupted_and_child_exits(self):
        invocation_id = 'c' * 32
        process = subprocess.Popen([sys.executable, str(ROOT / 'tools/host/build-invocation.py'),
            '--records', str(self.records), '--', sys.executable, '-c', 'import time; time.sleep(30)'],
            env={**os.environ, 'INVOCATION_ID': invocation_id})
        self.addCleanup(lambda: process.kill() if process.poll() is None else None)
        record = self.records / (invocation_id + '.json')
        end = time.monotonic() + 5
        while time.monotonic() < end:
            if record.exists() and json.loads(record.read_text()).get('entry_pid'):
                break
            time.sleep(.01)
        else:
            self.fail('Invocation child did not start')
        process.send_signal(signal.SIGTERM)
        self.assertEqual(process.wait(timeout=5), 143)
        state = json.loads(record.read_text())
        self.assertEqual(state['status'], 'interrupted')
        self.assertEqual(state['external_signals'][0]['signal'], signal.SIGTERM)
        with self.assertRaises(ProcessLookupError):
            os.kill(state['entry_pid'], 0)

    def test_invalid_identity_does_not_create_a_record(self):
        with self.assertRaises(ValueError):
            invocation.run(['true'], self.records, 'not-a-systemd-id')
        self.assertFalse(self.records.exists())


if __name__ == '__main__':
    unittest.main()
