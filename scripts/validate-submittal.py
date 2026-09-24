#!/usr/bin/env python3
"""Validate a DESIGN/ submittal's JSON deliverables against data/input schemas.

Usage:
    python3 scripts/validate-submittal.py DESIGN/submittals/P-01/rev-A
    python3 scripts/validate-submittal.py --self-test

Checks (spec: docs/superpowers/specs/2026-07-16-design-assist-track-design.md):
  1. Files parse and are lists of records.
  2. Required fields present, correct types, no unknown keys.
  3. Equipment IDs unique within submittal and against data/input/equipment.json.
  4. Point names unique within submittal and against data/input/points.json.
  5. Every proposed point references equipment in the submittal or live inventory.
  6. Every proposed alarm references a point in the submittal or live inventory.
  7. facility values match known facility IDs.

Synthetic training lab tooling. Standard library only.
"""

import json
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent

EQUIPMENT_SCHEMA = {
    "id": str, "type": str, "serves": str, "vendor": str,
    "controller": str, "purdue_level": int, "facility": str,
}
POINT_SCHEMA = {
    "point": str, "equipment": str, "type": str, "units": str,
    "normal_min": (int, float), "normal_max": (int, float),
    "writable": bool, "critical": bool,
    "trend_interval_sec": int, "facility": str,
}
ALARM_SCHEMA = {"point": str, "condition": str, "priority": str, "message": str}

POINT_TYPES = {"AI", "AO", "AV", "BI", "BO", "BV"}
ALARM_CONDITIONS = {"outside_normal"}
ALARM_PRIORITIES = {"critical", "high", "medium", "low"}

# (filename, schema, required) — survey/SOO/etc. are markdown, not validated here.
DELIVERABLES = [
    ("proposed_equipment.json", EQUIPMENT_SCHEMA),
    ("proposed_points.json", POINT_SCHEMA),
    ("proposed_alarms.json", ALARM_SCHEMA),
]


def load_live_inventory(lab_root):
    eq_doc = json.loads((lab_root / "data/input/equipment.json").read_text())
    points = json.loads((lab_root / "data/input/points.json").read_text())
    return {
        "facility_ids": {f["id"] for f in eq_doc["facilities"]},
        "equipment_ids": {e["id"] for e in eq_doc["equipment"]},
        "point_names": {p["point"] for p in points},
    }


def check_records(name, records, schema, errors):
    for i, rec in enumerate(records):
        where = f"{name}[{i}]"
        if not isinstance(rec, dict):
            errors.append(f"{where}: record is not an object")
            continue
        for field, ftype in schema.items():
            if field not in rec:
                errors.append(f"{where}: missing required field '{field}'")
            elif not isinstance(rec[field], ftype) or (
                ftype is not bool and isinstance(rec[field], bool)
                and ftype in (int, (int, float))
            ):
                errors.append(
                    f"{where}: field '{field}' has wrong type "
                    f"({type(rec[field]).__name__})")
        for key in rec:
            if key not in schema:
                errors.append(
                    f"{where}: unknown key '{key}' — engineer-only detail "
                    "belongs in the markdown deliverables, not the JSON")


def validate(submittal_dir, lab_root=LAB_ROOT):
    errors = []
    submittal_dir = Path(submittal_dir)
    if not submittal_dir.is_dir():
        return [f"ERROR: {submittal_dir} is not a directory"]
    live = load_live_inventory(lab_root)

    docs = {}
    for fname, schema in DELIVERABLES:
        fpath = submittal_dir / fname
        if not fpath.exists():
            # Briefs may not require every JSON deliverable (e.g. P-01 has
            # no alarms) — absence is the reviewer's call, not a schema error.
            continue
        try:
            data = json.loads(fpath.read_text())
        except json.JSONDecodeError as exc:
            errors.append(f"{fname}: does not parse as JSON ({exc})")
            continue
        if not isinstance(data, list):
            errors.append(f"{fname}: must be a JSON list of records")
            continue
        check_records(fname, data, schema, errors)
        docs[fname] = [r for r in data if isinstance(r, dict)]

    if not docs:
        errors.append("no JSON deliverables found "
                      "(expected at least proposed_equipment.json or "
                      "proposed_points.json)")

    eq = docs.get("proposed_equipment.json", [])
    pts = docs.get("proposed_points.json", [])
    alarms = docs.get("proposed_alarms.json", [])

    seen_eq = set()
    for rec in eq:
        eid = rec.get("id")
        if eid in seen_eq:
            errors.append(f"proposed_equipment: duplicate id '{eid}'")
        seen_eq.add(eid)
        if eid in live["equipment_ids"]:
            errors.append(
                f"proposed_equipment: id '{eid}' already exists in live "
                "inventory (data/input/equipment.json)")
        if rec.get("facility") not in live["facility_ids"]:
            errors.append(
                f"proposed_equipment '{eid}': unknown facility "
                f"'{rec.get('facility')}' (known: {sorted(live['facility_ids'])})")

    known_equipment = live["equipment_ids"] | seen_eq
    seen_pts = set()
    for rec in pts:
        pname = rec.get("point")
        if pname in seen_pts:
            errors.append(f"proposed_points: duplicate point '{pname}'")
        seen_pts.add(pname)
        if pname in live["point_names"]:
            errors.append(
                f"proposed_points: point '{pname}' already exists in live "
                "inventory (data/input/points.json)")
        if rec.get("equipment") not in known_equipment:
            errors.append(
                f"proposed_points '{pname}': equipment "
                f"'{rec.get('equipment')}' not found in submittal or live "
                "inventory")
        if rec.get("type") not in POINT_TYPES:
            errors.append(
                f"proposed_points '{pname}': type '{rec.get('type')}' not in "
                f"{sorted(POINT_TYPES)}")
        if rec.get("facility") not in live["facility_ids"]:
            errors.append(
                f"proposed_points '{pname}': unknown facility "
                f"'{rec.get('facility')}'")
        lo, hi = rec.get("normal_min"), rec.get("normal_max")
        if (isinstance(lo, (int, float)) and isinstance(hi, (int, float))
                and not isinstance(lo, bool) and not isinstance(hi, bool)
                and lo > hi):
            errors.append(
                f"proposed_points '{pname}': normal_min {lo} > normal_max {hi}")

    known_points = live["point_names"] | seen_pts
    for rec in alarms:
        pname = rec.get("point")
        if pname not in known_points:
            errors.append(
                f"proposed_alarms: point '{pname}' not found in submittal or "
                "live inventory")
        if rec.get("condition") not in ALARM_CONDITIONS:
            errors.append(
                f"proposed_alarms '{pname}': condition "
                f"'{rec.get('condition')}' not in {sorted(ALARM_CONDITIONS)}")
        if rec.get("priority") not in ALARM_PRIORITIES:
            errors.append(
                f"proposed_alarms '{pname}': priority "
                f"'{rec.get('priority')}' not in {sorted(ALARM_PRIORITIES)}")

    return [f"ERROR: {e}" for e in errors]


