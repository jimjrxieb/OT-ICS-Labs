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
    if not isinstance(scenario_id, str) or not _SCENARIO_ID.fullmatch(scenario_id):
        raise ValueError(f"invalid scenario id {scenario_id!r}")
    try:
        definition = json.loads((directory / f"{scenario_id}.json").read_text(encoding="utf-8"))
        truth = json.loads((directory / f"{scenario_id}.instructor.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"unknown scenario {scenario_id!r}")
    errors = validate_scenario(definition, truth)
    if errors:
        raise ValueError(f"scenario {scenario_id} is invalid: " + "; ".join(errors))
    return definition, truth


def _checked_actor(value: Any, label: str = "actor") -> str:
    if not isinstance(value, str) or not value or len(value) > 64:
        raise ValueError(f"{label} must be a non-empty string of at most 64 characters")
    return value


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
    prefixes = definition.get("local_display_prefixes")
    if prefixes is not None and not (
            isinstance(prefixes, list) and all(isinstance(p, str) and p for p in prefixes)):
        errors.append("local_display_prefixes must be a list of non-empty strings")
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
                   and st["chw"]["loop_psig"] >= t["LOOP_FILL_PSIG"] - 1.0
                   and loop["leak_gpm"] == 0.0)
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
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an int")
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
    actor = _checked_actor(actor)
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


def _checked_params(session: dict[str, Any], definition: dict[str, Any], action: dict[str, Any],
                     params: Any) -> dict[str, str]:
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
            local_only = any(value.startswith(p) for p in definition.get("local_display_prefixes", []))
            if value not in session["pts"] or local_only:
                raise ValueError(f"unknown point {value!r}")
        elif value not in allowed:
            raise ValueError(f"parameter {name!r} must be one of {allowed}")
        clean[name] = value
    clean.update(fixed)
    return json.loads(json.dumps(clean))


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
    actor = _checked_actor(actor)
    role = _checked_actor(role, "role")
    action = _action(definition, action_id)
    if role not in action["roles"]:
        raise PermissionError(f"role {role!r} may not perform {action_id!r}")
    clean = _checked_params(session, definition, action, params)
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


# --- verification, lifecycle, closeout -------------------------------------------

CLOSEOUT_FIELDS = (
    "complaint_and_baseline", "safety_and_decisions", "root_cause", "competing_causes_excluded",
    "corrective_action", "before_after_and_stabilization", "overrides_released",
    "remaining_risk_and_owner", "pm_task", "crew_summary", "executive_summary",
)
CITED_FIELDS = ("root_cause", "competing_causes_excluded")
HYPOTHESIS_STATUS = ("open", "supported", "ruled_out")
TRAINEE_RECORD_KEYS = ("record_id", "kind", "sim_min", "action_id", "params", "minutes", "outcome",
                       "observation", "evidence_type", "reasons", "verification")


def criteria(session: dict[str, Any], definition: dict[str, Any]) -> list[dict[str, Any]]:
    """Closeout acceptance, from model state. Labels describe observable
    conditions only -- never the hidden cause."""
    st, t = session["state"], model822.TUNING
    band, window = definition["supply_band_f"], definition["stabilization_window_min"]
    return [
        {"id": "loop_pressure", "label": "Loop holding fill pressure with the fill valve closed",
         "passed": (not session["lineup"]["makeup_valve_open"]
                    and st["chw"]["loop_psig"] >= t["LOOP_FILL_PSIG"] - 1.0
                    and st["_loop"]["leak_gpm"] == 0.0)},
        {"id": "no_air", "label": "No air in the chilled-water loop",
         "passed": st["chw"]["air_frac"] == 0.0},
        {"id": "flow_proven", "label": f"Chilled-water flow proven (at least {t['EVAP_MIN_FLOW_FRAC']:.0%} of design)",
         "passed": st["_loop"]["flow_frac"] >= t["EVAP_MIN_FLOW_FRAC"]},
        {"id": "chiller_running", "label": "Chiller running with no active diagnostic",
         "passed": not st["chiller"]["tripped"] and st["chiller"]["restart_min"] <= 0},
        {"id": "supply_stable",
         "label": f"Supply within ±{band:g} F of setpoint, loop holding pressure, for {window} continuous minutes",
         "passed": session["window_min"] >= window},
        {"id": "overrides_released", "label": "No temporary operator overrides left active",
         "passed": not session["overrides"]},
    ]


def lifecycle(session: dict[str, Any], definition: dict[str, Any]) -> str:
    """Derived from session and model state; the client never sets it."""
    if session["terminal"]:
        return session["terminal"]
    if not session["records"]:
        return "OPEN"
    st, t = session["state"], model822.TUNING
    if not session["flags"]["valve_replaced"] and not session["lineup"]["p1_branch_isolated"]:
        return "INVESTIGATING"
    if st["chw"]["loop_psig"] < t["LOOP_FILL_PSIG"] - 1.0 or st["chw"]["air_frac"] > 0.0:
        return "ISOLATED"
    cs = st["chiller"]
    if cs["tripped"] or cs["restart_min"] > 0 or st["_loop"]["flow_frac"] < t["EVAP_MIN_FLOW_FRAC"]:
        return "REPAIRING"
    if all(c["passed"] for c in criteria(session, definition)):
        return "READY_FOR_VERIFICATION"
    return "RECOVERING"


def _validate_closeout(session: dict[str, Any], fields: Any, citations: Any) -> None:
    if not isinstance(fields, dict):
        raise ValueError("closeout fields must be an object")
    errors = []
    for key in CLOSEOUT_FIELDS:
        value = fields.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"closeout field {key!r} is required")
        elif len(value) > 2000:
            errors.append(f"closeout field {key!r} is longer than 2000 characters")
    extra = set(fields) - set(CLOSEOUT_FIELDS)
    if extra:
        errors.append(f"unknown closeout field(s): {sorted(extra)}")
    summary = fields.get("executive_summary")
    if isinstance(summary, str) and (len(summary) > 300 or "$" in summary):
        errors.append("executive_summary must be one short sentence with no dollar figures")
    evidence = {r["record_id"] for r in session["records"]
                if r["kind"] == "action" and r["outcome"] == "done" and r["evidence_type"] != "none"}
    if not isinstance(citations, dict):
        errors.append("citations must be an object")
    else:
        for key in CITED_FIELDS:
            if not isinstance(citations.get(key), list) or not citations[key]:
                errors.append(f"{key!r} must cite at least one evidence record")
        for key, ids in citations.items():
            if key not in CLOSEOUT_FIELDS:
                errors.append(f"citation for unknown field {key!r}")
                continue
            if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
                errors.append(f"citation for {key!r} must be a list of strings")
                continue
            bad = [i for i in ids if i not in evidence]
            if bad:
                errors.append(f"{key!r} cites records that are not evidence in this session: {bad}")
    if errors:
        raise ValueError("; ".join(errors))


