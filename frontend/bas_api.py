"""Synthetic hospital BAS API — serves Metasys and Niagara front-end UIs."""

from __future__ import annotations

import csv
import json
import random
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "data" / "output"
INPUT_DIR = ROOT / "data" / "input"
STATIC_DIR = Path(__file__).resolve().parent / "static"

SCENARIOS = ["normal", "chilled_water_degraded", "isolation_pressure_loss", "or_humidity_excursion"]
ROLES = ["viewer", "operator", "technician", "vendor", "admin", "security reviewer"]
AUTHORIZED_TO_COMMAND = {"technician", "admin"}
OVERRIDES_FILE = OUTPUT_DIR / "operator_overrides.json"
OPERATOR_LOG_FILE = OUTPUT_DIR / "operator_actions.jsonl"
FAULT_LIBRARY_FILE = INPUT_DIR / "fault_library.json"
TROUBLE_CALL_ACTIVE_FILE = OUTPUT_DIR / "trouble_call_active.json"
TROUBLE_CALL_LOG_FILE = OUTPUT_DIR / "trouble_call_log.jsonl"


class DiagnosisRequest(BaseModel):
    guessed_equipment: str
    guessed_category: str

app = FastAPI(title="Synthetic Hospital BAS", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _load_points_file() -> dict[str, Any]:
    path = OUTPUT_DIR / "latest_points.json"
    if not path.exists():
        raise HTTPException(status_code=503, detail="No simulator output found — run a scenario first")
    return json.loads(path.read_text(encoding="utf-8"))


def _load_input_points() -> list[dict[str, Any]]:
    return json.loads((INPUT_DIR / "points.json").read_text(encoding="utf-8"))


def _load_input_equipment() -> dict[str, Any]:
    return json.loads((INPUT_DIR / "equipment.json").read_text(encoding="utf-8"))


def _load_faults() -> dict[str, dict[str, Any]]:
    raw = json.loads(FAULT_LIBRARY_FILE.read_text(encoding="utf-8"))
    return {item["fault_id"]: item for item in raw}


def _load_alarms() -> list[dict[str, Any]]:
    path = OUTPUT_DIR / "alarms.jsonl"
    if not path.exists():
        return []
    alarms = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            alarms.append(json.loads(line))
    return alarms


def _load_trends() -> list[dict[str, Any]]:
    path = OUTPUT_DIR / "trends.csv"
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def _load_overrides() -> dict[str, dict[str, Any]]:
    if not OVERRIDES_FILE.exists():
        return {}
    return json.loads(OVERRIDES_FILE.read_text(encoding="utf-8"))


def _write_overrides(overrides: dict[str, dict[str, Any]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    OVERRIDES_FILE.write_text(json.dumps(overrides, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_operator_action(action: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    role = action.get("role") or "system"
    operator_id = action.get("operator_id") or "BAS-OPR-01"
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data_boundary": "synthetic lab operator action only",
        **action,
        "role": role,
        "operator_id": operator_id,
    }
    with OPERATOR_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, sort_keys=True) + "\n")


def _point_metadata(point_name: str) -> dict[str, Any]:
    for pt in _load_input_points():
        if pt["point"] == point_name:
            return pt
    raise HTTPException(status_code=404, detail=f"Point {point_name!r} not found")


def _coerce_point_value(point: dict[str, Any], value: float) -> float | int:
    if point["units"] == "bool":
        if value not in (0, 1):
            raise HTTPException(status_code=400, detail="Boolean commands must be 0 or 1")
        return int(value)
    return round(float(value), 3)


def _require_command_role(role: str) -> None:
    if role not in AUTHORIZED_TO_COMMAND:
        raise HTTPException(
            status_code=403,
            detail=(
                f"Role {role!r} is not authorized to command or release points. "
                "Allowed roles: technician, admin."
            ),
        )


def _effective_fault(fault: dict[str, Any], seed: int) -> dict[str, Any]:
    variants = fault.get("variants") or []
    if not variants:
        return fault
    variant = random.Random(seed).choice(variants)
    selected = dict(fault)
    selected["category"] = variant.get("category", fault["category"])
    selected["correct_category"] = variant.get("correct_category", fault["correct_category"])
    selected["injection"] = variant["injection"]
    selected["explanation"] = variant.get("explanation", fault["explanation"])
    selected["variant_id"] = variant.get("variant_id")
    return selected


def _equipment_options(faults: dict[str, dict[str, Any]]) -> list[str]:
    return sorted({fault["correct_equipment"] for fault in faults.values()})


def _category_options() -> list[str]:
    return ["sensor_failure", "actuator_stuck", "mechanical_failure", "control_loop_fault", "comms_loss"]


def _load_active_ticket() -> dict[str, Any] | None:
    if not TROUBLE_CALL_ACTIVE_FILE.exists():
        return None
    return json.loads(TROUBLE_CALL_ACTIVE_FILE.read_text(encoding="utf-8"))


def _write_active_ticket(ticket: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    TROUBLE_CALL_ACTIVE_FILE.write_text(json.dumps(ticket, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _append_trouble_call_log(entry: dict[str, Any]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with TROUBLE_CALL_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")


def _load_trouble_call_log() -> list[dict[str, Any]]:
    if not TROUBLE_CALL_LOG_FILE.exists():
        return []
    rows = []
    for line in TROUBLE_CALL_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


# ---------------------------------------------------------------------------
# Root — redirect to index
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def root() -> HTMLResponse:
    index = STATIC_DIR / "index.html"
    return HTMLResponse(content=index.read_text(encoding="utf-8"))


@app.get("/metasys", response_class=HTMLResponse)
def metasys_redirect() -> HTMLResponse:
    page = STATIC_DIR / "metasys.html"
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


@app.get("/niagara", response_class=HTMLResponse)
def niagara_redirect() -> HTMLResponse:
    page = STATIC_DIR / "niagara.html"
    return HTMLResponse(content=page.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# API endpoints
# ---------------------------------------------------------------------------

@app.get("/api/points")
def get_points() -> dict[str, Any]:
    """All current point values organised by equipment."""
    snapshot = _load_points_file()
    input_pts = _load_input_points()
    alarms = _load_alarms()
    overrides = _load_overrides()
    alarmed = {a["point"] for a in alarms}

    by_equipment: dict[str, list[dict[str, Any]]] = {}
    for pt in input_pts:
        name = pt["point"]
        equip = pt["equipment"]
        value = snapshot["points"].get(name)
        override = overrides.get(name)
        if override:
            value = override["value"]
        entry = {
            "point": name,
            "equipment": equip,
            "facility": pt.get("facility"),
            "type": pt["type"],
            "units": pt["units"],
            "value": value,
            "normal_min": pt["normal_min"],
            "normal_max": pt["normal_max"],
            "writable": pt["writable"],
            "critical": pt["critical"],
            "status": "alarm" if name in alarmed else "normal",
            "overridden": bool(override),
            "operator_note": override.get("reason") if override else None,
        }
        by_equipment.setdefault(equip, []).append(entry)

    return {
        "scenario": snapshot.get("scenario", "unknown"),
        "generated_at": snapshot.get("generated_at"),
        "data_boundary": snapshot.get("data_boundary"),
        "equipment": by_equipment,
    }


@app.get("/api/points/{point_name}")
def get_point(point_name: str) -> dict[str, Any]:
    """Single point value with full metadata."""
    snapshot = _load_points_file()
    input_pts = _load_input_points()
    alarms = _load_alarms()
    overrides = _load_overrides()
    alarmed = {a["point"]: a for a in alarms}

    for pt in input_pts:
        if pt["point"] == point_name:
            value = snapshot["points"].get(point_name)
            override = overrides.get(point_name)
            if override:
                value = override["value"]
            result = {
                "point": point_name,
                "equipment": pt["equipment"],
                "facility": pt.get("facility"),
                "type": pt["type"],
                "units": pt["units"],
                "value": value,
                "normal_min": pt["normal_min"],
                "normal_max": pt["normal_max"],
                "writable": pt["writable"],
                "critical": pt["critical"],
                "status": "alarm" if point_name in alarmed else "normal",
                "overridden": bool(override),
                "operator_note": override.get("reason") if override else None,
            }
            if point_name in alarmed:
                result["alarm"] = alarmed[point_name]
            return result
    raise HTTPException(status_code=404, detail=f"Point {point_name!r} not found")


@app.get("/api/alarms")
def get_alarms() -> dict[str, Any]:
    """All active alarms from the most recent simulator run."""
    alarms = _load_alarms()
    by_priority: dict[str, int] = {}
    for a in alarms:
        by_priority[a["priority"]] = by_priority.get(a["priority"], 0) + 1
    return {
        "count": len(alarms),
        "by_priority": by_priority,
        "alarms": alarms,
    }


@app.get("/api/trends/{point_name}")
def get_trends(point_name: str) -> dict[str, Any]:
    """Trend rows for a specific point."""
    rows = [r for r in _load_trends() if r["point"] == point_name]
    if not rows:
        raise HTTPException(status_code=404, detail=f"No trend data for {point_name!r}")
    return {
        "point": point_name,
        "count": len(rows),
        "rows": rows,
    }


@app.get("/api/scenarios")
def get_scenarios() -> dict[str, Any]:
    """Available simulator scenarios."""
    return {"scenarios": SCENARIOS}


@app.get("/api/equipment")
def get_equipment() -> dict[str, Any]:
    """Equipment inventory from data/input/equipment.json."""
    return _load_input_equipment()


@app.get("/api/roles")
def get_roles() -> dict[str, Any]:
    """Synthetic lab roles for the technician panel selector."""
    return {
        "roles": ROLES,
        "authorized_to_command": sorted(AUTHORIZED_TO_COMMAND),
        "default": "viewer",
        "data_boundary": "synthetic lab roles only",
    }


@app.get("/api/operator-actions")
def get_operator_actions() -> dict[str, Any]:
    """Synthetic operator command/release history for the lab session."""
    if not OPERATOR_LOG_FILE.exists():
        return {"count": 0, "actions": [], "data_boundary": "synthetic lab operator action only"}
    actions = []
    for line in OPERATOR_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            actions.append(json.loads(line))
    return {
        "count": len(actions),
        "actions": actions[-50:],
        "data_boundary": "synthetic lab operator action only",
    }


@app.post("/api/trouble-calls/new")
def new_trouble_call(fault_id: str | None = None) -> dict[str, Any]:
    """Open one synthetic trouble-call ticket and run its fault simulation."""
    active = _load_active_ticket()
    if active and not active.get("diagnosed"):
        raise HTTPException(
            status_code=409,
            detail={
                "ticket_id": active["ticket_id"],
                "symptom_text": active["symptom_text"],
                "message": "A trouble-call ticket is already open.",
            },
        )

    faults = _load_faults()
    selected_fault_id = fault_id or random.choice(list(faults))
    if selected_fault_id not in faults:
        raise HTTPException(status_code=400, detail=f"Unknown fault_id {selected_fault_id!r}")

    seed = random.randint(1, 999999)
    fault = _effective_fault(faults[selected_fault_id], seed)
    result = subprocess.run(
        [
            sys.executable,
            str(ROOT / "simulator" / "bas_sim.py"),
            "--fault",
            selected_fault_id,
            "--steps",
            "12",
            "--seed",
            str(seed),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Simulator error: {result.stderr}")

    ticket = {
        "ticket_id": f"TC-{uuid4().hex[:8].upper()}",
        "fault_id": selected_fault_id,
        "variant_id": fault.get("variant_id"),
        "seed": seed,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "symptom_text": fault["symptom_text"],
        "diagnosed": False,
    }
    _write_active_ticket(ticket)
    return {
        "ticket_id": ticket["ticket_id"],
        "symptom_text": ticket["symptom_text"],
        "equipment_options": _equipment_options(faults),
        "category_options": _category_options(),
        "data_boundary": "synthetic lab trouble-call data only",
    }


@app.get("/api/trouble-calls/active")
def active_trouble_call() -> dict[str, Any]:
    """Return the open trouble-call symptom without answer fields."""
    active = _load_active_ticket()
    if not active or active.get("diagnosed"):
        return {
            "active": False,
            "equipment_options": _equipment_options(_load_faults()),
            "category_options": _category_options(),
            "data_boundary": "synthetic lab trouble-call data only",
        }
    return {
        "active": True,
        "ticket_id": active["ticket_id"],
        "symptom_text": active["symptom_text"],
        "equipment_options": _equipment_options(_load_faults()),
        "category_options": _category_options(),
        "data_boundary": "synthetic lab trouble-call data only",
    }


@app.post("/api/trouble-calls/{ticket_id}/diagnose")
def diagnose_trouble_call(ticket_id: str, diagnosis: DiagnosisRequest) -> dict[str, Any]:
    """Grade a synthetic trouble-call diagnosis and close the active ticket."""
    active = _load_active_ticket()
    if not active or active.get("diagnosed") or active["ticket_id"] != ticket_id:
        raise HTTPException(status_code=404, detail=f"Open trouble-call ticket {ticket_id!r} not found")

    faults = _load_faults()
    fault = _effective_fault(faults[active["fault_id"]], int(active["seed"]))
    correct = (
        diagnosis.guessed_equipment == fault["correct_equipment"]
        and diagnosis.guessed_category == fault["correct_category"]
    )
    answered_at = datetime.now(timezone.utc).isoformat()
    log_entry = {
        "ticket_id": active["ticket_id"],
        "fault_id": active["fault_id"],
        "variant_id": fault.get("variant_id"),
        "guessed_equipment": diagnosis.guessed_equipment,
        "guessed_category": diagnosis.guessed_category,
        "actual_equipment": fault["correct_equipment"],
        "actual_category": fault["correct_category"],
        "correct": correct,
        "opened_at": active["opened_at"],
        "answered_at": answered_at,
        "data_boundary": "synthetic lab trouble-call data only",
    }
    _append_trouble_call_log(log_entry)
    TROUBLE_CALL_ACTIVE_FILE.unlink(missing_ok=True)
    return {
        "correct": correct,
        "actual_equipment": fault["correct_equipment"],
        "actual_category": fault["correct_category"],
        "explanation": fault["explanation"],
        "data_boundary": "synthetic lab trouble-call data only",
    }


@app.get("/api/trouble-calls/history")
def trouble_call_history() -> dict[str, Any]:
    """Return the last 20 diagnosed trouble-call records."""
    rows = _load_trouble_call_log()
    return {
        "count": len(rows),
        "history": rows[-20:],
        "data_boundary": "synthetic lab trouble-call data only",
    }


@app.post("/api/points/{point_name}/command")
def command_point(
    point_name: str,
    value: float = Query(..., description="Synthetic commanded value"),
    role: str = Query(..., description="Self-declared synthetic lab role"),
    operator_id: str = Query("BAS-OPR-01", max_length=80),
    reason: str = Query("operator training", max_length=120),
) -> dict[str, Any]:
    """Command a writable synthetic point for operator training only."""
    _require_command_role(role)
    point = _point_metadata(point_name)
    if not point["writable"]:
        raise HTTPException(status_code=400, detail=f"{point_name!r} is read-only in the synthetic point map")
    command_value = _coerce_point_value(point, value)
    overrides = _load_overrides()
    overrides[point_name] = {
        "value": command_value,
        "reason": reason,
        "operator": operator_id,
        "role": role,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    _write_overrides(overrides)
    _append_operator_action(
        {
            "action": "command",
            "point": point_name,
            "equipment": point["equipment"],
            "value": command_value,
            "units": point["units"],
            "reason": reason,
            "role": role,
            "operator_id": operator_id,
        }
    )
    return {
        "point": point_name,
        "value": command_value,
        "units": point["units"],
        "status": "commanded",
        "role": role,
        "operator_id": operator_id,
        "data_boundary": "synthetic lab operator action only",
    }


@app.post("/api/points/{point_name}/release")
def release_point(
    point_name: str,
    role: str = Query(..., description="Self-declared synthetic lab role"),
    operator_id: str = Query("BAS-OPR-01", max_length=80),
) -> dict[str, Any]:
    """Release a synthetic point override and return control to the simulator snapshot."""
    _require_command_role(role)
    point = _point_metadata(point_name)
    overrides = _load_overrides()
    existed = point_name in overrides
    overrides.pop(point_name, None)
    _write_overrides(overrides)
    _append_operator_action(
        {
            "action": "release",
            "point": point_name,
            "equipment": point["equipment"],
            "value": None,
            "units": point["units"],
            "reason": "operator release to simulator",
            "role": role,
            "operator_id": operator_id,
        }
    )
    return {
        "point": point_name,
        "status": "released" if existed else "not_overridden",
        "role": role,
        "operator_id": operator_id,
        "data_boundary": "synthetic lab operator action only",
    }


@app.post("/api/run/{scenario}")
def run_scenario(scenario: str, steps: int = 12) -> dict[str, Any]:
    """Trigger the simulator for a given scenario and return summary."""
    if scenario not in SCENARIOS:
        raise HTTPException(status_code=400, detail=f"Unknown scenario {scenario!r}. Valid: {SCENARIOS}")
    result = subprocess.run(
        [sys.executable, str(ROOT / "simulator" / "bas_sim.py"),
         "--scenario", scenario, "--steps", str(steps)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    if result.returncode != 0:
        raise HTTPException(status_code=500, detail=f"Simulator error: {result.stderr}")
    _write_overrides({})
    _append_operator_action(
        {
            "action": "run_scenario",
            "scenario": scenario,
            "steps": steps,
            "reason": "operator selected simulator scenario",
        }
    )
    snapshot = _load_points_file()
    alarms = _load_alarms()
    return {
        "scenario": scenario,
        "steps": steps,
        "generated_at": snapshot.get("generated_at"),
        "alarm_count": len(alarms),
        "data_boundary": snapshot.get("data_boundary"),
    }
