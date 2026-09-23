"""Niagara-style Schedule components.

A weekly occupied/unoccupied time pattern plus date exceptions, mirroring
Niagara's BooleanSchedule. Linked points get a schedule-driven baseline
value (occupied vs. unoccupied) that bas_api.py applies whenever no
operator override is active for that point -- the same priority-array
idea Niagara uses (manual override beats a Schedule link beats a
block's default).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEDULES_FILE = ROOT / "data" / "input" / "schedules.json"


def load_schedules() -> list[dict[str, Any]]:
    if not SCHEDULES_FILE.exists():
        return []
    return json.loads(SCHEDULES_FILE.read_text(encoding="utf-8"))


def find_schedule(schedule_id: str) -> dict[str, Any] | None:
    for schedule in load_schedules():
        if schedule["schedule_id"] == schedule_id:
            return schedule
    return None


def effective_output(schedule: dict[str, Any], at: datetime) -> dict[str, Any]:
    """Resolve a schedule's effective boolean output at a given time.

    A same-date exception wins outright, exactly like a Niagara Schedule's
    Calendar-driven exceptions take priority over its weekly pattern.
    """
    date_str = at.date().isoformat()
    for exc in schedule.get("exceptions", []):
        if exc["date"] == date_str:
            return {"value": bool(exc["value"]), "source": "exception", "label": exc.get("label")}

    weekday = at.strftime("%A").lower()
    time_str = at.strftime("%H:%M")
    for start, end in schedule.get("weekly", {}).get(weekday, []):
        if start <= time_str < end:
            return {"value": True, "source": "weekly", "label": None}

    return {"value": bool(schedule.get("default_value", False)), "source": "default", "label": None}


def schedule_for_point(point_name: str) -> dict[str, Any] | None:
    """The schedule (if any) driving a given point's baseline value."""
    for schedule in load_schedules():
        if any(link["point"] == point_name for link in schedule.get("linked_points", [])):
            return schedule
    return None


def linked_point_baseline(schedule: dict[str, Any], point_name: str, occupied: bool) -> float | None:
    """A schedule-driven point's baseline value for the resolved occupied state."""
    for link in schedule.get("linked_points", []):
        if link["point"] == point_name:
            return link["occupied_value"] if occupied else link["unoccupied_value"]
    return None
