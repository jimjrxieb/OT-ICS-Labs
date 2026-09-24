#!/usr/bin/env python3
"""Field verification instruments for Building 822 -- the DDC technician's
mechanical/electrical tools, as opposed to the BAS dashboard.

Every instrument answers exactly ONE question, matching how a real tech
actually works a call:

    measure-signal EQUIPMENT   "Did the controller actually send the signal?"
                               (a multimeter at the actuator terminals)
    verify-travel  EQUIPMENT   "Did the actuator physically move?"
                               (visual inspection / travel verification)
    read-gauge                 "What is the loop pressure at the pump suction?"
                               (field gauge -- there is no BAS point for it)
    clamp-amps     P1|P2       "Is the pump motor actually loaded?"
                               (clamp meter at the motor leads)
    walk-pumproom              "What do I see when I walk in?"
    inspect-valve  P1_TDV|P2_TDV  "What does this valve body look like?"

measure-signal reads the COMMANDED value from the live points file and
computes what a multimeter would read, given that equipment's configured
signal type. It never touches the hidden ground-truth file -- a multimeter
cannot see inside a stuck linkage, only at the wire.

verify-travel reads ONLY the hidden ground-truth file
(data/output/.822-ground-truth.json, written by bas_sim.py, never surfaced
through /api/points, /tracer, or the BACnet server). It never touches command,
feedback, or signal voltage -- physically looking at a damper tells you where
the damper is, nothing about what the controller thinks or asked for.

This separation is deliberate: a trainee must choose which question to ask
and interpret the answer, not read one dashboard that answers everything.

Usage:
  python3 scripts/field-verify.py measure-signal MAU04
  python3 scripts/field-verify.py verify-travel MAU04
  python3 scripts/field-verify.py read-gauge
  python3 scripts/field-verify.py clamp-amps P1
  python3 scripts/field-verify.py walk-pumproom
  python3 scripts/field-verify.py inspect-valve P1_TDV
  python3 scripts/field-verify.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "simulator"))
import model822  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "output"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(
            f"{path.name} not found -- run the simulator first: "
            f"python3 simulator/bas_sim.py --scenario normal --steps 12") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{path.name} is unreadable: {exc}") from None


def measure_signal(equipment: str) -> None:
    """Multimeter at the actuator terminals: reads what the controller
    actually SENT, derived from command. Cannot see the physical result."""
    key = f"{equipment}_CHW_VLV"
    signal_type = model822.ACTUATOR_SIGNAL_TYPE.get(key)
    if signal_type is None:
        raise SystemExit(
            f"No signal type configured for {equipment!r}'s CHW valve actuator. "
            f"Configured equipment: {sorted(k.removesuffix('_CHW_VLV') for k in model822.ACTUATOR_SIGNAL_TYPE)}")
    points = _load_json(OUTPUT_DIR / "latest_points.json").get("points", {})
    cmd_point = f"{equipment}_CHW_VLV_CMD"
    if cmd_point not in points:
        raise SystemExit(f"{cmd_point!r} not in latest_points.json")
    command = float(points[cmd_point])
    volts = model822.control_signal_volts(command, signal_type)
    unit = "mA" if signal_type.endswith("mA") else "VDC"
    print(f"Multimeter at {equipment} CHW valve actuator terminals ({signal_type}):")
    print(f"  {volts} {unit}")
    print(f"  (commanded {command}% -- this instrument proves the controller's "
          f"output signal, nothing about whether the actuator responded)")


def verify_travel(equipment: str) -> None:
    """Visual/mechanical travel verification: reads the TRUE physical
    position. Cannot see what was commanded or what the BAS displays."""
    truth = _load_json(OUTPUT_DIR / ".822-ground-truth.json")
    key = f"{equipment}_CHW_VLV_PHYSICAL"
    if key not in truth:
        raise SystemExit(
            f"No ground truth recorded for {equipment!r}. "
            f"Known equipment: {_valve_equipment(truth)}")
    physical = truth[key]
    print(f"Field verification at {equipment} CHW valve:")
    print(f"  Actuator physically at {physical}% travel")
    print(f"  (this is what your eyes/hands confirm at the unit -- compare "
          f"against the BAS feedback and the command to find where the "
          f"signal chain broke)")


def _valve_equipment(truth: dict[str, float]) -> list[str]:
    return sorted(k.removesuffix("_CHW_VLV_PHYSICAL") for k in truth if k.endswith("_CHW_VLV_PHYSICAL"))


PLANT_TRUTH_KEYS = (
    "CHW822_LOOP_PSIG_PHYSICAL", "CHW822_P1_AMPS_PHYSICAL", "CHW822_P2_AMPS_PHYSICAL",
    "CHW822_P1_TDV_LEAK_GPM_PHYSICAL", "CHW822_P1_TDV_FAILED_PHYSICAL", "PUMPROOM_WATER_GAL_PHYSICAL",
)


def _missing_plant_keys(truth: dict[str, float]) -> list[str]:
    return [k for k in PLANT_TRUTH_KEYS if k not in truth]


def _plant_truth() -> dict[str, float]:
    """Ground truth for the plant instruments. A truth file written before the
    plant model existed lacks these keys -- say how to fix it, don't traceback."""
    truth = _load_json(OUTPUT_DIR / ".822-ground-truth.json")
    if _missing_plant_keys(truth):
        raise SystemExit(
            "No plant ground truth recorded yet -- run the simulator first: "
            "python3 simulator/bas_sim.py --scenario normal --steps 12")
    return truth


