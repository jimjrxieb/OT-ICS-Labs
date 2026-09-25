"""S-001 action effects and prerequisite checks, used by scenario_kernel.

Each effect handler runs *after* the kernel has advanced the simulated clock
by the action's time cost. It mutates the session (the lineup, flags, or the
model state through model822's public helpers) and returns
(observation text or None, list of state-change descriptions). Observations
come from field_obs and the model's own outputs: they are evidence, never
the hidden answer.
"""

from __future__ import annotations

from typing import Any

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