# ---------------------------------------------------------------- self-test

GOOD_EQUIPMENT = [{
    "id": "VAV-601", "type": "VAV", "serves": "Floor 6 Open Office",
    "vendor": "Johnson Controls", "controller": "JCI-VMA-601",
    "purdue_level": 1, "facility": "office",
}]
GOOD_POINTS = [{
    "point": "VAV601_TEMP", "equipment": "VAV-601", "type": "AI",
    "units": "F", "normal_min": 70, "normal_max": 76, "writable": False,
    "critical": False, "trend_interval_sec": 300, "facility": "office",
}]
GOOD_ALARMS = [{
    "point": "VAV601_TEMP", "condition": "outside_normal",
    "priority": "medium", "message": "Floor 6 zone temp outside range",
}]
BAD_EQUIPMENT = [
    {"id": "RTU-1", "type": "AHU", "serves": "x", "vendor": "x",
     "controller": "x", "purdue_level": 1, "facility": "office"},   # dup live id
    {"id": "VAV-602", "type": "VAV", "serves": "x", "vendor": "x",
     "controller": "x", "purdue_level": "one", "facility": "mars",  # bad type+facility
     "wire_gauge": "18AWG"},                                        # unknown key
]
BAD_POINTS = [
    {"point": "RTU1_SAT", "equipment": "VAV-602", "type": "AI", "units": "F",
     "normal_min": 80, "normal_max": 50, "writable": False, "critical": False,
     "trend_interval_sec": 60, "facility": "office"},  # dup live name, min>max
    {"point": "VAV699_TEMP", "equipment": "VAV-699", "type": "XX",
     "units": "F", "normal_min": 1, "normal_max": 2, "writable": False,
     "critical": False, "trend_interval_sec": 60, "facility": "office"},
]                                                      # orphan equip, bad type
BAD_ALARMS = [{"point": "NOPE_TEMP", "condition": "on_fire",
               "priority": "mega", "message": "x"}]


def self_test():
    import tempfile
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        good = Path(tmp) / "good"
        good.mkdir()
        (good / "proposed_equipment.json").write_text(json.dumps(GOOD_EQUIPMENT))
        (good / "proposed_points.json").write_text(json.dumps(GOOD_POINTS))
        (good / "proposed_alarms.json").write_text(json.dumps(GOOD_ALARMS))
        errs = validate(good)
        if errs:
            failures.append(f"good fixture should be clean, got: {errs}")

        bad = Path(tmp) / "bad"
        bad.mkdir()
        (bad / "proposed_equipment.json").write_text(json.dumps(BAD_EQUIPMENT))
        (bad / "proposed_points.json").write_text(json.dumps(BAD_POINTS))
        (bad / "proposed_alarms.json").write_text(json.dumps(BAD_ALARMS))
        errs = validate(bad)
        expected_fragments = [
            "already exists in live",       # RTU-1, RTU1_SAT
            "wrong type",                   # purdue_level "one"
            "unknown facility 'mars'",
            "unknown key 'wire_gauge'",
            "normal_min 80 > normal_max 50",
            "'VAV-699' not found",
            "type 'XX' not in",
            "'NOPE_TEMP' not found",
            "condition 'on_fire' not in",
            "priority 'mega' not in",
        ]
        for frag in expected_fragments:
            if not any(frag in e for e in errs):
                failures.append(f"bad fixture missing expected error: {frag}")

        empty = Path(tmp) / "empty"
        empty.mkdir()
        if not validate(empty):
            failures.append("empty submittal dir should error")

    if failures:
        for f in failures:
            print(f"SELF-TEST FAIL: {f}")
        return 1
    print("SELF-TEST PASS")
    return 0


def main(argv):
    if len(argv) != 2 or argv[1] in ("-h", "--help"):
        print(__doc__)
        return 2
    if argv[1] == "--self-test":
        return self_test()
    errors = validate(argv[1])
    if errors:
        print("\n".join(errors))
        print(f"\n{len(errors)} finding(s). Fix before submitting.")
        return 1
    print("OK — schema-clean. (Content quality is the reviewer's job.)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
