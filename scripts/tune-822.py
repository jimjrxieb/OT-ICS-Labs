#!/usr/bin/env python3
"""Calibration harness for the Building 822 model.

    python3 scripts/tune-822.py --check                 # gate: pass/fail vs targets
    python3 scripts/tune-822.py --sweep HALL_INFIL_CFM 5 10 15 25 40
    python3 scripts/tune-822.py --report                # full picture, healthy + degraded

Sweeps a single TUNING constant and reports the calibration measures, so the
remaining gaps get closed by measurement rather than guesswork.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulator"))

import model822 as m  # noqa: E402

SETTLE_STEPS = 150

TARGETS = {
    "sat_f": (62.0, 68.0, "MAU supply air mid-60s"),
    "bldg_dt_f": (10.0, 12.0, "building CHW delta-T 10-12"),
    "ewt_f": (43.9, 44.1, "entering CHW at 44"),
    "valve_pct": (40.0, 90.0, "valve modulating, not pegged"),
    "hall_rh_pct": (58.0, 65.0, "corridor RH low-60s"),
}


def settle(steps: int = SETTLE_STEPS, **kw) -> dict[str, float]:
    state = m.cold_start_state()
    pts: dict[str, float] = {}
    for i in range(steps):
        state, pts = m.step_822(state, i, **kw)
    return pts


def measures(pts: dict[str, float]) -> dict[str, float]:
    maus = [k for k in pts if k.endswith("_SAT") and k.startswith("MAU")]
    halls = [k for k in pts if k.startswith("HALL_") and k.endswith("_RH")]
    valves = [k for k in pts if k.startswith("MAU") and k.endswith("_CHW_VLV_CMD")]
    return {
        "sat_f": sum(pts[k] for k in maus) / len(maus),
        "bldg_dt_f": pts["CHW822_BLDG_DT"],
        "ewt_f": pts["CHW822_ENT_SUP_TEMP"],
        "valve_pct": sum(pts[k] for k in valves) / len(valves),
        "hall_rh_pct": sum(pts[k] for k in halls) / len(halls),
    }


def check() -> int:
    got = measures(settle())
    failed = 0
    for key, (lo, hi, label) in TARGETS.items():
        value = got[key]
        ok = lo <= value <= hi
        failed += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:34s} {value:7.2f}  (want {lo}-{hi})")

    degraded = measures(settle(knobs={"CHW-822": {"strainer_resistance": 0.85}}))
    dt = degraded["bldg_dt_f"]
    ok = 2.0 <= dt <= 5.0
    failed += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {'degraded dT collapses to 2-5':34s} {dt:7.2f}")

    print("CALIBRATION PASS" if not failed else f"CALIBRATION FAIL ({failed} measures)")
    return 0 if not failed else 1


def sweep(name: str, values: list[float]) -> int:
    if name not in m.TUNING:
        raise SystemExit(f"Unknown tuning constant {name!r}. Options: {sorted(m.TUNING)}")
    original = m.TUNING[name]
    print(f"{name} sweep (original {original}):")
    print(f"  {'value':>10} {'SAT':>7} {'dT':>7} {'EWT':>7} {'valve':>7} {'hallRH':>7}")
    for v in values:
        m.TUNING[name] = v
        g = measures(settle())
        print(f"  {v:>10.3f} {g['sat_f']:7.2f} {g['bldg_dt_f']:7.2f} {g['ewt_f']:7.2f} "
              f"{g['valve_pct']:7.2f} {g['hall_rh_pct']:7.2f}")
    m.TUNING[name] = original
    return 0


def report() -> int:
    cases = [
        ("healthy design_summer", {}),
        ("healthy shoulder", {"profile": "shoulder"}),
        ("coil_fouling .60", {"knobs": {"MAU01": {"coil_fouling": 0.60}}}),
        ("air_bound", {"knobs": {"MAU01": {"air_bound": True}}}),
        ("strainer .85", {"knobs": {"CHW-822": {"strainer_resistance": 0.85}}}),
        ("cond_fouling .50", {"knobs": {"CHILLER-RTAC-822": {"condenser_fouling": 0.50}}}),
    ]
    print(f"  {'case':26s} {'SAT':>7} {'dT':>7} {'EWT':>7} {'valve':>7} {'hallRH':>7}")
    for label, kw in cases:
        g = measures(settle(**kw))
        print(f"  {label:26s} {g['sat_f']:7.2f} {g['bldg_dt_f']:7.2f} {g['ewt_f']:7.2f} "
              f"{g['valve_pct']:7.2f} {g['hall_rh_pct']:7.2f}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Building 822 calibration harness")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sweep", nargs="+", metavar=("NAME", "VALUE"))
    args = ap.parse_args(argv[1:])
    if args.sweep:
        return sweep(args.sweep[0], [float(v) for v in args.sweep[1:]])
    if args.report:
        return report()
    return check()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
