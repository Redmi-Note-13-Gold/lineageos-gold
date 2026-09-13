#!/usr/bin/env python3
"""Observe one explicit Gold slot without changing device state (Python 3.9+)."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time


EXIT_CODES = {
    "booted": 0, "recovery": 10, "fastboot": 11, "unauthorized": 12,
    "timeout": 13, "wrong_slot": 14, "tool_error": 15, "interrupted": 130,
}
BOOT_ID_PATH = "/proc/sys/kernel/random/boot_id"
BOOT_ID_RE = re.compile(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}")
ADB_READS = {
    ("devices", "-l"), ("shell", "getprop"),
    ("shell", "cat", BOOT_ID_PATH), ("shell", "cat", "/proc/bootconfig"),
    ("shell", "cat", "/proc/cmdline"), ("shell", "dmesg"),
    ("shell", "logcat", "-b", "all", "-d", "-t", "2000"),
}
FASTBOOT_READS = {
    ("devices",), ("getvar", "current-slot"), ("getvar", "is-userspace"),
}
NORMAL_MODES = {"normal", "reboot"}
CLEANUP_TIMEOUT = 1.0


class DeadlineReached(Exception):
    pass


def append_json(path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(value, sort_keys=True) + "\n")


def listed_state(text, serial):
    matches = [fields[1] for line in text.splitlines()
               if len(fields := line.split()) >= 2 and fields[0] == serial]
    if len(matches) > 1:
        raise ValueError(f"Ambiguous duplicate serial in device inventory: {serial}")
    return matches[0] if matches else None


def parse_properties(text):
    properties = {}
    for line in text.splitlines():
        match = re.fullmatch(r"\[([^\]]+)\]: \[(.*)\]", line)
        if match:
            key, value = match.groups()
            if key in properties and properties[key] != value:
                raise ValueError(f"Conflicting property values: {key}")
            properties[key] = value
    return properties


def property_slot(properties):
    values = {value.removeprefix("_") for key in ("ro.boot.slot_suffix", "ro.boot.slot")
              if (value := properties.get(key, "").strip())}
    if not values:
        return None
    if len(values) != 1 or not values <= {"a", "b"}:
        return "conflict"
    return values.pop()


def command_ok(result):
    return result["returncode"] == 0 and not result["timed_out"] and not result.get("error")


def command_text(result, stream="stdout"):
    if not command_ok(result):
        return ""
    with Path(result[stream]).open(encoding="utf-8", errors="replace") as source:
        text = source.read(1024 * 1024 + 1)
    if len(text) > 1024 * 1024:
        raise ValueError("Control response exceeds 1 MiB; raw output retained")
    return text


def getvar_value(result, name):
    text = command_text(result) + "\n" + command_text(result, "stderr")
    values = re.findall(r"^(?:\(bootloader\)\s*)?" + re.escape(name)
                        + r":\s*([^\r\n]*)$", text, re.MULTILINE)
    return values[0].strip() if len(values) == 1 else None


class Commands:
    def __init__(self, args, deadline):
        self.args = args
        self.output = args.output.resolve()
        self.deadline = deadline
        self.sequence = 0
        self.failures = 0
        self.executables = {}
        for tool in ("adb", "fastboot"):
            executable = shutil.which(getattr(args, tool))
            if not executable:
                raise ValueError(f"Required host executable not found: {getattr(args, tool)}")
            self.executables[tool] = executable

    def allowed(self, tool, arguments):
        if tool == "fastboot":
            return arguments in FASTBOOT_READS
        if tool != "adb":
            return False
        if arguments in ADB_READS:
            return True
        if len(arguments) == 3 and arguments[:2] == ("pull", "/sys/fs/pstore"):
            try:
                relative = Path(arguments[2]).resolve().relative_to(self.output / "snapshots")
            except ValueError:
                return False
            return (len(relative.parts) == 2 and relative.name == "pstore"
                    and re.fullmatch(r"[0-9]{4,}", relative.parts[0]) is not None)
        return False

    @staticmethod
    def stop_client(process):
        # Only this client's new process group is killed, never the adb server.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        return process.wait(timeout=CLEANUP_TIMEOUT)

    def run(self, tool, arguments, label):
        arguments = tuple(arguments)
        if not self.allowed(tool, arguments) or not re.fullmatch(r"[a-z][a-z0-9_-]*", label):
            raise ValueError(f"Device command is not an approved read: {tool} {arguments}")
        if time.monotonic() >= self.deadline:
            raise DeadlineReached
        self.sequence += 1
        stem = self.output / f"{self.sequence:05d}-{label}"
        result = {
            "argv": [self.executables[tool], "-s", self.args.serial, *arguments],
            "stdout": str(stem.with_suffix(".stdout")),
            "stderr": str(stem.with_suffix(".stderr")),
            "returncode": None, "timed_out": False,
        }
        started = time.monotonic()
        interrupted = False
        cleanup_failed = False
        with Path(result["stdout"]).open("xb") as stdout, \
                Path(result["stderr"]).open("xb") as stderr:
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise DeadlineReached
            try:
                process = subprocess.Popen(result["argv"], stdin=subprocess.DEVNULL,
                                           stdout=stdout, stderr=stderr, start_new_session=True)
                try:
                    result["returncode"] = process.wait(
                        timeout=min(self.args.command_timeout, remaining))
                except (subprocess.TimeoutExpired, KeyboardInterrupt) as error:
                    interrupted = isinstance(error, KeyboardInterrupt)
                    result["timed_out"] = not interrupted
                    result["interrupted"] = interrupted
                    try:
                        result["returncode"] = self.stop_client(process)
                    except (OSError, subprocess.TimeoutExpired) as cleanup_error:
                        cleanup_failed = True
                        result["error"] = f"Client cleanup failed: {cleanup_error}"
            except OSError as error:
                result["error"] = str(error)
        result["elapsed_seconds"] = round(time.monotonic() - started, 6)
        self.failures += not command_ok(result)
        append_json(self.output / "commands.jsonl", result)
        if interrupted:
            raise KeyboardInterrupt
        if cleanup_failed:
            raise RuntimeError(result["error"])
        return result


class Capture:
    def __init__(self, args):
        self.args = args
        self.started = time.monotonic()
        self.deadline = self.started + args.timeout
        self.commands = Commands(args, self.deadline)
        self.last_observation = {"transport": "unknown", "slot": None, "ready": False}
        self.stable_since = None
        self.stable_boot_id = None
        self.last_ready_at = None
        self.stable_samples = 0
        self.stable_seconds = 0.0
        self.snapshot_count = 0
        self.snapshot_key = None
        self.snapshot_at = None

    def observe(self):
        observation = {"transport": "unknown", "slot": None, "boot_id": None,
                       "boot_completed": None, "recovery": False, "ready": False}
        self.last_observation = observation
        inventory = self.commands.run("adb", ("devices", "-l"), "adb-devices")
        state = listed_state(command_text(inventory), self.args.serial)
        observation["transport"] = state or "disconnected"
        if state in ("device", "recovery"):
            observation["recovery"] = state == "recovery"
            result = self.commands.run("adb", ("shell", "getprop"), "getprop")
            properties = parse_properties(command_text(result))
            modes = [properties[key].strip().lower() for key in ("ro.bootmode", "ro.boot.mode")
                     if properties.get(key, "").strip()]
            observation.update({
                "slot": property_slot(properties), "boot_modes": modes,
                "boot_completed": properties.get("sys.boot_completed"),
                "properties_ok": command_ok(result),
                "recovery": (state == "recovery" or "recovery" in modes
                             or properties.get("init.svc.recovery") in ("running", "restarting")),
            })
            boot_id = command_text(self.commands.run(
                "adb", ("shell", "cat", BOOT_ID_PATH), "boot-id")).strip()
            observation["boot_id"] = boot_id.lower() if BOOT_ID_RE.fullmatch(boot_id) else None
            observation["ready"] = (
                state == "device" and observation["slot"] == self.args.slot
                and observation["boot_completed"] == "1" and not observation["recovery"]
                and bool(modes) and all(mode in NORMAL_MODES for mode in modes)
                and observation["boot_id"] is not None)
        elif state != "unauthorized":
            fastboot = self.commands.run("fastboot", ("devices",), "fastboot-devices")
            fastboot_state = listed_state(command_text(fastboot), self.args.serial)
            if fastboot_state == "fastboot":
                observation["transport"] = "fastboot"
                slot = getvar_value(self.commands.run(
                    "fastboot", ("getvar", "current-slot"), "fastboot-slot"), "current-slot")
                observation["slot"] = slot if slot in ("a", "b") else None
                observation["is_userspace"] = getvar_value(self.commands.run(
                    "fastboot", ("getvar", "is-userspace"), "fastboot-userspace"), "is-userspace")
            elif not state and (not command_ok(inventory) or not command_ok(fastboot)):
                observation["transport"] = "tool_error"
        observation["elapsed_seconds"] = time.monotonic() - self.started
        return observation

    def snapshot(self, observation):
        if observation["transport"] not in ("device", "recovery"):
            return False
        key = (observation["transport"], observation["slot"], observation["boot_id"],
               observation["recovery"])
        now = time.monotonic()
        if (key == self.snapshot_key and self.snapshot_at is not None
                and now - self.snapshot_at < self.args.snapshot_interval):
            return False
        self.snapshot_count += 1
        directory = self.args.output / "snapshots" / f"{self.snapshot_count:04d}"
        directory.mkdir(parents=True)
        (directory / "observation.json").write_text(
            json.dumps(observation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        # Read pstore first so a short Recovery connection can retain the previous boot log.
        self.commands.run("adb", ("pull", "/sys/fs/pstore", str(directory / "pstore")), "pstore")
        for label, arguments in (
            ("bootconfig", ("shell", "cat", "/proc/bootconfig")),
            ("dmesg", ("shell", "dmesg")),
            ("logcat", ("shell", "logcat", "-b", "all", "-d", "-t", "2000")),
            ("cmdline", ("shell", "cat", "/proc/cmdline")),
        ):
            self.commands.run("adb", arguments, label)
        self.snapshot_key, self.snapshot_at = key, time.monotonic()
        return True

    def update_stability(self, observation):
        if not observation.get("ready"):
            self.stable_since = self.stable_boot_id = self.last_ready_at = None
            self.stable_samples = 0
            self.stable_seconds = 0.0
            return False
        now = self.started + observation["elapsed_seconds"]
        max_gap = self.args.poll_interval + 3 * self.args.command_timeout
        if (self.stable_since is None or observation["boot_id"] != self.stable_boot_id
                or now - self.last_ready_at > max_gap):
            self.stable_since = now
            self.stable_boot_id = observation["boot_id"]
            self.stable_samples = 0
        self.stable_samples += 1
        self.last_ready_at = now
        self.stable_seconds = now - self.stable_since
        return self.stable_samples >= 2 and self.stable_seconds >= self.args.stable_seconds

    def expired_outcome(self):
        observation = self.last_observation
        if observation["slot"] in ("a", "b") and observation["slot"] != self.args.slot:
            return "wrong_slot"
        if observation.get("recovery"):
            return "recovery"
        if observation["transport"] in ("fastboot", "unauthorized", "tool_error"):
            return observation["transport"]
        return "timeout"

    def run(self):
        error = None
        outcome = None
        try:
            while time.monotonic() < self.deadline:
                observation = self.observe()
                stable = self.update_stability(observation)
                append_json(self.args.output / "timeline.jsonl", {
                    **observation, "stable_seconds": self.stable_seconds,
                    "stable_samples": self.stable_samples,
                })
                if self.snapshot(observation):
                    continue  # Resample after log capture; never accept stale completion.
                if stable and time.monotonic() < self.deadline:
                    outcome = "booted"
                    break
                time.sleep(min(self.args.poll_interval, max(0, self.deadline - time.monotonic())))
        except DeadlineReached:
            self.update_stability({"ready": False})
        except KeyboardInterrupt:
            outcome = "interrupted"
        except (OSError, ValueError, RuntimeError) as failure:
            outcome, error = "tool_error", str(failure)
        outcome = outcome or self.expired_outcome()
        result = {
            "schema_version": 1, "serial": self.args.serial, "target_slot": self.args.slot,
            "outcome": outcome, "exit_code": EXIT_CODES[outcome],
            "elapsed_seconds": time.monotonic() - self.started,
            "stable_seconds": self.stable_seconds, "stable_samples": self.stable_samples,
            "last_observation": self.last_observation,
            "command_failures": self.commands.failures, "error": error,
        }
        (self.args.output / "result.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(json.dumps(result, sort_keys=True))
        return result["exit_code"]


def positive_seconds(value):
    try:
        number = float(value)
    except ValueError:
        raise argparse.ArgumentTypeError("Expected positive finite seconds")
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("Expected positive finite seconds")
    return number


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial", required=True, help="Exact USB/ADB serial; never inferred")
    parser.add_argument("--slot", required=True, choices=("a", "b"), help="Expected Android slot")
    parser.add_argument("--output", required=True, type=Path, help="New host evidence directory")
    for name, default in (("timeout", 180), ("command-timeout", 5), ("stable-seconds", 15),
                          ("poll-interval", 1), ("snapshot-interval", 15)):
        parser.add_argument("--" + name, type=positive_seconds, default=default,
                            help=f"Positive seconds (default: {default})")
    parser.add_argument("--adb", default="adb", help="Host adb executable")
    parser.add_argument("--fastboot", default="fastboot", help="Host fastboot executable")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", args.serial):
        parser.error("--serial must be an explicit serial without whitespace or shell syntax")
    if args.stable_seconds > args.timeout:
        parser.error("--stable-seconds must not exceed --timeout")
    args.output = args.output.expanduser().resolve()
    return args


def main(argv=None):
    args = parse_args(argv)
    try:
        capture = Capture(args)
        args.output.mkdir(mode=0o700, parents=True, exist_ok=False)
        return capture.run()
    except (OSError, ValueError, RuntimeError) as error:
        print(f"capture_boot: {error}", file=sys.stderr)
        return EXIT_CODES["tool_error"]


if __name__ == "__main__":
    sys.exit(main())
