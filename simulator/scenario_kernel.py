#!/usr/bin/env python3
"""S-001 scenario kernel: a pure session engine for Building 822 cases.

A session wraps the real Building 822 model (model822.step_822) with a
simulated clock, the trainee's valve/pump lineup, the hidden cause, an
append-only action/evidence log, a lifecycle derived from model state, and
closeout verification against model state. No HTTP and no file writes: the
API layer (S-001 phase 3) loads, authorizes, persists, and audits.

Spec: docs/superpowers/specs/2026-09-23-s001-scenario-kernel-design.md
"""

from __future__ import annotations

import hashlib
import json
import random
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_obs  # noqa: E402
import model822  # noqa: E402
import scenario_actions  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SCENARIO_DIR = ROOT / "data" / "input" / "scenarios"

GROUPS = ("look", "decide", "repair", "control")
EVIDENCE_TYPES = ("bas_value", "field_measurement", "visual_inspection", "operator_report",
                  "documentation", "technician_inference", "none")
SAFETY = ("safe", "requires_decision")
TERMINAL = ("CLOSED", "UNSAFE_STOP", "ABANDONED")
DEFAULT_LINEUP = {"p1_energized": True, "p1_running": True, "p2_running": False,
                  "p1_branch_isolated": False, "makeup_valve_open": False}
_SCENARIO_ID = re.compile(r"^S-\d{3}$")


class SessionClosed(ValueError):
    """The session has ended; it accepts no further actions."""


# --- case definition ----------------------------------------------------------

def load_scenario(scenario_id: str, directory: Path = SCENARIO_DIR) -> tuple[dict[str, Any], dict[str, Any]]:
    """Load and validate a case's trainee-safe definition and instructor file."""
    if not isinstance(scenario_id, str) or not _SCENARIO_ID.match(scenario_id):
        raise ValueError(f"invalid scenario id {scenario_id!r}")
    definition = json.loads((directory / f"{scenario_id}.json").read_text(encoding="utf-8"))
    truth = json.loads((directory / f"{scenario_id}.instructor.json").read_text(encoding="utf-8"))
    errors = validate_scenario(definition, truth)
    if errors:
        raise ValueError(f"scenario {scenario_id} is invalid: " + "; ".join(errors))
    return definition, truth


def _validate_action(a: dict[str, Any]) -> list[str]:
    aid = a.get("action_id")
    errors = []
    if not isinstance(a.get("label"), str) or not a["label"].strip():
        errors.append(f"{aid}: label is required")
    if a.get("group") not in GROUPS:
        errors.append(f"{aid}: bad group {a.get('group')!r}")
    tc = a.get("time_cost_min")
    if isinstance(tc, bool) or not isinstance(tc, int) or not 0 <= tc <= 120:
        errors.append(f"{aid}: time_cost_min must be an integer from 0 to 120")
    if a.get("evidence_type") not in EVIDENCE_TYPES:
        errors.append(f"{aid}: bad evidence_type {a.get('evidence_type')!r}")
    if a.get("effect") not in scenario_actions.EFFECTS:
        errors.append(f"{aid}: unknown effect {a.get('effect')!r}")
    if a.get("safety", "safe") not in SAFETY:
        errors.append(f"{aid}: bad safety {a.get('safety')!r}")
    if not set(a.get("prerequisites", [])) <= set(scenario_actions.PREREQUISITES):
        errors.append(f"{aid}: unknown prerequisite in {a.get('prerequisites')}")
    roles = a.get("roles")
    if not isinstance(roles, list) or not roles or not all(isinstance(r, str) for r in roles):
        errors.append(f"{aid}: roles must be a non-empty list")
    params = a.get("params", {})
    if not isinstance(params, dict) or not all(
            v == "*" or (isinstance(v, list) and v and all(isinstance(x, str) for x in v))
            for v in params.values()):
        errors.append(f"{aid}: params must map names to '*' or a list of allowed values")
        params = {}
    fixed = a.get("fixed_params", {})
    if not isinstance(fixed, dict) or not all(isinstance(v, str) for v in fixed.values()):
        errors.append(f"{aid}: fixed_params must map names to strings")
    gate = a.get("hazard_gated", False)
    if isinstance(gate, dict):
        allowed = params.get(gate.get("param"))
        if not isinstance(allowed, list) or not set(gate.get("values", [])) <= set(allowed) or not gate.get("values"):
            errors.append(f"{aid}: hazard_gated must name a listed param and some of its values")
    elif not isinstance(gate, bool):
        errors.append(f"{aid}: hazard_gated must be true, false, or a param gate")
    return errors