def gauge_reading(truth: dict[str, float]) -> str:
    return f"Pump suction gauge reads {truth['CHW822_LOOP_PSIG_PHYSICAL']:.1f} psig."


def amps_reading(truth: dict[str, float], pump: str) -> str:
    amps = truth[f"CHW822_{pump}_AMPS_PHYSICAL"]
    return f"CHW822_{pump} motor: {amps:.1f} A (nameplate FLA {model822.TUNING['PUMP_FLA_AMPS']:.1f} A)."


def pumproom_walk(truth: dict[str, float]) -> str:
    gal = truth["PUMPROOM_WATER_GAL_PHYSICAL"]
    if gal < 0.5:
        return "Pump room floor is dry."
    if gal < 15.0:
        return "Wet floor around the P1 pump base; no standing water yet."
    return ("Standing water on the floor, spreading from the P1 branch piping "
            "toward the P1 motor and its local disconnect.")


def valve_inspection(truth: dict[str, float], valve: str) -> str:
    if valve == "P1_TDV" and truth["CHW822_P1_TDV_FAILED_PHYSICAL"]:
        leak = truth["CHW822_P1_TDV_LEAK_GPM_PHYSICAL"]
        if leak <= 0.0:
            state = "not leaking right now (no pressure behind it)"
        elif leak < 0.5:
            state = "slow drip from the body"
        else:
            state = "steady stream of water from the body"
        return f"{valve}: corrosion through the valve body; {state}."
    return f"{valve}: body dry, no visible corrosion."


def _truth(**overrides: float) -> dict[str, float]:
    base = {"CHW822_LOOP_PSIG_PHYSICAL": 15.0, "CHW822_P1_AMPS_PHYSICAL": 12.0,
            "CHW822_P2_AMPS_PHYSICAL": 0.0, "CHW822_P1_TDV_LEAK_GPM_PHYSICAL": 0.0,
            "CHW822_P1_TDV_FAILED_PHYSICAL": 0.0, "PUMPROOM_WATER_GAL_PHYSICAL": 0.0,
            "MAU04_CHW_VLV_PHYSICAL": 40.0}
    base.update(overrides)
    return base


