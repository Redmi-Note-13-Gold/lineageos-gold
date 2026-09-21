#!/usr/bin/env python3
"""Summarize the owned Gold benchmark without treating frames as independent runs.

Consumes measure-power-strategies.py's completed, restored comparison. Confidence
intervals and sign-flip probabilities are exploratory paired statistics; this
synthetic workload cannot establish benefits for every app or battery life.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import random
import statistics


def percentile(values, quantile):
    values = sorted(values)
    point = (len(values) - 1) * quantile
    lower = int(point)
    upper = min(lower + 1, len(values) - 1)
    return values[lower] + (values[upper] - values[lower]) * (point - lower)


def paired_summary(pairs):
    differences = [b - a for a, b in pairs]
    mean = statistics.mean(differences)
    generator = random.Random(20260921)
    means = [statistics.mean(generator.choices(differences, k=len(differences)))
             for _ in range(10000)]
    # With four scroll pairs the minimum two-sided probability is 0.125.
    # Reporting this explicitly avoids treating thousands of frames as thousands
    # of independent comparisons or calling a small visual difference proven.
    extreme = sum(abs(statistics.mean(x * sign for x, sign in zip(differences, signs)))
                  >= abs(mean) - 1e-12
                  for signs in itertools.product((-1, 1), repeat=len(differences)))
    return {
        "pairs": len(pairs), "baseline_mean": statistics.mean(a for a, _ in pairs),
        "boost_mean": statistics.mean(b for _, b in pairs),
        "boost_minus_baseline_by_pair": differences, "mean_difference": mean,
        "paired_bootstrap_mean_difference_95pct": [percentile(means, .025), percentile(means, .975)],
        "two_sided_paired_sign_flip_probability": extreme / (2 ** len(differences)),
    }


def sample_metrics(sample):
    requested = sample["requested_duration_ms"] / 1000
    frames = sample["frames"]
    # Frame timestamps use CLOCK_MONOTONIC, battery timestamps use BOOTTIME.
    # Never subtract created_elapsed_ns from a frame timestamp.
    origin = frames[0][0]
    steady = [row for row in frames if not row[3]
              and 2 <= (row[0] - origin) / 1e9 < requested - 2]
    battery = sample["battery"]
    start, end = sample["created_elapsed_ns"] + 2e9, sample["created_elapsed_ns"] + (requested - 2) * 1e9
    energy, covered = 0.0, 0.0
    for left, right in zip(battery, battery[1:]):
        t0, t1 = left[0], right[0]
        if t1 <= t0 or t1 - t0 > 2.5e9:
            raise ValueError("invalid battery sample interval")
        lo, hi = max(t0, start), min(t1, end)
        if hi <= lo:
            continue
        # Discharge current is negative on the verified device. uA * mV / 1e9 = W.
        w0, w1 = -left[2] * left[3] / 1e9, -right[2] * right[3] / 1e9
        a = w0 + (w1 - w0) * ((lo - t0) / (t1 - t0))
        b = w0 + (w1 - w0) * ((hi - t0) / (t1 - t0))
        seconds = (hi - lo) / 1e9
        energy += (a + b) * .5 * seconds
        covered += seconds
    if not steady or covered < requested - 4 - .1:
        raise ValueError("incomplete steady scroll frame or battery window")
    if any(row[2] <= 0 for row in steady):
        raise ValueError("frame deadlines unavailable")
    durations = [row[1] / 1e6 for row in steady]
    return {
        "steady_frames": len(steady), "p50_frame_ms": percentile(durations, .5),
        "p95_frame_ms": percentile(durations, .95), "p99_frame_ms": percentile(durations, .99),
        "deadline_miss_percent": 100 * sum(row[1] > row[2] for row in steady) / len(steady),
        "energy_window_seconds": covered, "energy_joules": energy,
        "average_battery_power_watts": energy / covered,
        "full_sample_charge_counter_drop_uah": battery[0][1] - battery[-1][1],
        "temperature_start_end_decic": [battery[0][4], battery[-1][4]],
        "temperature_peak_decic": max(row[4] for row in battery),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("comparison", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    state = json.loads((args.comparison / "progress.json").read_text())
    if not state["completed"] or not state["strategies_restored"] or state.get("error"):
        raise ValueError("comparison did not finish and restore production defaults")
    result = {"schema_version": 1, "incremental": state["incremental"],
              "apk_sha256": state["apk_sha256"], "protocol": state["protocol"],
              "framework_launch_calibration": state["framework_launch_calibration"],
              "strategies_restored": state["strategies_restored"], "samples": [], "comparisons": {},
              "limitations": ["One synthetic app; cold process with warm filesystem caches.",
                              "Fuel gauge estimates, not an external power meter; charge counter is coarse.",
                              "Network ADB and synthetic input overhead are shared by both strategies.",
                              "Frame duration and deadline misses are not a full input-to-display latency measurement.",
                              "Paired runs, not individual frames, are independent comparison units.",
                              "Small sample exploratory statistics do not prove equivalence or general battery life."]}
    groups = {}
    for row in state["samples"]:
        name = row["sample"]
        if not name.replace("_", "").isalnum():
            raise ValueError("unexpected sample name")
        path = args.comparison / (name + ".json")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != row["sample_sha256"]:
            raise ValueError("sample changed: " + name)
        sample = json.loads(raw)
        if sample["reason"] != "completed" or sample["dropped_frame_callbacks"] != 0:
            raise ValueError("incomplete frame sampling: " + name)
        if any(b[5] != 0 or b[2] >= 0 for b in sample["battery"]):
            raise ValueError("charging or invalid current sample: " + name)
        entry = dict(row)
        if row["phase"] == "scroll":
            entry.update(sample_metrics(sample))
        result["samples"].append(entry)
        group = groups.setdefault((row["phase"], row["pair"]), {})
        if row["uclamp"] in group:
            raise ValueError("duplicate strategy in pair")
        group[row["uclamp"]] = entry
    for phase, metrics in [("launch", ["cold_launch_ms"]),
                           ("scroll", ["p95_frame_ms", "p99_frame_ms", "deadline_miss_percent",
                                       "average_battery_power_watts", "energy_joules"])]:
        matched, excluded = [], []
        for (kind, number), group in groups.items():
            if kind != phase:
                continue
            if set(group) != {0, 20}:
                raise ValueError("incomplete pair")
            a, b = group[0], group[20]
            if not all(r["pair_start_temperature_matched"] for r in group.values()) or abs(
                    a["initial_refresh_hz"] - b["initial_refresh_hz"]) > .1:
                excluded.append(number)
            else:
                matched.append((a, b))
        if len(matched) < 2:
            raise ValueError("too few matched pairs for " + phase)
        result["comparisons"][phase] = {
            "excluded_pair_numbers": excluded,
            "metrics": {metric: paired_summary([(a[metric], b[metric]) for a, b in matched])
                        for metric in metrics}}
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result["comparisons"], indent=2))


if __name__ == "__main__":
    main()