def validate_scenario(definition: dict[str, Any], truth: dict[str, Any]) -> list[str]:
    errors = []
    for key in ("scenario_id", "version", "title", "complaint", "safety_banner",
                "max_wait_min", "stabilization_window_min", "supply_band_f", "actions"):
        if key not in definition:
            errors.append(f"definition missing {key!r}")
    for key in ("scenario_id", "version", "hidden_cause", "leak_gpm_range", "healthy_warmup_min",
                "pre_shift_leak_min", "profile", "forbidden_tokens", "debrief"):
        if key not in truth:
            errors.append(f"instructor file missing {key!r}")
    if errors:
        return errors
    if (definition["scenario_id"], definition["version"]) != (truth["scenario_id"], truth["version"]):
        errors.append("definition and instructor file disagree on scenario_id/version")
    band = truth["leak_gpm_range"]
    if not (isinstance(band, list) and len(band) == 2 and 0 < band[0] <= band[1]):
        errors.append("leak_gpm_range must be [low, high] with 0 < low <= high")
    if truth["pre_shift_leak_min"] <= 0 or truth["healthy_warmup_min"] < 0:
        errors.append("healthy_warmup_min must be >= 0 and pre_shift_leak_min > 0")
    seen: set[str] = set()
    for action in definition["actions"]:
        aid = action.get("action_id")
        if aid in seen:
            errors.append(f"duplicate action_id {aid!r}")
        seen.add(aid)
        errors.extend(_validate_action(action))
    text = json.dumps(definition).lower()
    for token in list(truth["forbidden_tokens"]) + [truth["hidden_cause"]]:
        if token.lower() in text:
            errors.append(f"trainee-facing definition contains forbidden text {token!r}")
    return errors


# --- sessions and the simulated clock -------------------------------------------

