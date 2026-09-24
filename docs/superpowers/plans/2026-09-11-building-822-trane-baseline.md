# Building 822 Trane Baseline — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a synthetic Trane-controlled barracks ("Building 822") inside BAS-SIM that responds correctly to operator commands when healthy — plug in, log in, navigate, command a valve, watch the building answer.

**Architecture:** A new coupled state model (`simulator/model822.py`) runs alongside — never replacing — the existing open-loop `bas_sim.py` path. `bas_sim.py` routes points by `facility`: `barracks822` points go to the state model, everything else keeps the committed `scenario_value()` behavior byte-for-byte. The model chains weather → chiller → CHW loop → coil (sensible + latent via bypass factor / apparatus dew point) → space, persisting thermal state between steps. A new `/tracer` front end models *connection* — you choose where you plug in, and the server decides what you can see.

**Tech Stack:** Python 3.11+ standard library only for the simulator (no new runtime dependencies — this is a hard constraint, see below). FastAPI 0.111.0 + uvicorn 0.29.0 for the API, already pinned in `requirements.txt`. Front end is a single static HTML file with no build tools and no CDN.

**Spec:** `docs/superpowers/specs/2026-09-10-building-822-trane-baseline-design.md` — read it before Task 1. The plan argues from the spec; where they disagree, the spec wins and you should stop and flag it.

---

## Global Constraints

Every task's requirements implicitly include this section.

**Git — read this first.** **Do not run any git command.** No `git add`, no `git commit`, no `git checkout`, no branching. J is the sole owner of this repository's history and stages everything manually. Every task below ends with a **Checkpoint** step instead of a commit: you stop, report what changed, and wait. A worker that commits has failed the task regardless of whether the code works. This overrides the commit step in any skill template you are following.