def closeout(session: dict[str, Any], definition: dict[str, Any], fields: dict[str, str],
             citations: dict[str, list[str]], actor: str) -> dict[str, Any]:
    """Validate the structured closeout, then verify the building. All criteria
    pass -> CLOSED; otherwise the failed criteria are recorded and the session
    stays open."""
    if session["terminal"]:
        raise SessionClosed(f"session is {session['terminal']}")
    actor = _checked_actor(actor)
    _validate_closeout(session, fields, citations)
    results = criteria(session, definition)
    passed = all(c["passed"] for c in results)
    fields = json.loads(json.dumps(fields))
    citations = json.loads(json.dumps(citations))
    session["closeout"] = {"fields": fields, "citations": citations}
    session["verification"] = results
    if passed:
        session["terminal"] = "CLOSED"
    return _record(session, kind="closeout", fields=fields, citations=citations, actor=actor,
                   outcome="closed" if passed else "failed_verification", verification=results)


MAX_HYPOTHESES = 20


def set_hypotheses(session: dict[str, Any], hypotheses: list[dict[str, Any]], actor: str) -> dict[str, Any]:
    if session["terminal"]:
        raise SessionClosed(f"session is {session['terminal']}")
    actor = _checked_actor(actor)
    if not isinstance(hypotheses, list):
        raise ValueError("hypotheses must be a list")
    if len(hypotheses) > MAX_HYPOTHESES:
        raise ValueError(f"at most {MAX_HYPOTHESES} hypotheses are allowed")
    ids = {r["record_id"] for r in session["records"]}
    clean: list[dict[str, Any]] = []
    for h in hypotheses:
        if not isinstance(h, dict) or not isinstance(h.get("text"), str) or not 0 < len(h["text"].strip()) <= 500:
            raise ValueError("each hypothesis needs text of 1-500 characters")
        if h.get("status") not in HYPOTHESIS_STATUS:
            raise ValueError(f"hypothesis status must be one of {list(HYPOTHESIS_STATUS)}")
        refs_clean: dict[str, list[str]] = {}
        for key in ("supporting", "contradicting"):
            refs = h.get(key, [])
            if not isinstance(refs, list) or not all(isinstance(ref, str) for ref in refs):
                raise ValueError(f"hypothesis {key} must be a list of record ids")
            if any(ref not in ids for ref in refs):
                raise ValueError(f"hypothesis {key} must reference records in this session")
            refs_clean[key] = refs
        clean.append({"text": h["text"], "status": h["status"], **refs_clean})
    session["hypotheses"] = json.loads(json.dumps(clean))
    return _record(session, kind="hypotheses", hypotheses=session["hypotheses"], actor=actor)


