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
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model822  # noqa: E402


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
    facility: str
    states: tuple[str, ...] | None = None

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
            facility=str(item["facility"]),
            states=tuple(item["states"]) if item.get("states") else None,
        )
        for item in raw
    ]


def load_alarm_rules() -> dict[str, dict[str, Any]]:
    raw = json.loads((INPUT_DIR / "alarm_rules.json").read_text(encoding="utf-8"))
    return {item["point"]: item for item in raw}


def load_fault_library() -> dict[str, dict[str, Any]]:
    raw = json.loads((INPUT_DIR / "fault_library.json").read_text(encoding="utf-8"))
    return {item["fault_id"]: item for item in raw}


def load_overrides_822() -> dict[str, dict[str, Any]]:
    """Operator overrides, filtered to 822 points only.

    Hospital and office overrides deliberately keep their existing
    display-layer behavior in bas_api.py. Feeding them into the simulator
    would change committed output.
    """
    path = OUTPUT_DIR / "operator_overrides.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    names_822 = {
        item["point"]
        for item in json.loads((INPUT_DIR / "points.json").read_text(encoding="utf-8"))
        if item.get("facility") == model822.FACILITY
    }
    return {k: v for k, v in raw.items() if k in names_822}


def load_served_822_points() -> dict[str, float]:
    """Current 822 values published by bacnet822.py.

    While the BACnet server owns Building 822 we must not simulate it, but its
    points still belong in trends, alarms and latest_points.json -- so we
    observe what the server publishes instead of driving it ourselves.
    """
    try:
        blob = json.loads(
            (OUTPUT_DIR / "latest_points.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(blob.get("points", {}))


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


def select_fault_variant(fault: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    variants = fault.get("variants") or []
    if not variants:
        return fault
    variant = rng.choice(variants)
    selected = dict(fault)
    selected["category"] = variant.get("category", fault["category"])
    selected["correct_category"] = variant.get("correct_category", fault["correct_category"])
    selected["injection"] = variant["injection"]
    selected["explanation"] = variant.get("explanation", fault["explanation"])
    selected["variant_id"] = variant.get("variant_id")
    return selected


def injected_value(point: Point, base_value: float, directive: dict[str, Any], step: int) -> float:
    start_step = int(directive.get("start_step", 0))
    if step < start_step:
        return base_value

    mode = directive["mode"]
    if mode == "drift":
        return round(base_value + float(directive.get("rate_per_step", 0)) * (step - start_step + 1), 4)
    if mode in {"stuck", "step", "noise_flatline"}:
        return float(directive.get("value", base_value))
    raise ValueError(f"Unknown fault injection mode {mode!r} for {point.name}")


def apply_fault(
    snapshot: dict[str, float],
    fault: dict[str, Any],
    points_by_name: dict[str, Point],
    step: int,
) -> tuple[dict[str, float], list[dict[str, Any]]]:
    forced_alarms: list[dict[str, Any]] = []
    for directive in fault["injection"]:
        point_name = directive["point"]
        point = points_by_name[point_name]
        value = injected_value(point, snapshot[point_name], directive, step)
        if point.units == "bool":
            value = int(value)
        snapshot[point_name] = value

        if step >= int(directive.get("start_step", 0)):
            forces = directive.get("forces") or {}
            for forced_point, forced_value in forces.items():
                if forced_point == "raise_alarm":
                    continue
                snapshot[forced_point] = forced_value
            if "raise_alarm" in forces and step == int(directive.get("start_step", 0)):
                forced_alarms.append(
                    {
                        "point": point_name,
                        "equipment": point.equipment,
                        "value": snapshot[point_name],
                        "normal_min": point.normal_min,
                        "normal_max": point.normal_max,
                        "units": point.units,
                        **forces["raise_alarm"],
                    }
                )
    return snapshot, forced_alarms


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


def run_simulation(scenario: str, steps: int, seed: int, fault_id: str | None = None,
                   profile: str = "design_summer",
                   knobs: dict[str, dict[str, Any]] | None = None) -> None:
    rng = random.Random(seed)
    points = load_points()
    rules = load_alarm_rules()
    points_by_name = {point.name: point for point in points}
    legacy_points = [p for p in points if p.facility != model822.FACILITY]
    has_822 = any(p.facility == model822.FACILITY for p in points)
    served_822: dict[str, float] = {}
    if has_822 and (OUTPUT_DIR / ".822-bacnet.lock").exists():
        print("bas_sim: Building 822 is served by bacnet822.py; observing its "
              "points instead of simulating them", file=sys.stderr)
        has_822 = False
        served_822 = load_served_822_points()
        # Any 822 point the server has not published yet cannot be observed
        # this run, so drop it -- the per-point loop below indexes `snapshot`
        # unconditionally and would otherwise raise KeyError.
        observable = set(served_822)
        points = [p for p in points
                  if p.facility != model822.FACILITY or p.name in observable]
        points_by_name = {p.name: p for p in points}
    state_822 = model822.load_state() if has_822 else None
    overrides_822 = load_overrides_822() if has_822 else {}
    fault = None
    run_label = scenario
    if fault_id:
        faults = load_fault_library()
        if fault_id not in faults:
            raise SystemExit(f"Unknown fault {fault_id!r}")
        fault = select_fault_variant(faults[fault_id], rng)
        run_label = fault_id
    start = datetime(2026, 6, 25, 12, 0, tzinfo=timezone.utc)
    snapshots: list[dict[str, Any]] = []
    alarms: list[dict[str, Any]] = []
    trends: list[dict[str, Any]] = []

    for step in range(steps):
        ts = (start + timedelta(minutes=step)).isoformat()
        snapshot: dict[str, float] = {}
        for point in legacy_points:
            snapshot[point.name] = scenario_value(point, scenario, step, rng)
        if served_822:
            snapshot.update(served_822)
        if state_822 is not None:
            state_822, pts_822 = model822.step_822(
                state_822, step, profile, overrides_822, knobs
            )
            snapshot.update(pts_822)

        forced_alarms: list[dict[str, Any]] = []
        if fault:
            snapshot, forced_alarms = apply_fault(snapshot, fault, points_by_name, step)

        for point in points:
            value = snapshot[point.name]
            trends.append(
                {
                    "timestamp": ts,
                    "scenario": run_label,
                    "point": point.name,
                    "equipment": point.equipment,
                    "value": value,
                    "units": point.units,
                }
            )
            alarm = alarm_for(point, value, rules, ts)
            if alarm:
                alarms.append(alarm)
        for alarm in forced_alarms:
            alarms.append({"timestamp": ts, **alarm})
        snapshots.append({"timestamp": ts, "points": snapshot})

    if state_822 is not None:
        model822.save_state(state_822)
        # Hidden field-verification channel -- physical truth, never surfaced
        # through /api/points, the BACnet server, or any normal dashboard.
        # The only sanctioned reader is scripts/field-verify.py.
        (OUTPUT_DIR / ".822-ground-truth.json").write_text(
            json.dumps(model822.ground_truth_snapshot(state_822), indent=2, sort_keys=True) + "\n",
            encoding="utf-8")
    write_outputs(run_label, snapshots, alarms, trends)


def _coerce_knob_value(equipment: str, key: str, default: Any, raw: str) -> Any:
    """Coerce a --knob CLI string to the type its model822 default declares."""
    if isinstance(default, bool):
        low = raw.strip().lower()
        if low in ("true", "1"):
            return True
        if low in ("false", "0"):
            return False
        raise SystemExit(f"--knob {equipment}:{key}: {raw!r} is not true/false")
    if isinstance(default, list):
        inner = raw.strip().removeprefix("[").removesuffix("]")
        try:
            return [int(x) for x in inner.split(",") if x.strip()]
        except ValueError:
            raise SystemExit(f"--knob {equipment}:{key}: {raw!r} is not a list of ints "
                              f"(e.g. [1] or [1,2])") from None
    try:
        return float(raw)
    except ValueError:
        raise SystemExit(f"--knob {equipment}:{key}: {raw!r} is not a number") from None


def parse_knob_args(knob_args: list[str]) -> dict[str, dict[str, Any]]:
    """Parse repeated --knob EQUIPMENT:KEY=VALUE into model822's knobs shape.

    Codex (or any fault-injection agent) breaks the CAUSE through this --
    a coil fouling fraction, a stuck damper, a locked-out chiller circuit --
    never a sensor reading directly. The physics in model822.step_822()
    computes everything downstream. This is a deliberate, load-bearing
    separation: see docs/superpowers/specs/2026-09-15-bacnet-822-server-design.md,
    "Companion Milestone -- Fault Injection And Troubleshooting Training Mode".

    "_all" applies a knob to every MAU, FCU, the CHW loop, and the chiller at
    once; each of those only reads the keys it recognizes (model822._knobs_for),
    so an "_all" knob only meaningful to one device type is silently harmless
    everywhere else -- validated here only against the union of all schemas.
    """
    knobs: dict[str, dict[str, Any]] = {}
    for arg in knob_args:
        if ":" not in arg:
            raise SystemExit(f"--knob {arg!r}: expected EQUIPMENT:KEY=VALUE")
        equipment, rest = arg.split(":", 1)
        if "=" not in rest:
            raise SystemExit(f"--knob {arg!r}: expected EQUIPMENT:KEY=VALUE")
        key, raw_value = rest.split("=", 1)

        if equipment == "_all":
            schema = {**model822.COIL_KNOB_DEFAULTS,
                      **model822.CHW_KNOB_DEFAULTS,
                      **model822.CHILLER_KNOB_DEFAULTS}
        elif equipment in model822.MAU_IDS or equipment in model822.FCU_IDS:
            schema = model822.COIL_KNOB_DEFAULTS
        elif equipment == "CHW-822":
            schema = model822.CHW_KNOB_DEFAULTS
        elif equipment == "CHILLER-RTAC-822":
            schema = model822.CHILLER_KNOB_DEFAULTS
        else:
            raise SystemExit(f"--knob {arg!r}: unknown equipment {equipment!r}")

        if key not in schema:
            raise SystemExit(
                f"--knob {arg!r}: {key!r} is not a knob on {equipment!r}. "
                f"Valid knobs: {sorted(schema)}")

        knobs.setdefault(equipment, {})[key] = _coerce_knob_value(
            equipment, key, schema[key], raw_value)
    return knobs


def self_test() -> int:
    """Schema checks that need no simulation run."""
    points = load_points()
    facilities = {p.facility for p in points}
    assert "hospital" in facilities, facilities
    assert "office" in facilities, facilities
    mv_points = [p for p in points if p.point_type == "MV"]
    for p in mv_points:
        assert p.states, f"MV point {p.name} has no states list"

    # --- --knob CLI parsing -------------------------------------------------
    knobs = parse_knob_args([
        "MAU04:coil_fouling=0.6",
        "CHW-822:strainer_resistance=0.7",
        "CHW-822:p2_running=true",
        "CHILLER-RTAC-822:condenser_fan_failed=[1]",
        "_all:air_bound=false",
    ])
    assert knobs["MAU04"]["coil_fouling"] == 0.6
    assert isinstance(knobs["MAU04"]["coil_fouling"], float)
    assert knobs["CHW-822"]["strainer_resistance"] == 0.7
    assert knobs["CHW-822"]["p2_running"] is True
    assert knobs["CHILLER-RTAC-822"]["condenser_fan_failed"] == [1]
    assert knobs["_all"]["air_bound"] is False

    for bad in ("MAU04:strainer_resistance=0.7",   # wrong knob for a coil device
                "MAU04:coil_fouling",               # missing "="
                "MAU04",                            # missing ":"
                "NOT-A-DEVICE:coil_fouling=0.5",    # unknown equipment
                "MAU04:coil_fouling=nope"):         # unparseable value
        try:
            parse_knob_args([bad])
        except SystemExit:
            pass
        else:
            raise AssertionError(f"expected SystemExit for bad --knob arg: {bad!r}")

    print(f"SELF-TEST PASS ({len(points)} points, facilities={sorted(facilities)})")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic hospital BAS simulator")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--scenario",
        choices=["normal", "chilled_water_degraded", "isolation_pressure_loss", "or_humidity_excursion"],
        default=None,
    )
    group.add_argument("--fault", help="Fault ID from data/input/fault_library.json")
    parser.add_argument("--steps", type=int, default=12)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--profile", choices=["design_summer", "shoulder"],
                        default="design_summer",
                        help="Building 822 weather profile")
    parser.add_argument(
        "--knob", action="append", default=[], metavar="EQUIPMENT:KEY=VALUE",
        help="Inject a Building 822 fault CAUSE (repeatable). Breaks the cause, "
             "never a reading directly -- model822 computes the symptom. "
             "e.g. --knob MAU04:coil_fouling=0.6 --knob CHW-822:strainer_resistance=0.7. "
             "Ignored while bacnet822.py owns 822 (see docs/bacnet-822.md).")
    parser.add_argument("--self-test", action="store_true", help="Run schema self-checks and exit")
    args = parser.parse_args()
    if args.self_test:
        raise SystemExit(self_test())
    if args.steps < 1:
        raise SystemExit("--steps must be >= 1")
    knobs = parse_knob_args(args.knob) if args.knob else None
    run_simulation(args.scenario or "normal", args.steps, args.seed, args.fault, args.profile, knobs)


if __name__ == "__main__":
    main()
