#!/usr/bin/env python3
"""Generate Building 822 inventory records into data/input/.

Build tool, not a runtime dependency. Output is committed as ordinary JSON so
the inventory stays readable, diffable and hand-editable afterward.

    python3 scripts/gen-822-inventory.py              # dry run, prints counts
    python3 scripts/gen-822-inventory.py --apply      # write into data/input/
    python3 scripts/gen-822-inventory.py --apply --force   # overwrite existing 822 records
    python3 scripts/gen-822-inventory.py --remove         # take 822 back out entirely
    python3 scripts/gen-822-inventory.py --self-test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"

FACILITY = "barracks822"
WINGS = ("A", "B", "C", "D")
FLOORS = (1, 2, 3)
ROOMS = (1, 2, 3)

# MAU-01..12 serve wing/floor in order; MAU-13 serves the lobby.
MAU_ASSIGNMENT = {}
_n = 1
for _w in WINGS:
    for _f in FLOORS:
        MAU_ASSIGNMENT[f"MAU-{_n:02d}"] = (_w, _f)
        _n += 1
MAU_ASSIGNMENT["MAU-13"] = ("LOBBY", 1)

# Trunk membership is DERIVED from build_equipment() parents, never hand-listed.
# A hand-maintained copy drifts: the CHW service entrance sits on MSTP-01-A and
# the hallway sensors sit on the B trunks, so the counts are 7/24/7/24 -- not
# the 6/18/7/18 you get by counting only MAUs and FCUs.


def trunk_membership() -> dict[str, list[str]]:
    members: dict[str, list[str]] = {}
    for record in build_equipment():
        parent = record.get("parent")
        if parent:
            members.setdefault(parent, []).append(record["id"])
    return members


COMM_POINT_EQUIPMENT = {
    "SC82201": "SC-822-01",
    "SC82202": "SC-822-02",
    "MSTP01A": "MSTP-01-A",
    "MSTP01B": "MSTP-01-B",
    "MSTP02A": "MSTP-02-A",
    "MSTP02B": "MSTP-02-B",
}


def _pt(name, equipment, ptype, units, lo, hi, writable, critical, interval, states=None):
    rec = {
        "point": name,
        "equipment": equipment,
        "type": ptype,
        "units": units,
        "normal_min": lo,
        "normal_max": hi,
        "writable": writable,
        "critical": critical,
        "trend_interval_sec": interval,
        "facility": FACILITY,
    }
    if states:
        rec["states"] = list(states)
    return rec


def build_points():
    pts = []

    for i in range(1, 14):
        tag, eq = f"MAU{i:02d}", f"MAU-{i:02d}"
        pts += [
            _pt(f"{tag}_SAT",          eq, "AI", "F",    58, 68,  False, False, 60),
            _pt(f"{tag}_SAT_SP",       eq, "AV", "F",    60, 66,  True,  False, 300),
            # Supply air leaves close to coil saturation (85-95% RH per
            # MAU-822-SOO.md) -- that is the HEALTHY state, not a fault.
            # A value well below this band, not above, is the alarm-worthy
            # direction: it means the coil is running dry, not dehumidifying.
            _pt(f"{tag}_SA_RH",        eq, "AI", "%",    80, 98,  False, False, 60),
            _pt(f"{tag}_EAT",          eq, "AI", "F",    70, 95,  False, False, 60),
            _pt(f"{tag}_EA_RH",        eq, "AI", "%",    45, 90,  False, False, 60),
            _pt(f"{tag}_FAN_CMD",      eq, "BO", "bool",  1,  1,  True,  False, 300),
            _pt(f"{tag}_FAN_STATUS",   eq, "BI", "bool",  1,  1,  False, False, 300),
            _pt(f"{tag}_OA_DMPR_CMD",  eq, "AO", "%",    40, 60,  True,  False, 300),
            _pt(f"{tag}_OA_DMPR_POS",  eq, "AI", "%",    40, 60,  False, False, 60),
            _pt(f"{tag}_CHW_VLV_CMD",  eq, "AO", "%",     0, 100, True,  False, 300),
            _pt(f"{tag}_CHW_VLV_POS",  eq, "AI", "%",     0, 100, False, False, 60),
            _pt(f"{tag}_COIL_DT",      eq, "AV", "F",     8, 20,  False, False, 60),
        ]

    for w in WINGS:
        for f in FLOORS:
            for r in ROOMS:
                tag, eq = f"FCU_{w}{f}{r:02d}", f"UC-FCU-{w}{f}{r:02d}"
                pts += [
                    _pt(f"{tag}_SPACE_TEMP",    eq, "AI", "F",    70, 76,  False, False, 300),
                    _pt(f"{tag}_SPACE_TEMP_SP", eq, "AV", "F",    72, 74,  True,  False, 300),
                    _pt(f"{tag}_FAN_MODE",      eq, "MV", "state", 0, 4,   True,  False, 300,
                        states=("Off", "Auto", "Low", "Mid", "High")),
                    _pt(f"{tag}_FAN_STATUS",    eq, "BI", "bool",  0,  1,  False, False, 300),
                    _pt(f"{tag}_CHW_VLV_CMD",   eq, "AO", "%",     0, 100, True,  False, 300),
                    _pt(f"{tag}_CHW_VLV_POS",   eq, "AI", "%",     0, 100, False, False, 300),
                    # Inferred from commanded fan speed, like a real ECM unit --
                    # not a dedicated flow station. 0-1.0*FCU_CFM design airflow.
                    _pt(f"{tag}_CFM",           eq, "AI", "CFM",   0, 400, False, False, 300),
                ]

    for w in WINGS:
        for f in FLOORS:
            eq = f"HALL-{w}{f}"
            pts += [
                _pt(f"HALL_{w}{f}_TEMP", eq, "AI", "F", 72, 78, False, False, 300),
                _pt(f"HALL_{w}{f}_RH",   eq, "AI", "%", 55, 65, False, True,  300),
            ]

    chw = "CHW-822"
    pts += [
        _pt("CHW822_ENT_SUP_TEMP", chw, "AI", "F",    42, 46,  False, True,  60),
        _pt("CHW822_ENT_RET_TEMP", chw, "AI", "F",    52, 58,  False, False, 60),
        _pt("CHW822_BLDG_DT",      chw, "AV", "F",     8, 14,  False, True,  60),
        _pt("CHW822_GPM",          chw, "AI", "GPM",   0, 80,  False, False, 60),
        _pt("CHW822_BLDG_DP",      chw, "AI", "psid",  8, 14,  False, False, 300),
        _pt("CHW822_STRAINER_DP",  chw, "AI", "psid",  1,  4,  False, False, 300),
        _pt("CHW822_P1_CMD",       chw, "BO", "bool",  1,  1,  True,  False, 300),
        _pt("CHW822_P1_STATUS",    chw, "BI", "bool",  1,  1,  False, False, 300),
        _pt("CHW822_P2_CMD",       chw, "BO", "bool",  0,  0,  True,  False, 300),
        _pt("CHW822_P2_STATUS",    chw, "BI", "bool",  0,  0,  False, False, 300),
    ]

    # Explicit map, never string surgery: "MSTP01A".replace("MSTP","MSTP-") gives
    # "MSTP-01A", but the network id is "MSTP-01-A" -- dashed on both sides.
    for dev, eq in COMM_POINT_EQUIPMENT.items():
        pts.append(_pt(f"{dev}_STATUS", eq, "BI", "bool", 1, 1, False, True, 300))

    rt = "CHILLER-RTAC-822"
    pts += [
        _pt("RTAC822_EVAP_ENT_TEMP", rt, "AI", "F",     52, 58,  False, False, 300),
        _pt("RTAC822_EVAP_LVG_TEMP", rt, "AI", "F",     42, 46,  False, True,  300),
        _pt("RTAC822_EVAP_LVG_SP",   rt, "AV", "F",     44, 44,  False, False, 300),
        _pt("RTAC822_AMBIENT_TEMP",  rt, "AI", "F",     70, 100, False, False, 300),
        _pt("RTAC822_PCT_CAPACITY",  rt, "AI", "%",      0, 100, False, False, 300),
        _pt("RTAC822_CKT1_STATUS",   rt, "BI", "bool",   1,  1,  False, False, 300),
        _pt("RTAC822_CKT2_STATUS",   rt, "BI", "bool",   1,  1,  False, False, 300),
        _pt("RTAC822_CKT1_FAN_STATUS", rt, "BI", "bool", 1,  1,  False, False, 300),
        _pt("RTAC822_CKT2_FAN_STATUS", rt, "BI", "bool", 1,  1,  False, False, 300),
        _pt("RTAC822_ACTIVE_DIAG",   rt, "MV", "state",  0,  3,  False, True,  300,
            states=("None", "LowEvapTemp", "CondFanFail", "CircuitLockout")),
    ]
    return pts


def build_equipment():
    equip = []
    for i in range(1, 14):
        wing, floor = MAU_ASSIGNMENT[f"MAU-{i:02d}"]
        serves = "Lobby" if wing == "LOBBY" else f"Wing {wing} Floor {floor}"
        equip.append({
            "id": f"MAU-{i:02d}", "type": "Makeup Air Unit", "serves": serves,
            "vendor": "Trane", "controller": f"UC400-MAU-{i:02d}",
            "purdue_level": 1, "facility": FACILITY,
            "parent": "MSTP-01-A" if i <= 6 else "MSTP-02-A",
        })
    for w in WINGS:
        for f in FLOORS:
            for r in ROOMS:
                equip.append({
                    "id": f"UC-FCU-{w}{f}{r:02d}", "type": "Fan Coil Unit",
                    "serves": f"Room {w}{f}{r:02d}", "vendor": "Trane",
                    "controller": f"UC-FCU-{w}{f}{r:02d}", "purdue_level": 1,
                    "facility": FACILITY,
                    "parent": "MSTP-01-B" if w in ("A", "B") else "MSTP-02-B",
                })
    for w in WINGS:
        for f in FLOORS:
            equip.append({
                "id": f"HALL-{w}{f}", "type": "Hallway Sensor",
                "serves": f"Wing {w} Floor {f} Corridor", "vendor": "Trane",
                "controller": f"UC-FCU-{w}{f}01", "purdue_level": 1,
                "facility": FACILITY,
                "parent": "MSTP-01-B" if w in ("A", "B") else "MSTP-02-B",
            })
    equip.append({
        "id": "CHW-822", "type": "CHW Service Entrance", "serves": "Building 822",
        "vendor": "Mixed", "controller": "UC400-CHW-822", "purdue_level": 1,
        "facility": FACILITY, "parent": "MSTP-01-A",
    })
    equip.append({
        "id": "CHILLER-RTAC-822", "type": "Air-Cooled Chiller (RTAC, ~155 ton)",
        "serves": "Campus CHW Loop", "vendor": "Trane", "controller": "unit-mounted",
        "purdue_level": 1, "facility": FACILITY, "parent": None,
        "note": "Off-tree. No BACnet integration to SC-822. Local display only.",
        "serial": "SYNTHETIC-822-0001",
        "reference": "RTAC-SVX01M-EN (public product literature)",
    })
    return equip


def build_networks():
    nets = [{"id": "ETH-822", "type": "ethernet", "facility": FACILITY, "parent": None}]
    for trunk in ("MSTP-01-A", "MSTP-01-B"):
        nets.append({"id": trunk, "type": "bacnet_mstp", "facility": FACILITY, "parent": "SC-822-01"})
    for trunk in ("MSTP-02-A", "MSTP-02-B"):
        nets.append({"id": trunk, "type": "bacnet_mstp", "facility": FACILITY, "parent": "SC-822-02"})
    return nets


def build_supervisory():
    return [
        {"id": "SC-822-01", "type": "Tracer SC+", "vendor": "Trane",
         "purdue_level": 2, "facility": FACILITY, "parent": "ETH-822"},
        {"id": "SC-822-02", "type": "Tracer SC+", "vendor": "Trane",
         "purdue_level": 2, "facility": FACILITY, "parent": "ETH-822"},
    ]


def build_alarm_rules():
    rules = [
        {"point": "CHW822_ENT_SUP_TEMP", "condition": "outside_normal", "priority": "high",
         "message": "Building 822 entering chilled water temperature abnormal"},
        {"point": "CHW822_BLDG_DT", "condition": "outside_normal", "priority": "high",
         "message": "Building 822 chilled water delta-T outside expected range"},
        {"point": "RTAC822_EVAP_LVG_TEMP", "condition": "outside_normal", "priority": "high",
         "message": "RTAC leaving evaporator water temperature off setpoint"},
    ]
    for w in WINGS:
        for f in FLOORS:
            rules.append({
                "point": f"HALL_{w}{f}_RH", "condition": "outside_normal", "priority": "medium",
                "message": f"Wing {w} Floor {f} corridor humidity outside target range",
            })
    for i in range(1, 14):
        rules.append({
            "point": f"MAU{i:02d}_SAT", "condition": "outside_normal", "priority": "medium",
            "message": f"MAU-{i:02d} supply air temperature abnormal",
        })
        rules.append({
            "point": f"MAU{i:02d}_SA_RH", "condition": "outside_normal", "priority": "medium",
            "message": f"MAU-{i:02d} supply air humidity abnormal",
        })
    return rules


def _merge(path, new_records, key, force):
    existing = json.loads(path.read_text(encoding="utf-8"))
    new_keys = {r[key] for r in new_records}
    collisions = [r for r in existing if r.get(key) in new_keys]
    if collisions and not force:
        raise SystemExit(
            f"{path.name}: {len(collisions)} existing 822 records would be overwritten. "
            f"Re-run with --force if that is what you want."
        )
    kept = [r for r in existing if r.get(key) not in new_keys]
    return kept + new_records


def apply(force: bool) -> None:
    pts_path, eq_path, al_path = (INPUT_DIR / n for n in
                                  ("points.json", "equipment.json", "alarm_rules.json"))

    merged_points = _merge(pts_path, build_points(), "point", force)
    pts_path.write_text(json.dumps(merged_points, indent=2) + "\n", encoding="utf-8")

    eq = json.loads(eq_path.read_text(encoding="utf-8"))
    eq.setdefault("networks", [])
    for record in eq["equipment"] + eq["supervisory"] + eq["front_end"]:
        record.setdefault("parent", None)
    if not any(f["id"] == FACILITY for f in eq["facilities"]):
        eq["facilities"].append({
            "id": FACILITY, "name": "Building 822 (synthetic barracks)",
            "floors": 3, "wings": list(WINGS), "critical_spaces": [],
        })
    new_eq_ids = {r["id"] for r in build_equipment()}
    new_sup_ids = {r["id"] for r in build_supervisory()}
    new_net_ids = {r["id"] for r in build_networks()}
    if not force and (
        {r["id"] for r in eq["equipment"]} & new_eq_ids
        or {r["id"] for r in eq["supervisory"]} & new_sup_ids
        or {r["id"] for r in eq["networks"]} & new_net_ids
    ):
        raise SystemExit("equipment.json: existing 822 records. Re-run with --force.")
    eq["equipment"] = [r for r in eq["equipment"] if r["id"] not in new_eq_ids] + build_equipment()
    eq["supervisory"] = [r for r in eq["supervisory"] if r["id"] not in new_sup_ids] + build_supervisory()
    eq["networks"] = [r for r in eq["networks"] if r["id"] not in new_net_ids] + build_networks()
    eq_path.write_text(json.dumps(eq, indent=2) + "\n", encoding="utf-8")

    merged_rules = _merge(al_path, build_alarm_rules(), "point", force)
    al_path.write_text(json.dumps(merged_rules, indent=2) + "\n", encoding="utf-8")


def remove() -> None:
    """Remove every Building 822 record from the shared inventories.

    The reversibility guarantee: 822 merges into points.json / equipment.json /
    alarm_rules.json, and this takes it back out, leaving hospital and office
    records exactly as they were.
    """
    pts_path, eq_path, al_path = (INPUT_DIR / n for n in
                                  ("points.json", "equipment.json", "alarm_rules.json"))

    pts = json.loads(pts_path.read_text(encoding="utf-8"))
    kept_pts = [r for r in pts if r.get("facility") != FACILITY]
    pts_path.write_text(json.dumps(kept_pts, indent=2) + "\n", encoding="utf-8")

    eq = json.loads(eq_path.read_text(encoding="utf-8"))
    removed_eq = 0
    for key in ("equipment", "supervisory", "front_end", "networks"):
        before = len(eq.get(key, []))
        eq[key] = [r for r in eq.get(key, []) if r.get("facility") != FACILITY]
        removed_eq += before - len(eq[key])
    if not eq["networks"]:
        eq.pop("networks")          # leave no empty scaffolding behind
    eq["facilities"] = [f for f in eq["facilities"] if f["id"] != FACILITY]
    for record in eq["equipment"] + eq["supervisory"] + eq["front_end"]:
        record.pop("parent", None)  # the nullable parent was added for 822
    eq_path.write_text(json.dumps(eq, indent=2) + "\n", encoding="utf-8")

    names_822 = {r["point"] for r in build_points()}
    al = json.loads(al_path.read_text(encoding="utf-8"))
    kept_rules = [r for r in al if r["point"] not in names_822]
    al_path.write_text(json.dumps(kept_rules, indent=2) + "\n", encoding="utf-8")

    print(f"Removed {len(pts) - len(kept_pts)} points, {removed_eq} equipment/network "
          f"records, {len(al) - len(kept_rules)} alarm rules.")
    print("Also delete if you want 822 fully gone: simulator/model822.py, "
          "simulator/psychro.py, scripts/tune-822.py, data/input/weather_822.json, "
          "data/output/state_822.json, frontend/static/tracer.html, sequences/*-822-SOO.md")


def self_test() -> int:
    pts = build_points()
    # 421 original + 36 FCU_*_CFM + 1 CHW822_GPM
    assert len(pts) == 458, f"expected 458 points, got {len(pts)}"
    names = [p["point"] for p in pts]
    assert len(names) == len(set(names)), "duplicate point names"
    assert all(p["facility"] == FACILITY for p in pts)

    eq = build_equipment()
    assert len([e for e in eq if e["type"] == "Makeup Air Unit"]) == 13
    assert len([e for e in eq if e["type"] == "Fan Coil Unit"]) == 36
    assert len([e for e in eq if e["type"] == "Hallway Sensor"]) == 12

    rtac = [e for e in eq if e["id"] == "CHILLER-RTAC-822"][0]
    assert rtac["parent"] is None, "chiller must be off-tree"
    assert rtac["serial"].startswith("SYNTHETIC"), "chiller serial must be fictional"

    trunks = trunk_membership()
    flat = [m for members in trunks.values() for m in members]
    assert len(flat) == len(set(flat)), "a controller is on two trunks"
    counts = {k: len(v) for k, v in sorted(trunks.items())}
    assert counts == {"MSTP-01-A": 7, "MSTP-01-B": 24,
                      "MSTP-02-A": 7, "MSTP-02-B": 24}, counts
    assert len(flat) == 62 and len(eq) == 63, "62 on trunks + 1 off-tree chiller"

    mv = [p for p in pts if p["type"] == "MV"]
    assert mv and all(p.get("states") for p in mv), "MV points need states"

    # Referential integrity: every point must name equipment that actually exists.
    # Without this, a typo in an equipment id stays invisible until a later task
    # tries to join points to the device tree.
    known_ids = ({e["id"] for e in eq}
                 | {n["id"] for n in build_networks()}
                 | {sup["id"] for sup in build_supervisory()})
    dangling = sorted({p["equipment"] for p in pts} - known_ids)
    assert not dangling, f"points reference non-existent equipment: {dangling}"

    # Every MAU's SA_RH must be able to alarm -- a coil losing the moisture
    # fight but staying quiet on the dashboard is exactly the gap that
    # matters in a humid climate. See MAU-822-SOO.md's troubleshooting
    # section: dewpoint/RH, not SAT alone, tells the corridor-humidity story.
    rules = build_alarm_rules()
    ruled_points = {r["point"] for r in rules}
    for i in range(1, 14):
        assert f"MAU{i:02d}_SA_RH" in ruled_points, \
            f"MAU{i:02d}_SA_RH has no alarm rule -- a humidity excursion would never flag"
    # A genuinely healthy near-saturation reading must sit INSIDE the point's
    # own normal_min/max, or the alarm we just required would false-fire on
    # every clean run -- exactly the bug this line catches.
    sa_rh_bounds = next(p for p in pts if p["point"] == "MAU01_SA_RH")
    assert sa_rh_bounds["normal_min"] <= 90.0 <= sa_rh_bounds["normal_max"], \
        f"a healthy 90% SA_RH would false-alarm against {sa_rh_bounds['normal_min']}-{sa_rh_bounds['normal_max']}"

    print(f"SELF-TEST PASS ({len(pts)} points, {len(eq)} equipment records)")
    return 0


def main(argv) -> int:
    ap = argparse.ArgumentParser(description="Generate Building 822 inventory")
    ap.add_argument("--apply", action="store_true", help="Write into data/input/")
    ap.add_argument("--force", action="store_true", help="Overwrite existing 822 records")
    ap.add_argument("--remove", action="store_true",
                    help="Remove all 822 records from the shared inventories")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv[1:])
    if args.self_test:
        return self_test()
    if args.remove:
        remove()
        return 0
    if not args.apply:
        print(f"DRY RUN: would write {len(build_points())} points, "
              f"{len(build_equipment())} equipment, {len(build_networks())} networks, "
              f"{len(build_alarm_rules())} alarm rules. Re-run with --apply.")
        return 0
    apply(args.force)
    print("Applied. Re-run bas_sim.py to generate 822 data.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
