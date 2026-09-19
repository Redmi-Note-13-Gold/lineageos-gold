#!/usr/bin/env python3
"""No-hardware capture regressions: mock every client process and the clock."""

import contextlib
import io
import json
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest import mock

import capture_boot


SERIAL = "EXAMPLE_GOLD_SERIAL"
BOOT_A = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
BOOT_B = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"


def frame(transport="device", **overrides):
    result = {"transport": transport, "slot": "a", "completed": "1",
              "mode": "normal", "boot_id": BOOT_A}
    result.update(overrides)
    return result


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        if seconds < 0:
            raise AssertionError("negative wait")
        self.now += seconds


class FakeClients:
    def __init__(self, clock, frames):
        self.clock = clock
        self.frames = frames
        self.index = -1
        self.current = frame("disconnected")
        self.calls = []
        self.waits = []
        self.cleaned = 0

    def popen(self, argv, *, stdin, stdout, stderr, start_new_session):
        if argv[1:3] != ["-s", SERIAL] or not start_new_session:
            raise AssertionError("unbound device command or unmanaged process")
        if stdin != subprocess.DEVNULL:
            raise AssertionError("client must not read terminal input")
        tool, arguments = Path(argv[0]).name, tuple(argv[3:])
        self.calls.append((tool, arguments))
        if tool == "adb" and arguments == ("devices", "-l"):
            self.index += 1
            self.current = (self.frames(self.index) if callable(self.frames)
                            else self.frames[min(self.index, len(self.frames) - 1)])
        current = self.current
        owner = self

        class Process:
            pid = 999999

            def __init__(self):
                self.wait_count = 0

            def wait(self, timeout=None):
                self.wait_count += 1
                if self.wait_count > 1:
                    owner.cleaned += 1
                    return -signal.SIGKILL
                owner.waits.append(timeout)
                if current.get("interrupt_on") == arguments:
                    raise KeyboardInterrupt
                if current.get("timeout_on") == arguments:
                    stdout.write(b"partial capture\n")
                    owner.clock.sleep(timeout)
                    raise subprocess.TimeoutExpired(argv, timeout)
                owner.clock.sleep(min(0.01, timeout))
                code, output, errors = owner.response(tool, arguments)
                stdout.write(output.encode())
                stderr.write(errors.encode())
                return code

        return Process()

    def response(self, tool, arguments):
        current = self.current
        if tool == "adb" and arguments == ("devices", "-l"):
            output = "List of devices attached\nother-phone device\n"
            if current["transport"] not in ("fastboot", "disconnected"):
                output += f"{SERIAL} {current['transport']} product:lineage_gold\n"
            if current.get("duplicate_serial"):
                output += f"{SERIAL} recovery\n"
            return 0, output, ""
        if tool == "fastboot" and arguments == ("devices",):
            output = "other-phone fastboot\n"
            if current["transport"] == "fastboot":
                output += f"{SERIAL}\tfastboot\n"
            return 0, output, ""
        if tool == "fastboot" and arguments[0] == "getvar":
            value = current["slot"] if arguments[1] == "current-slot" else current.get("userspace", "no")
            return 0, "", f"(bootloader) {arguments[1]}: {value}\nFinished.\n"
        if arguments == ("shell", "getprop"):
            properties = {"sys.boot_completed": current["completed"]}
            if current["slot"] is not None:
                properties["ro.boot.slot_suffix"] = "_" + current["slot"]
                properties["ro.boot.slot"] = current.get("slot_property", current["slot"])
            if current["mode"] is not None:
                properties["ro.bootmode"] = current["mode"]
                properties["ro.boot.mode"] = current.get("other_mode", current["mode"])
            if current.get("recovery_service"):
                properties["init.svc.recovery"] = "running"
            output = "".join(f"[{key}]: [{value}]\n" for key, value in properties.items())
            return current.get("property_status", 0), output, ""
        if arguments == ("shell", "cat", capture_boot.BOOT_ID_PATH):
            return 0, (current["boot_id"] or "") + "\n", ""
        if arguments[:2] == ("pull", "/sys/fs/pstore"):
            if current.get("pstore_missing"):
                return 1, "", "remote object does not exist\n"
            destination = Path(arguments[2])
            destination.mkdir()
            (destination / "console-ramoops-0").write_text("previous init failure\n")
            return 0, "1 file pulled\n", ""
        if arguments == ("shell", "cat", "/proc/bootconfig"):
            return 0, 'androidboot.slot_suffix = "_a"\n', ""
        if arguments == ("shell", "cat", "/proc/cmdline"):
            return 0, "bootopt=64S3,32N2,64N2\n", ""
        if arguments == ("shell", "dmesg"):
            return 0, "[ 1.0] init: mock kernel log\n", ""
        if arguments == ("shell", "logcat", "-b", "all", "-d", "-t", "2000"):
            if current.get("logcat_missing"):
                return 127, "", "logcat: not found\n"
            return 0, "F libc: mock userspace crash\n", ""
        raise AssertionError(f"unexpected device command: {tool} {arguments}")


class CaptureTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="gold-capture-test-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.clock = FakeClock()

    def arguments(self, **overrides):
        args = capture_boot.parse_args([
            "--serial", SERIAL, "--slot", "a", "--output", str(self.root / "logs"),
            "--timeout", "3", "--stable-seconds", "0.6", "--poll-interval", "0.2",
            "--command-timeout", "0.15", "--snapshot-interval", "10",
        ])
        for key, value in overrides.items():
            setattr(args, key, value)
        return args

    def run_capture(self, frames, **overrides):
        args = self.arguments(**overrides)
        args.output.mkdir()
        self.clients = FakeClients(self.clock, frames)
        with mock.patch.object(capture_boot.time, "monotonic", self.clock.monotonic), \
             mock.patch.object(capture_boot.time, "sleep", self.clock.sleep), \
             mock.patch.object(capture_boot.shutil, "which", side_effect=lambda tool: "/mock/" + tool), \
             mock.patch.object(capture_boot.subprocess, "Popen", side_effect=self.clients.popen), \
             mock.patch.object(capture_boot.os, "killpg") as killpg, \
             contextlib.redirect_stdout(io.StringIO()):
            capture = capture_boot.Capture(args)
            code = capture.run()
            self.kill_calls = killpg.call_args_list
        self.summary = json.loads((args.output / "result.json").read_text())
        self.assertEqual(code, self.summary["exit_code"])
        self.assertLessEqual(self.clock.now, args.timeout + 0.0001)
        return code

    def test_correct_slot_requires_sustained_completion(self):
        self.assertEqual(self.run_capture([frame()]), 0)
        self.assertGreaterEqual(self.summary["stable_seconds"], 0.6)
        self.assertGreaterEqual(self.summary["stable_samples"], 2)
        self.assertEqual(self.summary["last_observation"]["slot"], "a")

    def test_explicit_target_b_also_works(self):
        self.assertEqual(self.run_capture([frame(slot="b")], slot="b"), 0)

    def test_b_boot_completed_is_not_a_success(self):
        self.assertEqual(self.run_capture([frame(slot="b")]), 14)

    def test_b_recovery_is_captured_but_is_not_a_success(self):
        self.assertEqual(self.run_capture([frame("recovery", slot="b", mode="recovery")]), 14)
        self.assertTrue(list(self.root.glob("logs/snapshots/*/pstore/console-ramoops-0")))

    def test_recovery_transport_never_succeeds_even_with_normal_properties(self):
        self.assertEqual(self.run_capture([frame("recovery")]), 10)

    def test_recovery_mode_under_device_transport_never_succeeds(self):
        self.assertEqual(self.run_capture([frame(mode="recovery")]), 10)

    def test_conflicting_recovery_mode_is_not_ignored(self):
        self.assertEqual(self.run_capture([frame(other_mode="recovery")]), 10)

    def test_running_recovery_service_is_not_android_success(self):
        self.assertEqual(self.run_capture([frame(recovery_service=True)]), 10)

    def test_fastboot_and_fastbootd_have_distinct_logged_mode(self):
        self.assertEqual(self.run_capture([frame("fastboot", userspace="yes")]), 11)
        self.assertEqual(self.summary["last_observation"]["is_userspace"], "yes")

    def test_unauthorized_wait_is_bounded(self):
        self.assertEqual(self.run_capture([frame("unauthorized")]), 12)
        self.assertFalse(list(self.root.glob("logs/snapshots/*")))

    def test_initial_fastboot_can_transition_to_android_without_device_writes(self):
        self.assertEqual(self.run_capture([frame("fastboot"), frame()]), 0)

    def test_authorization_can_arrive_during_capture(self):
        self.assertEqual(self.run_capture([frame("unauthorized"), frame()]), 0)

    def test_recovery_can_transition_to_target_android(self):
        self.assertEqual(self.run_capture([frame("recovery", slot="b"), frame()]), 0)

    def test_other_connected_devices_are_ignored(self):
        self.assertEqual(self.run_capture([frame("disconnected")]), 13)
        self.assertTrue(all(args[0] == "devices" for _, args in self.clients.calls))

    def test_offline_never_succeeds(self):
        self.assertEqual(self.run_capture([frame("offline")]), 13)

    def test_ambiguous_duplicate_serial_fails_closed(self):
        self.assertEqual(self.run_capture([frame(duplicate_serial=True)]), 15)

    def test_missing_slot_never_succeeds(self):
        self.assertEqual(self.run_capture([frame(slot=None)]), 13)

    def test_conflicting_slot_properties_never_succeed(self):
        self.assertEqual(self.run_capture([frame(slot_property="b")]), 13)
        self.assertEqual(self.summary["last_observation"]["slot"], "conflict")

    def test_missing_boot_mode_never_succeeds(self):
        self.assertEqual(self.run_capture([frame(mode=None)]), 13)

    def test_missing_boot_id_never_succeeds(self):
        self.assertEqual(self.run_capture([frame(boot_id=None)]), 13)

    def test_failed_getprop_cannot_supply_success_properties(self):
        self.assertEqual(self.run_capture([frame(property_status=1)]), 13)

    def test_every_boot_id_change_resets_stability(self):
        self.assertEqual(self.run_capture(lambda n: frame(boot_id=BOOT_A if n % 2 else BOOT_B)), 13)
        timeline = [json.loads(line) for line in
                    (self.root / "logs/timeline.jsonl").read_text().splitlines()]
        self.assertTrue(timeline)
        self.assertTrue(all(sample["stable_samples"] == int(sample["ready"])
                            and sample["stable_seconds"] == 0 for sample in timeline))
        self.assertEqual(self.summary["outcome"], "timeout")
        # A deadline in the final probe can clear the last incomplete sample too.
        self.assertLessEqual(self.summary["stable_samples"], 1)

    def test_disconnect_resets_stability(self):
        frames = [frame(), frame(), frame("disconnected"), frame(), frame()]
        self.assertEqual(self.run_capture(frames, timeout=1.05), 13)
        self.assertLess(self.summary["stable_seconds"], 0.6)

    def test_completion_property_regression_resets_stability(self):
        self.assertEqual(self.run_capture(lambda n: frame(completed=str(n % 2))), 13)

    def test_pstore_bootconfig_dmesg_and_logcat_are_preserved(self):
        self.assertEqual(self.run_capture([frame("recovery", mode="recovery")]), 10)
        self.assertTrue(list(self.root.glob("logs/snapshots/*/pstore/console-ramoops-0")))
        for label in ("bootconfig", "dmesg", "logcat"):
            outputs = list(self.root.glob(f"logs/*-{label}.stdout"))
            self.assertTrue(outputs)
            self.assertTrue(all(path.stat().st_size for path in outputs))

    def test_missing_logcat_is_recorded_without_root_or_recovery_changes(self):
        self.assertEqual(self.run_capture([frame(logcat_missing=True)]), 0)
        self.assertGreater(self.summary["command_failures"], 0)
        self.assertTrue(any("logcat: not found" in path.read_text()
                            for path in self.root.glob("logs/*-logcat.stderr")))

    def test_logcat_timeout_retains_partial_output_and_reaps_client(self):
        command = ("shell", "logcat", "-b", "all", "-d", "-t", "2000")
        self.assertEqual(self.run_capture([frame(timeout_on=command)]), 0)
        self.assertEqual(self.clients.cleaned, 1)
        self.assertTrue(any("partial capture" in path.read_text()
                            for path in self.root.glob("logs/*-logcat.stdout")))

    def test_optional_log_failure_is_visible_but_does_not_fake_boot_failure(self):
        self.assertEqual(self.run_capture([frame(pstore_missing=True)]), 0)
        self.assertGreater(self.summary["command_failures"], 0)
        self.assertTrue(any("does not exist" in path.read_text()
                            for path in self.root.glob("logs/*-pstore.stderr")))

    def test_hung_command_is_killed_and_budget_is_not_extended(self):
        self.assertEqual(self.run_capture([frame(timeout_on=("shell", "getprop"))]), 13)
        self.assertGreater(self.clients.cleaned, 0)
        self.assertEqual(len(self.kill_calls), self.clients.cleaned)
        self.assertTrue(all(call.args == (999999, signal.SIGKILL) for call in self.kill_calls))
        self.assertTrue(all(0 < value <= 0.15 for value in self.clients.waits))
        self.assertTrue(any("partial capture" in path.read_text()
                            for path in self.root.glob("logs/*-getprop.stdout")))

    def test_deadline_truncates_even_a_long_configured_command_timeout(self):
        self.assertEqual(self.run_capture([frame(timeout_on=("shell", "getprop"))],
                                         timeout=1, command_timeout=10), 13)
        self.assertLessEqual(max(self.clients.waits), 1)

    def test_interrupt_reaps_client_and_reports_130(self):
        self.assertEqual(self.run_capture([frame(interrupt_on=("shell", "getprop"))]), 130)
        self.assertEqual(self.clients.cleaned, 1)

    def test_all_executed_commands_are_serial_bound_read_operations(self):
        self.assertEqual(self.run_capture([frame("fastboot"), frame("recovery"), frame()]), 0)
        for tool, args in self.clients.calls:
            if tool == "fastboot":
                self.assertIn(args, capture_boot.FASTBOOT_READS)
            elif args[:2] == ("pull", "/sys/fs/pstore"):
                self.assertTrue(Path(args[2]).resolve().is_relative_to(
                    (self.root / "logs/snapshots").resolve()))
            else:
                self.assertIn(args, capture_boot.ADB_READS)

    def test_unapproved_commands_are_rejected_before_process_creation(self):
        args = self.arguments()
        with mock.patch.object(capture_boot.shutil, "which", return_value="/mock/tool"), \
             mock.patch.object(capture_boot.subprocess, "Popen") as popen:
            commands = capture_boot.Commands(args, 100)
            for tool, command in (
                ("adb", ("root",)), ("adb", ("reboot",)),
                ("adb", ("shell", "setprop", "sys.usb.config", "adb")),
                ("adb", ("shell", "dmesg", "-c")),
                ("adb", ("shell", "logcat", "-c")),
                ("adb", ("shell", "logcat", "-b", "all")),
                ("adb", ("pull", "/sys/fs/pstore", str(self.root / "elsewhere"))),
                ("fastboot", ("flash", "system_a", "image")),
                ("fastboot", ("erase", "metadata")), ("fastboot", ("set_active", "a")),
                ("fastboot", ("snapshot-update", "cancel")),
            ):
                with self.subTest(command=command), self.assertRaises(ValueError):
                    commands.run(tool, command, "forbidden")
            popen.assert_not_called()

    def test_required_identity_and_finite_timeouts(self):
        base = ["--serial", SERIAL, "--slot", "a", "--output", str(self.root / "logs")]
        invalid = [[], base[2:], base[:2] + base[4:],
                   base + ["--timeout", "nan"], base + ["--timeout", "inf"],
                   base + ["--command-timeout", "0"], base + ["--stable-seconds", "-1"],
                   base + ["--stable-seconds", "999"], base + ["--serial", "bad serial"]]
        for arguments in invalid:
            with self.subTest(arguments=arguments), contextlib.redirect_stderr(io.StringIO()), \
                 self.assertRaises(SystemExit) as error:
                capture_boot.parse_args(arguments)
            self.assertEqual(error.exception.code, 2)

    def test_existing_output_is_never_overwritten(self):
        destination = self.root / "logs"
        destination.mkdir()
        (destination / "evidence.txt").write_text("keep")
        with mock.patch.object(capture_boot.subprocess, "Popen") as popen, \
             contextlib.redirect_stderr(io.StringIO()):
            code = capture_boot.main(["--serial", SERIAL, "--slot", "a", "--output", str(destination)])
        self.assertEqual(code, 15)
        self.assertEqual((destination / "evidence.txt").read_text(), "keep")
        popen.assert_not_called()

    def test_missing_binary_never_attempts_a_device_command(self):
        with mock.patch.object(capture_boot.shutil, "which", return_value=None), \
             mock.patch.object(capture_boot.subprocess, "Popen") as popen, \
             contextlib.redirect_stderr(io.StringIO()):
            code = capture_boot.main(["--serial", SERIAL, "--slot", "a",
                                      "--output", str(self.root / "logs")])
        self.assertEqual(code, 15)
        popen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