def self_test() -> int:
    healthy = _truth()
    assert gauge_reading(healthy) == "Pump suction gauge reads 15.0 psig."
    assert amps_reading(healthy, "P1") == "CHW822_P1 motor: 12.0 A (nameplate FLA 12.0 A)."
    assert amps_reading(healthy, "P2") == "CHW822_P2 motor: 0.0 A (nameplate FLA 12.0 A)."
    assert pumproom_walk(healthy) == "Pump room floor is dry."
    assert valve_inspection(healthy, "P1_TDV") == "P1_TDV: body dry, no visible corrosion."
    assert valve_inspection(healthy, "P2_TDV") == "P2_TDV: body dry, no visible corrosion."

    wet = _truth(PUMPROOM_WATER_GAL_PHYSICAL=8.0)
    assert pumproom_walk(wet) == "Wet floor around the P1 pump base; no standing water yet."
    flooded = _truth(PUMPROOM_WATER_GAL_PHYSICAL=110.0)
    assert "Standing water" in pumproom_walk(flooded)
    assert "P1 motor and its local disconnect" in pumproom_walk(flooded)

    leaking = _truth(CHW822_P1_TDV_LEAK_GPM_PHYSICAL=1.2, CHW822_P1_TDV_FAILED_PHYSICAL=1.0)
    assert valve_inspection(leaking, "P1_TDV") == \
        "P1_TDV: corrosion through the valve body; steady stream of water from the body."
    dripping = _truth(CHW822_P1_TDV_LEAK_GPM_PHYSICAL=0.2, CHW822_P1_TDV_FAILED_PHYSICAL=1.0)
    assert valve_inspection(dripping, "P1_TDV") == \
        "P1_TDV: corrosion through the valve body; slow drip from the body."
    isolated = _truth(CHW822_P1_TDV_LEAK_GPM_PHYSICAL=0.0, CHW822_P1_TDV_FAILED_PHYSICAL=1.0)
    assert valve_inspection(isolated, "P1_TDV") == \
        "P1_TDV: corrosion through the valve body; not leaking right now (no pressure behind it)."
    assert valve_inspection(leaking, "P2_TDV") == "P2_TDV: body dry, no visible corrosion."

    # Instruments must refuse a truth file that predates the plant model, not traceback.
    assert _missing_plant_keys(healthy) == []
    assert _missing_plant_keys({"MAU04_CHW_VLV_PHYSICAL": 40.0}) == list(PLANT_TRUTH_KEYS)

    # verify-travel's "known equipment" list must ignore the new plant keys.
    assert _valve_equipment(healthy) == ["MAU04"]
    print("field-verify self-test passed")
    return 0


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if "--self-test" in argv:
        return self_test()
    parser = argparse.ArgumentParser(description="Building 822 field verification instruments")
    sub = parser.add_subparsers(dest="action", required=True)
    for name, fn, help_text in (
        ("measure-signal", measure_signal, "Multimeter: did the controller send the signal?"),
        ("verify-travel", verify_travel, "Visual/travel check: did the actuator physically move?"),
    ):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("equipment", help="e.g. MAU04")
        p.set_defaults(run=lambda a, fn=fn: fn(a.equipment))
    sub.add_parser("read-gauge", help="Loop pressure at the pump suction (field gauge)").set_defaults(
        run=lambda a: print(gauge_reading(_plant_truth())))
    p = sub.add_parser("clamp-amps", help="Clamp meter on a CHW pump motor")
    p.add_argument("pump", choices=("P1", "P2"))
    p.set_defaults(run=lambda a: print(amps_reading(_plant_truth(), a.pump)))
    sub.add_parser("walk-pumproom", help="Walk into the pump room and look").set_defaults(
        run=lambda a: print(pumproom_walk(_plant_truth())))
    p = sub.add_parser("inspect-valve", help="Look at a CHW branch valve body")
    p.add_argument("valve", choices=("P1_TDV", "P2_TDV"))
    p.set_defaults(run=lambda a: print(valve_inspection(_plant_truth(), a.valve)))
    args = parser.parse_args(argv)
    args.run(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