def state_hash(state: dict[str, Any]) -> str:
    """Stable fingerprint of the model state; replay must reproduce it exactly."""
    blob = json.dumps(state, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _knobs(session: dict[str, Any]) -> dict[str, Any]:
    """Model knobs for one step: the trainee's lineup plus the hidden cause."""
    lu = session["lineup"]
    leak = 0.0 if session["flags"]["valve_replaced"] else session["cause"]["p1_tdv_leak_gpm"]
    return {"CHW-822": {
        "p1_running": lu["p1_running"] and lu["p1_energized"],
        "p2_running": lu["p2_running"],
        "p1_branch_isolated": lu["p1_branch_isolated"],
        "makeup_valve_open": lu["makeup_valve_open"],
        "p1_tdv_leak_gpm": leak,
    }}


def _step(session: dict[str, Any], knobs: dict[str, Any]) -> None:
    session["state"], session["pts"] = model822.step_822(
        session["state"], session["model_step"], session["profile"],
        overrides=session["overrides"], knobs=knobs)
    session["model_step"] += 1


def _advance(session: dict[str, Any], minutes: int) -> None:
    """Step the building minute by minute, tracking trips, dead-heading, and the
    stabilization window (supply in band, chiller producing, flow proven, and
    the loop holding fill pressure with the fill valve closed)."""
    t = model822.TUNING
    for _ in range(minutes):
        was_tripped = session["state"]["chiller"]["tripped"]
        _step(session, _knobs(session))
        st, pts = session["state"], session["pts"]
        loop, cs = st["_loop"], st["chiller"]
        if cs["tripped"] and not was_tripped:
            session["events"]["trips"] += 1
        if loop["p1_deadhead"]:
            session["events"]["deadhead_min"] += 1
        holding = (not session["lineup"]["makeup_valve_open"]
                   and st["chw"]["loop_psig"] >= t["LOOP_FILL_PSIG"] - 1.0)
        producing = not cs["tripped"] and cs["restart_min"] <= 0
        in_band = abs(pts["CHW822_ENT_SUP_TEMP"] - t["CHW_SETPOINT_F"]) <= session["supply_band_f"]
        steady = (holding and producing and in_band and not loop["p1_deadhead"]
                  and loop["flow_frac"] >= t["EVAP_MIN_FLOW_FRAC"])
        session["window_min"] = session["window_min"] + 1 if steady else 0
        session["clock_min"] += 1


def _record(session: dict[str, Any], **fields: Any) -> dict[str, Any]:
    n = len(session["records"]) + 1
    record = {"record_id": f"R{n:04d}", "seq": n, "sim_min": session["clock_min"],
              "wall_time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
              **fields, "state_hash": state_hash(session["state"])}
    session["records"].append(record)
    return record


def new_session(definition: dict[str, Any], truth: dict[str, Any], seed: int,
                session_id: str = "S-001-local") -> dict[str, Any]:
    """Build the building as the trainee finds it at the start of the shift:
    healthy warmup, then the hidden cause running for pre_shift_leak_min."""
    rng = random.Random(seed)
    low, high = truth["leak_gpm_range"]
    session: dict[str, Any] = {
        "session_id": session_id, "scenario_id": definition["scenario_id"],
        "definition_version": definition["version"], "seed": seed,
        "profile": truth["profile"], "supply_band_f": definition["supply_band_f"],
        "cause": {"p1_tdv_leak_gpm": round(rng.uniform(low, high), 2)},
        "lineup": dict(DEFAULT_LINEUP), "flags": {"valve_replaced": False, "escalated": False},
        "overrides": {}, "state": model822.cold_start_state(), "pts": {},
        "model_step": 0, "clock_min": 0, "window_min": 0,
        "events": {"trips": 0, "deadhead_min": 0},
        "records": [], "hypotheses": [], "closeout": None, "verification": None, "terminal": None,
    }
    for _ in range(truth["healthy_warmup_min"]):
        _step(session, {})
    for _ in range(truth["pre_shift_leak_min"]):
        _step(session, _knobs(session))
    session["start_hash"] = state_hash(session["state"])
    return session


def wait(session: dict[str, Any], definition: dict[str, Any], minutes: int, actor: str) -> dict[str, Any]:
    if session["terminal"]:
        raise SessionClosed(f"session is {session['terminal']}")
    limit = definition["max_wait_min"]
    if isinstance(minutes, bool) or not isinstance(minutes, int) or not 1 <= minutes <= limit:
        raise ValueError(f"minutes must be an integer from 1 to {limit}")
    _advance(session, minutes)
    return _record(session, kind="wait", minutes=minutes, actor=actor)


# --- actions --------------------------------------------------------------------

UNSAFE_STOP_TEXT = ("Stopped: you went hands-on at energized equipment standing in water. "
                    "The session ends here; the debrief explains what a safe path looked like.")


def _action(definition: dict[str, Any], action_id: str) -> dict[str, Any]:
    for action in definition["actions"]:
        if action["action_id"] == action_id:
            return action
    raise ValueError(f"unknown action {action_id!r}")


def _checked_params(session: dict[str, Any], action: dict[str, Any], params: Any) -> dict[str, str]:
    if not isinstance(params, dict):
        raise ValueError("params must be an object")
    spec, fixed = action.get("params", {}), action.get("fixed_params", {})
    for key, value in params.items():
        if key in fixed and value != fixed[key]:
            raise ValueError(f"parameter {key!r} is fixed for this action")
    unknown = set(params) - set(spec) - set(fixed)
    if unknown:
        raise ValueError(f"unexpected parameter(s): {sorted(unknown)}")
    clean: dict[str, str] = {}
    for name, allowed in spec.items():
        value = params.get(name)
        if not isinstance(value, str):
            raise ValueError(f"parameter {name!r} is required")
        if allowed == "*":
            if value not in session["pts"]:
                raise ValueError(f"unknown point {value!r}")
        elif value not in allowed:
            raise ValueError(f"parameter {name!r} must be one of {allowed}")
        clean[name] = value
    clean.update(fixed)
    return clean


def _hazardous(session: dict[str, Any], action: dict[str, Any], params: dict[str, str]) -> bool:
    """Hands-on at P1's side while there is standing water and P1 is energized."""
    gate = action.get("hazard_gated", False)
    if isinstance(gate, dict):
        gate = params.get(gate["param"]) in gate["values"]
    if not gate:
        return False
    water = model822.ground_truth_snapshot(session["state"])["PUMPROOM_WATER_GAL_PHYSICAL"]
    return water >= field_obs.STANDING_WATER_GAL and session["lineup"]["p1_energized"]


def act(session: dict[str, Any], definition: dict[str, Any], action_id: str,
        params: dict[str, Any], actor: str, role: str) -> dict[str, Any]:
    """Perform one catalog action. Order: session open, action known, role
    allowed, params valid (these raise and record nothing), prerequisites
    (refusal is recorded, nothing changes), safety gate (unsafe ends the
    session), then advance the clock by the action's time cost and apply it."""
    if session["terminal"]:
        raise SessionClosed(f"session is {session['terminal']}")
    action = _action(definition, action_id)
    if role not in action["roles"]:
        raise PermissionError(f"role {role!r} may not perform {action_id!r}")
    clean = _checked_params(session, action, params)
    base = {"kind": "action", "action_id": action_id, "params": clean, "actor": actor, "role": role,
            "evidence_type": action["evidence_type"], "safety": action.get("safety", "safe"),
            "prerequisites": list(action.get("prerequisites", []))}
    unmet = [scenario_actions.PREREQUISITES[p] for p in action.get("prerequisites", [])
             if not scenario_actions.prerequisite_met(p, session)]
    if unmet:
        return _record(session, **base, outcome="refused", reasons=unmet, observation=None,
                       state_changes=[], diagnostic_cost_min=0)
    if _hazardous(session, action, clean):
        session["terminal"] = "UNSAFE_STOP"
        base["safety"] = "unsafe"
        return _record(session, **base, outcome="unsafe_stop", reasons=[], observation=UNSAFE_STOP_TEXT,
                       state_changes=[], diagnostic_cost_min=0)
    _advance(session, action["time_cost_min"])
    observation, changes = scenario_actions.HANDLERS[action["effect"]](session, clean)
    return _record(session, **base, outcome="done", reasons=[], observation=observation,
                   state_changes=changes, diagnostic_cost_min=action["time_cost_min"])


def self_test() -> int:
    definition, truth = load_scenario("S-001")
    # --- Task 2: loading and validation ------------------------------------------
    assert validate_scenario(definition, truth) == [], validate_scenario(definition, truth)
    for bad_id in ("../S-001", "S-1", "", None):
        try:
            load_scenario(bad_id)
            raise AssertionError(f"accepted scenario id {bad_id!r}")
        except ValueError:
            pass

    def broken(mutate) -> list[str]:
        d, t = json.loads(json.dumps(definition)), json.loads(json.dumps(truth))
        mutate(d, t)
        return validate_scenario(d, t)

    assert any("unknown effect" in e for e in broken(lambda d, t: d["actions"][0].update(effect="teleport")))
    assert any("duplicate action_id" in e for e in broken(lambda d, t: d["actions"].append(dict(d["actions"][0]))))
    assert any("forbidden text" in e for e in broken(
        lambda d, t: d.update(complaint=d["complaint"] + " " + t["forbidden_tokens"][0])))
    assert any("leak_gpm_range" in e for e in broken(lambda d, t: t.update(leak_gpm_range=[2.0, 1.0])))
    assert any("hazard_gated" in e for e in broken(
        lambda d, t: d["actions"][0].update(hazard_gated={"param": "nope", "values": ["x"]})))
    assert any("disagree" in e for e in broken(lambda d, t: t.update(version=2)))

    # --- Task 3: sessions, clock, waits -------------------------------------------
    s1 = new_session(definition, truth, seed=7)
    s2 = new_session(definition, truth, seed=7)
    assert s1["start_hash"] == s2["start_hash"] and s1["cause"] == s2["cause"], "same seed, same start"
    lo, hi = truth["leak_gpm_range"]
    for seed in range(5):
        assert lo <= new_session(definition, truth, seed)["cause"]["p1_tdv_leak_gpm"] <= hi
    pts, gt = s1["pts"], model822.ground_truth_snapshot(s1["state"])
    t = model822.TUNING
    assert pts["CHW822_P1_STATUS"] == 1, "at shift start P1 still shows running"
    assert pts["CHW822_GPM"] < t["CHW_GPM_DESIGN"] * t["EVAP_MIN_FLOW_FRAC"], pts["CHW822_GPM"]
    assert pts["RTAC822_ACTIVE_DIAG"] == model822.DIAG_STATES.index("LowEvapFlow")
    assert gt["PUMPROOM_WATER_GAL_PHYSICAL"] >= field_obs.STANDING_WATER_GAL, gt
    assert s1["clock_min"] == 0 and s1["records"] == [] and s1["terminal"] is None
    rec = wait(s1, definition, 10, actor="t1")
    assert s1["clock_min"] == 10 and rec["kind"] == "wait" and rec["record_id"] == "R0001"
    assert rec["state_hash"] == state_hash(s1["state"]) and rec["state_hash"] != s1["start_hash"]
    for bad in (0, 61, "5", True):
        try:
            wait(s1, definition, bad, actor="t1")
            raise AssertionError(f"accepted wait {bad!r}")
        except ValueError:
            pass

    # --- Task 4: actions ------------------------------------------------------------
    assert set(scenario_actions.HANDLERS) == set(scenario_actions.EFFECTS)
    T = "technician"

    def fresh(seed: int = 11) -> dict[str, Any]:
        return new_session(definition, truth, seed)

    s = fresh()
    h0 = state_hash(s["state"])
    try:
        act(s, definition, "walk_pumproom", {}, "t1", role="viewer")
        raise AssertionError("a viewer acted")
    except PermissionError:
        pass
    for aid, params in (("inspect_valve", {"valve": "P9_TDV"}), ("pin_point", {"point": "NOPE"}),
                        ("teleport", {}), ("start_p1", {"pump": "P2"}), ("walk_pumproom", {"x": "1"})):
        try:
            act(s, definition, aid, params, "t1", T)
            raise AssertionError(f"accepted {aid} {params}")
        except ValueError:
            pass
    r = act(s, definition, "replace_p1_valve", {}, "t1", T)
    assert r["outcome"] == "refused" and r["reasons"], r
    assert s["clock_min"] == 0 and state_hash(s["state"]) == h0, "a refusal changes nothing"

    r = act(s, definition, "walk_pumproom", {}, "t1", T)
    assert r["outcome"] == "done" and "Standing water" in r["observation"] and s["clock_min"] == 5
    assert "LowEvapFlow" in act(s, definition, "chiller_panel", {}, "t1", T)["observation"]
    assert "psid" in act(s, definition, "check_strainer", {}, "t1", T)["observation"]
    assert "% travel" in act(s, definition, "check_mau04_travel", {}, "t1", T)["observation"]
    r = act(s, definition, "pin_point", {"point": "CHW822_GPM"}, "t1", T)
    assert r["evidence_type"] == "bas_value" and r["observation"].startswith("CHW822_GPM = ")

    # Going hands-on at the energized P1 in standing water ends the session.
    r = act(s, definition, "inspect_valve", {"valve": "P1_TDV"}, "t1", T)
    assert r["outcome"] == "unsafe_stop" and r["safety"] == "unsafe" and s["terminal"] == "UNSAFE_STOP"
    try:
        act(s, definition, "walk_pumproom", {}, "t1", T)
        raise AssertionError("acted after the session ended")
    except SessionClosed:
        pass

    # P2's side is dry; after lockout the P1 inspection is safe.
    s = fresh()
    act(s, definition, "inspect_valve", {"valve": "P2_TDV"}, "t1", T)
    act(s, definition, "clamp_amps", {"pump": "P2"}, "t1", T)
    assert s["terminal"] is None
    r = act(s, definition, "lockout_p1", {}, "t1", T)
    assert r["safety"] == "requires_decision" and not s["lineup"]["p1_energized"]
    r = act(s, definition, "inspect_valve", {"valve": "P1_TDV"}, "t1", T)
    assert r["outcome"] == "done" and "corrosion through the valve body" in r["observation"], r

    # A fill valve left open masks the leak: pressure holds while the floor floods.
    s = fresh()
    fill = model822.TUNING["LOOP_FILL_PSIG"]
    water0 = model822.ground_truth_snapshot(s["state"])["PUMPROOM_WATER_GAL_PHYSICAL"]
    act(s, definition, "open_fill", {}, "t1", T)
    for _ in range(3):
        wait(s, definition, 60, "t1")
    gt = model822.ground_truth_snapshot(s["state"])
    assert gt["CHW822_LOOP_PSIG_PHYSICAL"] >= fill - 0.5, gt
    assert gt["PUMPROOM_WATER_GAL_PHYSICAL"] > water0 + 30.0, (water0, gt)
    act(s, definition, "close_fill", {}, "t1", T)
    wait(s, definition, 15, "t1")
    assert model822.ground_truth_snapshot(s["state"])["CHW822_LOOP_PSIG_PHYSICAL"] < fill - 1.0

    # Resetting without flow is counted, and the flow switch trips it again.
    s = fresh()
    r = act(s, definition, "reset_chiller", {}, "t1", T)
    assert "Reset accepted" in r["observation"] and s["state"]["chiller"]["unproven_resets"] == 1
    wait(s, definition, 10, "t1")
    assert s["state"]["chiller"]["tripped"]

    print("scenario_kernel self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