def abandon(session: dict[str, Any], actor: str) -> dict[str, Any]:
    if session["terminal"]:
        raise SessionClosed(f"session is {session['terminal']}")
    actor = _checked_actor(actor)
    session["terminal"] = "ABANDONED"
    return _record(session, kind="abandon", actor=actor)


def trainee_view(session: dict[str, Any], definition: dict[str, Any]) -> dict[str, Any]:
    """Everything a trainee may see. No cause, no instructor text, no model
    internals beyond what the actions themselves returned."""
    actions = []
    for a in definition["actions"]:
        unmet = [scenario_actions.PREREQUISITES[p] for p in a.get("prerequisites", [])
                 if not scenario_actions.prerequisite_met(p, session)]
        actions.append({
            "action_id": a["action_id"], "label": a["label"], "group": a["group"],
            "time_cost_min": a["time_cost_min"],
            "params": {k: ("any BAS point" if v == "*" else v) for k, v in a.get("params", {}).items()},
            "available": not unmet and not session["terminal"], "unavailable_because": unmet,
        })
    return {
        "session_id": session["session_id"], "scenario_id": session["scenario_id"],
        "title": definition["title"], "complaint": definition["complaint"],
        "safety_banner": definition["safety_banner"], "status": lifecycle(session, definition),
        "clock_min": session["clock_min"], "max_wait_min": definition["max_wait_min"],
        "actions": actions,
        "records": [{k: r[k] for k in TRAINEE_RECORD_KEYS if k in r} for r in session["records"]],
        "hypotheses": session["hypotheses"], "closeout": session["closeout"],
        "verification": session["verification"],
    }


def debrief(session: dict[str, Any], definition: dict[str, Any], truth: dict[str, Any]) -> dict[str, Any]:
    """The answer and a review of the run -- only after the session has ended."""
    if not session["terminal"]:
        raise ValueError("the debrief is available after the session ends")
    records, cs = session["records"], session["state"]["chiller"]
    first_p1 = next((r["sim_min"] for r in records
                     if r.get("action_id") == "inspect_valve" and r.get("outcome") == "done"
                     and r.get("params", {}).get("valve") == "P1_TDV"), None)
    closed_at = next((r["sim_min"] for r in records if r.get("outcome") == "closed"), None)
    return {
        "outcome": session["terminal"], "hidden_cause": truth["hidden_cause"],
        "leak_gpm": session["cause"]["p1_tdv_leak_gpm"], "pre_shift_leak_min": truth["pre_shift_leak_min"],
        "timeline": trainee_view(session, definition)["records"],
        "safety_decisions": [{"record_id": r["record_id"], "action_id": r["action_id"],
                              "safety": r["safety"], "outcome": r["outcome"]}
                             for r in records if r.get("safety") in ("requires_decision", "unsafe")],
        "resets": cs["resets"], "unproven_resets": cs["unproven_resets"],
        "pump_deadhead_min": session["events"]["deadhead_min"],
        "chiller_trips_during_session": session["events"]["trips"],
        "first_p1_valve_inspection_min": first_p1, "closed_at_min": closed_at,
        "notes": truth["debrief"],
    }