**No new dependencies.** `simulator/model822.py` and `scripts/gen-822-inventory.py` must import only the Python 3.11 standard library. No numpy, no scipy, no psychrolib. The existing simulator is deliberately dependency-free so it runs in the lab without network access; `requirements.txt` stays exactly `fastapi==0.111.0` and `uvicorn[standard]==0.29.0`. Repo rule: standard library over third-party (`.claude/rules/security-standards.md` #12).

**Tests use `--self-test`, not pytest.** The repo has no test suite and no pytest in `requirements.txt`. The established pattern is a `--self-test` flag on the script itself — see `scripts/validate-submittal.py:217` and `scripts/merge-submittal.py`. Follow it. Do not add pytest, do not create a `tests/` directory.

**Never modify hospital or office behavior.** `AHU-OR-1`, `AHU-ICU-1`, `VAV-OR-101`, `RM-ISO-201`, `CHW-PLANT-1`, `HW-PLANT-1`, `RTU-1`, `VAV-301`, `CHILLER-1`, `BOILER-1` and all their points are committed, verified work. Task 9 enforces this with a regression check captured in Task 1. Additive changes to shared files are fine; behavioral changes are not.

**Never modify** `frontend/static/niagara.html`, `frontend/static/metasys.html`, `BREAK/`, `DESIGN/`, or `data/input/fault_library.json`. Niagara stays hospital-only by explicit instruction. Faults are spec 2, not this plan.

**Known interaction with the DESIGN track — do not "fix" it.** `validate-submittal.py:52` and `merge-submittal.py` check proposed design submittals for point-name and equipment-ID collisions against the live `data/input/` inventory. Once 822 is merged, design submittals are checked against 822 too. That is correct behavior — a new design should not collide with Building 822 any more than with the hospital — but it is a behavior change to already-shipped tooling, so expect it rather than treating it as a bug. Neither script needs modification.

**Synthetic data only.** No real building numbers, IPs, MAC addresses, controller IDs, usernames, or base topology. The chiller carries a **fictional** serial number — the real unit's serial, CRC and option-code string are deliberately excluded from this repo (spec §3). Wing-to-unit numbering is fictional and clean by instruction.

**Bind 127.0.0.1 only.** Existing constraint in `scripts/start-frontend.sh`. Nothing in this plan opens a new listener.

**Units are US customary throughout** — °F, psia, Btu/lb, gpm, cfm, tons. The existing points file uses °F. Do not introduce SI anywhere, including internal intermediates, except inside `_sat_pressure_psia()` where the Magnus coefficients require °C and the conversion is local to that function.

**Point count is 421 and that is settled** (spec §11, resolved 2026-09-11). Do not trim `FCU_FAN_STATUS` or `MAU_EA_RH`.

---

## File Structure

**New files**

| Path | Responsibility |
|---|---|
| `simulator/psychro.py` | Psychrometric primitives only — saturation pressure, humidity ratio, enthalpy, dew point. No BAS concepts. Pure functions, trivially testable. |
| `simulator/model822.py` | The coupled state model: weather, chiller, CHW loop, coil, space. Owns `state_822.json`. Imports `psychro`. Knows nothing about FastAPI or file layout beyond its own state file. |
| `scripts/gen-822-inventory.py` | Build tool. Emits 822 equipment, networks, points, alarm rules into `data/input/`. Idempotent. Not imported at runtime. |
| `data/input/weather_822.json` | Design summer and shoulder day hourly profiles. |
| `frontend/static/tracer.html` | Tracer SC front end — connect screen, tree, MAU diagnostic row, service entrance, chiller walk-up. |
| `sequences/MAU-822-SOO.md` | Sequence of operations, makeup air unit. |
| `sequences/FCU-822-SOO.md` | Sequence of operations, room fan coil. |

`psychro.py` is split from `model822.py` deliberately: the psychrometric functions are the part most likely to be wrong in a way that is hard to see, and isolating them means they can be tested against known values without standing up a building.

**Modified files**

| Path | Change |
|---|---|
| `simulator/bas_sim.py` | `Point` gains `facility` and `states`; facility routing; override loading. Existing `scenario_value()` path untouched. |
| `data/input/points.json` | +421 822 points |
| `data/input/equipment.json` | `networks` list, nullable `parent`, 822 facility and devices |
| `data/input/alarm_rules.json` | +822 rules |
| `frontend/bas_api.py` | `/tracer`, `/api/topology`, `/api/chiller/822` |
| `frontend/static/index.html` | Third building card |
| `scripts/run-smoke-test.sh` | 822 coverage |

---

## Task Sequence

| # | Task | Deliverable |
|---|---|---|
| 1 | Regression baseline + point schema | `facility` reaches the simulator; hospital/office output frozen for comparison |
| 2 | Inventory generator | 421 points and the full device tree exist in `data/input/` |
| 3 | Psychrometric primitives | `psychro.py` verified against known values |
| 4 | Weather driver | Deterministic OA conditions per step |
| 5 | Chiller sub-model | Entering CHW temp computed from ambient and health |
| 6 | CHW loop sub-model | Building flow, return temp, ΔT falls out |
| 7 | Coil sub-model | Sensible/latent split — the core of the build |
| 8 | Space, hallway, state persistence | Thermal lag; `state_822.json` |
| 9 | Routing + override feedback | Commands move the building; hospital/office regression verified |
| 10 | Calibration + dynamic range | The model matches J's field numbers |
| 11 | API endpoints | `/api/topology`, `/api/chiller/822` |
| 12 | Tracer front end + wire-up | `/tracer` works end to end |

---

### Task 1: Regression baseline and point schema

The `Point` dataclass in `bas_sim.py` drops the `facility` field that already exists in `points.json`. Nothing can route by facility until it carries it. This task also freezes the current hospital/office output so Task 9 can prove nothing regressed.

**Files:**
- Modify: `simulator/bas_sim.py:25-38` (dataclass), `:43-58` (loader)
- Create: `data/output/.regression-baseline/` (scratch, git-ignored)

**Interfaces:**
- Consumes: nothing
- Produces: `Point.facility: str`, `Point.states: tuple[str, ...] | None` (tuple, not list — the dataclass is `frozen=True` and must stay hashable) — every later task filters points with `point.facility == "barracks822"`

- [ ] **Step 1: Capture the regression baseline BEFORE touching anything**

This must run against unmodified code. If you have already edited `bas_sim.py`, revert first.

```bash
cd GP-SECLAB/target-application/BAS-SIM
mkdir -p data/output/.regression-baseline
for s in normal chilled_water_degraded isolation_pressure_loss or_humidity_excursion; do
  python3 simulator/bas_sim.py --scenario "$s" --steps 12 --seed 7
  cp data/output/trends.csv  "data/output/.regression-baseline/$s-trends.csv"
  cp data/output/alarms.jsonl "data/output/.regression-baseline/$s-alarms.jsonl"
  python3 -c "
import json,sys
d=json.load(open('data/output/latest_points.json'))
d.pop('generated_at',None)
json.dump(d,open('data/output/.regression-baseline/$s-points.json','w'),indent=2,sort_keys=True)
"
done
ls data/output/.regression-baseline/
```

Expected: 12 files (4 scenarios × 3). `generated_at` is stripped because it is the only wall-clock field — `bas_sim.py:203`. Step timestamps are deterministic (`bas_sim.py:266` uses a fixed `start`), so trends and alarms compare byte-for-byte.

- [ ] **Step 2: Add the baseline directory to .gitignore**

```bash
grep -q '.regression-baseline' .gitignore || printf 'data/output/.regression-baseline/\n' >> .gitignore
tail -3 .gitignore
```

- [ ] **Step 3: Write the failing self-test**

Add to `simulator/bas_sim.py`, immediately above `def main()`:

```python
def self_test() -> int:
    """Schema checks that need no simulation run."""
    points = load_points()
    facilities = {p.facility for p in points}
    assert "hospital" in facilities, facilities
    assert "office" in facilities, facilities
    mv_points = [p for p in points if p.point_type == "MV"]
    for p in mv_points:
        assert p.states, f"MV point {p.name} has no states list"
    print(f"SELF-TEST PASS ({len(points)} points, facilities={sorted(facilities)})")
    return 0
```

And in `main()`, as the first lines after `args = parser.parse_args()`:

```python
    if args.self_test:
        raise SystemExit(self_test())
```

And register the flag on the parser, after the `--seed` argument:

```python
    parser.add_argument("--self-test", action="store_true", help="Run schema self-checks and exit")
```

- [ ] **Step 4: Run it to verify it fails**

Run: `python3 simulator/bas_sim.py --self-test`
Expected: `AttributeError: 'Point' object has no attribute 'facility'`

- [ ] **Step 5: Add the fields to the dataclass**

In `simulator/bas_sim.py`, replace the `Point` dataclass body (currently ending at `trend_interval_sec: int`) so the two new fields follow it:

```python
@dataclass(frozen=True)
class Point:
    name: str
    equipment: str
    point_type: str
    units: str
    normal_min: float
    normal_max: float
    writable: bool
    critical: bool
    trend_interval_sec: int
    facility: str
    states: tuple[str, ...] | None = None

    @property
    def midpoint(self) -> float:
        return (self.normal_min + self.normal_max) / 2
```

`states` is a tuple, not a list, because the dataclass is `frozen=True` and must stay hashable.

- [ ] **Step 6: Populate them in the loader**

In `load_points()`, add two entries to the `Point(...)` constructor call, after `trend_interval_sec=...`:

```python
            facility=str(item["facility"]),
            states=tuple(item["states"]) if item.get("states") else None,
```

`facility` is required — every record in `points.json` already has it, and a missing one should raise rather than silently default.

- [ ] **Step 7: Run the self-test to verify it passes**

Run: `python3 simulator/bas_sim.py --self-test`
Expected: `SELF-TEST PASS (24 points, facilities=['hospital', 'office'])`

- [ ] **Step 8: Verify the schema change did not alter output**

```bash
python3 simulator/bas_sim.py --scenario normal --steps 12 --seed 7
diff data/output/trends.csv data/output/.regression-baseline/normal-trends.csv && echo "TRENDS IDENTICAL"
```

Expected: `TRENDS IDENTICAL`. If this differs, the dataclass change leaked into value generation — stop and investigate before continuing.

- [ ] **Step 9: Checkpoint**

Do not commit. Report: files modified, self-test output, and confirmation that the regression diff was clean. Wait for review.

---

### Task 2: Inventory generator

36 FCUs × 6 points is not hand-authorable. This generates all 421 points plus the device and network tree, deterministically.

**Files:**
- Create: `scripts/gen-822-inventory.py`
- Modify: `data/input/points.json`, `data/input/equipment.json`, `data/input/alarm_rules.json` (by running the generator)

**Interfaces:**
- Consumes: `Point` schema from Task 1 (`facility`, `states`)
- Produces: point names every later task depends on. The naming contract is exact:
  - MAU: `MAU01_SAT`, `MAU01_SAT_SP`, `MAU01_SA_RH`, `MAU01_EAT`, `MAU01_EA_RH`, `MAU01_FAN_CMD`, `MAU01_FAN_STATUS`, `MAU01_OA_DMPR_CMD`, `MAU01_OA_DMPR_POS`, `MAU01_CHW_VLV_CMD`, `MAU01_CHW_VLV_POS`, `MAU01_COIL_DT` (`MAU01` … `MAU13`)
  - FCU: `FCU_A101_SPACE_TEMP`, `_SPACE_TEMP_SP`, `_FAN_MODE`, `_FAN_STATUS`, `_CHW_VLV_CMD`, `_CHW_VLV_POS` (wings A–D, floors 1–3, rooms 01–03)
  - Hallway: `HALL_A1_TEMP`, `HALL_A1_RH`
  - CHW: `CHW822_ENT_SUP_TEMP`, `_ENT_RET_TEMP`, `_BLDG_DT`, `_BLDG_DP`, `_STRAINER_DP`, `_P1_CMD`, `_P1_STATUS`, `_P2_CMD`, `_P2_STATUS`
  - Comm: `SC82201_STATUS`, `SC82202_STATUS`, `MSTP01A_STATUS`, `MSTP01B_STATUS`, `MSTP02A_STATUS`, `MSTP02B_STATUS`
  - Chiller: `RTAC822_EVAP_ENT_TEMP`, `_EVAP_LVG_TEMP`, `_EVAP_LVG_SP`, `_AMBIENT_TEMP`, `_PCT_CAPACITY`, `_CKT1_STATUS`, `_CKT2_STATUS`, `_CKT1_FAN_STATUS`, `_CKT2_FAN_STATUS`, `_ACTIVE_DIAG`

- [ ] **Step 1: Write the generator with its self-test**

Create `scripts/gen-822-inventory.py`:

```python
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
            _pt(f"{tag}_SA_RH",        eq, "AI", "%",    50, 70,  False, False, 60),
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
    assert len(pts) == 421, f"expected 421 points, got {len(pts)}"
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
```

- [ ] **Step 2: Run the self-test**

Run: `python3 scripts/gen-822-inventory.py --self-test`
Expected: `SELF-TEST PASS (421 points, 63 equipment records)`

If the point count is not exactly 421, do not adjust the assertion — find the missing or extra points. The count is fixed by spec §4.4 and §11.

- [ ] **Step 3: Dry run**

Run: `python3 scripts/gen-822-inventory.py`
Expected: `DRY RUN: would write 421 points, 63 equipment, 5 networks, 28 alarm rules. Re-run with --apply.`

- [ ] **Step 4: Back up the inventories, then apply**

```bash
mkdir -p /tmp/822-inv-backup
cp data/input/points.json data/input/equipment.json data/input/alarm_rules.json /tmp/822-inv-backup/
python3 scripts/gen-822-inventory.py --apply
```

- [ ] **Step 5: Verify the merge is additive**

```bash
python3 - <<'PY'
import json
p = json.load(open('data/input/points.json'))
by_fac = {}
for r in p:
    by_fac[r['facility']] = by_fac.get(r['facility'], 0) + 1
print(by_fac, 'total', len(p))
assert by_fac['hospital'] == 14 and by_fac['office'] == 10, 'existing points changed!'
assert by_fac['barracks822'] == 421
eq = json.load(open('data/input/equipment.json'))
print('networks:', len(eq['networks']), 'facilities:', [f['id'] for f in eq['facilities']])
PY
```

Expected: `{'hospital': 14, 'office': 10, 'barracks822': 421} total 445`, and networks 5.

- [ ] **Step 6: Verify idempotency and the force gate**

```bash
python3 scripts/gen-822-inventory.py --apply 2>&1 | tail -2
```
Expected: exits with the collision message naming `--force`, and writes nothing.

```bash
cp data/input/points.json /tmp/822-inv-backup/points-after.json
python3 scripts/gen-822-inventory.py --apply --force
diff <(python3 -c "import json;print(json.dumps(sorted(json.load(open('data/input/points.json')),key=lambda r:r['point']),indent=1))") \
     <(python3 -c "import json;print(json.dumps(sorted(json.load(open('/tmp/822-inv-backup/points-after.json')),key=lambda r:r['point']),indent=1))") \
  && echo "IDEMPOTENT"
```
Expected: `IDEMPOTENT`.

- [ ] **Step 7: Verify the simulator still loads and hospital records are unchanged**

```bash
python3 simulator/bas_sim.py --self-test
python3 simulator/bas_sim.py --scenario normal --steps 12 --seed 7
python3 -c "
import csv, json
live = json.load(open('data/input/points.json'))
orig = json.load(open('/tmp/822-inv-backup/points.json'))
kept = [r for r in live if r['facility'] != 'barracks822']
assert kept == orig, 'hospital/office point records were modified'
print('HOSPITAL/OFFICE RECORDS IDENTICAL')
rows = list(csv.DictReader(open('data/output/trends.csv')))
print(len({r['point'] for r in rows}), 'points now trending')
"
```

Expected: `HOSPITAL/OFFICE RECORDS IDENTICAL` and `445 points now trending`.

**Do NOT assert hospital/office trend VALUES here — they will legitimately differ,
and that is not a regression.** `bas_sim.py` advances one shared
`random.Random(seed)` across every point in a step (`normal_value()` draws once
per non-bool point). Adding 421 points shifts the RNG state that hospital and
office draws consume, so step 0 still matches the baseline and step 1 onward
diverges. Verified empirically: 24 points/step vs 445 points/step from seed 7 —
step 0 identical, step 1 not.

This is transient and expected. **Task 9 splits the snapshot loop so 822 points
consume no randomness**, restoring the original draw order and count for hospital
and office. Task 9 Step 4 is where the trend-value regression gate belongs, and it
must pass there. Between Task 2 and Task 9 the lab sits in a known,
temporarily-shifted state.

At this point 822 points exist but produce jitter, not physics — they are still
going through the old `normal_value()` path. That is expected until Task 9 wires
the routing.

- [ ] **Step 7b: Verify 822 can be removed cleanly**

This is the reversibility guarantee. If J decides 822 was a mistake, one
command must put the lab back exactly as it was.

```bash
python3 scripts/gen-822-inventory.py --remove
python3 -c "
import json
for name in ('points.json','equipment.json','alarm_rules.json'):
    now  = json.load(open('data/input/'+name))
    orig = json.load(open('/tmp/822-inv-backup/'+name))
    assert now == orig, name + ' did NOT round-trip back to its pre-822 state'
    print('  ' + name + ': round-trip clean')
"
python3 scripts/gen-822-inventory.py --apply    # put 822 back and carry on
```

Compares against the `/tmp/822-inv-backup/` copies taken in Step 4 — the true
pre-822 state. All three files must come back **exactly** equal, including the
`parent` keys that `--apply` added and `--remove` strips again. If any file
differs, `remove()` is leaving residue and the reversibility claim is false.

- [ ] **Step 8: Checkpoint**

Do not commit. Report point counts by facility, self-test output, idempotency result, and the regression comparison. Wait for review.

---

### Task 3: Psychrometric primitives

Isolated from the building model because these are the functions most likely to be subtly wrong in a way nobody notices. They are verified against published ASHRAE values.

**Files:**
- Create: `simulator/psychro.py`

**Interfaces:**
- Consumes: nothing (standard library only)
- Produces: `sat_pressure_psia(t_f)`, `humidity_ratio(t_f, rh_pct)`, `humidity_ratio_saturated(t_f)`, `rh_from_w(t_f, w)`, `enthalpy(t_f, w)`, `dew_point(t_f, rh_pct)` — all floats in, float out

- [ ] **Step 1: Write the module**

Create `simulator/psychro.py`:

```python
#!/usr/bin/env python3
"""Psychrometric primitives for the Building 822 model.

US customary units, sea-level pressure, standard library only. Teaching-grade:
accurate to roughly 1% against ASHRAE tables over the range this lab uses
(40-110 F), which is far tighter than the model's other assumptions.
"""

from __future__ import annotations

import math
import sys

P_ATM_PSIA = 14.696


def _f_to_c(t_f: float) -> float:
    return (t_f - 32.0) * 5.0 / 9.0


def _c_to_f(t_c: float) -> float:
    return t_c * 9.0 / 5.0 + 32.0


def sat_pressure_psia(t_f: float) -> float:
    """Saturation vapor pressure, psia. Magnus formula.

    Celsius appears only inside this function because the Magnus coefficients
    are defined in Celsius. Everything else in this codebase is Fahrenheit.
    """
    t_c = _f_to_c(t_f)
    kpa = 0.61078 * math.exp(17.27 * t_c / (t_c + 237.3))
    return kpa * 0.145038


def humidity_ratio(t_f: float, rh_pct: float) -> float:
    """Humidity ratio W, lb moisture per lb dry air."""
    rh = max(0.0, min(100.0, rh_pct))
    pv = min(rh / 100.0 * sat_pressure_psia(t_f), P_ATM_PSIA * 0.99)
    return 0.621945 * pv / (P_ATM_PSIA - pv)


def humidity_ratio_saturated(t_f: float) -> float:
    """W at saturation for a given dry bulb — used for apparatus dew point."""
    return humidity_ratio(t_f, 100.0)


def rh_from_w(t_f: float, w: float) -> float:
    """Relative humidity percent from dry bulb and humidity ratio."""
    w = max(0.0, w)
    pv = P_ATM_PSIA * w / (0.621945 + w)
    return max(0.0, min(100.0, 100.0 * pv / sat_pressure_psia(t_f)))


def enthalpy(t_f: float, w: float) -> float:
    """Moist air enthalpy, Btu per lb dry air."""
    return 0.240 * t_f + w * (1061.0 + 0.444 * t_f)


def dew_point(t_f: float, rh_pct: float) -> float:
    """Dew point temperature, F. Inverse Magnus."""
    pv_kpa = (max(1e-6, rh_pct) / 100.0 * sat_pressure_psia(t_f)) / 0.145038
    ln_ratio = math.log(pv_kpa / 0.61078)
    return _c_to_f(237.3 * ln_ratio / (17.27 - ln_ratio))


def self_test() -> int:
    """Verify against published ASHRAE psychrometric values at sea level."""
    cases = [
        # (dry bulb F, RH %, expected W, expected h, expected dew point F)
        (80.0, 50.0, 0.0110, 31.5, 59.7),
        (75.0, 50.0, 0.00927, 28.1, 55.1),
        (95.0, 60.0, 0.0215, 46.3, 79.4),
    ]
    for t, rh, w_exp, h_exp, dp_exp in cases:
        w = humidity_ratio(t, rh)
        assert abs(w - w_exp) < 0.0005, f"W at {t}F/{rh}%: {w:.5f} vs {w_exp}"
        assert abs(enthalpy(t, w) - h_exp) < 0.5, f"h at {t}F/{rh}%"
        assert abs(dew_point(t, rh) - dp_exp) < 1.0, f"DP at {t}F/{rh}%"
        assert abs(rh_from_w(t, w) - rh) < 0.5, f"RH round-trip at {t}F"

    # Monotonicity — these must hold everywhere, not just at the sample points.
    assert sat_pressure_psia(90.0) > sat_pressure_psia(70.0)
    assert humidity_ratio(80.0, 80.0) > humidity_ratio(80.0, 40.0)
    assert humidity_ratio_saturated(60.0) > humidity_ratio_saturated(45.0)
    assert enthalpy(80.0, 0.012) > enthalpy(80.0, 0.008)

    # Guard rails
    assert rh_from_w(75.0, 0.0) == 0.0
    assert humidity_ratio(75.0, 0.0) == 0.0
    assert 0.0 <= rh_from_w(50.0, 0.050) <= 100.0, "RH must clamp, not exceed 100"

    print("SELF-TEST PASS (psychro: 3 ASHRAE cases, monotonicity, guard rails)")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
```

- [ ] **Step 2: Run the self-test**

Run: `python3 simulator/psychro.py --self-test`
Expected: `SELF-TEST PASS (psychro: 3 ASHRAE cases, monotonicity, guard rails)`

These tolerances have been verified to pass — actual values are W=0.01092/0.00923/0.02142, h=31.17/28.10/46.43, DP=59.7/55.1/78.9. If an assertion fails, the formula was mistyped; do not loosen the tolerance.

- [ ] **Step 3: Checkpoint**

Do not commit. Report the self-test output. Wait for review.

---

### Task 4: Weather driver

An air-cooled chiller and a latent load problem are the same seasonal story. Weather is a shared input to both the chiller and every coil, so it gets its own small interface.

**Files:**
- Create: `data/input/weather_822.json`
- Create: `simulator/model822.py` (first content — constants and weather only)

**Interfaces:**
- Consumes: nothing
- Produces: `load_weather(profile: str) -> list[tuple[float, float]]` returning 24 hourly `(dry_bulb_F, rh_pct)` pairs; `weather_at(profile, step)` returning the pair for a simulation step

- [ ] **Step 1: Create the weather profiles**

Create `data/input/weather_822.json`. Jacksonville-like, synthetic, deterministic:

```json
{
  "profiles": {
    "design_summer": {
      "description": "Synthetic design summer day. Peak 92F/65% mid-afternoon.",
      "hourly": [
        [78, 88], [77, 90], [76, 91], [76, 92], [75, 92], [76, 91],
        [78, 88], [81, 82], [84, 76], [87, 71], [89, 68], [91, 66],
        [92, 65], [92, 64], [92, 64], [91, 65], [89, 68], [87, 72],
        [85, 77], [83, 81], [81, 84], [80, 86], [79, 87], [78, 88]
      ]
    },
    "shoulder": {
      "description": "Synthetic shoulder-season day. Peak 82F/55%.",
      "hourly": [
        [68, 78], [67, 80], [66, 81], [66, 82], [65, 82], [66, 81],
        [68, 77], [71, 71], [74, 66], [77, 61], [79, 58], [81, 56],
        [82, 55], [82, 54], [82, 54], [81, 55], [79, 58], [77, 62],
        [75, 66], [73, 70], [71, 73], [70, 75], [69, 76], [68, 77]
      ]
    }
  },
  "notes": "Synthetic lab weather. Not real observed data for any location."
}
```

- [ ] **Step 2: Start model822.py with constants and the weather loader**

Create `simulator/model822.py`:

```python
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
    "COIL_APPROACH_PENALTY": 45.0,
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
```

- [ ] **Step 3: Verify the loader**

```bash
python3 -c "
import sys; sys.path.insert(0,'simulator')
import model822 as m
print('summer noon:', m.weather_at('design_summer', 0))
print('summer 3pm :', m.weather_at('design_summer', 180))
print('shoulder   :', m.weather_at('shoulder', 0))
print('bad profile:', m.weather_at('nope', 0))
"
```

Expected: `summer noon: (92.0, 65.0)`, `summer 3pm : (91.0, 65.0)`, `shoulder   : (82.0, 55.0)`, and for the bad profile a stderr warning followed by `(78.0, 60.0)` — a fallback, never a crash.

Step 180 is three hours past noon, so it reads `hourly[15]` = `[91, 65]`. (Hours 13 and 14 are the `[92, 64]` pair — do not expect those here.)

- [ ] **Step 4: Checkpoint**

Do not commit. Report the four weather lookups. Wait for review.

---

### Task 5: Chiller sub-model

The campus RTAC. Off-tree, visible only through the service entrance and its own local display. Its whole job is to make entering water temperature something the model computes rather than something a human types.

**Files:**
- Modify: `simulator/model822.py` (append)

**Interfaces:**
- Consumes: `TUNING` from Task 4
- Produces: `chiller_step(load_tons, ambient_f, knobs) -> ChillerState` where `ChillerState` is a dict with keys `lwt_f`, `ewt_f`, `pct_capacity`, `available_tons`, `load_tons`, `ambient_f`, `ckt1_on`, `ckt2_on`, `ckt1_fan_ok`, `ckt2_fan_ok`, `active_diag`. **`load_tons` and `ambient_f` are required, not incidental** — Task 8 emits `ambient_f` as `RTAC822_AMBIENT_TEMP`, and Task 11's `/api/chiller/822` returns both on the walk-up display.

- [ ] **Step 1: Append the chiller model**

```python
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
        "ewt_f": round(lwt + TUNING["CHILLER_EVAP_RISE_F"], 2),
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
```

- [ ] **Step 2: Verify chiller behavior**

```bash
python3 -c "
import sys; sys.path.insert(0,'simulator')
from model822 import chiller_step as c
print('healthy 90F 100t :', c(100, 90)['lwt_f'], c(100, 90)['pct_capacity'], c(100,90)['active_diag'])
print('hot 105F 140t    :', c(140, 105)['lwt_f'], c(140,105)['active_diag'])
print('fouled .40 @100F :', c(120, 100, {'condenser_fouling':0.40})['lwt_f'])
print('circuit out      :', c(100, 90, {'circuit_locked_out':[1]})['lwt_f'], c(100,90,{'circuit_locked_out':[1]})['active_diag'])
print('derate monotonic :', c(100,85)['available_tons'], c(100,95)['available_tons'], c(100,105)['available_tons'])
"
```

Expected, verified:

```
healthy 90F 100t         lwt= 44.00 pct= 67.9 diag=None
hot 105F 140t            lwt= 50.19 pct=100.0 diag=LowEvapTemp
fouled .40 @100F 120t    lwt= 59.85 pct=100.0 diag=LowEvapTemp
circuit out              lwt= 54.21 pct=100.0 diag=CircuitLockout
derate tons @85/95/105: [155.0, 139.5, 124.0]
```

Healthy holds exactly 44.0. Available tons decrease monotonically with ambient — that is the air-cooled behavior the whole chiller story rests on.

- [ ] **Step 3: Checkpoint**

Do not commit. Report the five chiller cases. Wait for review.

---

### Task 6: CHW loop sub-model

Building flow, and the return temperature that makes ΔT an instrument instead of a number.

**Files:**
- Modify: `simulator/model822.py` (append)

**Interfaces:**
- Consumes: `TUNING`
- Produces: `chw_loop(entering_f, total_btuh, knobs) -> dict` with keys `gpm`, `flow_frac`, `supply_f`, `return_f`, `delta_t_f`, `strainer_dp_psid`, `bldg_dp_psid`

- [ ] **Step 1: Append the CHW loop**

```python
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
```

- [ ] **Step 2: Verify loop behavior**

```bash
python3 -c "
import sys; sys.path.insert(0,'simulator')
from model822 import chw_loop as L
h = L(44.0, 440000)
print('healthy      :', h['gpm'], 'dT', h['delta_t_f'], 'strainerDP', h['strainer_dp_psid'])
r = L(44.0, 440000, {'strainer_resistance':0.70})
print('strainer .70 :', r['gpm'], 'dT', r['delta_t_f'], 'strainerDP', r['strainer_dp_psid'])
o = L(44.0, 440000, {'p1_running':False,'p2_running':False})
print('pumps off    :', o['gpm'], 'dT', o['delta_t_f'])
assert h['delta_t_f'] == 11.0, h
assert r['strainer_dp_psid'] > h['strainer_dp_psid']
assert o['gpm'] == 0.0 and o['delta_t_f'] == 0.0, 'no divide-by-zero with pumps off'
print('OK')
"
```

Expected, verified:

```
healthy      : 80.0 11.0 1.5
strainer .70 : 24.0 36.67 5.91
pumps off    : 0.0 0.0
```

**ΔT must be exactly 11.0** on the healthy case — that is the calibration anchor confirming `CHW_GPM_DESIGN`.

**Do not "fix" the strainer case.** Tested in isolation with the heat load held constant, restricting flow *raises* ΔT to 36.67 — same heat, less water. That is correct. In the coupled model the restriction also collapses coil capacity, so total heat falls further than flow does and the building ΔT *drops* to roughly 2-4 °F, which is the diagnostic signature J sees in the field. Both behaviors are right; they are different experiments. A worker who changes `chw_loop` to make the isolated case fall has broken it.

- [ ] **Step 3: Checkpoint**

Do not commit. Report the three loop cases. Wait for review.

---

### Task 7: Coil sub-model — sensible and latent

The core of the build. A bypass-factor / apparatus-dew-point coil, which is the standard teaching-grade approach and the reason sensible and latent come out separately instead of collapsing into one temperature symptom.

**Files:**
- Modify: `simulator/model822.py` (append)

**Interfaces:**
- Consumes: `psychro`, `TUNING`
- Produces: `coil_step(t_ent_f, rh_ent_pct, entering_water_f, valve_pct, flow_frac, cfm, q_max_btuh, knobs) -> dict` with keys `t_lvg_f`, `rh_lvg_pct`, `w_lvg`, `q_total_btuh`, `q_sensible_btuh`, `q_latent_btuh`, `adp_f`, `bypass_factor`, `capacity_fraction`

- [ ] **Step 1: Append the coil model**

```python
# --- cooling coil -----------------------------------------------------------

COIL_KNOB_DEFAULTS: dict[str, Any] = {
    "coil_fouling": 0.0,             # 0..1
    "air_bound": False,              # air trapped in the tubes
    "valve_authority": 1.0,          # 0..1, command-to-flow gain
    "three_way_position_error": 0.0, # 0..1, mixing wrong despite full flow
}


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
```

- [ ] **Step 2: Verify the coil, especially the latent split**

```bash
python3 -c "
import sys; sys.path.insert(0,'simulator')
from model822 import coil_step as C
from model822 import TUNING as T
qm = T['MAU_COIL_MAX_BTUH']
def show(label, **kw):
    r = C(83.0, 58.0, 44.0, kw.pop('valve',100.0), kw.pop('flow',1.0), T['MAU_CFM'], qm, kw or None)
    print(f\"{label:22s} SAT={r['t_lvg_f']:5.1f} RH={r['rh_lvg_pct']:5.1f} ADP={r['adp_f']:5.1f} \"
          f\"BF={r['bypass_factor']:.3f} cf={r['capacity_fraction']:.2f} \"
          f\"sens={r['q_sensible_btuh']:7.0f} lat={r['q_latent_btuh']:7.0f}\")
show('valve 100%')
show('valve 60%', valve=60.0)
show('valve 20%', valve=20.0)
show('valve 0%',  valve=0.0)
show('fouling .60', coil_fouling=0.60)
show('air bound', air_bound=True)
show('3way error .5', three_way_position_error=0.5)
"
```

Expected, and each of these is a property the later faults depend on:
- Leaving temperature rises monotonically as the valve closes; at 0% the coil does nothing and leaving air equals entering air.
- Latent heat is **non-zero** whenever the ADP is below the entering dew point, and falls to zero as cf collapses. If latent is always zero the `w_adp` comparison is inverted and the whole humidity story is dead.
- `fouling .60`, `air bound` and `3way error .5` all raise leaving temperature and cut latent — three different causes, one family of symptoms, which is exactly the diagnostic problem being taught.

- [ ] **Step 3: Verify the capacity limit reverses the damper effect**

This is the single most important behavioral check in the build. It is the mechanism behind J's field fix of backing dampers from wide open toward half.

```bash
python3 -c "
import sys; sys.path.insert(0,'simulator')
from model822 import coil_step as C, mix_air, TUNING as T
for damper in (0.95, 0.50, 0.25):
    t,rh = mix_air(92.0, 65.0, 75.0, 0.0110, damper)
    r = C(t, rh, 44.0, 100.0, 1.0, T['MAU_CFM'], T['MAU_COIL_MAX_BTUH'])
    print(f'damper {int(damper*100):3d}%  entering {t:5.1f}F/{rh:4.1f}%  ->  '
          f'SAT {r[\"t_lvg_f\"]:5.1f}F  w_lvg {r[\"w_lvg\"]:.5f}  q {r[\"q_total_btuh\"]:7.0f}')
"
```

Expected: as the damper opens the entering air gets hotter and wetter, the coil hits `q_max`, and **leaving air gets both warmer and wetter**. If opening the damper produces *drier* supply air, the capacity limit is not engaging — check that `q_max_btuh` is being passed, because without it the coil is infinitely powerful and the damper fault cannot exist.

- [ ] **Step 4: Checkpoint**

Do not commit. Report both verification outputs. Wait for review.

---

### Task 8: Spaces, control loops, and state persistence

Per-unit state for 13 MAUs, 36 FCUs and 12 corridors — not the averaged prototype. This task produces the full step function and the state file.

**Files:**
- Modify: `simulator/model822.py` (append)

**Interfaces:**
- Consumes: everything from Tasks 4-7
- Produces: `cold_start_state() -> dict`, `load_state() -> dict`, `save_state(state)`, `step_822(state, step, profile, overrides, knobs) -> tuple[dict, dict[str, float]]` returning `(new_state, point_values)` keyed by the exact point names from Task 2

- [ ] **Step 1: Append the identity helpers and cold-start state**

```python
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
```

- [ ] **Step 2: Append the control loop**

```python
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
```

- [ ] **Step 3: Append the step function**

```python
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
            valve, integral = float(cmd_override["value"]), st["integral"]
        else:
            valve, integral = pi_valve(st["sat_f"], sp, st["integral"], st["valve_pct"])

        if not fan_on:
            res = {"t_lvg_f": t_ent, "rh_lvg_pct": rh_ent, "w_lvg": ps.humidity_ratio(t_ent, rh_ent),
                   "q_total_btuh": 0.0, "q_sensible_btuh": 0.0, "q_latent_btuh": 0.0,
                   "adp_f": t_ent, "bypass_factor": 1.0, "capacity_fraction": 0.0}
        else:
            res = coil_step(t_ent, rh_ent, entering_f, valve, flow_frac,
                            TUNING["MAU_CFM"], TUNING["MAU_COIL_MAX_BTUH"], k)

        total_btuh += res["q_total_btuh"]
        st.update(valve_pct=valve, integral=integral, sat_f=res["t_lvg_f"],
                  damper_pct=damper, fan_on=fan_on, sat_sp_f=sp)
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
        pts[f"{mau}_CHW_VLV_CMD"] = round(valve, 1)
        pts[f"{mau}_CHW_VLV_POS"] = round(valve, 1)
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

        res = coil_step(st["space_t_f"], room_rh, entering_f, valve, flow_frac,
                        TUNING["FCU_CFM"] * flow_scale,
                        TUNING["FCU_COIL_MAX_BTUH"] * flow_scale if flow_scale else 0.0, k)
        total_btuh += res["q_total_btuh"]

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
```

- [ ] **Step 4: Append the module self-test**

```python
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

    assert len(healthy) == 421, f"step_822 produced {len(healthy)} points, expected 421"

    print(f"SELF-TEST PASS (model822: 421 points, healthy SAT {sat:.1f}F, "
          f"dT {healthy['CHW822_BLDG_DT']:.1f}F, hall RH {healthy['HALL_A1_RH']:.1f}%)")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
```

- [ ] **Step 5: Run the model self-test**

Run: `python3 simulator/model822.py --self-test`
Expected: `SELF-TEST PASS (model822: 421 points, healthy SAT ~65F, dT ~11F, hall RH ~68%)`

The point count assertion is the important one — it proves `step_822` emits exactly the inventory Task 2 generated, with no typos in point names. If it reports fewer than 421, diff the emitted keys against `points.json`:

```bash
python3 -c "
import sys, json; sys.path.insert(0,'simulator')
import model822 as m
st = m.cold_start_state()
st, pts = m.step_822(st, 0)
want = {p['point'] for p in json.load(open('data/input/points.json')) if p['facility']=='barracks822'}
print('missing from model:', sorted(want - set(pts))[:10])
print('extra in model   :', sorted(set(pts) - want)[:10])
"
```

- [ ] **Step 6: Checkpoint**

Do not commit. Report the self-test line and the point-name diff (both sides must be empty). Wait for review.

---

### Task 9: Facility routing and command feedback

Wire the model into `bas_sim.py` so 822 points come from physics and everything else keeps the committed path exactly. This is also where `operator_overrides.json` stops being a display-layer fiction — for 822 only.

**Files:**
- Modify: `simulator/bas_sim.py` — imports, `run_simulation()`, `main()`

**Interfaces:**
- Consumes: `step_822`, `load_state`, `save_state`, `cold_start_state` from Task 8
- Produces: 822 point values in `latest_points.json`, `trends.csv`, `alarms.jsonl`

- [ ] **Step 1: Add the import and override loader**

In `simulator/bas_sim.py`, after the existing `from typing import Any` line:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
import model822  # noqa: E402
```

And add `import sys` to the existing import block.

Then add this loader beside the other `load_*` functions:

```python
def load_overrides_822() -> dict[str, dict[str, Any]]:
    """Operator overrides, filtered to 822 points only.

    Hospital and office overrides deliberately keep their existing
    display-layer behavior in bas_api.py. Feeding them into the simulator
    would change committed output.
    """
    path = OUTPUT_DIR / "operator_overrides.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    names_822 = {
        item["point"]
        for item in json.loads((INPUT_DIR / "points.json").read_text(encoding="utf-8"))
        if item.get("facility") == model822.FACILITY
    }
    return {k: v for k, v in raw.items() if k in names_822}
