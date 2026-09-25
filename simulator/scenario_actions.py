"""S-001 action effects and prerequisite checks, used by scenario_kernel.

Each effect handler runs *after* the kernel has advanced the simulated clock
by the action's time cost. It mutates the session (the lineup, flags, or the
model state through model822's public helpers) and returns
(observation text or None, list of state-change descriptions). Observations
come from field_obs and the model's own outputs: they are evidence, never
the hidden answer.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
import field_obs  # noqa: E402
import model822  # noqa: E402

PREREQUISITES: dict[str, str] = {
    "p1_deenergized": "P1 is still energized",
    "p1_energized": "P1 is locked out",
    "p1_branch_isolated": "The P1 branch is not isolated",
}

EFFECTS = (
    "pin_point", "observe_chiller_panel", "observe_pumproom", "observe_gauge",
    "observe_amps", "observe_valve", "observe_strainer", "observe_travel",
    "lockout_p1", "escalate_hazard", "energize_p1", "isolate_p1_branch",
    "open_p1_branch", "replace_p1_valve", "open_fill", "close_fill",
    "vent_air", "start_pump", "stop_pump", "reset_chiller",
)


def prerequisite_met(name: str, session: dict[str, Any]) -> bool:
    lineup = session["lineup"]
    if name == "p1_deenergized":
        return not lineup["p1_energized"]
    if name == "p1_energized":
        return lineup["p1_energized"]
    if name == "p1_branch_isolated":
        return lineup["p1_branch_isolated"]
    raise KeyError(name)


Handler = Callable[[dict[str, Any], dict[str, str]], tuple[Any, list[str]]]


def _truth(session: dict[str, Any]) -> dict[str, float]:
    return model822.ground_truth_snapshot(session["state"])


def _set_lineup(session: dict[str, Any], key: str, value: bool, changes: list[str]) -> None:
    old = session["lineup"][key]
    if old != value:
        session["lineup"][key] = value
        changes.append(f"{key}: {old} -> {value}")


def _pin_point(session, params):
    point = params["point"]
    return f"{point} = {session['pts'][point]} (BAS, minute {session['clock_min']})", []


def _observe_chiller_panel(session, params):
    ch = session["state"].get("_chiller", {})
    return (f"Chiller panel: active diagnostic {ch.get('active_diag', 'None')}; evaporator "
            f"leaving {ch.get('lwt_f')} F, entering {ch.get('ewt_f')} F; capacity "
            f"{ch.get('pct_capacity')}%."), []


def _observe_pumproom(session, params):
    return field_obs.pumproom_walk(_truth(session)), []


def _observe_gauge(session, params):
    return field_obs.gauge_reading(_truth(session)), []


def _observe_amps(session, params):
    return field_obs.amps_reading(_truth(session), params["pump"]), []


def _observe_valve(session, params):
    return field_obs.valve_inspection(_truth(session), params["valve"]), []


def _observe_strainer(session, params):
    dp = session["pts"]["CHW822_STRAINER_DP"]
    return f"Strainer differential pressure {dp:.1f} psid (a clean strainer reads about 1.5 psid).", []


def _observe_travel(session, params):
    return field_obs.travel_reading(_truth(session), "MAU04"), []


def _lockout_p1(session, params):
    changes: list[str] = []
    _set_lineup(session, "p1_running", False, changes)
    _set_lineup(session, "p1_energized", False, changes)
    return "P1 de-energized at its breaker and locked out (simulated lockout/tagout decision).", changes


def _escalate_hazard(session, params):
    changes: list[str] = []
    if not session["flags"]["escalated"]:
        session["flags"]["escalated"] = True
        changes.append("escalated: False -> True")
    _set_lineup(session, "p1_running", False, changes)
    _set_lineup(session, "p1_energized", False, changes)
    return ("Supervisor notified of standing water at the P1 pump; the electrician de-energized "
            "P1 at its breaker and locked it out."), changes


def _energize_p1(session, params):
    changes: list[str] = []
    _set_lineup(session, "p1_energized", True, changes)
    return "P1 lockout removed and P1 re-energized; it stays off until started.", changes


def _isolate_p1_branch(session, params):
    changes: list[str] = []
    _set_lineup(session, "p1_branch_isolated", True, changes)
    return "P1 branch suction and discharge isolation valves closed.", changes


def _open_p1_branch(session, params):
    changes: list[str] = []
    _set_lineup(session, "p1_branch_isolated", False, changes)
    return "P1 branch isolation valves opened.", changes


def _replace_p1_valve(session, params):
    if session["flags"]["valve_replaced"]:
        return "P1_TDV was already replaced.", []
    session["flags"]["valve_replaced"] = True
    return "P1_TDV valve body replaced.", ["P1_TDV valve body replaced"]


def _open_fill(session, params):
    changes: list[str] = []
    _set_lineup(session, "makeup_valve_open", True, changes)
    return "Makeup (fill) valve open.", changes


def _close_fill(session, params):
    changes: list[str] = []
    _set_lineup(session, "makeup_valve_open", False, changes)
    return "Makeup (fill) valve closed.", changes


def _vent_air(session, params):
    if model822.purge_air(session["state"]):
        return "Air sputters out of the high-point vent, then solid water.", ["loop air vented"]
    return "Nothing comes out of the high-point vent: there is no pressure behind it.", []


def _pump_key(params) -> str:
    return "p1_running" if params["pump"] == "P1" else "p2_running"


def _start_pump(session, params):
    changes: list[str] = []
    _set_lineup(session, _pump_key(params), True, changes)
    return f"{params['pump']} started.", changes


def _stop_pump(session, params):
    changes: list[str] = []
    _set_lineup(session, _pump_key(params), False, changes)
    return f"{params['pump']} stopped.", changes


def _reset_chiller(session, params):
    if model822.reset_chiller(session["state"])["cleared"]:
        return "Reset accepted; the chiller is starting.", ["chiller reset"]
    return "Reset pressed; there was no latched diagnostic to clear.", ["chiller reset (nothing latched)"]


HANDLERS: dict[str, Handler] = {
    "pin_point": _pin_point, "observe_chiller_panel": _observe_chiller_panel,
    "observe_pumproom": _observe_pumproom, "observe_gauge": _observe_gauge,
    "observe_amps": _observe_amps, "observe_valve": _observe_valve,
    "observe_strainer": _observe_strainer, "observe_travel": _observe_travel,
    "lockout_p1": _lockout_p1, "escalate_hazard": _escalate_hazard, "energize_p1": _energize_p1,
    "isolate_p1_branch": _isolate_p1_branch, "open_p1_branch": _open_p1_branch,
    "replace_p1_valve": _replace_p1_valve, "open_fill": _open_fill, "close_fill": _close_fill,
    "vent_air": _vent_air, "start_pump": _start_pump, "stop_pump": _stop_pump,
    "reset_chiller": _reset_chiller,
}