# --- replay ------------------------------------------------------------------------

def replay(definition: dict[str, Any], truth: dict[str, Any], session: dict[str, Any],
           on_step: Any = None) -> list[str]:
    """Rebuild the session from its seed and re-apply every record; each record
    must reproduce its stored state hash. Returns the mismatches (empty = exact)."""
    fresh = new_session(definition, truth, session["seed"], session["session_id"])
    if fresh["start_hash"] != session["start_hash"]:
        return ["start state differs"]
    problems: list[str] = []
    for rec in session["records"]:
        kind = rec["kind"]
        if kind not in ("action", "wait", "hypotheses", "closeout", "abandon"):
            problems.append(f"{rec['record_id']}: unknown record kind {kind!r}")
            break
        try:
            if kind == "action":
                act(fresh, definition, rec["action_id"], rec["params"], rec["actor"], rec["role"])
            elif kind == "wait":
                wait(fresh, definition, rec["minutes"], rec["actor"])
            elif kind == "hypotheses":
                set_hypotheses(fresh, rec["hypotheses"], rec["actor"])
            elif kind == "closeout":
                closeout(fresh, definition, rec["fields"], rec["citations"], rec["actor"])
            elif kind == "abandon":
                abandon(fresh, rec["actor"])
        except (SessionClosed, ValueError, PermissionError, KeyError, TypeError) as exc:
            problems.append(f"{rec['record_id']}: cannot re-apply ({exc})")
            break
        fresh_rec = fresh["records"][-1]
        if fresh_rec["state_hash"] != rec["state_hash"]:
            problems.append(f"{rec['record_id']}: state hash differs")
        stored = {k: v for k, v in rec.items() if k != "wall_time"}
        rebuilt = {k: v for k, v in fresh_rec.items() if k != "wall_time"}
        if rebuilt != stored:
            problems.append(f"{rec['record_id']}: record differs")
        if on_step is not None:
            on_step(fresh)
    if fresh["terminal"] != session["terminal"]:
        problems.append("terminal state differs")
    return problems


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

    # --- Task 5: lifecycle, verification, closeout, debrief ----------------------
    s = fresh(3)

    def do(aid: str, **params: str) -> dict[str, Any]:
        return act(s, definition, aid, params, "t1", T)

    assert lifecycle(s, definition) == "OPEN"
    view = trainee_view(s, definition)
    replace = next(a for a in view["actions"] if a["action_id"] == "replace_p1_valve")
    assert not replace["available"] and replace["unavailable_because"], replace
    ev = [do("walk_pumproom"), do("chiller_panel"), do("read_suction_gauge"), do("check_strainer")]
    assert lifecycle(s, definition) == "INVESTIGATING"
    do("lockout_p1")
    ev.append(do("inspect_valve", valve="P1_TDV"))
    do("isolate_p1_branch")
    assert lifecycle(s, definition) == "ISOLATED"

    fields = {k: "Synthetic test entry." for k in CLOSEOUT_FIELDS}
    fields["executive_summary"] = "Building 822 cooling was restored after a failed valve body was isolated and replaced."
    cites = {"root_cause": [ev[-1]["record_id"]], "competing_causes_excluded": [ev[3]["record_id"]]}
    r = closeout(s, definition, fields, cites, "t1")
    assert r["outcome"] == "failed_verification" and s["terminal"] is None, r
    failed = {c["id"] for c in r["verification"] if not c["passed"]}
    assert {"chiller_running", "supply_stable"} <= failed, failed

    do("replace_p1_valve")
    do("open_fill")
    wait(s, definition, 60, "t1")
    wait(s, definition, 30, "t1")
    do("close_fill")
    assert lifecycle(s, definition) == "ISOLATED", "refilled but still air-bound"
    assert "solid water" in do("vent_air")["observation"]
    do("open_p1_branch")
    do("energize_p1")
    do("start_p1")
    wait(s, definition, 5, "t1")
    assert lifecycle(s, definition) == "REPAIRING", "flow back, chiller still latched"
    do("reset_chiller")
    wait(s, definition, 10, "t1")
    assert lifecycle(s, definition) == "RECOVERING"
    wait(s, definition, 60, "t1")
    assert lifecycle(s, definition) == "READY_FOR_VERIFICATION", \
        [c for c in criteria(s, definition) if not c["passed"]]

    try:
        set_hypotheses(s, [{"text": "x", "status": "supported", "supporting": ["R9999"], "contradicting": []}], "t1")
        raise AssertionError("hypothesis cited a missing record")
    except ValueError:
        pass
    set_hypotheses(s, [{"text": "Failed valve body on the P1 branch", "status": "supported",
                        "supporting": [ev[-1]["record_id"]], "contradicting": []}], "t1")
    bad_cases = (
        (dict(fields, executive_summary="Saved $10,000 in one night."), cites),
        (fields, {"root_cause": ["R9999"], "competing_causes_excluded": cites["competing_causes_excluded"]}),
        ({k: v for k, v in fields.items() if k != "pm_task"}, cites),
        (fields, {"root_cause": cites["root_cause"]}),
    )
    for bad_fields, bad_cites in bad_cases:
        try:
            closeout(s, definition, bad_fields, bad_cites, "t1")
            raise AssertionError("accepted an invalid closeout")
        except ValueError:
            pass
    try:
        debrief(s, definition, truth)
        raise AssertionError("debrief before the session ended")
    except ValueError:
        pass
    r = closeout(s, definition, fields, cites, "t1")
    assert r["outcome"] == "closed" and s["terminal"] == "CLOSED" and lifecycle(s, definition) == "CLOSED"
    d = debrief(s, definition, truth)
    assert d["hidden_cause"] == truth["hidden_cause"] and d["outcome"] == "CLOSED"
    assert d["unproven_resets"] == 0 and d["first_p1_valve_inspection_min"] is not None
    assert any(x["action_id"] == "lockout_p1" for x in d["safety_decisions"])

    s_abandoned = fresh(4)
    abandon(s_abandoned, "instructor-1")
    assert s_abandoned["terminal"] == "ABANDONED" and debrief(s_abandoned, definition, truth)["outcome"] == "ABANDONED"

    # --- Task 6: replay and the hidden-truth boundary -----------------------------
    def assert_no_leak(obj: Any, where: str) -> None:
        text = json.dumps(obj).lower()
        for token in list(truth["forbidden_tokens"]) + [truth["hidden_cause"]]:
            assert token.lower() not in text, (where, token)

    # The closed happy path replays exactly, and no trainee view along the way leaks.
    assert replay(definition, truth, s,
                  on_step=lambda x: assert_no_leak(trainee_view(x, definition), "trainee view")) == []
    unsafe = fresh(5)
    act(unsafe, definition, "clamp_amps", {"pump": "P1"}, "t1", T)
    assert unsafe["terminal"] == "UNSAFE_STOP" and replay(definition, truth, unsafe) == []
    assert_no_leak(trainee_view(unsafe, definition), "unsafe view")
    tampered = json.loads(json.dumps(s))
    first_wait = next(r for r in tampered["records"] if r["kind"] == "wait")
    first_wait["minutes"] -= 1
    assert replay(definition, truth, tampered), "replay must detect a tampered record"

    # Refusals and error messages are trainee-facing too.
    probe = fresh(9)
    messages: list[Any] = [act(probe, definition, "replace_p1_valve", {}, "t1", T)["reasons"]]
    for aid, params in (("pin_point", {"point": "NOPE"}), ("inspect_valve", {"valve": "P9"}),
                        ("start_p1", {"pump": "P2"}), ("teleport", {})):
        try:
            act(probe, definition, aid, params, "t1", T)
        except ValueError as exc:
            messages.append(str(exc))
    assert len(messages) == 5, messages
    assert_no_leak(messages, "messages")
    # Positive control: the boundary check does catch the cause when it is there.
    assert truth["hidden_cause"].lower() in json.dumps(debrief(s, definition, truth)).lower()

    # --- Final review fixes ---------------------------------------------------------
    # F1: chiller points are local-display only, not on the BAS.
    probe1 = fresh(31)
    try:
        act(probe1, definition, "pin_point", {"point": "RTAC822_ACTIVE_DIAG"}, "t1", T)
        raise AssertionError("pinned a local-display-only chiller point")
    except ValueError:
        pass
    assert "LowEvapFlow" in act(probe1, definition, "chiller_panel", {}, "t1", T)["observation"]
    assert any("local_display_prefixes" in e
               for e in broken(lambda d, t: d.update(local_display_prefixes=[""])))

    # F2: replay verifies the whole log, not only model-state hashes.
    pinned = fresh(37)
    act(pinned, definition, "pin_point", {"point": "CHW822_GPM"}, "t1", T)

    swapped = json.loads(json.dumps(s))
    rec = next(r for r in swapped["records"] if r["action_id"] == "walk_pumproom")
    rec["action_id"] = "chiller_panel"
    assert replay(definition, truth, swapped), "a swapped action_id must be detected"

    obs_edit = json.loads(json.dumps(pinned))
    rec = next(r for r in obs_edit["records"] if r["action_id"] == "pin_point")
    rec["observation"] = "tampered observation"
    assert replay(definition, truth, obs_edit), "a tampered observation must be detected"

    actor_edit = json.loads(json.dumps(s))
    actor_edit["records"][0]["actor"] = ""
    assert replay(definition, truth, actor_edit), "a tampered actor must be detected"

    terminal_edit = json.loads(json.dumps(s))
    terminal_edit["terminal"] = "ABANDONED"
    assert replay(definition, truth, terminal_edit), "a tampered terminal state must be detected"

    unknown_action = json.loads(json.dumps(s))
    rec = next(r for r in unknown_action["records"] if r["kind"] == "action")
    rec["action_id"] = "teleport"
    result = replay(definition, truth, unknown_action)
    assert result, "an unreplayable action_id must be reported, not raised"

    # F3: recovery requires an explicit zero leak rate.
    assert s["state"]["_loop"]["leak_gpm"] == 0.0

    # F4: window reset and gate behavior.
    def to_ready(seed: int) -> dict[str, Any]:
        sess = fresh(seed)

        def go(aid: str, **params: str) -> dict[str, Any]:
            return act(sess, definition, aid, params, "t1", T)

        go("walk_pumproom"); go("chiller_panel"); go("read_suction_gauge"); go("check_strainer")
        go("lockout_p1")
        go("inspect_valve", valve="P1_TDV")
        go("isolate_p1_branch")
        go("replace_p1_valve")
        go("open_fill")
        wait(sess, definition, 60, "t1")
        wait(sess, definition, 30, "t1")
        go("close_fill")
        go("vent_air")
        go("open_p1_branch")
        go("energize_p1")
        go("start_p1")
        wait(sess, definition, 5, "t1")
        go("reset_chiller")
        wait(sess, definition, 10, "t1")
        wait(sess, definition, 60, "t1")
        assert lifecycle(sess, definition) == "READY_FOR_VERIFICATION", \
            [c for c in criteria(sess, definition) if not c["passed"]]
        return sess

    ready = to_ready(41)
    act(ready, definition, "open_fill", {}, "t1", T)
    wait(ready, definition, 1, "t1")
    assert ready["window_min"] == 0, ready["window_min"]
    assert not next(c for c in criteria(ready, definition) if c["id"] == "supply_stable")["passed"]

    deadhead = fresh(43)
    act(deadhead, definition, "lockout_p1", {}, "t1", T)
    act(deadhead, definition, "isolate_p1_branch", {}, "t1", T)
    act(deadhead, definition, "energize_p1", {}, "t1", T)
    act(deadhead, definition, "start_p1", {}, "t1", T)
    wait(deadhead, definition, 5, "t1")
    assert deadhead["events"]["deadhead_min"] > 0

    unproven = fresh(47)
    act(unproven, definition, "reset_chiller", {}, "t1", T)
    wait(unproven, definition, 10, "t1")
    assert unproven["state"]["chiller"]["tripped"]
    assert unproven["events"]["trips"] > 0

    escalated = fresh(19)
    act(escalated, definition, "escalate_hazard", {}, "t1", T)
    r_esc = act(escalated, definition, "inspect_valve", {"valve": "P1_TDV"}, "t1", T)
    assert r_esc["outcome"] == "done", r_esc

    rearmed = fresh(19)
    act(rearmed, definition, "lockout_p1", {}, "t1", T)
    act(rearmed, definition, "energize_p1", {}, "t1", T)
    r_rearm = act(rearmed, definition, "inspect_valve", {"valve": "P1_TDV"}, "t1", T)
    assert r_rearm["outcome"] == "unsafe_stop", r_rearm

    # Isolate-only path (lockout, isolate, start_p2, reset_chiller, waits): confirmed
    # BLOCKED, not asserted here -- see final-fix-report.md. The loop never regains
    # pressure or purges air without open_fill/vent_air, so it stays ISOLATED.

    # F5: input validation at the kernel boundary.
    v5 = fresh(53)
    r0 = act(v5, definition, "walk_pumproom", {}, "t1", T)
    try:
        set_hypotheses(v5, [{"text": "x", "status": "open", "supporting": [["R0001"]], "contradicting": []}], "t1")
        raise AssertionError("accepted a non-string supporting ref")
    except ValueError:
        pass

    fields5 = {k: "Synthetic test entry." for k in CLOSEOUT_FIELDS}
    fields5["executive_summary"] = "Synthetic closeout used for boundary validation."
    try:
        closeout(v5, definition, fields5,
                 {"root_cause": [{}], "competing_causes_excluded": [r0["record_id"]]}, "t1")
        raise AssertionError("accepted a non-string citation id")
    except ValueError:
        pass
    try:
        closeout(v5, definition, fields5,
                 {"root_cause": [r0["record_id"]], "competing_causes_excluded": [r0["record_id"]],
                  "pm_task": "junk"}, "t1")
        raise AssertionError("accepted a non-list citation for an uncited field")
    except ValueError:
        pass

    set_hypotheses(v5, [{"text": "A hypothesis.", "status": "open", "supporting": [], "contradicting": [],
                         "extra": "drop me"}], "t1")
    assert "extra" not in v5["hypotheses"][0], v5["hypotheses"]

    try:
        set_hypotheses(v5, [{"text": "x", "status": "open", "supporting": [], "contradicting": []}] * 21, "t1")
        raise AssertionError("accepted 21 hypotheses")
    except ValueError:
        pass

    caller_hyps = [{"text": "Mutate me.", "status": "open", "supporting": [], "contradicting": []}]
    set_hypotheses(v5, caller_hyps, "t1")
    caller_hyps[0]["text"] = "mutated after the call"
    assert v5["hypotheses"][0]["text"] == "Mutate me."

    for bad_actor in ("", None):
        try:
            act(v5, definition, "walk_pumproom", {}, bad_actor, T)
            raise AssertionError(f"accepted actor {bad_actor!r}")
        except ValueError:
            pass

    for bad_seed in (None, True):
        try:
            new_session(definition, truth, bad_seed)
            raise AssertionError(f"accepted seed {bad_seed!r}")
        except ValueError:
            pass

    for bad_id in ("S-001\n", "S-999"):
        try:
            load_scenario(bad_id)
            raise AssertionError(f"accepted scenario id {bad_id!r}")
        except ValueError:
            pass

    print("scenario_kernel self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
