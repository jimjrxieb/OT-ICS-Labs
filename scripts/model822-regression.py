#!/usr/bin/env python3
"""Building 822 regression check: step_822 outputs for fixed cases vs a
recorded baseline.

Record once, from code you trust, before a physics change:
    python3 scripts/model822-regression.py --record
Check after every change (the smoke test runs this):
    python3 scripts/model822-regression.py --check

Exact equality is the default. A case listed in TOLERANCE may drift by that
many units on any point -- use it only for a documented, intended change.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulator"))
import model822  # noqa: E402

BASELINE = ROOT / "simulator" / "testdata" / "model822-regression-baseline.json"
STEPS = 120

CASES: dict[str, dict[str, Any]] = {
    "healthy": {},
    "mau01_coil_fouling": {"knobs": {"MAU01": {"coil_fouling": 0.6}}},
    "strainer_0_7": {"knobs": {"CHW-822": {"strainer_resistance": 0.7}}},
    "mau01_air_bound": {"knobs": {"MAU01": {"air_bound": True}}},
    "mau01_fan_off": {"overrides": {"MAU01_FAN_CMD": {"value": 0}}},
    "condenser_fouling_0_5": {"knobs": {"CHILLER-RTAC-822": {"condenser_fouling": 0.5}}},
    "mau04_stuck_lying": {"knobs": {"MAU04": {"actuator_stuck_at": 15.0, "feedback_stuck_at": 98.0}}},
}

# Intended, documented drift per case (max absolute difference on any point).
# condenser_fouling_0_5 was re-recorded in S-001 phase 1 task 3: before loop
# thermal mass, that case's CHW supply alternated ~49 <-> 64 F every step (the
# instant loop fed an overloaded chiller's output straight back into coil
# load), so its baseline captured one half of an oscillation. The lagged loop
# settles it; the re-recorded values are the settled state.
TOLERANCE: dict[str, float] = {}


def run_case(case: dict[str, Any]) -> dict[str, float]:
    st, pts = model822.cold_start_state(), {}
    for i in range(STEPS):
        st, pts = model822.step_822(st, i, overrides=case.get("overrides"), knobs=case.get("knobs"))
    return pts


def record() -> int:
    BASELINE.parent.mkdir(parents=True, exist_ok=True)
    data = {name: run_case(case) for name, case in CASES.items()}
    BASELINE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"recorded {len(data)} cases to {BASELINE.relative_to(ROOT)}")
    return 0


def check() -> int:
    base = json.loads(BASELINE.read_text(encoding="utf-8"))
    failures: list[str] = []
    for name, case in CASES.items():
        got, want, tol = run_case(case), base[name], TOLERANCE.get(name, 0.0)
        if set(got) != set(want):
            failures.append(f"{name}: point set changed ({len(set(got) ^ set(want))} names differ)")
            continue
        worst = 0.0
        for point, w in want.items():
            g = got[point]
            diff = abs(float(g) - float(w))
            worst = max(worst, diff)
            if (tol == 0.0 and g != w) or diff > tol:
                failures.append(f"{name}: {point} {w} -> {g}")
        if tol:
            print(f"  {name}: max drift {worst:.4f} (tolerance {tol})")
    if failures:
        print(f"model822 regression FAILED ({len(failures)} differences):")
        for line in failures[:20]:
            print("  " + line)
        return 1
    print(f"model822 regression: {len(CASES)} cases match baseline")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--record", action="store_true")
    group.add_argument("--check", action="store_true")
    args = ap.parse_args()
    return record() if args.record else check()


if __name__ == "__main__":
    sys.exit(main())