```

- [ ] **Step 2: Route by facility in run_simulation**

In `run_simulation()`, replace the inner snapshot loop. The existing code is:

```python
        snapshot: dict[str, float] = {}
        for point in points:
            value = scenario_value(point, scenario, step, rng)
            snapshot[point.name] = value
```

Replace with:

```python
        snapshot: dict[str, float] = {}
        for point in legacy_points:
            snapshot[point.name] = scenario_value(point, scenario, step, rng)
        if state_822 is not None:
            state_822, pts_822 = model822.step_822(
                state_822, step, profile, overrides_822
            )
            snapshot.update(pts_822)
```

And immediately after `points_by_name = {point.name: point for point in points}`, add:

```python
    legacy_points = [p for p in points if p.facility != model822.FACILITY]
    has_822 = any(p.facility == model822.FACILITY for p in points)
    state_822 = model822.load_state() if has_822 else None
    overrides_822 = load_overrides_822() if has_822 else {}
```

Splitting the loop this way keeps the `rng` draw sequence for hospital and office points exactly as it was — 822 points consume no randomness — which is what makes the Task 1 regression baseline still match.

Finally, immediately before `write_outputs(...)`, add:

```python
    if state_822 is not None:
        model822.save_state(state_822)
```

- [ ] **Step 3: Add the --profile argument**

Change the `run_simulation` signature to accept the profile:

```python
def run_simulation(scenario: str, steps: int, seed: int, fault_id: str | None = None,
                   profile: str = "design_summer") -> None:
