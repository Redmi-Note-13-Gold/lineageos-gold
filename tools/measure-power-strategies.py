#!/usr/bin/env python3
"""Run an explicitly selected Gold device's bounded 0/20 uclamp comparison.

Requires prior authorization for temporary root, the installed owned test APK,
screen input, and Power HAL restarts. Does not install apps or change global
display settings, SIM configuration, thermal policy or network settings.
Raw observations are private; no result automatically changes production defaults.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

PACKAGE = "org.lineageos.gold.perfprobe"
COMPONENT = PACKAGE + "/.MainActivity"
APP_FILES = "/data/user/0/" + PACKAGE + "/files/"
POWER = "dumpsys android.hardware.power.IPower/default"
CLAMP = "/dev/cpuctl/top-app/cpu.uclamp.min"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", default="adb")
    parser.add_argument("--serial", required=True, help="Explicit ADB transport, including a Wi-Fi endpoint")
    parser.add_argument("--hardware-serial", required=True)
    parser.add_argument("--incremental", required=True)
    parser.add_argument("--apk-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--launch-pairs", type=int, default=12)
    parser.add_argument("--scroll-pairs", type=int, default=4)
    parser.add_argument("--scroll-seconds", type=int, default=60)
    args = parser.parse_args()
    if not (4 <= args.launch_pairs <= 20 and 2 <= args.scroll_pairs <= 6 and 30 <= args.scroll_seconds <= 80):
        parser.error("bounded ranges: launch pairs 4..20, scroll pairs 2..6, scroll seconds 30..80")
    os.umask(0o077)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    adb = [args.adb, "-s", args.serial, "shell"]
    state = {"schema_version": 1, "incremental": args.incremental, "apk_sha256": args.apk_sha256,
             "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
             "protocol": {"strategies": [[0, 0], [20, 20]], "pair_order": "AB, BA, alternating",
                          "launch_pairs": args.launch_pairs, "scroll_pairs": args.scroll_pairs,
                          "scroll_seconds": args.scroll_seconds, "brightness": "test window 0.35",
                          "temperature_pair_start_tolerance_decic": 5,
                          "force_stop_scope": PACKAGE, "filesystem_cache_not_cleared": True,
                          "synthetic_workload_not_general_app_benchmark": True},
             "samples": [], "completed": False, "strategies_restored": False}

    def persist():
        (output / "progress.json").write_text(json.dumps(state, indent=2) + "\n")

    def shell(command, timeout=20, check=True):
        result = subprocess.run(adb + [command], capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            raise RuntimeError("device command failed: " + command + "\n" + result.stdout + result.stderr)
        return result.stdout.strip()

    def eligibility():
        text = shell("dumpsys battery")
        level = int(re.search(r"^  level: (\d+)", text, re.M).group(1))
        temperature = int(re.search(r"^  temperature: (\d+)", text, re.M).group(1))
        if any(re.search(r"^  " + kind + r" powered: true", text, re.M)
               for kind in ["USB", "AC", "Wireless", "Dock"]):
            raise RuntimeError("external power connected; energy comparison invalid")
        if level < 25 or temperature > 380:
            raise RuntimeError("battery reserve or temperature outside protocol")
        thermal = shell("dumpsys thermalservice")
        if "Thermal Status: 0\n" not in thermal + "\n":
            raise RuntimeError("thermal throttling active")
        if shell("settings get global low_power") not in ["0", "null"]:
            raise RuntimeError("battery saver enabled")
        return {"level": level, "temperature_decic": temperature, "thermal_status": 0}

    def restart():
        old = shell("pidof android.hardware.power-service.gold")
        shell("setprop ctl.restart vendor.power-hal-gold")
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            pid = shell("pidof android.hardware.power-service.gold || true")
            if pid and pid != old:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Power HAL did not restart")
        shell("input keyevent 223")
        time.sleep(0.2)
        shell("input keyevent 224")
        deadline = time.monotonic() + 6
        while time.monotonic() < deadline:
            dump = shell(POWER)
            if "ready=1 enabled=1" in dump:
                return dump
            time.sleep(0.15)
        raise RuntimeError("Power HAL remained gated after normal display notification")

    def strategy(value):
        result = shell(POWER + " --set-strategy %d %d" % (value, value))
        if "Strategy stored;" not in result:
            raise RuntimeError("owning HAL did not accept strategy")
        dump = restart()
        if "launch_uclamp=%d interaction_uclamp=%d" % (value, value) not in dump:
            raise RuntimeError("strategy was not applied")
        # Finish any wake interaction before measuring the next launch.
        time.sleep(1)
        if float(shell("cat " + CLAMP)) != 0:
            raise RuntimeError("another resource request is active")

    def launch(name, duration):
        # The same installed probe may be used for a later run. Never accept
        # an earlier run's file while waiting for this activity to finish.
        shell("rm -f " + APP_FILES + name + ".json")
        started = time.monotonic()
        text = shell("am start -S -W -n " + COMPONENT + " --es sample " + name
                     + " --ei duration_ms " + str(duration), timeout=25)
        (output / (name + "-am.txt")).write_text(text + "\n")
        match = re.search(r"^TotalTime: (\d+)$", text, re.M)
        if not match or "LaunchState: COLD" not in text or "Status: ok" not in text:
            raise RuntimeError("not a successful cold process launch: " + text)
        return started, int(match.group(1))

    def collect(name, deadline):
        while time.monotonic() < deadline:
            present = shell("test -f " + APP_FILES + name + ".json && echo ready", check=False)
            if present == "ready":
                raw = shell("cat " + APP_FILES + name + ".json")
                result = json.loads(raw)
                (output / (name + ".json")).write_text(raw + "\n")
                if result["reason"] != "completed" or not result["frames"]:
                    raise RuntimeError("test interrupted or frame metrics absent")
                if not result["battery"] or any(row[5] != 0 or row[2] >= 0 for row in result["battery"]):
                    raise RuntimeError("sample not entirely on discharging battery")
                return result
            time.sleep(0.25)
        raise RuntimeError("app sample did not finish")

    identity = shell("getprop ro.serialno; getprop ro.product.device; getprop ro.build.version.incremental; getenforce; id -u")
    if identity.splitlines() != [args.hardware_serial, "gold", args.incremental, "Enforcing", "0"]:
        raise RuntimeError("device identity, build, enforcing state or temporary root differs")
    size = shell("wm size")
    if "Physical size: 1080x2400" not in size or "Override size:" in size:
        raise RuntimeError("swipe geometry requires the verified native Gold display size")
    apk = shell("pm path " + PACKAGE).removeprefix("package:")
    if not apk or shell("sha256sum " + apk).split()[0] != args.apk_sha256:
        raise RuntimeError("installed APK differs from the prepared owned test")
    initial = shell(POWER)
    if "launch_uclamp=0 interaction_uclamp=0" not in initial or "requests=0" not in initial:
        raise RuntimeError("initial strategies or votes are not the reviewed baseline")
    (output / "initial-power.txt").write_text(initial + "\n")
    state["preflight"] = eligibility()
    persist()
    try:
        strategy(20)
        command = "for i in $(seq 1 100); do cat " + CLAMP + "; sleep 0.025; done"
        monitor = subprocess.Popen(adb + [command], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        started, _ = launch("calibration", 3500)
        values, errors = monitor.communicate(timeout=10)
        (output / "calibration-clamp.txt").write_text(values + errors)
        values = [float(value) for value in values.splitlines()]
        collect("calibration", started + 10)
        state["framework_launch_calibration"] = {"samples": len(values), "maximum": max(values),
                                                 "final": float(shell("cat " + CLAMP))}
        if max(values) != 20 or state["framework_launch_calibration"]["final"] != 0:
            raise RuntimeError("framework launch did not exercise and release the selected vote")
        for phase, pairs in [("launch", args.launch_pairs), ("scroll", args.scroll_pairs)]:
            for pair in range(pairs):
                pair_temperature = None
                for value in ([0, 20] if pair % 2 == 0 else [20, 0]):
                    strategy(value)
                    before = eligibility()
                    if pair_temperature is not None:
                        deadline = time.monotonic() + 120
                        while abs(before["temperature_decic"] - pair_temperature) > 5 and time.monotonic() < deadline:
                            shell("input keyevent 223")
                            time.sleep(5)
                            before = eligibility()
                        shell("input keyevent 224")
                    else:
                        pair_temperature = before["temperature_decic"]
                    name = "%s_%02d_%02d" % (phase, pair, value)
                    duration = 3000 if phase == "launch" else args.scroll_seconds * 1000
                    started, total_ms = launch(name, duration)
                    swipes = 0
                    if phase == "scroll":
                        # Fixed generated content; use actual input dispatch so the
                        # framework issues INTERACTION requests through its HAL.
                        time.sleep(2)
                        while time.monotonic() < started + args.scroll_seconds - 2:
                            up = swipes % 2 == 0
                            shell("input swipe 540 %d 540 %d 250" % ((1800, 600) if up else (600, 1800)))
                            swipes += 1
                            time.sleep(0.15)
                    sample = collect(name, started + duration / 1000 + 8)
                    row = {"phase": phase, "pair": pair, "uclamp": value, "sample": name,
                           "cold_launch_ms": total_ms, "preflight": before, "swipes": swipes,
                           "pair_temperature_decic": pair_temperature,
                           "pair_start_temperature_matched": abs(before["temperature_decic"] - pair_temperature) <= 5,
                           "frames": len(sample["frames"]), "dropped_callbacks": sample["dropped_frame_callbacks"],
                           "initial_refresh_hz": sample["initial_refresh_hz"],
                           "sample_sha256": hashlib.sha256((output / (name + ".json")).read_bytes()).hexdigest()}
                    state["samples"].append(row)
                    persist()
                    print(json.dumps(row), flush=True)
        state["completed"] = True
    except BaseException as error:
        state["error"] = str(error)
        raise
    finally:
        try:
            shell("am force-stop " + PACKAGE)
            strategy(0)
            final = shell(POWER)
            (output / "final-power.txt").write_text(final + "\n")
            state["strategies_restored"] = "launch_uclamp=0 interaction_uclamp=0" in final and "requests=0" in final
        finally:
            state["ended_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            persist()


if __name__ == "__main__":
    main()
