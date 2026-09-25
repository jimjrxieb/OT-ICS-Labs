"""Field observations for Building 822: what a technician's instruments and
eyes report, worded from model822.ground_truth_snapshot().

Pure functions, no files. Shared by scripts/field-verify.py (CLI) and
simulator/scenario_kernel.py (S-001 sessions), so both describe the plant
the same way.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model822  # noqa: E402

WET_FLOOR_GAL = 0.5          # below this the pump-room floor reads dry
STANDING_WATER_GAL = 15.0    # at or above this there is standing water (S-001's hazard threshold)

PLANT_TRUTH_KEYS = (
    "CHW822_LOOP_PSIG_PHYSICAL", "CHW822_P1_AMPS_PHYSICAL", "CHW822_P2_AMPS_PHYSICAL",
    "CHW822_P1_TDV_LEAK_GPM_PHYSICAL", "CHW822_P1_TDV_FAILED_PHYSICAL", "PUMPROOM_WATER_GAL_PHYSICAL",
)


def missing_plant_keys(truth: dict[str, float]) -> list[str]:
    return [k for k in PLANT_TRUTH_KEYS if k not in truth]


def valve_equipment(truth: dict[str, float]) -> list[str]:
    return sorted(k.removesuffix("_CHW_VLV_PHYSICAL") for k in truth if k.endswith("_CHW_VLV_PHYSICAL"))


def gauge_reading(truth: dict[str, float]) -> str:
    return f"Pump suction gauge reads {truth['CHW822_LOOP_PSIG_PHYSICAL']:.1f} psig."


def amps_reading(truth: dict[str, float], pump: str) -> str:
    amps = truth[f"CHW822_{pump}_AMPS_PHYSICAL"]
    return f"CHW822_{pump} motor: {amps:.1f} A (nameplate FLA {model822.TUNING['PUMP_FLA_AMPS']:.1f} A)."


def pumproom_walk(truth: dict[str, float]) -> str:
    gal = truth["PUMPROOM_WATER_GAL_PHYSICAL"]
    if gal < WET_FLOOR_GAL:
        return "Pump room floor is dry."
    if gal < STANDING_WATER_GAL:
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


def travel_reading(truth: dict[str, float], equipment: str) -> str:
    physical = truth[f"{equipment}_CHW_VLV_PHYSICAL"]
    return f"{equipment} CHW valve: actuator physically at {physical:.1f}% travel."