```

In `main()`, add the argument after `--seed`:

```python
    parser.add_argument("--profile", choices=["design_summer", "shoulder"],
                        default="design_summer",
                        help="Building 822 weather profile")
```

and pass it through:

```python
    run_simulation(args.scenario or "normal", args.steps, args.seed, args.fault, args.profile)
```

- [ ] **Step 4: Verify the hospital and office regression**

This is the gate on "the existing engine is untouched."

```bash
python3 simulator/bas_sim.py --scenario normal --steps 12 --seed 7
python3 - <<'PY'
import csv, json
rows = list(csv.DictReader(open('data/output/trends.csv')))
base = list(csv.DictReader(open('data/output/.regression-baseline/normal-trends.csv')))
base_pts = {r['point'] for r in base}
assert [r for r in rows if r['point'] in base_pts] == base, "REGRESSION: hospital/office changed"
print("REGRESSION CLEAN — hospital/office trend rows byte-identical")
pts = json.load(open('data/output/latest_points.json'))
snap = pts['points']
print("822 sample:", {k: snap[k] for k in ('MAU01_SAT','MAU01_CHW_VLV_CMD','CHW822_BLDG_DT','HALL_A1_RH') if k in snap})
PY
```

Expected: `REGRESSION CLEAN`, plus real 822 values — SAT near 65, valve modulating, ΔT near 11.

Repeat for the other three scenarios; all four must be clean.

**Cold-start note — use enough steps.** `state_822.json` persists between runs, but
from a cold start the PI loops need simulated time to wind up. Measured from cold:

| Steps | MAU01_SAT | Valve |
|---|---|---|
| 12 | 76.0 °F | 55 % |
| 24 | 69.5 °F | 70 % |
| 60 | **65.3 °F** | **76 %** |
| 120 | 65.1 °F | 76 % |

A 12-step run from cold shows a building still coming up to temperature, which reads
like a fault to anyone learning the healthy signature. This transient is physically
honest — a real building does not hit setpoint instantly — so do not fake it away in
`cold_start_state()`. Instead **use `--steps 60` or more for any run meant to show a
settled building**, and re-run once if a prior `state_822.json` already exists.

- [ ] **Step 5: Verify commands actually move the building**

The headline requirement of the whole spec.

```bash
python3 - <<'PY'
import json, pathlib, subprocess
ov = pathlib.Path('data/output/operator_overrides.json')
backup = ov.read_text() if ov.exists() else '{}'
ov.write_text(json.dumps({"MAU01_CHW_VLV_CMD": {"value": 0.0, "reason": "plan task 9 check"}}))
subprocess.run(['python3','simulator/bas_sim.py','--scenario','normal','--steps','60'], check=True)
snap = json.load(open('data/output/latest_points.json'))
snap = snap['points']          # latest_points.json nests points under 'points'
print("valve forced 0 -> MAU01_SAT =", snap['MAU01_SAT'])
assert snap['MAU01_SAT'] > 80.0, "commanding the valve shut did not warm the supply air"
ov.write_text(backup)
subprocess.run(['python3','simulator/bas_sim.py','--scenario','normal','--steps','60'], check=True)
snap = json.load(open('data/output/latest_points.json'))
snap = snap['points']          # latest_points.json nests points under 'points'
print("override released -> MAU01_SAT =", snap['MAU01_SAT'])
assert snap['MAU01_SAT'] < 72.0, "releasing the override did not return control to the loop"
print("COMMAND FEEDBACK WORKS")
PY
```

Expected: forcing the valve shut pushes MAU01_SAT near 90 °F; releasing it returns SAT to roughly 65. **If this test fails, nothing else in the build matters** — the building is not responding, which was the entire requirement.

- [ ] **Step 6: Checkpoint**

Do not commit. Report the regression result for all four scenarios and both command-feedback numbers. Wait for review.

---

### Task 10: Calibration and tuning harness

The model is structurally correct and most targets already land. This task closes the remaining gap systematically instead of by guesswork, and leaves behind a harness so the constants can be re-tuned when spec 2 changes the load.

**Known state entering this task** (measured on the assembled model, 150 steps, design summer):

| Measure | Target | Current | Status |
|---|---|---|---|
| MAU supply air | mid-60s °F | **65.1** | ✅ |
| Building CHW ΔT | 10–12 °F | **11.1** | ✅ |
| Entering CHW | 44 °F | **44.0** | ✅ |
| Valve at setpoint | partial, modulating | **76 %** | ✅ |
| Corridor RH | low-60s % | **72.5** | ❌ ~10 points wet |
| Degraded ΔT (building-wide) | 2–4 °F | **6.6** @ strainer 0.70 | ❌ not collapsing far enough |

**Files:**
- Create: `scripts/tune-822.py`
- Modify: `simulator/model822.py` — `TUNING` values only, never physics

**Interfaces:**
- Consumes: `model822.TUNING`, `model822.step_822`
- Produces: calibrated `TUNING` values; `scripts/tune-822.py --check` as a repeatable gate

- [ ] **Step 1: Write the tuning harness**

Create `scripts/tune-822.py`:

```python
#!/usr/bin/env python3
"""Calibration harness for the Building 822 model.

    python3 scripts/tune-822.py --check                 # gate: pass/fail vs targets
    python3 scripts/tune-822.py --sweep HALL_INFIL_CFM 5 10 15 25 40
    python3 scripts/tune-822.py --report                # full picture, healthy + degraded

Sweeps a single TUNING constant and reports the calibration measures, so the
remaining gaps get closed by measurement rather than guesswork.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "simulator"))

import model822 as m  # noqa: E402

SETTLE_STEPS = 150

TARGETS = {
    "sat_f": (62.0, 68.0, "MAU supply air mid-60s"),
    "bldg_dt_f": (10.0, 12.0, "building CHW delta-T 10-12"),
    "ewt_f": (43.9, 44.1, "entering CHW at 44"),
    "valve_pct": (40.0, 90.0, "valve modulating, not pegged"),
    "hall_rh_pct": (58.0, 65.0, "corridor RH low-60s"),
}


def settle(steps: int = SETTLE_STEPS, **kw) -> dict[str, float]:
    state = m.cold_start_state()
    pts: dict[str, float] = {}
    for i in range(steps):
        state, pts = m.step_822(state, i, **kw)
    return pts


def measures(pts: dict[str, float]) -> dict[str, float]:
    maus = [k for k in pts if k.endswith("_SAT") and k.startswith("MAU")]
    halls = [k for k in pts if k.startswith("HALL_") and k.endswith("_RH")]
    valves = [k for k in pts if k.startswith("MAU") and k.endswith("_CHW_VLV_CMD")]
    return {
        "sat_f": sum(pts[k] for k in maus) / len(maus),
        "bldg_dt_f": pts["CHW822_BLDG_DT"],
        "ewt_f": pts["CHW822_ENT_SUP_TEMP"],
        "valve_pct": sum(pts[k] for k in valves) / len(valves),
        "hall_rh_pct": sum(pts[k] for k in halls) / len(halls),
    }


def check() -> int:
    got = measures(settle())
    failed = 0
    for key, (lo, hi, label) in TARGETS.items():
        value = got[key]
        ok = lo <= value <= hi
        failed += 0 if ok else 1
        print(f"  [{'PASS' if ok else 'FAIL'}] {label:34s} {value:7.2f}  (want {lo}-{hi})")

    degraded = measures(settle(knobs={"CHW-822": {"strainer_resistance": 0.85}}))
    dt = degraded["bldg_dt_f"]
    ok = 2.0 <= dt <= 5.0
    failed += 0 if ok else 1
    print(f"  [{'PASS' if ok else 'FAIL'}] {'degraded dT collapses to 2-5':34s} {dt:7.2f}")

    print("CALIBRATION PASS" if not failed else f"CALIBRATION FAIL ({failed} measures)")
    return 0 if not failed else 1


def sweep(name: str, values: list[float]) -> int:
    if name not in m.TUNING:
        raise SystemExit(f"Unknown tuning constant {name!r}. Options: {sorted(m.TUNING)}")
    original = m.TUNING[name]
    print(f"{name} sweep (original {original}):")
    print(f"  {'value':>10} {'SAT':>7} {'dT':>7} {'EWT':>7} {'valve':>7} {'hallRH':>7}")
    for v in values:
        m.TUNING[name] = v
        g = measures(settle())
        print(f"  {v:>10.3f} {g['sat_f']:7.2f} {g['bldg_dt_f']:7.2f} {g['ewt_f']:7.2f} "
              f"{g['valve_pct']:7.2f} {g['hall_rh_pct']:7.2f}")
    m.TUNING[name] = original
    return 0


def report() -> int:
    cases = [
        ("healthy design_summer", {}),
        ("healthy shoulder", {"profile": "shoulder"}),
        ("coil_fouling .60", {"knobs": {"MAU01": {"coil_fouling": 0.60}}}),
        ("air_bound", {"knobs": {"MAU01": {"air_bound": True}}}),
        ("strainer .85", {"knobs": {"CHW-822": {"strainer_resistance": 0.85}}}),
        ("cond_fouling .50", {"knobs": {"CHILLER-RTAC-822": {"condenser_fouling": 0.50}}}),
    ]
    print(f"  {'case':26s} {'SAT':>7} {'dT':>7} {'EWT':>7} {'valve':>7} {'hallRH':>7}")
    for label, kw in cases:
        g = measures(settle(**kw))
        print(f"  {label:26s} {g['sat_f']:7.2f} {g['bldg_dt_f']:7.2f} {g['ewt_f']:7.2f} "
              f"{g['valve_pct']:7.2f} {g['hall_rh_pct']:7.2f}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="Building 822 calibration harness")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--sweep", nargs="+", metavar=("NAME", "VALUE"))
    args = ap.parse_args(argv[1:])
    if args.sweep:
        return sweep(args.sweep[0], [float(v) for v in args.sweep[1:]])
    if args.report:
        return report()
    return check()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

- [ ] **Step 2: Establish the starting position**

Run: `python3 scripts/tune-822.py --check`
Expected: the four passing measures pass, corridor RH fails high, degraded ΔT fails high. Record the exact numbers — that is the calibration starting point.

- [ ] **Step 3: Close the corridor humidity gap**

Corridor moisture has three inputs: MAU supply air, infiltration, and transfer air from the rooms. Sweep them in this order, because that is roughly their leverage:

```bash
python3 scripts/tune-822.py --sweep HALL_INFIL_CFM 0 5 10 15 25
python3 scripts/tune-822.py --sweep ROOM_LATENT_BTUH 150 300 450 600
python3 scripts/tune-822.py --sweep COIL_BASE_BF 0.04 0.06 0.08 0.10
python3 scripts/tune-822.py --sweep FCU_COIL_MAX_BTUH 9000 12000 15000
python3 scripts/tune-822.py --sweep HALL_SUPPLY_FRACTION 0.20 0.30 0.40 0.50
```

Pick values that bring corridor RH into 58-65 **without** pushing SAT out of 62-68 or ΔT out of 10-12. If no single constant does it, combine two — but change one at a time and re-run `--check` after each, so you always know which change did what.

A lower `COIL_BASE_BF` means a tighter coil that dehumidifies harder, and `FCU_COIL_MAX_BTUH` controls how much latent the room units can actually remove — these are the two most physically meaningful levers. Prefer them over shrinking infiltration to an unrealistic value.

- [ ] **Step 4: Close the degraded delta-T gap**

A building-wide restriction should collapse ΔT to 2-5 °F. At `strainer_resistance: 0.85` it currently lands around 6.6.

```bash
python3 scripts/tune-822.py --sweep CHW_GPM_DESIGN 60 70 80 90
python3 scripts/tune-822.py --sweep COIL_APPROACH_PENALTY 35 45 55 65
```

The chiller curve is sweepable too, and is the direct lever on the degraded
entering-water target:

```bash
python3 scripts/tune-822.py --sweep CHILLER_OVERLOAD_SLOPE 40 60 80 100
python3 scripts/tune-822.py --sweep CHILLER_DERATE_PER_F 0.006 0.010 0.014
```

`COIL_APPROACH_PENALTY` is the honest lever: it controls how fast coil capacity dies as flow is lost. Raising it makes a restricted building lose capacity faster than it loses flow, which is what collapses ΔT in the field. Do not fix this by shrinking `CHW_GPM_DESIGN` alone — that would break the healthy ΔT of 11.

- [ ] **Step 5: Write the calibrated values into TUNING and re-verify everything**

Update the `TUNING` dict in `simulator/model822.py` with the values you chose. Change values only — never the physics.

```bash
python3 simulator/psychro.py --self-test
python3 simulator/model822.py --self-test
python3 scripts/tune-822.py --check
python3 scripts/tune-822.py --report
python3 simulator/bas_sim.py --scenario normal --steps 12 --seed 7
python3 - <<'PY'
import csv
rows = list(csv.DictReader(open('data/output/trends.csv')))
base = list(csv.DictReader(open('data/output/.regression-baseline/normal-trends.csv')))
bp = {r['point'] for r in base}
assert [r for r in rows if r['point'] in bp] == base, "REGRESSION"
print("REGRESSION STILL CLEAN")
PY
```

Expected: `CALIBRATION PASS`, both self-tests pass, regression still clean.

- [ ] **Step 6: Checkpoint**

Do not commit. Report the before and after `--check` output, which constants you changed and to what, and the `--report` table. If a target could not be met without distorting another, say so plainly rather than loosening `TARGETS` — the numbers come from J's field observations and moving the goalposts defeats the purpose.

---

### Task 11: Topology and chiller endpoints

Two endpoints. The topology one matters more than it looks: it is where visibility becomes a server-side fact rather than a client-side illusion.

**Files:**
- Modify: `frontend/bas_api.py`

**Interfaces:**
- Consumes: `data/input/equipment.json` (networks, parent), `data/output/state_822.json`
- Produces: `GET /api/topology?from=<node>`, `GET /api/chiller/822`, `GET /tracer`

- [ ] **Step 1: Add the topology endpoint**

Append to `frontend/bas_api.py`, beside the existing `/api/equipment` route:

```python
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
```

No new imports are needed: `bas_api.py:15-16` already imports `FastAPI`, `HTTPException`, `Query` and `HTMLResponse`, `json` is imported at line 6, and `INPUT_DIR` / `OUTPUT_DIR` / `STATIC_DIR` are defined at lines 21-23. The equipment loader already exists as `_load_input_equipment()` at line 54 — use it; do not add a second one.

- [ ] **Step 2: Add the chiller endpoint**

```python
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
```

- [ ] **Step 3: Add the /tracer route**

Beside the existing `/metasys` and `/niagara` routes:

```python
@app.get("/tracer", response_class=HTMLResponse)
def tracer_page() -> HTMLResponse:
    page = STATIC_DIR / "tracer.html"
    return HTMLResponse(content=page.read_text(encoding="utf-8"))
```

This mirrors `niagara_redirect()` at `bas_api.py:201-204` exactly, including the `content=` keyword.

- [ ] **Step 4: Verify the endpoints**

```bash
python3 simulator/bas_sim.py --scenario normal --steps 60
scripts/start-frontend.sh &
sleep 3
echo "--- topology from SC-822-01 ---"
curl -s 'http://127.0.0.1:8001/api/topology?from=SC-822-01' | python3 -m json.tool | head -25
echo "--- trunk counts ---"
curl -s 'http://127.0.0.1:8001/api/topology?from=SC-822-01' | python3 -c "
import json,sys
d=json.load(sys.stdin)
for t in d['trunks']: print(' ', t['id'], t['online_count'], 'of', t['member_count'])
"
echo "--- unknown node ---"
curl -s -o /dev/null -w '%{http_code}\n' 'http://127.0.0.1:8001/api/topology?from=NOPE'
echo "--- chiller ---"
curl -s http://127.0.0.1:8001/api/chiller/822 | python3 -m json.tool | head -20
```

Expected: SC-822-01 shows `MSTP-01-A 7 of 7` and `MSTP-01-B 24 of 24`; SC-822-02 shows the same 7 and 24; an unknown node returns `404`; the chiller returns leaving water 44.0 with `active_diagnostic: None` and `integration` stating there is none.

Critically: `MSTP-02-A` must **not** appear in the SC-822-01 response. If it does, visibility is not being filtered and spec 2's blind-trunk fault will not work.

- [ ] **Step 5: Checkpoint**

Stop the server. Do not commit. Report all four curl outputs. Wait for review.

---

### Task 12: Tracer front end and wire-up

Connect, log in, navigate, read the diagnostic row. One static file, no build tools, no CDN.

**Files:**
- Create: `frontend/static/tracer.html`
- Modify: `frontend/static/index.html`, `scripts/run-smoke-test.sh`
- Create: `sequences/MAU-822-SOO.md`, `sequences/FCU-822-SOO.md`

**Interfaces:**
- Consumes: `/api/topology`, `/api/chiller/822`, `/api/points`, `/api/trends/{point}`, `/api/alarms`, `/api/roles`, `/api/points/{point}/command`, `/api/points/{point}/release`
- Produces: the `/tracer` page

- [ ] **Step 1: Create tracer.html**

Create `frontend/static/tracer.html`. Read `frontend/static/niagara.html` first and match its CSS conventions, fetch helpers and tab mechanics — this must look like it belongs in the same codebase, not like a different author dropped a file in.

```html
<!-- Building 822 — Tracer SC-style operator view. Synthetic lab. -->
<title>Building 822 — Tracer SC</title>
<style>
  :root { --bg:#1b1f24; --panel:#242a31; --line:#39414a; --text:#dfe4ea;
          --dim:#9aa5b1; --ok:#5ac18e; --warn:#e0a458; --bad:#d9534f; --accent:#4a90d9; }
  * { box-sizing:border-box; }
  body { margin:0; background:var(--bg); color:var(--text);
         font:14px/1.45 -apple-system,Segoe UI,Roboto,sans-serif; }
  header { background:var(--panel); border-bottom:1px solid var(--line);
           padding:10px 16px; display:flex; align-items:center; gap:16px; }
  header h1 { font-size:15px; margin:0; font-weight:600; }
  .muted { color:var(--dim); font-size:12px; }
  #connect { max-width:520px; margin:60px auto; background:var(--panel);
             border:1px solid var(--line); border-radius:6px; padding:24px; }
  #connect h2 { margin:0 0 4px; font-size:16px; }
  label { display:block; margin:14px 0 4px; font-size:12px; color:var(--dim); }
  select,input,button { font:inherit; padding:7px 9px; background:#1b1f24;
                        color:var(--text); border:1px solid var(--line); border-radius:4px; }
  select,input { width:100%; }
  button { cursor:pointer; background:var(--accent); border-color:var(--accent); color:#fff; }
  button.secondary { background:transparent; color:var(--text); border-color:var(--line); }
  #workspace { display:none; grid-template-columns:280px 1fr; height:calc(100vh - 45px); }
  #tree { border-right:1px solid var(--line); overflow:auto; padding:10px; }
  .node { padding:3px 6px; cursor:pointer; border-radius:3px; white-space:nowrap; }
  .node:hover { background:#2c333b; }
  .node.sel { background:var(--accent); color:#fff; }
  .lvl1 { padding-left:16px; } .lvl2 { padding-left:32px; }
  .dot { display:inline-block; width:8px; height:8px; border-radius:50%;
         background:var(--ok); margin-right:6px; }
  .dot.off { background:var(--bad); }
  main { overflow:auto; padding:16px; }
  .tabs { display:flex; gap:4px; border-bottom:1px solid var(--line); margin-bottom:14px; }
  .tab { padding:7px 14px; cursor:pointer; border-bottom:2px solid transparent; color:var(--dim); }
  .tab.on { color:var(--text); border-bottom-color:var(--accent); }
  .diag { display:grid; grid-template-columns:repeat(auto-fit,minmax(110px,1fr));
          gap:1px; background:var(--line); border:1px solid var(--line);
          border-radius:5px; overflow:hidden; margin-bottom:16px; }
  .cell { background:var(--panel); padding:10px 12px; }
  .cell .k { font-size:11px; color:var(--dim); text-transform:uppercase;
             letter-spacing:.4px; margin-bottom:3px; }
  .cell .v { font-size:19px; font-variant-numeric:tabular-nums; }
  .cell.key { background:#2a323b; }
  table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
  th,td { text-align:left; padding:6px 10px; border-bottom:1px solid var(--line); }
  th { color:var(--dim); font-weight:500; font-size:12px; }
  .wrap { overflow-x:auto; }
  .err { color:var(--bad); } .note { color:var(--warn); }
</style>

<header>
  <h1>Building 822 <span class="muted">Tracer SC</span></h1>
  <span class="muted" id="connInfo"></span>
  <span style="flex:1"></span>
  <button class="secondary" id="disconnect" style="display:none">Disconnect</button>
</header>

<section id="connect">
  <h2>Connect to Building 822</h2>
  <p class="muted">Select where you are plugging in. What you can see depends on it.</p>
  <label for="node">Connection point</label>
  <select id="node">
    <option value="SC-822-01">Tracer SC-822-01 — Ethernet (Wings A/B)</option>
    <option value="SC-822-02">Tracer SC-822-02 — Ethernet (Wings C/D + Lobby)</option>
    <option value="CHILLER-PANEL">RTAC local panel — walk-up</option>
  </select>
  <label for="role">Sign in as</label>
  <select id="role"></select>
  <label for="op">Operator ID</label>
  <input id="op" value="tech-01" />
  <p style="margin-top:18px"><button id="go">Connect</button></p>
  <p class="muted" id="connErr"></p>
</section>

<div id="workspace">
  <nav id="tree"></nav>
  <main>
    <div class="tabs">
      <div class="tab on" data-tab="summary">Summary</div>
      <div class="tab" data-tab="points">Points</div>
      <div class="tab" data-tab="trends">Trends</div>
      <div class="tab" data-tab="alarms">Alarms</div>
    </div>
    <div id="body"></div>
  </main>
</div>

<script>
const S = { node:null, role:null, op:null, sel:null, tab:'summary', points:{}, topo:null };
const $ = id => document.getElementById(id);
const j = async u => { const r = await fetch(u); if(!r.ok) throw new Error(r.status+' '+u); return r.json(); };
const esc = s => String(s).replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));

async function init(){
  try {
    const roles = await j('/api/roles');
    const list = roles.roles || roles;
    $('role').innerHTML = list.map(r => {
      const v = typeof r === 'string' ? r : r.role || r.name;
      return `<option value="${esc(v)}">${esc(v)}</option>`;
    }).join('');
  } catch(e){ $('role').innerHTML = '<option value="technician">technician</option>'; }
}

$('go').onclick = async () => {
  S.node = $('node').value; S.role = $('role').value; S.op = $('op').value.trim();
  $('connErr').textContent = '';
  try { S.topo = await j('/api/topology?from=' + encodeURIComponent(S.node)); }
  catch(e){ $('connErr').textContent = 'Cannot reach ' + S.node + ' (' + e.message + ')'; return; }
  $('connect').style.display='none';
  $('workspace').style.display='grid';
  $('disconnect').style.display='inline-block';
  $('connInfo').textContent = `connected at ${S.node} · ${S.role} · ${S.op}`;
  if (S.node === 'CHILLER-PANEL'){ S.sel = {kind:'chiller'}; renderTree(); return render(); }
  await refreshPoints(); renderTree(); render();
};

$('disconnect').onclick = () => location.reload();

async function refreshPoints(){
  const data = await j('/api/points');
  S.points = {};
  const rows = data.points || data;
  (Array.isArray(rows) ? rows : Object.values(rows).flat()).forEach(p => {
    const name = p.point || p.name; if(name) S.points[name] = p;
  });
}

function renderTree(){
  const t = $('tree');
  if (S.node === 'CHILLER-PANEL'){
    t.innerHTML = `<div class="node sel"><span class="dot"></span>RTAC local panel</div>
      <div class="muted lvl1" style="margin-top:8px">No BACnet integration.<br>Walk-up display only.</div>`;
    return;
  }
  let h = `<div class="node" data-kind="sc"><span class="dot"></span>${esc(S.topo.supervisory.id)}</div>`;
  S.topo.trunks.forEach(tr => {
    const allUp = tr.online_count === tr.member_count;
    h += `<div class="node lvl1" data-kind="trunk" data-id="${esc(tr.id)}">
            <span class="dot${allUp?'':' off'}"></span>${esc(tr.id)}
            <span class="muted">${tr.online_count} of ${tr.member_count}</span></div>`;
    tr.members.forEach(mem => {
      h += `<div class="node lvl2" data-kind="device" data-id="${esc(mem.id)}">
              <span class="dot${mem.online?'':' off'}"></span>${esc(mem.id)}</div>`;
    });
  });
  t.innerHTML = h;
  t.querySelectorAll('.node[data-kind="device"]').forEach(n => {
    n.onclick = () => {
      t.querySelectorAll('.node').forEach(x => x.classList.remove('sel'));
      n.classList.add('sel');
      S.sel = { kind:'device', id:n.dataset.id };
      render();
    };
  });
}

document.querySelectorAll('.tab').forEach(tab => {
  tab.onclick = () => {
    document.querySelectorAll('.tab').forEach(x => x.classList.remove('on'));
    tab.classList.add('on'); S.tab = tab.dataset.tab; render();
  };
});

function pointsFor(equipId){
  return Object.entries(S.points)
    .filter(([, p]) => (p.equipment || '') === equipId)
    .map(([n, p]) => ({ name:n, ...p }));
}

function cell(k, v, key){
  return `<div class="cell${key?' key':''}"><div class="k">${esc(k)}</div><div class="v">${esc(v)}</div></div>`;
}

function val(name){ const p = S.points[name]; return p == null ? '—' : (p.value ?? p.current ?? '—'); }

async function render(){
  const b = $('body');
  if (!S.sel){ b.innerHTML = '<p class="muted">Select a controller in the tree.</p>'; return; }

  if (S.sel.kind === 'chiller'){
    try {
      const c = await j('/api/chiller/822');
      b.innerHTML = `<div class="diag">
        ${cell('Evap entering', c.evap_entering_f + ' °F')}
        ${cell('Evap leaving', c.evap_leaving_f + ' °F', true)}
        ${cell('Leaving SP', c.evap_leaving_setpoint_f + ' °F')}
        ${cell('Ambient', c.ambient_f + ' °F')}
        ${cell('Capacity', c.pct_capacity + ' %', true)}
        ${cell('Diagnostic', c.active_diagnostic)}</div>
        <p class="muted">${esc(c.model_family)} · serial ${esc(c.serial)} · ${esc(c.reference)}</p>
        <p class="note">${esc(c.integration)}</p>
        <div class="wrap"><table><tr><th>Circuit</th><th>Running</th><th>Condenser fan</th></tr>
        ${c.circuits.map(ct => `<tr><td>${ct.id}</td><td>${ct.running?'Yes':'No'}</td>
          <td>${ct.condenser_fan_ok?'OK':'FAIL'}</td></tr>`).join('')}</table></div>`;
    } catch(e){ b.innerHTML = `<p class="err">Chiller panel unavailable: ${esc(e.message)}</p>`; }
    return;
  }

  const id = S.sel.id;
  const mine = pointsFor(id);

  if (S.tab === 'summary'){
    const m = id.match(/UC400-MAU-(\d+)/);
    if (m){
      const t = 'MAU' + m[1];
      b.innerHTML = `<h3>${esc(id)} — makeup air</h3><div class="diag">
        ${cell('Entering air', val(t+'_EAT') + ' °F')}
        ${cell('Entering RH', val(t+'_EA_RH') + ' %')}
        ${cell('OA damper', val(t+'_OA_DMPR_POS') + ' %')}
        ${cell('CHW valve', val(t+'_CHW_VLV_POS') + ' %', true)}
        ${cell('Supply air', val(t+'_SAT') + ' °F', true)}
        ${cell('Supply SP', val(t+'_SAT_SP') + ' °F')}
        ${cell('Coil ΔT', val(t+'_COIL_DT') + ' °F', true)}
        ${cell('Supply RH', val(t+'_SA_RH') + ' %')}</div>
        <p class="muted">Valve modulating with supply air at setpoint is healthy.
        Valve pegged with supply air above setpoint means the coil is not doing
        what it is being told to do — check water before you check controls.</p>`;
      return;
    }
    b.innerHTML = `<h3>${esc(id)}</h3>` + renderTable(mine);
    return;
  }

  if (S.tab === 'points'){ b.innerHTML = renderTable(mine); return; }

  if (S.tab === 'trends'){
    if (!mine.length){ b.innerHTML = '<p class="muted">No points.</p>'; return; }
    const first = mine[0].name;
    try {
      const tr = await j('/api/trends/' + encodeURIComponent(first));
      const rows = tr.rows || tr;
      b.innerHTML = `<p class="muted">${esc(first)} — most recent first</p><div class="wrap"><table>
        <tr><th>Timestamp</th><th>Value</th></tr>
        ${rows.slice(-40).reverse().map(r =>
          `<tr><td>${esc(r.timestamp)}</td><td>${esc(r.value)}</td></tr>`).join('')}</table></div>`;
    } catch(e){ b.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
    return;
  }

  if (S.tab === 'alarms'){
    try {
      const a = await j('/api/alarms');
      const rows = (a.alarms || a).filter(x => (x.point||'').match(/^(MAU|FCU_|HALL_|CHW822|RTAC822|SC822|MSTP)/));
      b.innerHTML = rows.length ? `<div class="wrap"><table>
        <tr><th>Timestamp</th><th>Point</th><th>Priority</th><th>Message</th></tr>
        ${rows.map(r => `<tr><td>${esc(r.timestamp)}</td><td>${esc(r.point)}</td>
          <td>${esc(r.priority)}</td><td>${esc(r.message)}</td></tr>`).join('')}</table></div>`
        : '<p class="muted">No active alarms in Building 822.</p>';
    } catch(e){ b.innerHTML = `<p class="err">${esc(e.message)}</p>`; }
  }
}

function renderTable(rows){
  if (!rows.length) return '<p class="muted">No points for this device.</p>';
  return `<div class="wrap"><table><tr><th>Point</th><th>Value</th><th>Units</th><th>Writable</th></tr>
    ${rows.map(p => `<tr><td>${esc(p.name)}</td><td>${esc(p.value ?? p.current ?? '—')}</td>
      <td>${esc(p.units ?? '')}</td><td>${p.writable ? 'yes' : ''}</td></tr>`).join('')}</table></div>`;
}

init();
</script>
```

The field values this page reads (`p.value`, `p.units`, `tr.rows`, `a.alarms`) are guesses at the existing API shapes. **Check `bas_api.py` and fix them to match** — do not leave the `??` fallbacks doing the work.

- [ ] **Step 1b: Add the command panel and the service-entrance view**

Spec §6.2 requires role-gated commanding with visible 403s, and §6.4 requires a
CHW service-entrance view. Neither is in the markup above — add both now.

The command endpoint takes **query parameters**, not a JSON body
(`bas_api.py:484`): `value`, `role`, `operator_id`, `reason`. Commanding is what
makes the building answer, so this is not optional polish.

Add these two functions before `function renderTable(rows)`:

```javascript
function commandPanel(rows){
  const writable = rows.filter(p => p.writable);
  if (!writable.length) return '';
  return `<h4 style="margin:18px 0 6px">Command</h4>
    <div style="display:flex; gap:8px; align-items:flex-end; flex-wrap:wrap; max-width:640px">
      <div style="flex:2 1 220px">
        <label for="cmdPt">Point</label>
        <select id="cmdPt">${writable.map(p =>
          `<option value="${esc(p.name)}">${esc(p.name)}</option>`).join('')}</select>
      </div>
      <div style="flex:1 1 100px">
        <label for="cmdVal">Value</label>
        <input id="cmdVal" type="number" step="any" />
      </div>
      <button id="cmdGo">Command</button>
      <button class="secondary" id="cmdRel">Release</button>
    </div>
    <p id="cmdMsg" class="muted" style="margin-top:8px"></p>`;
}

function wireCommandPanel(){
  const go = $('cmdGo'), rel = $('cmdRel');
  if (!go) return;
  const send = async (verb) => {
    const pt = $('cmdPt').value;
    const msg = $('cmdMsg');
    const qs = new URLSearchParams({ role:S.role, operator_id:S.op, reason:'tracer panel' });
    if (verb === 'command'){
      const v = $('cmdVal').value;
      if (v === ''){ msg.className='err'; msg.textContent='Enter a value.'; return; }
      qs.set('value', v);
    }
    msg.className='muted'; msg.textContent = verb + 'ing ' + pt + '...';
    try {
      const r = await fetch(`/api/points/${encodeURIComponent(pt)}/${verb}?` + qs, { method:'POST' });
      const body = await r.json().catch(() => ({}));
      if (r.status === 403){
        msg.className='err';
        msg.textContent = `403 Forbidden — role "${S.role}" may not command. ` +
                          `Reconnect as technician or admin. (${body.detail || ''})`;
        return;
      }
      if (!r.ok){ msg.className='err'; msg.textContent = r.status + ' — ' + (body.detail || 'rejected'); return; }
      msg.className='note';
      msg.textContent = `${pt} ${body.status || verb + 'd'}. Re-run the simulator to see the building respond.`;
      await refreshPoints(); render();
    } catch(e){ msg.className='err'; msg.textContent = e.message; }
  };
  go.onclick = () => send('command');
  rel.onclick = () => send('release');
}
```

Then wire them into `render()`. In the MAU summary branch, change the final
`return;` so the panel is appended and wired:

```javascript
      b.innerHTML = `<h3>${esc(id)} — makeup air</h3><div class="diag">
        ... existing cells ...
        </div>
        <p class="muted">Valve modulating with supply air at setpoint is healthy.
        Valve pegged with supply air above setpoint means the coil is not doing
        what it is being told to do — check water before you check controls.</p>`
        + commandPanel(mine);
      wireCommandPanel();
      return;
```

Add the CHW service-entrance branch immediately before the generic
`b.innerHTML = \`<h3>${esc(id)}</h3>\` + renderTable(mine);` line:

```javascript
    if (id === 'CHW-822'){
      b.innerHTML = `<h3>CHW service entrance</h3><div class="diag">
        ${cell('Entering water', val('CHW822_ENT_SUP_TEMP') + ' °F', true)}
        ${cell('Return water', val('CHW822_ENT_RET_TEMP') + ' °F')}
        ${cell('Building ΔT', val('CHW822_BLDG_DT') + ' °F', true)}
        ${cell('Building DP', val('CHW822_BLDG_DP') + ' psid')}
        ${cell('Strainer DP', val('CHW822_STRAINER_DP') + ' psid', true)}
        ${cell('Pump P-1', val('CHW822_P1_STATUS') == 1 ? 'Running' : 'Off')}
        ${cell('Pump P-2', val('CHW822_P2_STATUS') == 1 ? 'Running' : 'Off')}</div>
        <p class="muted">Entering water well above 44 °F is not a building problem —
        the chiller is off-tree. Walk up to it. A collapsed ΔT with normal entering
        water is a flow problem: strainer, pumps, or a three-way valve.</p>`
        + commandPanel(mine);
      wireCommandPanel();
      return;
    }
```

Also append `+ commandPanel(mine); wireCommandPanel();` to the `points` tab
branch so FCU valves and fan modes are commandable there too.

- [ ] **Step 1c: Verify commanding through the UI**

```bash
python3 simulator/bas_sim.py --scenario normal --steps 60
scripts/start-frontend.sh &
sleep 3
echo "--- command as technician (expect 200) ---"
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  'http://127.0.0.1:8001/api/points/MAU01_CHW_VLV_CMD/command?value=0&role=technician&operator_id=tech-01&reason=plan+check'
echo "--- command as viewer (expect 403) ---"
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  'http://127.0.0.1:8001/api/points/MAU01_CHW_VLV_CMD/command?value=0&role=viewer&operator_id=tech-01'
echo "--- command a read-only point (expect 400) ---"
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  'http://127.0.0.1:8001/api/points/MAU01_SAT/command?value=50&role=technician'
echo "--- release (expect 200) ---"
curl -s -o /dev/null -w '%{http_code}\n' -X POST \
  'http://127.0.0.1:8001/api/points/MAU01_CHW_VLV_CMD/release?role=technician&operator_id=tech-01'
```

Expected: `200`, `403`, `400`, `200`. Then in the browser, command
`MAU01_CHW_VLV_CMD` to 0, re-run the simulator, and confirm `MAU01_SAT` climbs
above 80 °F on the diagnostic row — the building answering a command is the
entire point of this build.

- [ ] **Step 2: Add the landing page card**

In `frontend/static/index.html`, copy the existing Metasys/Niagara card markup exactly and add a third:

```html
<a class="card" href="/tracer">
  <h2>Tracer SC</h2>
  <p>Building 822 — synthetic barracks. Connect at an SC, or walk up to the chiller.</p>
</a>
```

Match the surrounding class names and structure; do not introduce new CSS.

- [ ] **Step 3: Extend the smoke test**

In `scripts/run-smoke-test.sh`, before the final `echo`:

```bash
python3 simulator/psychro.py --self-test
python3 simulator/model822.py --self-test
python3 scripts/gen-822-inventory.py --self-test
python3 simulator/bas_sim.py --scenario normal --steps 60
test -s data/output/state_822.json
python3 -c "
import json
s = json.load(open('data/output/latest_points.json'))
s = s['points']          # latest_points.json nests points under 'points'
for p in ('MAU01_SAT','CHW822_BLDG_DT','HALL_A1_RH','RTAC822_EVAP_LVG_TEMP'):
    assert p in s, 'missing 822 point: ' + p
print('822 points present')
"
```

- [ ] **Step 4: Write the sequences of operation**

Create `sequences/MAU-822-SOO.md` and `sequences/FCU-822-SOO.md`. Read an existing file such as `sequences/RTU-1-SOO.md` and match its structure exactly. Content must describe what the model actually does — the MAU one covers the CHW valve modulating to hold supply air setpoint, the OA damper position and its effect on latent load, fan operation, and the fact that a pegged valve with supply air above setpoint indicates a capacity problem rather than a control problem. The FCU one covers space temperature control, the Off/Auto/Low/Mid/High fan modes and the flow fractions in `FAN_MODE_FLOW`.

These are synthetic training documents, not real design sequences, and must say so in the same way the existing SOO files do.

- [ ] **Step 5: Full end-to-end verification**

```bash
scripts/run-smoke-test.sh
scripts/start-frontend.sh &
sleep 3
for u in / /tracer /metasys /niagara '/api/topology?from=SC-822-01' /api/chiller/822; do
  printf '%-38s %s\n' "$u" "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8001$u")"
done
```

Expected: every URL returns `200`. Then open `http://127.0.0.1:8001/tracer` in a browser and confirm by eye:
- the connect screen appears first, before any data
- connecting at SC-822-01 shows `MSTP-01-A 7 of 7` and `MSTP-01-B 24 of 24`, and **no** `MSTP-02-*`
- clicking `UC400-MAU-01` shows the diagnostic row with supply air near 65 °F and the valve modulating
- the chiller panel connection shows the RTAC display and states there is no integration
- Metasys and Niagara still work and still show only their own buildings

- [ ] **Step 6: Checkpoint**

Stop the server. Do not commit. Report the smoke test output, the HTTP status table, and what you saw on each screen. Wait for J's review — this is the last task, so this checkpoint is the handoff for the whole plan.
