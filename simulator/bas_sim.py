#!/usr/bin/env python3
"""Synthetic hospital BAS simulator for slot-3.

This simulator emits fictional BAS point snapshots, alarms, and trend data.
It is intentionally small and dependency-free so it can run in the lab without
network access or package installation.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
OUTPUT_DIR = ROOT / "data" / "output"


@dataclass(frozen=True)
class Point:
    name: str
    equipment: str
    point_type: str
    units: str
    normal_min: float
    normal_max: float
    writable: bool
    critical: bool
    trend_interval_sec: int

    @property
    def midpoint(self) -> float:
        return (self.normal_min + self.normal_max) / 2


def load_points() -> list[Point]:
    raw = json.loads((INPUT_DIR / "points.json").read_text(encoding="utf-8"))
    return [
        Point(
            name=item["point"],
            equipment=item["equipment"],
            point_type=item["type"],
            units=item["units"],
            normal_min=float(item["normal_min"]),
            normal_max=float(item["normal_max"]),
            writable=bool(item["writable"]),
            critical=bool(item["critical"]),
            trend_interval_sec=int(item["trend_interval_sec"]),
        )
        for item in raw
    ]


def load_alarm_rules() -> dict[str, dict[str, Any]]:
    raw = json.loads((INPUT_DIR / "alarm_rules.json").read_text(encoding="utf-8"))
    return {item["point"]: item for item in raw}


def bool_value(point: Point) -> int:
    return int(point.normal_max)


def normal_value(point: Point, rng: random.Random) -> float:
    if point.units == "bool":
        return bool_value(point)
    span = point.normal_max - point.normal_min
    jitter = span * 0.12 if span else 0.1
    return round(point.midpoint + rng.uniform(-jitter, jitter), 3)


def scenario_value(point: Point, scenario: str, step: int, rng: random.Random) -> float:
    value = normal_value(point, rng)

    if scenario == "chilled_water_degraded":
        if point.name == "CHW_SUPPLY_TEMP":
            return round(48.0 + min(step * 0.25, 4.0), 3)
        if point.name == "CHW_DIFF_PRESSURE":
            return round(10.5 - min(step * 0.12, 2.5), 3)
        if point.name == "AHU_OR1_SAT":
            return round(59.0 + min(step * 0.18, 3.0), 3)
        if point.name == "OR1_TEMP":
            return round(72.5 + min(step * 0.10, 1.8), 3)

    if scenario == "isolation_pressure_loss":
        if point.name == "ISO201_PRESSURE":
            return round(-0.008 + min(step * 0.001, 0.012), 4)
        if point.name == "ISO201_EXH_CMD" and step > 6:
            return 0

    if scenario == "or_humidity_excursion":
        if point.name == "OR1_RH":
            return round(61.5 + min(step * 0.45, 8.0), 3)

    return value


def alarm_for(point: Point, value: float, rules: dict[str, dict[str, Any]], ts: str) -> dict[str, Any] | None:
    if point.name not in rules:
        return None
    if point.normal_min <= value <= point.normal_max:
        return None
    rule = rules[point.name]
    return {
        "timestamp": ts,
        "point": point.name,
        "equipment": point.equipment,
        "priority": rule["priority"],
        "message": rule["message"],
        "value": value,
        "normal_min": point.normal_min,
        "normal_max": point.normal_max,
        "units": point.units,
    }


def write_outputs(
    scenario: str,
    snapshots: list[dict[str, Any]],
    alarms: list[dict[str, Any]],
    trends: list[dict[str, Any]],
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    (OUTPUT_DIR / "latest_points.json").write_text(
        json.dumps(
            {
                "scenario": scenario,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "data_boundary": "synthetic lab data only",
                "points": snapshots[-1]["points"] if snapshots else {},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with (OUTPUT_DIR / "alarms.jsonl").open("w", encoding="utf-8") as fh:
        for alarm in alarms:
            fh.write(json.dumps(alarm, sort_keys=True) + "\n")

    with (OUTPUT_DIR / "trends.csv").open("w", newline="", encoding="utf-8") as fh:
        fieldnames = ["timestamp", "scenario", "point", "equipment", "value", "units"]
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(trends)

    (OUTPUT_DIR / "scenario-summary.md").write_text(
        "\n".join(
            [
                f"# Scenario Summary -- {scenario}",
                "",
                f"- snapshots: {len(snapshots)}",
                f"- trend rows: {len(trends)}",
                f"- alarms: {len(alarms)}",
                "- data boundary: synthetic lab data only",
                "",
                "## Alarm Counts",
                "",
                *summary_lines(alarms),
                "",
            ]
        ),
        encoding="utf-8",
    )


def summary_lines(alarms: list[dict[str, Any]]) -> list[str]:
    if not alarms:
        return ["- none"]
    counts: dict[str, int] = {}
    for alarm in alarms:
        key = f"{alarm['priority']}:{alarm['point']}"
        counts[key] = counts.get(key, 0) + 1
    return [f"- {key}: {count}" for key, count in sorted(counts.items())]


def run_simulation(scenario: str, steps: int, seed: int) -> None:
    rng = random.Random(seed)
    points = load_points()
    rules = load_alarm_rules()
    start = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    snapshots: list[dict[str, Any]] = []
    alarms: list[dict[str, Any]] = []
    trends: list[dict[str, Any]] = []

    for step in range(steps):
        ts = (start + timedelta(minutes=step)).isoformat()
        snapshot: dict[str, float] = {}
        for point in points:
            value = scenario_value(point, scenario, step, rng)
            snapshot[point.name] = value
            trends.append(
                {
                    "timestamp": ts,
                    "scenario": scenario,
                    "point": point.name,
                    "equipment": point.equipment,
                    "value": value,
                    "units": point.units,
                }
            )
            alarm = alarm_for(point, value, rules, ts)
            if alarm:
                alarms.append(alarm)
        snapshots.append({"timestamp": ts, "points": snapshot})

    write_outputs(scenario, snapshots, alarms, trends)


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic hospital BAS simulator")
    parser.add_argument(
        "--scenario",
        choices=["normal", "chilled_water_degraded", "isolation_pressure_loss", "or_humidity_excursion"],
        default="normal",
    )
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()
    if args.steps < 1:
        raise SystemExit("--steps must be >= 1")
    run_simulation(args.scenario, args.steps, args.seed)


if __name__ == "__main__":
    main()

