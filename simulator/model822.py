#!/usr/bin/env python3
"""Building 822 coupled state model.

Chain: weather -> chiller -> CHW loop -> coil (sensible + latent) -> space.

Teaching-grade, not engineering-grade: the numbers move correctly and for the
right reasons. This is not a load calculation and must never be presented as
one. Standard library only.

Every tuning constant lives in TUNING so scripts/tune-822.py can sweep them
without editing physics code.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import psychro as ps  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
OUTPUT_DIR = ROOT / "data" / "output"
STATE_FILE = OUTPUT_DIR / "state_822.json"

FACILITY = "barracks822"
STEP_MINUTES = 1

# --- tuning constants -------------------------------------------------------
# Values converged against J's field observations in prototype; see the
# calibration task. Do not scatter magic numbers through the physics.
TUNING: dict[str, float] = {
    "MAU_CFM": 700.0,
    "FCU_CFM": 400.0,
    "MAU_COIL_MAX_BTUH": 34000.0,
    "FCU_COIL_MAX_BTUH": 9000.0,
    "COIL_BASE_APPROACH": 3.0,
    "COIL_APPROACH_PENALTY": 50.0,
    "AIR_BOUND_CAPACITY_FACTOR": 0.30,  # how much capacity an air-bound coil keeps
    "COIL_BASE_BF": 0.08,
    "COIL_BF_PENALTY": 0.90,
    "CHW_GPM_DESIGN": 80.0,
    "CHILLER_TONS": 155.0,
    "CAMPUS_BASE_TONS": 70.0,
    "CHW_SETPOINT_F": 44.0,
    "CHILLER_DERATE_PER_F": 0.010,      # capacity lost per F of ambient above the knee
    "CHILLER_OVERLOAD_SLOPE": 60.0,     # how fast leaving water rises once overloaded
    "CHILLER_EVAP_RISE_F": 10.0,        # nominal evaporator entering-minus-leaving
    "KP": 1.2,
    "KI": 0.25,
    "DEADBAND_F": 0.5,
    "ACTUATOR_SLEW_PCT": 5.0,
    "UA_ROOM": 70.0,
    "Q_INT_ROOM": 1500.0,
    "C_ROOM": 6000.0,
    "ROOM_LATENT_BTUH": 450.0,
    "UA_HALL": 60.0,
    "Q_INT_HALL": 600.0,
    "C_HALL": 9000.0,
    "HALL_INFIL_CFM": 25.0,
    "HALL_SUPPLY_FRACTION": 0.30,
    "AIR_LB_PER_CF": 0.075,
}

DEFAULT_WEATHER = (78.0, 60.0)


def load_weather(profile: str = "design_summer") -> list[tuple[float, float]]:
    """Return 24 hourly (dry bulb F, RH %) pairs. Falls back rather than crashing."""
    path = INPUT_DIR / "weather_822.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        hourly = data["profiles"][profile]["hourly"]
    except (OSError, KeyError, json.JSONDecodeError) as exc:
        print(f"model822: weather profile {profile!r} unavailable ({exc}); "
              f"using fixed {DEFAULT_WEATHER[0]}F/{DEFAULT_WEATHER[1]}%", file=sys.stderr)
        return [DEFAULT_WEATHER] * 24
    if len(hourly) != 24:
        print(f"model822: weather profile {profile!r} has {len(hourly)} hours, expected 24; "
              f"using fixed fallback", file=sys.stderr)
        return [DEFAULT_WEATHER] * 24
    return [(float(t), float(rh)) for t, rh in hourly]


def weather_at(profile: str, step: int) -> tuple[float, float]:
    """Weather for a simulation step. Steps are STEP_MINUTES apart, starting at noon."""
    hourly = load_weather(profile)
    hour = (12 + (step * STEP_MINUTES) // 60) % 24
    return hourly[hour]


# --- chiller ----------------------------------------------------------------

CHILLER_KNOB_DEFAULTS: dict[str, Any] = {
    "condenser_fouling": 0.0,     # 0..1
    "capacity_limit": 1.0,        # 0..1
    "condenser_fan_failed": [],   # list of circuit numbers, e.g. [1]
    "circuit_locked_out": [],     # list of circuit numbers
}


def chiller_step(load_tons: float, ambient_f: float,
                 knobs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Air-cooled RTAC. Capacity derates with ambient; leaving water drifts up
    when load exceeds what the machine can make.

    This is the causal origin of warm entering water. Spec 1 ships every knob
    healthy, so leaving water holds setpoint.
    """
    k = {**CHILLER_KNOB_DEFAULTS, **(knobs or {})}
    sp = TUNING["CHW_SETPOINT_F"]
    nominal = TUNING["CHILLER_TONS"]

    # Air-cooled: rejection gets harder as ambient rises. 1% per F above 85F.
    derate = max(0.60, 1.0 - max(0.0, ambient_f - 85.0) * TUNING["CHILLER_DERATE_PER_F"])

    fans_failed = len(k["condenser_fan_failed"])
    ckts_out = len(k["circuit_locked_out"])
    available = (nominal * derate
                 * (1.0 - float(k["condenser_fouling"]))
                 * float(k["capacity_limit"])
                 * (1.0 - 0.5 * ckts_out)
                 * (1.0 - 0.25 * fans_failed))
    available = max(0.0, available)

    if available <= 0.0:
        lwt, pct = sp + 25.0, 0.0
    elif load_tons <= available:
        lwt, pct = sp, min(100.0, 100.0 * load_tons / available)
    else:
        lwt, pct = sp + (load_tons - available) / nominal * TUNING["CHILLER_OVERLOAD_SLOPE"], 100.0

    if ckts_out:
        diag = "CircuitLockout"
    elif fans_failed:
        diag = "CondFanFail"
    elif lwt > sp + 3.0:
        diag = "LowEvapTemp"     # machine is not holding setpoint
    else:
        diag = "None"

    return {
        "lwt_f": round(lwt, 2),
        "ewt_f": round(lwt + TUNING["CHILLER_EVAP_RISE_F"], 2),      # nominal evaporator rise
        "pct_capacity": round(pct, 1),
        "available_tons": round(available, 1),
        "load_tons": round(load_tons, 1),
        "ambient_f": round(ambient_f, 1),
        "ckt1_on": 1 not in k["circuit_locked_out"],
        "ckt2_on": 2 not in k["circuit_locked_out"],
        "ckt1_fan_ok": 1 not in k["condenser_fan_failed"],
        "ckt2_fan_ok": 2 not in k["condenser_fan_failed"],
        "active_diag": diag,
    }


