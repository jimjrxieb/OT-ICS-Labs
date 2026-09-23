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

from . import platform_admin, px_pages, schedules, wiresheets

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


class WireSheetSaveRequest(BaseModel):
    blocks: list[dict[str, Any]]
    links: list[dict[str, Any]]


class PxSaveRequest(BaseModel):
    widgets: list[dict[str, Any]]

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


def _schedule_baseline(point_name: str, now: datetime | None = None) -> dict[str, Any] | None:
    """A Schedule-driven baseline for a point, if one links to it.

    Mirrors Niagara's priority array: this is consulted only when no
    operator override is active for the point (the caller enforces that).
    """
    schedule = schedules.schedule_for_point(point_name)
    if schedule is None:
        return None
    resolved = schedules.effective_output(schedule, now or datetime.now(timezone.utc))
    return {
        "schedule_id": schedule["schedule_id"],
        "occupied": resolved["value"],
        "source": resolved["source"],
        "value": schedules.linked_point_baseline(schedule, point_name, resolved["value"]),
    }


def _resolve_point_value(
    point_name: str,
    snapshot: dict[str, Any],
    overrides: dict[str, dict[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    """A point's effective value plus what's driving it.

    Priority order mirrors Niagara's priority array: an operator override
    always wins; failing that, a Schedule's linked baseline; failing
    that, the simulator's computed value.
    """
    value = snapshot["points"].get(point_name)
    override = overrides.get(point_name)
    driven_by = "computed"
    schedule_id = None
    if override:
        value = override["value"]
        driven_by = "override"
    else:
        baseline = _schedule_baseline(point_name, now)
        if baseline and baseline["value"] is not None:
            value = baseline["value"]
            driven_by = "schedule"
            schedule_id = baseline["schedule_id"]
    return {
        "value": value,
        "driven_by": driven_by,
        "schedule_id": schedule_id,
        "overridden": bool(override),
        "operator_note": override.get("reason") if override else None,
    }


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
        resolved = _resolve_point_value(name, snapshot, overrides)
        entry = {
            "point": name,
            "equipment": equip,
            "facility": pt.get("facility"),
            "type": pt["type"],
            "units": pt["units"],
            "value": resolved["value"],
            "normal_min": pt["normal_min"],
            "normal_max": pt["normal_max"],
            "writable": pt["writable"],
            "critical": pt["critical"],
            "status": "alarm" if name in alarmed else "normal",
            "overridden": resolved["overridden"],
            "operator_note": resolved["operator_note"],
            "states": pt.get("states"),
            "driven_by": resolved["driven_by"],
            "schedule_id": resolved["schedule_id"],
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
            resolved = _resolve_point_value(point_name, snapshot, overrides)
            result = {
                "point": point_name,
                "equipment": pt["equipment"],
                "facility": pt.get("facility"),
                "type": pt["type"],
                "units": pt["units"],
                "value": resolved["value"],
                "normal_min": pt["normal_min"],
                "normal_max": pt["normal_max"],
                "writable": pt["writable"],
                "critical": pt["critical"],
                "status": "alarm" if point_name in alarmed else "normal",
                "overridden": resolved["overridden"],
                "operator_note": resolved["operator_note"],
                "states": pt.get("states"),
                "driven_by": resolved["driven_by"],
                "schedule_id": resolved["schedule_id"],
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


@app.get("/api/schedules")
def get_schedules() -> dict[str, Any]:
    """All Schedule components and their current effective output."""
    now = datetime.now(timezone.utc)
    result = []
    for schedule in schedules.load_schedules():
        resolved = schedules.effective_output(schedule, now)
        result.append({
            "schedule_id": schedule["schedule_id"],
            "display_name": schedule.get("display_name", schedule["schedule_id"]),
            "type": schedule.get("type", "BooleanSchedule"),
            "facility": schedule.get("facility"),
            "effective_value": resolved["value"],
            "effective_source": resolved["source"],
            "effective_label": resolved["label"],
            "linked_points": [link["point"] for link in schedule.get("linked_points", [])],
        })
    return {"generated_at": now.isoformat(), "schedules": result}


@app.get("/api/schedules/{schedule_id}")
def get_schedule(schedule_id: str) -> dict[str, Any]:
    """One Schedule component's weekly pattern, exceptions, and linked points."""
    schedule = schedules.find_schedule(schedule_id)
    if schedule is None:
        raise HTTPException(status_code=404, detail=f"Schedule {schedule_id!r} not found")
    now = datetime.now(timezone.utc)
    resolved = schedules.effective_output(schedule, now)
    overrides = _load_overrides()
    linked = []
    for link in schedule.get("linked_points", []):
        point_name = link["point"]
        override = overrides.get(point_name)
        linked.append({
            "point": point_name,
            "equipment": link["equipment"],
            "occupied_value": link["occupied_value"],
            "unoccupied_value": link["unoccupied_value"],
            "current_baseline": schedules.linked_point_baseline(schedule, point_name, resolved["value"]),
            "driven_by": "override" if override else "schedule",
        })
    return {
        "schedule_id": schedule["schedule_id"],
        "display_name": schedule.get("display_name", schedule["schedule_id"]),
        "type": schedule.get("type", "BooleanSchedule"),
        "facility": schedule.get("facility"),
        "weekly": schedule.get("weekly", {}),
        "exceptions": schedule.get("exceptions", []),
        "default_value": schedule.get("default_value", False),
        "effective_value": resolved["value"],
        "effective_source": resolved["source"],
        "effective_label": resolved["label"],
        "linked_points": linked,
        "generated_at": now.isoformat(),
    }


@app.get("/api/wiresheets")
def get_wiresheets() -> dict[str, Any]:
    """All Wire Sheet programs."""
    return {
        "wiresheets": [
            {
                "wiresheet_id": ws["wiresheet_id"],
                "display_name": ws.get("display_name", ws["wiresheet_id"]),
                "ord": ws.get("ord"),
            }
            for ws in wiresheets.load_wiresheets()
        ]
    }


@app.get("/api/wiresheets/block-types")
def get_wiresheet_block_types() -> dict[str, Any]:
    """Known Wire Sheet block types and their input/output slots, for the editor's Add Block/Add Link forms."""
    return {"block_types": wiresheets.BLOCK_SLOTS}


@app.get("/api/wiresheets/{wiresheet_id}")
def get_wiresheet(wiresheet_id: str) -> dict[str, Any]:
    """One Wire Sheet's blocks and links, each block's slots resolved live."""
    ws = wiresheets.find_wiresheet(wiresheet_id)
    if ws is None:
        raise HTTPException(status_code=404, detail=f"Wire Sheet {wiresheet_id!r} not found")

    now = datetime.now(timezone.utc)
    schedule_ctx = {}
    for schedule_id in wiresheets.referenced_schedule_ids(ws):
        schedule = schedules.find_schedule(schedule_id)
        if schedule is not None:
            schedule_ctx[schedule_id] = schedules.effective_output(schedule, now)["value"]

    point_ctx: dict[str, Any] = {}
    point_names = wiresheets.referenced_point_names(ws)
    if point_names:
        snapshot = _load_points_file()
        overrides = _load_overrides()
        for name in point_names:
            point_ctx[name] = _resolve_point_value(name, snapshot, overrides, now)["value"]

    resolved = wiresheets.evaluate(ws, {"schedules": schedule_ctx, "points": point_ctx})

    return {
        "wiresheet_id": ws["wiresheet_id"],
        "display_name": ws.get("display_name", ws["wiresheet_id"]),
        "ord": ws.get("ord"),
        "description": ws.get("description"),
        "blocks": [
            {**block, "slots": wiresheets.slot_spec(block["type"]), "resolved": resolved.get(block["block_id"], {})}
            for block in ws["blocks"]
        ],
        "links": ws.get("links", []),
        "generated_at": now.isoformat(),
    }


def _wiresheet_reference_inventory() -> dict[str, set[str]]:
    """Points and schedules a Wire Sheet block may reference on save."""
    return {
        "known_points": {pt["point"] for pt in _load_input_points()},
        "known_schedules": {s["schedule_id"] for s in schedules.load_schedules()},
    }


def _entity_from_backup(backup_dir: str, filename: str, id_key: str, entity_id: str) -> dict[str, Any]:
    """The one Wire Sheet / Px page with `entity_id` inside a recorded backup.

    Raises BackupError for anything that makes the backup unusable as a
    restore source. Reads only; nothing is written.
    """
    records = platform_admin.read_backup_file(backup_dir, filename)
    matches = [r for r in records if isinstance(r, dict) and r.get(id_key) == entity_id]
    if not matches:
        raise platform_admin.BackupError(f"backup {backup_dir!r} does not contain {id_key} {entity_id!r}")
    if len(matches) > 1:
        raise platform_admin.BackupError(f"backup {backup_dir!r} contains {id_key} {entity_id!r} more than once")
    return matches[0]


def _backup_rows(filename: str, id_key: str, entity_id: str) -> list[dict[str, Any]]:
    """Backups holding `filename` that contain this entity, newest first."""
    rows = []
    for entry in platform_admin.backups_containing(filename):
        try:
            _entity_from_backup(entry["backup_dir"], filename, id_key, entity_id)
        except platform_admin.BackupError:
            continue
        rows.append({
            "backup_dir": entry["backup_dir"],
            "timestamp": entry["timestamp"],
            "kind": entry.get("kind"),
            "operator_id": entry.get("operator_id"),
        })
    return rows


def _restore_entity(
    *,
    noun: str,
    action_prefix: str,
    id_key: str,
    entity_id: str,
    filename: str,
    backup_dir: str,
    role: str,
    operator_id: str,
    load: Any,
    save: Any,
    validate: Any,
) -> dict[str, Any]:
    """Restore one Wire Sheet / Px page from a recorded backup.

    Order matters: authorize, then validate the backup completely, then
    snapshot the current store, then write, then audit. Any failure before
    the snapshot leaves the store untouched.
    """
    _require_command_role(role)
    current = load()
    if not any(r[id_key] == entity_id for r in current):
        raise HTTPException(status_code=404, detail=f"{noun} {entity_id!r} not found")

    try:
        restored = _entity_from_backup(backup_dir, filename, id_key, entity_id)
    except platform_admin.BackupError as exc:
        errors = [str(exc)]
    else:
        others = [r for r in current if r[id_key] != entity_id]
        errors = validate(restored, others)
    if errors:
        _append_operator_action({
            "action": f"{action_prefix}_restore_rejected",
            id_key: entity_id,
            "role": role,
            "operator_id": operator_id,
            "restored_from": backup_dir,
            "errors": errors,
        })
        raise HTTPException(status_code=400, detail={"errors": errors})

    pre_restore = platform_admin.snapshot_single_file(
        f"{action_prefix.replace('_', '-')}-restore", entity_id, filename, operator_id
    )
    save([restored if r[id_key] == entity_id else r for r in current])
    _append_operator_action({
        "action": f"{action_prefix}_restored",
        id_key: entity_id,
        "role": role,
        "operator_id": operator_id,
        "restored_from": backup_dir,
        "pre_restore_backup": pre_restore["backup_dir"],
    })
    return {"restored": restored, "restored_from": backup_dir, "pre_restore_backup": pre_restore["backup_dir"]}


@app.post("/api/wiresheets")
def create_wiresheet(
    wiresheet_id: str,
    display_name: str,
    description: str | None = None,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Create a new, empty Wire Sheet."""
    _require_command_role(role)
    sheets = wiresheets.load_wiresheets()
    new_sheet = {
        "wiresheet_id": wiresheet_id,
        "display_name": display_name,
        "ord": f"station:|slot:/WireSheet/{wiresheet_id}",
        "description": description,
        "blocks": [],
        "links": [],
    }
    errors = wiresheets.validate_wiresheet(new_sheet, sheets, is_create=True)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    sheets.append(new_sheet)
    wiresheets.save_wiresheets(sheets)
    _append_operator_action({
        "action": "wiresheet_created",
        "wiresheet_id": wiresheet_id,
        "role": role,
        "operator_id": operator_id,
    })
    return new_sheet


@app.post("/api/wiresheets/{wiresheet_id}/save")
def save_wiresheet(
    wiresheet_id: str,
    body: WireSheetSaveRequest,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Replace a Wire Sheet's blocks and links."""
    _require_command_role(role)
    sheets = wiresheets.load_wiresheets()
    existing = next((w for w in sheets if w["wiresheet_id"] == wiresheet_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Wire Sheet {wiresheet_id!r} not found")

    candidate = {**existing, "blocks": body.blocks, "links": body.links}
    errors = wiresheets.validate_wiresheet(
        candidate, sheets, is_create=False, **_wiresheet_reference_inventory()
    )
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    platform_admin.snapshot_single_file("wiresheet-editor", wiresheet_id, "wiresheets.json", operator_id)
    updated = [candidate if w["wiresheet_id"] == wiresheet_id else w for w in sheets]
    wiresheets.save_wiresheets(updated)
    _append_operator_action({
        "action": "wiresheet_saved",
        "wiresheet_id": wiresheet_id,
        "role": role,
        "operator_id": operator_id,
        "block_count": len(body.blocks),
        "link_count": len(body.links),
    })
    return candidate


@app.post("/api/wiresheets/{wiresheet_id}/backup")
def backup_wiresheet(
    wiresheet_id: str,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Explicit backup of the Wire Sheet store before hand-editing."""
    _require_command_role(role)
    if wiresheets.find_wiresheet(wiresheet_id) is None:
        raise HTTPException(status_code=404, detail=f"Wire Sheet {wiresheet_id!r} not found")
    entry = platform_admin.snapshot_single_file("wiresheet-editor", wiresheet_id, "wiresheets.json", operator_id)
    _append_operator_action({
        "action": "wiresheet_backup",
        "wiresheet_id": wiresheet_id,
        "role": role,
        "operator_id": operator_id,
        "backup_dir": entry["backup_dir"],
    })
    return entry


@app.get("/api/wiresheets/{wiresheet_id}/backups")
def get_wiresheet_backups(wiresheet_id: str) -> dict[str, Any]:
    """Backups this Wire Sheet can be restored from, newest first."""
    if wiresheets.find_wiresheet(wiresheet_id) is None:
        raise HTTPException(status_code=404, detail=f"Wire Sheet {wiresheet_id!r} not found")
    return {"backups": _backup_rows("wiresheets.json", "wiresheet_id", wiresheet_id)}


@app.post("/api/wiresheets/{wiresheet_id}/restore")
def restore_wiresheet(
    wiresheet_id: str,
    backup_dir: str,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Replace this one Wire Sheet with its copy from a backup; other sheets are untouched."""
    return _restore_entity(
        noun="Wire Sheet", action_prefix="wiresheet", id_key="wiresheet_id", entity_id=wiresheet_id,
        filename="wiresheets.json", backup_dir=backup_dir, role=role, operator_id=operator_id,
        load=wiresheets.load_wiresheets, save=wiresheets.save_wiresheets,
        validate=lambda ws, others: wiresheets.validate_wiresheet(
            ws, others, is_create=True, **_wiresheet_reference_inventory()
        ),
    )


@app.get("/api/px")
def get_px_pages() -> dict[str, Any]:
    """All Px graphic pages."""
    return {
        "pages": [
            {"px_id": p["px_id"], "display_name": p.get("display_name", p["px_id"]), "ord": p.get("ord")}
            for p in px_pages.load_px_pages()
        ]
    }


@app.get("/api/px/{px_id}")
def get_px_page(px_id: str) -> dict[str, Any]:
    """One Px page's widgets, each bound to its point's live resolved value."""
    page = px_pages.find_px_page(px_id)
    if page is None:
        raise HTTPException(status_code=404, detail=f"Px page {px_id!r} not found")

    snapshot = _load_points_file()
    overrides = _load_overrides()
    input_pts = {pt["point"]: pt for pt in _load_input_points()}
    now = datetime.now(timezone.utc)

    widgets = []
    for widget in page["widgets"]:
        point_name = widget["point"]
        meta = input_pts.get(point_name, {})
        resolved = _resolve_point_value(point_name, snapshot, overrides, now)
        widgets.append({
            **widget,
            "value": resolved["value"],
            "units": meta.get("units"),
            "driven_by": resolved["driven_by"],
            "schedule_id": resolved["schedule_id"],
            "overridden": resolved["overridden"],
        })

    return {
        "px_id": page["px_id"],
        "display_name": page.get("display_name", page["px_id"]),
        "ord": page.get("ord"),
        "facility": page.get("facility"),
        "widgets": widgets,
        "generated_at": now.isoformat(),
    }


@app.post("/api/px")
def create_px_page(
    px_id: str,
    display_name: str,
    facility: str | None = None,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Create a new, empty Px page."""
    _require_command_role(role)
    pages = px_pages.load_px_pages()
    new_page = {
        "px_id": px_id,
        "display_name": display_name,
        "ord": f"station:|slot:/Px/{px_id}",
        "facility": facility,
        "widgets": [],
    }
    valid_points = {pt["point"] for pt in _load_input_points()}
    errors = px_pages.validate_page(new_page, pages, valid_points, is_create=True)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    pages.append(new_page)
    px_pages.save_px_pages(pages)
    _append_operator_action({
        "action": "px_page_created",
        "px_id": px_id,
        "role": role,
        "operator_id": operator_id,
    })
    return new_page


@app.post("/api/px/{px_id}/save")
def save_px_page(
    px_id: str,
    body: PxSaveRequest,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Replace a Px page's widgets."""
    _require_command_role(role)
    pages = px_pages.load_px_pages()
    existing = next((p for p in pages if p["px_id"] == px_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Px page {px_id!r} not found")

    candidate = {**existing, "widgets": body.widgets}
    valid_points = {pt["point"] for pt in _load_input_points()}
    errors = px_pages.validate_page(candidate, pages, valid_points, is_create=False)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    platform_admin.snapshot_single_file("px-editor", px_id, "px_pages.json", operator_id)
    updated = [candidate if p["px_id"] == px_id else p for p in pages]
    px_pages.save_px_pages(updated)
    _append_operator_action({
        "action": "px_page_saved",
        "px_id": px_id,
        "role": role,
        "operator_id": operator_id,
        "widget_count": len(body.widgets),
    })
    return candidate


@app.post("/api/px/{px_id}/backup")
def backup_px_page(
    px_id: str,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Explicit backup of the Px page store before hand-editing."""
    _require_command_role(role)
    if px_pages.find_px_page(px_id) is None:
        raise HTTPException(status_code=404, detail=f"Px page {px_id!r} not found")
    entry = platform_admin.snapshot_single_file("px-editor", px_id, "px_pages.json", operator_id)
    _append_operator_action({
        "action": "px_page_backup",
        "px_id": px_id,
        "role": role,
        "operator_id": operator_id,
        "backup_dir": entry["backup_dir"],
    })
    return entry


@app.get("/api/px/{px_id}/backups")
def get_px_backups(px_id: str) -> dict[str, Any]:
    """Backups this Px page can be restored from, newest first."""
    if px_pages.find_px_page(px_id) is None:
        raise HTTPException(status_code=404, detail=f"Px page {px_id!r} not found")
    return {"backups": _backup_rows("px_pages.json", "px_id", px_id)}


@app.post("/api/px/{px_id}/restore")
def restore_px_page(
    px_id: str,
    backup_dir: str,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Replace this one Px page with its copy from a backup; other pages are untouched."""
    valid_points = {pt["point"] for pt in _load_input_points()}
    return _restore_entity(
        noun="Px page", action_prefix="px_page", id_key="px_id", entity_id=px_id,
        filename="px_pages.json", backup_dir=backup_dir, role=role, operator_id=operator_id,
        load=px_pages.load_px_pages, save=px_pages.save_px_pages,
        validate=lambda page, others: px_pages.validate_page(page, others, valid_points, is_create=True),
    )


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


@app.get("/api/platform/stations")
def get_platform_stations() -> dict[str, Any]:
    """Station topology for the Platform tab (synthetic host/license info)."""
    return {"stations": platform_admin.load_stations()}


@app.get("/api/platform/backups")
def get_platform_backups() -> dict[str, Any]:
    """Distribution backup history."""
    return {"backups": platform_admin.load_backup_log()}


@app.post("/api/platform/backup")
def post_platform_backup(
    station_id: str,
    role: str = "viewer",
    operator_id: str = "eng-workbench",
) -> dict[str, Any]:
    """Take a distribution backup of data/input/ -- the one real Platform action."""
    _require_command_role(role)
    if platform_admin.find_station(station_id) is None:
        raise HTTPException(status_code=404, detail=f"Station {station_id!r} not found")
    entry = platform_admin.take_backup(station_id, operator_id)
    _append_operator_action({
        "action": "platform_backup",
        "role": role,
        "operator_id": operator_id,
        "station": station_id,
        "backup_dir": entry["backup_dir"],
    })
    return entry


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


# ---------------------------------------------------------------------------
# Building 822 — Tracer SC topology, chiller walk-up, front end
# ---------------------------------------------------------------------------

CONNECTION_POINTS = {
    "SC-822-01": {"label": "Tracer SC-822-01 (Ethernet)",
                  "trunks": ["MSTP-01-A", "MSTP-01-B"]},
    "SC-822-02": {"label": "Tracer SC-822-02 (Ethernet)",
                  "trunks": ["MSTP-02-A", "MSTP-02-B"]},
    "CHILLER-PANEL": {"label": "RTAC local panel (walk-up)", "trunks": []},
}


@app.get("/api/topology")
def api_topology(from_node: str = Query("SC-822-01", alias="from")) -> dict[str, Any]:
    """Return only what this connection point can actually reach.

    Visibility is computed here, on purpose. Spec 2 makes a disconnected MS/TP
    trunk a real fault, and the controllers behind it must be ABSENT from this
    response rather than greyed out by the browser. Hiding them client-side
    would make that fault a lie.
    """
    if from_node not in CONNECTION_POINTS:
        raise HTTPException(status_code=404, detail=f"Unknown connection point {from_node}")

    equipment = _load_input_equipment()
    conn = CONNECTION_POINTS[from_node]
    if from_node == "CHILLER-PANEL":
        return {"from": from_node, "label": conn["label"], "supervisory": None, "trunks": []}

    devices = equipment.get("equipment", [])
    trunks = []
    for trunk_id in conn["trunks"]:
        members = [d for d in devices if d.get("parent") == trunk_id]
        online = [d for d in members if _device_online(d["id"])]
        trunks.append({
            "id": trunk_id,
            "type": "bacnet_mstp",
            "member_count": len(members),
            "online_count": len(online),
            "members": [{"id": d["id"], "equipment": d["id"], "type": d["type"],
                         "serves": d.get("serves", ""), "online": d in online}
                        for d in online],
        })
    return {"from": from_node, "label": conn["label"],
            "supervisory": {"id": from_node, "type": "Tracer SC+", "online": True},
            "trunks": trunks}


def _device_online(device_id: str) -> bool:
    """Spec 1: everything is online. Spec 2 reads comm state from the fault knobs."""
    return True


@app.get("/api/chiller/822")
def api_chiller_822() -> dict[str, Any]:
    """RTAC local display. Deliberately NOT part of /api/topology.

    The building has no BACnet integration to this machine. It is reachable
    only by walking to it, which is the point: warm entering water is visible
    from inside 822, but the reason is not.
    """
    try:
        state = json.loads((OUTPUT_DIR / "state_822.json").read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        raise HTTPException(status_code=503,
                            detail="Building 822 has not been simulated yet. "
                                   "Run: python3 simulator/bas_sim.py --scenario normal --steps 60")
    ch = state.get("_chiller")
    if not ch:
        raise HTTPException(status_code=503, detail="No chiller state in state_822.json")
    return {
        "unit": "CHILLER-RTAC-822",
        "model_family": "Trane RTAC air-cooled helical rotary, ~155 nominal tons",
        "serial": "SYNTHETIC-822-0001",
        "reference": "RTAC-SVX01M-EN",
        "integration": "None — local display only, no BACnet to SC-822",
        "evap_entering_f": ch["ewt_f"],
        "evap_leaving_f": ch["lwt_f"],
        "evap_leaving_setpoint_f": ch["lwt_f"] if ch["active_diag"] == "None" else 44.0,
        "ambient_f": ch["ambient_f"],
        "pct_capacity": ch["pct_capacity"],
        "available_tons": ch["available_tons"],
        "load_tons": ch["load_tons"],
        "circuits": [
            {"id": 1, "running": ch["ckt1_on"], "condenser_fan_ok": ch["ckt1_fan_ok"]},
            {"id": 2, "running": ch["ckt2_on"], "condenser_fan_ok": ch["ckt2_fan_ok"]},
        ],
        "active_diagnostic": ch["active_diag"],
    }


@app.get("/tracer", response_class=HTMLResponse)
def tracer_page() -> HTMLResponse:
    page = STATIC_DIR / "tracer.html"
    return HTMLResponse(content=page.read_text(encoding="utf-8"))