# --- chilled water loop -----------------------------------------------------

CHW_KNOB_DEFAULTS: dict[str, Any] = {
    "strainer_resistance": 0.0,   # 0..1, fraction of flow lost
    "p1_running": True,
    "p2_running": False,
}


def chw_loop(entering_f: float, total_btuh: float,
             knobs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Three-way valves at the coils, so building flow is roughly constant and
    the valves modulate mixing.

    That distinction matters diagnostically: a failed three-way gives you full
    flow and no cooling, which must not look like no flow at all.
    """
    k = {**CHW_KNOB_DEFAULTS, **(knobs or {})}
    pumping = bool(k["p1_running"]) or bool(k["p2_running"])
    flow_frac = (1.0 - float(k["strainer_resistance"])) if pumping else 0.0
    flow_frac = max(0.0, min(1.0, flow_frac))
    gpm = TUNING["CHW_GPM_DESIGN"] * flow_frac

    delta_t = total_btuh / (500.0 * gpm) if gpm > 0.0 else 0.0
    # A restricted strainer shows up as pressure drop across it, and as reduced
    # differential pressure across the building.
    strainer_dp = 1.5 + 9.0 * float(k["strainer_resistance"]) ** 2
    bldg_dp = 11.0 * flow_frac ** 2

    return {
        "gpm": round(gpm, 1),
        "flow_frac": round(flow_frac, 4),
        "supply_f": round(entering_f, 2),
        "return_f": round(entering_f + delta_t, 2),
        "delta_t_f": round(delta_t, 2),
        "strainer_dp_psid": round(strainer_dp, 2),
        "bldg_dp_psid": round(bldg_dp, 2),
    }


# --- cooling coil -----------------------------------------------------------

COIL_KNOB_DEFAULTS: dict[str, Any] = {
    "coil_fouling": 0.0,             # 0..1
    "air_bound": False,              # air trapped in the tubes
    "valve_authority": 1.0,          # 0..1, command-to-flow gain
    "three_way_position_error": 0.0, # 0..1, mixing wrong despite full flow
    "actuator_stuck_at": None,       # 0..100 or None; physical position pinned here
                                      # regardless of command -- a stuck actuator/linkage
    "feedback_stuck_at": None,       # 0..100 or None; BAS-displayed feedback pinned here
                                      # regardless of physical position -- a failed
                                      # feedback pot/switch, independent of the actuator
}

# Control signal type per equipment -- the electrical signal a multimeter would
# read at the actuator terminals, driven by command. This is a field-verification
# concept, not a stored point: it is derived on demand, never persisted or
# exposed over BACnet. Not every actuator uses the same signal convention, so
# this is configurable per device rather than a single global assumption.
ACTUATOR_SIGNAL_TYPE: dict[str, str] = {f"MAU{i:02d}_CHW_VLV": "2-10V" for i in range(1, 14)}

SIGNAL_RANGES: dict[str, tuple[float, float]] = {
    "0-10V": (0.0, 10.0),
    "2-10V": (2.0, 10.0),
    "4-20mA": (4.0, 20.0),
}


def control_signal_volts(command_pct: float, signal_type: str) -> float:
    """The field-measurable output signal for a given command, in the signal's
    own native unit (volts for V types, milliamps for 4-20mA).

    Deliberately does not attempt floating/tri-state or digital/network
    commands -- those have no single scalar a multimeter reads, and pretending
    otherwise would teach the wrong instinct. Raises rather than guess.
    """
    if signal_type not in SIGNAL_RANGES:
        raise ValueError(
            f"signal_type {signal_type!r} has no scalar field measurement "
            f"(supported: {sorted(SIGNAL_RANGES)}; floating/tri-state and "
            f"digital/network commands are not modeled)")
    lo, hi = SIGNAL_RANGES[signal_type]
    pct = max(0.0, min(100.0, command_pct))
    return round(lo + (hi - lo) * pct / 100.0, 2)


def ground_truth_snapshot(state: dict[str, Any]) -> dict[str, float]:
    """Hidden physical-position values, keyed with a _PHYSICAL suffix that is
    never a real point name and never appears in points.json or over BACnet.

    This is the field-verification channel: the only way to see it is an
    explicit field action (scripts/field-verify.py), matching the rule that a
    trainee must walk out and look, not read it off the dashboard. Reads
    `physical_valve_pct` defensively so a state file saved before this field
    existed does not crash -- it falls back to the commanded value, i.e. "no
    fault recorded yet," which is correct for an old, healthy state.
    """
    out: dict[str, float] = {}
    for mau, st in state.get("mau", {}).items():
        out[f"{mau}_CHW_VLV_PHYSICAL"] = round(
            float(st.get("physical_valve_pct", st.get("valve_pct", 0.0))), 1)
    return out


def coil_step(t_ent_f: float, rh_ent_pct: float, entering_water_f: float,
              valve_pct: float, flow_frac: float, cfm: float,
              q_max_btuh: float, knobs: dict[str, Any] | None = None) -> dict[str, Any]:
    """Bypass-factor / apparatus-dew-point cooling coil.

    Capacity fraction cf collapses everything that can weaken the coil into one
    number. As cf falls the apparatus dew point rises toward the entering air
    and the bypass factor rises toward 1, so leaving air approaches entering
    air -- the physical meaning of "commanded cooling, weak response".

    The finite q_max is what makes an over-open damper hurt: past the coil's
    capacity the air leaves both warmer AND wetter, which is the mechanism
    behind high corridor humidity.
    """
    k = {**COIL_KNOB_DEFAULTS, **(knobs or {})}
    w_ent = ps.humidity_ratio(t_ent_f, rh_ent_pct)

    valve_frac = max(0.0, min(1.0, valve_pct / 100.0)) * float(k["valve_authority"])
    valve_frac = max(0.0, valve_frac - float(k["three_way_position_error"]))
    cf = valve_frac * flow_frac * (1.0 - float(k["coil_fouling"]))
    if k["air_bound"]:
        cf *= TUNING["AIR_BOUND_CAPACITY_FACTOR"]
    cf = max(0.0, min(1.0, cf))

    approach = TUNING["COIL_BASE_APPROACH"] + (1.0 - cf) * TUNING["COIL_APPROACH_PENALTY"]
    adp = min(entering_water_f + approach, t_ent_f)     # a coil cannot heat the air
    bf = min(0.98, TUNING["COIL_BASE_BF"] + (1.0 - cf) * TUNING["COIL_BF_PENALTY"])

    t_lvg = adp + bf * (t_ent_f - adp)
    w_adp = ps.humidity_ratio_saturated(adp)
    # Dry coil when entering air is already drier than saturation at the ADP.
    w_lvg = w_ent if w_ent <= w_adp else w_adp + bf * (w_ent - w_adp)

    mdot = cfm * 60.0 * TUNING["AIR_LB_PER_CF"]         # lb dry air per hour
    q_total = max(0.0, mdot * (ps.enthalpy(t_ent_f, w_ent) - ps.enthalpy(t_lvg, w_lvg)))

    if q_max_btuh and q_total > q_max_btuh:
        scale = q_max_btuh / q_total
        t_lvg = t_ent_f - (t_ent_f - t_lvg) * scale
        w_lvg = w_ent - (w_ent - w_lvg) * scale
        q_total = q_max_btuh

    q_sens = max(0.0, mdot * 0.240 * (t_ent_f - t_lvg))
    return {
        "t_lvg_f": t_lvg,
        "rh_lvg_pct": ps.rh_from_w(t_lvg, w_lvg),
        "w_lvg": w_lvg,
        "q_total_btuh": q_total,
        "q_sensible_btuh": q_sens,
        "q_latent_btuh": max(0.0, q_total - q_sens),
        "adp_f": adp,
        "bypass_factor": bf,
        "capacity_fraction": cf,
    }


def mix_air(t1_f: float, rh1_pct: float, t2_f: float, w2: float,
            frac1: float) -> tuple[float, float]:
    """Mix two air streams by mass fraction. Returns (dry bulb F, RH %)."""
    w = frac1 * ps.humidity_ratio(t1_f, rh1_pct) + (1.0 - frac1) * w2
    t = frac1 * t1_f + (1.0 - frac1) * t2_f
    return t, ps.rh_from_w(t, w)


# --- building identity ------------------------------------------------------

WINGS = ("A", "B", "C", "D")
FLOORS = (1, 2, 3)
ROOMS = (1, 2, 3)

MAU_IDS = [f"MAU{i:02d}" for i in range(1, 14)]
FCU_IDS = [f"FCU_{w}{f}{r:02d}" for w in WINGS for f in FLOORS for r in ROOMS]
HALL_IDS = [f"HALL_{w}{f}" for w in WINGS for f in FLOORS]

# MAU-01..12 serve wing/floor in order; MAU-13 serves the lobby.
MAU_SERVES: dict[str, tuple[str, int]] = {}
_i = 1
for _w in WINGS:
    for _f in FLOORS:
        MAU_SERVES[f"MAU{_i:02d}"] = (_w, _f)
        _i += 1
MAU_SERVES["MAU13"] = ("LOBBY", 1)

# Which MAU feeds which corridor and which rooms.
HALL_MAU = {f"HALL_{w}{f}": mau for mau, (w, f) in MAU_SERVES.items() if w != "LOBBY"}
FCU_MAU = {
    f"FCU_{w}{f}{r:02d}": mau
    for mau, (w, f) in MAU_SERVES.items() if w != "LOBBY"
    for r in ROOMS
}


def cold_start_state() -> dict[str, Any]:
    """Healthy defaults. Used on first run and whenever the state file is unusable."""
    return {
        "version": 1,
        "step": 0,
        "mau": {m: {"valve_pct": 45.0, "integral": 0.0, "sat_f": 65.0,
                    "damper_pct": 50.0, "fan_on": True, "sat_sp_f": 65.0}
                for m in MAU_IDS},
        "fcu": {f: {"valve_pct": 45.0, "integral": 0.0,
                    "space_t_f": 74.0, "space_w": ps.humidity_ratio(74.0, 55.0),
                    "space_sp_f": 73.0, "fan_mode": 1}
                for f in FCU_IDS},
        "hall": {h: {"t_f": 75.0, "w": ps.humidity_ratio(75.0, 60.0)} for h in HALL_IDS},
        "chw": {"entering_f": TUNING["CHW_SETPOINT_F"]},
    }


def load_state() -> dict[str, Any]:
    """Never crash on a bad state file — cold start and say so."""
    try:
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return cold_start_state()
    except (OSError, json.JSONDecodeError) as exc:
        print(f"model822: state file unusable ({exc}); cold starting", file=sys.stderr)
        return cold_start_state()
    if state.get("version") != 1 or "mau" not in state:
        print("model822: state file schema mismatch; cold starting", file=sys.stderr)
        return cold_start_state()
    return state


def save_state(state: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# --- control ----------------------------------------------------------------

FAN_MODE_FLOW = {0: 0.0, 1: 0.65, 2: 0.35, 3: 0.65, 4: 1.0}  # Off/Auto/Low/Mid/High


def pi_valve(measured_f: float, setpoint_f: float, integral: float,
             current_valve_pct: float) -> tuple[float, float]:
    """Cooling PI loop with deadband, conditional anti-windup, and actuator slew.

    Returns (new_valve_pct, new_integral).

    The slew limit is not cosmetic. Without it the loop limit-cycles 0<->100:
    the coil responds within one step and the capacity limit makes plant gain
    very high near crossover. Real actuators stroke over 90-150 seconds, so
    rate limiting is both the physical truth and the stability fix.
    """
    err = measured_f - setpoint_f
    if abs(err) < TUNING["DEADBAND_F"]:
        err = 0.0
    kp, ki = TUNING["KP"], TUNING["KI"]
    raw = kp * err + ki * (integral + err)
    # Conditional integration: stop winding only when pushing further into a stop.
    if not ((raw >= 100.0 and err > 0.0) or (raw <= 0.0 and err < 0.0)):
        integral += err
    target = max(0.0, min(100.0, kp * err + ki * integral))
    slew = TUNING["ACTUATOR_SLEW_PCT"]
    new_valve = current_valve_pct + max(-slew, min(slew, target - current_valve_pct))
    return max(0.0, min(100.0, new_valve)), integral


# --- step -------------------------------------------------------------------

def _knobs_for(knobs: dict[str, Any], device: str) -> dict[str, Any]:
    """Per-device knob overlay on top of the global defaults. Spec 1 ships empty."""
    merged = dict(knobs.get("_all", {}))
    merged.update(knobs.get(device, {}))
    return merged


def step_822(state: dict[str, Any], step: int, profile: str = "design_summer",
             overrides: dict[str, Any] | None = None,
             knobs: dict[str, Any] | None = None) -> tuple[dict[str, Any], dict[str, float]]:
    """Advance the building one step. Returns (new_state, point values)."""
    overrides = overrides or {}
    knobs = knobs or {}
    oa_t, oa_rh = weather_at(profile, step)
    oa_w = ps.humidity_ratio(oa_t, oa_rh)
    pts: dict[str, float] = {}

    def ov(name: str, fallback: float) -> float:
        """Operator override wins over the control loop, for 822 points only."""
        entry = overrides.get(name)
        return float(entry["value"]) if entry else fallback

    chw_knobs = _knobs_for(knobs, "CHW-822")
    flow_frac = 0.0 if not (chw_knobs.get("p1_running", True)
                            or chw_knobs.get("p2_running", False)) else \
        max(0.0, 1.0 - float(chw_knobs.get("strainer_resistance", 0.0)))
    entering_f = float(state["chw"]["entering_f"])

    # --- MAUs ---------------------------------------------------------------
    total_btuh = 0.0
    for mau in MAU_IDS:
        st = state["mau"][mau]
        k = _knobs_for(knobs, mau)
        damper = ov(f"{mau}_OA_DMPR_CMD", st["damper_pct"])
        sp = ov(f"{mau}_SAT_SP", st["sat_sp_f"])
        fan_on = bool(ov(f"{mau}_FAN_CMD", 1.0 if st["fan_on"] else 0.0))

        wing, floor = MAU_SERVES[mau]
        ret_key = f"HALL_{wing}{floor}" if wing != "LOBBY" else "HALL_A1"
        ret_t = state["hall"][ret_key]["t_f"]
        ret_w = state["hall"][ret_key]["w"]
        t_ent, rh_ent = mix_air(oa_t, oa_rh, ret_t, ret_w, max(0.0, min(1.0, damper / 100.0)))

        cmd_override = overrides.get(f"{mau}_CHW_VLV_CMD")
        if cmd_override:
            command, integral = float(cmd_override["value"]), st["integral"]
        else:
            command, integral = pi_valve(st["sat_f"], sp, st["integral"], st["valve_pct"])

        # Physical position: what the actuator/linkage actually does. Normally
        # this follows command. A stuck actuator means it never gets there no
        # matter what is commanded -- the coil sees THIS value, not command.
        # The PI loop's own slew tracking (st["valve_pct"] below) still follows
        # its own commanded history, exactly like a real controller that has
        # no way to know its output isn't reaching the field -- which is why a
        # stuck actuator organically drives command to 100% over time as the
        # loop keeps asking for more of something that never arrives.
        stuck_at = k.get("actuator_stuck_at")
        physical = float(stuck_at) if stuck_at is not None else command

        # Feedback: what the BAS displays. Normally an honest read of physical
        # position. A failed feedback potentiometer/switch is an INDEPENDENT
        # failure from the actuator itself -- and the more dangerous one,
        # since the BAS then reports healthy while the field is not.
        feedback_at = k.get("feedback_stuck_at")
        feedback = float(feedback_at) if feedback_at is not None else physical

        if not fan_on:
            res = {"t_lvg_f": t_ent, "rh_lvg_pct": rh_ent, "w_lvg": ps.humidity_ratio(t_ent, rh_ent),
                   "q_total_btuh": 0.0, "q_sensible_btuh": 0.0, "q_latent_btuh": 0.0,
                   "adp_f": t_ent, "bypass_factor": 1.0, "capacity_fraction": 0.0}
        else:
            res = coil_step(t_ent, rh_ent, entering_f, physical, flow_frac,
                            TUNING["MAU_CFM"], TUNING["MAU_COIL_MAX_BTUH"], k)

        total_btuh += res["q_total_btuh"]
        st.update(valve_pct=command, integral=integral, sat_f=res["t_lvg_f"],
                  damper_pct=damper, fan_on=fan_on, sat_sp_f=sp,
                  physical_valve_pct=physical)
        st["sa_w"] = res["w_lvg"]

        offset = float(k.get("sensor_offset", 0.0))
        pts[f"{mau}_SAT"] = round(res["t_lvg_f"] + offset, 2)
        pts[f"{mau}_SAT_SP"] = round(sp, 2)
        pts[f"{mau}_SA_RH"] = round(res["rh_lvg_pct"], 1)
        pts[f"{mau}_EAT"] = round(t_ent, 2)
        pts[f"{mau}_EA_RH"] = round(rh_ent, 1)
        pts[f"{mau}_FAN_CMD"] = 1 if fan_on else 0
        pts[f"{mau}_FAN_STATUS"] = 1 if fan_on else 0
        pts[f"{mau}_OA_DMPR_CMD"] = round(damper, 1)
        pts[f"{mau}_OA_DMPR_POS"] = round(damper, 1)
        pts[f"{mau}_CHW_VLV_CMD"] = round(command, 1)
        pts[f"{mau}_CHW_VLV_POS"] = round(feedback, 1)
        pts[f"{mau}_COIL_DT"] = round(max(0.0, t_ent - res["t_lvg_f"]), 2)

    # --- FCUs and rooms -----------------------------------------------------
    for fcu in FCU_IDS:
        st = state["fcu"][fcu]
        k = _knobs_for(knobs, fcu)
        sp = ov(f"{fcu}_SPACE_TEMP_SP", st["space_sp_f"])
        mode = int(ov(f"{fcu}_FAN_MODE", st["fan_mode"]))
        flow_scale = FAN_MODE_FLOW.get(mode, 0.65)
        room_rh = ps.rh_from_w(st["space_t_f"], st["space_w"])

        cmd_override = overrides.get(f"{fcu}_CHW_VLV_CMD")
        if cmd_override:
            valve, integral = float(cmd_override["value"]), st["integral"]
        else:
            valve, integral = pi_valve(st["space_t_f"], sp, st["integral"], st["valve_pct"])

        fcu_cfm = TUNING["FCU_CFM"] * flow_scale
        res = coil_step(st["space_t_f"], room_rh, entering_f, valve, flow_frac,
                        fcu_cfm,
                        TUNING["FCU_COIL_MAX_BTUH"] * flow_scale if flow_scale else 0.0, k)
        total_btuh += res["q_total_btuh"]
        pts[f"{fcu}_CFM"] = round(fcu_cfm, 1)

        mau = FCU_MAU.get(fcu, "MAU01")
        sat = state["mau"][mau]["sat_f"]
        sa_w = state["mau"][mau].get("sa_w", ps.humidity_ratio(sat, 85.0))
        vent_cfm = TUNING["MAU_CFM"] * (1.0 - TUNING["HALL_SUPPLY_FRACTION"]) / 3.0
        m_vent = vent_cfm * 60.0 * TUNING["AIR_LB_PER_CF"]

        q_room = (TUNING["UA_ROOM"] * (oa_t - st["space_t_f"])
                  + TUNING["Q_INT_ROOM"]
                  + m_vent * 0.240 * (sat - st["space_t_f"])
                  - res["q_sensible_btuh"])
        new_t = st["space_t_f"] + q_room / TUNING["C_ROOM"]

        m_room = TUNING["C_ROOM"] / 0.240 * 0.6
        new_w = st["space_w"] + (m_vent * (sa_w - st["space_w"])
                                 + TUNING["ROOM_LATENT_BTUH"] / 1061.0
                                 - res["q_latent_btuh"] / 1061.0) / m_room

        st.update(valve_pct=valve, integral=integral, space_sp_f=sp, fan_mode=mode,
                  space_t_f=max(50.0, min(110.0, new_t)),
                  space_w=max(0.002, min(0.030, new_w)))

        offset = float(k.get("sensor_offset", 0.0))
        pts[f"{fcu}_SPACE_TEMP"] = round(st["space_t_f"] + offset, 2)
        pts[f"{fcu}_SPACE_TEMP_SP"] = round(sp, 2)
        pts[f"{fcu}_FAN_MODE"] = mode
        pts[f"{fcu}_FAN_STATUS"] = 1 if flow_scale > 0 else 0
        pts[f"{fcu}_CHW_VLV_CMD"] = round(valve, 1)
        pts[f"{fcu}_CHW_VLV_POS"] = round(valve, 1)

    # --- corridors ----------------------------------------------------------
    for hall in HALL_IDS:
        hst = state["hall"][hall]
        mau = HALL_MAU[hall]
        sat = state["mau"][mau]["sat_f"]
        sa_w = state["mau"][mau].get("sa_w", ps.humidity_ratio(sat, 85.0))
        rooms = [f for f, m in FCU_MAU.items() if m == mau]
        room_t = sum(state["fcu"][f]["space_t_f"] for f in rooms) / max(1, len(rooms))
        room_w = sum(state["fcu"][f]["space_w"] for f in rooms) / max(1, len(rooms))

        m_supply = TUNING["MAU_CFM"] * TUNING["HALL_SUPPLY_FRACTION"] * 60.0 * TUNING["AIR_LB_PER_CF"]
        m_xfer = TUNING["MAU_CFM"] * (1.0 - TUNING["HALL_SUPPLY_FRACTION"]) * 60.0 * TUNING["AIR_LB_PER_CF"]
        m_inf = TUNING["HALL_INFIL_CFM"] * 60.0 * TUNING["AIR_LB_PER_CF"]

        q_hall = (TUNING["UA_HALL"] * (oa_t - hst["t_f"]) + TUNING["Q_INT_HALL"]
                  + m_supply * 0.240 * (sat - hst["t_f"])
                  + m_inf * 0.240 * (oa_t - hst["t_f"])
                  + m_xfer * 0.240 * (room_t - hst["t_f"]))
        hst["t_f"] = max(50.0, min(110.0, hst["t_f"] + q_hall / TUNING["C_HALL"]))

        m_hall = TUNING["C_HALL"] / 0.240 * 0.6
        hst["w"] = max(0.002, min(0.030, hst["w"] + (
            m_supply * (sa_w - hst["w"]) + m_inf * (oa_w - hst["w"])
            + m_xfer * (room_w - hst["w"])) / m_hall))

        pts[f"{hall}_TEMP"] = round(hst["t_f"], 2)
        pts[f"{hall}_RH"] = round(ps.rh_from_w(hst["t_f"], hst["w"]), 1)

    # --- plant and service entrance ----------------------------------------
    load_tons = total_btuh / 12000.0 + TUNING["CAMPUS_BASE_TONS"]
    ch = chiller_step(load_tons, oa_t, _knobs_for(knobs, "CHILLER-RTAC-822"))
    state["chw"]["entering_f"] = ch["lwt_f"]
    loop = chw_loop(ch["lwt_f"], total_btuh, chw_knobs)

    pts["CHW822_ENT_SUP_TEMP"] = loop["supply_f"]
    pts["CHW822_ENT_RET_TEMP"] = loop["return_f"]
    pts["CHW822_BLDG_DT"] = loop["delta_t_f"]
    pts["CHW822_GPM"] = loop["gpm"]
    pts["CHW822_BLDG_DP"] = loop["bldg_dp_psid"]
    pts["CHW822_STRAINER_DP"] = loop["strainer_dp_psid"]
    pts["CHW822_P1_CMD"] = 1 if chw_knobs.get("p1_running", True) else 0
    pts["CHW822_P1_STATUS"] = pts["CHW822_P1_CMD"]
    pts["CHW822_P2_CMD"] = 1 if chw_knobs.get("p2_running", False) else 0
    pts["CHW822_P2_STATUS"] = pts["CHW822_P2_CMD"]

    for dev in ("SC82201", "SC82202", "MSTP01A", "MSTP01B", "MSTP02A", "MSTP02B"):
        pts[f"{dev}_STATUS"] = 1      # spec 1 is healthy; spec 2 turns these off

    diag_states = ("None", "LowEvapTemp", "CondFanFail", "CircuitLockout")
    pts["RTAC822_EVAP_ENT_TEMP"] = ch["ewt_f"]
    pts["RTAC822_EVAP_LVG_TEMP"] = ch["lwt_f"]
    pts["RTAC822_EVAP_LVG_SP"] = TUNING["CHW_SETPOINT_F"]
    pts["RTAC822_AMBIENT_TEMP"] = ch["ambient_f"]
    pts["RTAC822_PCT_CAPACITY"] = ch["pct_capacity"]
    pts["RTAC822_CKT1_STATUS"] = 1 if ch["ckt1_on"] else 0
    pts["RTAC822_CKT2_STATUS"] = 1 if ch["ckt2_on"] else 0
    pts["RTAC822_CKT1_FAN_STATUS"] = 1 if ch["ckt1_fan_ok"] else 0
    pts["RTAC822_CKT2_FAN_STATUS"] = 1 if ch["ckt2_fan_ok"] else 0
    pts["RTAC822_ACTIVE_DIAG"] = diag_states.index(ch["active_diag"])

    state["step"] = step + 1
    state["_chiller"] = ch          # consumed by /api/chiller/822
    state["_loop"] = loop
    return state, pts


def self_test() -> int:
    """Monotonicity and sanity across the coupled model. No fixtures."""
    base = cold_start_state()

    def settle(steps=120, **kw):
        st = cold_start_state()
        pts = {}
        for i in range(steps):
            st, pts = step_822(st, i, **kw)
        return pts

    healthy = settle()
    sat = healthy["MAU01_SAT"]
    assert 58.0 < sat < 72.0, f"healthy MAU SAT out of range: {sat}"
    assert healthy["CHW822_ENT_SUP_TEMP"] == TUNING["CHW_SETPOINT_F"], "healthy chiller must hold setpoint"
    assert 5.0 < healthy["CHW822_BLDG_DT"] < 16.0, healthy["CHW822_BLDG_DT"]

    # Valve open -> colder supply air.
    warm = settle(knobs={"MAU01": {"coil_fouling": 0.6}})
    assert warm["MAU01_SAT"] > healthy["MAU01_SAT"], "fouling must raise SAT"

    # Restricted flow collapses building delta-T in the coupled model.
    restricted = settle(knobs={"CHW-822": {"strainer_resistance": 0.7}})
    assert restricted["CHW822_BLDG_DT"] < healthy["CHW822_BLDG_DT"], "strainer must collapse dT"

    # Air bound is worse than healthy.
    bound = settle(knobs={"MAU01": {"air_bound": True}})
    assert bound["MAU01_SAT"] > healthy["MAU01_SAT"], "air bound must raise SAT"

    # Fan off lets the space drift toward ambient.
    off = settle(overrides={"MAU01_FAN_CMD": {"value": 0}})
    assert off["MAU01_SAT"] > healthy["MAU01_SAT"], "fan off must raise SAT"

    # Warm entering water degrades the coil.
    hot = settle(knobs={"CHILLER-RTAC-822": {"condenser_fouling": 0.5}})
    assert hot["CHW822_ENT_SUP_TEMP"] > healthy["CHW822_ENT_SUP_TEMP"]

    # No NaN or infinity anywhere.
    for name, value in healthy.items():
        assert value == value and abs(value) != float("inf"), f"{name} is not finite: {value}"

    assert len(healthy) == 458, f"step_822 produced {len(healthy)} points, expected 458"

    # --- stuck actuator with honest feedback: BAS itself shows the problem ---
    st, pts = cold_start_state(), {}
    for i in range(120):
        st, pts = step_822(st, i, knobs={"MAU04": {"actuator_stuck_at": 15.0}})
    truth = ground_truth_snapshot(st)
    assert truth["MAU04_CHW_VLV_PHYSICAL"] == 15.0, truth["MAU04_CHW_VLV_PHYSICAL"]
    assert pts["MAU04_CHW_VLV_POS"] == 15.0, \
        "honest feedback must report the true physical position"
    assert pts["MAU04_CHW_VLV_CMD"] > 95.0, \
        "a PI loop chasing an unreachable SAT must organically climb to ~100% " \
        f"command, got {pts['MAU04_CHW_VLV_CMD']}"
    assert pts["MAU04_SAT"] > healthy["MAU04_SAT"] + 5.0, \
        "a valve stuck at 15% must fail to hold setpoint"

    # --- stuck actuator with LYING feedback: the harder, more realistic case -
    # BAS reports feedback near command (looks healthy); only a field
    # verification of physical position exposes the failure.
    st, pts = cold_start_state(), {}
    for i in range(120):
        st, pts = step_822(st, i, knobs={
            "MAU04": {"actuator_stuck_at": 15.0, "feedback_stuck_at": 98.0}})
    truth = ground_truth_snapshot(st)
    assert truth["MAU04_CHW_VLV_PHYSICAL"] == 15.0, \
        "ground truth must show the real position regardless of what feedback claims"
    assert pts["MAU04_CHW_VLV_POS"] == 98.0, \
        "a lying feedback point must report its own stuck value, not physical truth"
    assert pts["MAU04_CHW_VLV_CMD"] > 95.0, \
        "command still climbs toward 100% -- the loop only sees SAT, never feedback"
    assert pts["MAU04_SAT"] > healthy["MAU04_SAT"] + 5.0, \
        "the coil must respond to PHYSICAL position, not the lying feedback value"

    # --- repair needs no special code: simply stop passing the knob, and the
    # PI loop's own slew rate paces the recovery -- it must NOT snap back ---
    st2, pts2 = st, pts
    for i in range(120, 121):
        st2, pts2 = step_822(st2, i)  # no knobs -- actuator "repaired"
    assert abs(pts2["MAU04_CHW_VLV_CMD"] - pts["MAU04_CHW_VLV_CMD"]) <= TUNING["ACTUATOR_SLEW_PCT"] + 0.1, \
        "one step after repair must move by at most one slew step, not snap instantly"
    assert pts2["MAU04_SAT"] > 65.5, \
        "SAT must not have recovered in a single step -- physics paces the recovery"
    for i in range(121, 400):
        st2, pts2 = step_822(st2, i)
    recovered_truth = ground_truth_snapshot(st2)
    assert recovered_truth["MAU04_CHW_VLV_PHYSICAL"] == pts2["MAU04_CHW_VLV_CMD"], \
        "once repaired, physical position must track command again"
    assert abs(pts2["MAU04_SAT"] - healthy["MAU04_SAT"]) < 1.0, \
        f"given enough steps, SAT must fully recover: {pts2['MAU04_SAT']} vs healthy {healthy['MAU04_SAT']}"

    # --- control signal: configurable per device, not a single global assumption
    assert control_signal_volts(100.0, "2-10V") == 10.0
    assert control_signal_volts(0.0, "2-10V") == 2.0
    assert control_signal_volts(50.0, "2-10V") == 6.0
    assert control_signal_volts(100.0, "0-10V") == 10.0
    assert control_signal_volts(100.0, "4-20mA") == 20.0
    try:
        control_signal_volts(50.0, "floating")
        raise AssertionError("floating/tri-state must not produce a fabricated scalar")
    except ValueError:
        pass

    print(f"SELF-TEST PASS (model822: 458 points, healthy SAT {sat:.1f}F, "
          f"dT {healthy['CHW822_BLDG_DT']:.1f}F, hall RH {healthy['HALL_A1_RH']:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
