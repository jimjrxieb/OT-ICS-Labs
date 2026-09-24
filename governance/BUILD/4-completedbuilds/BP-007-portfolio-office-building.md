# BUILD Plan BP-007 — Portfolio Expansion: Office Building + Niagara Portfolio Navigation

**Status:** COMPLETE
**Approved by:** J — 2026-07-06. Both judgment calls confirmed: (1) the
  `equipment.json` facility-schema restructuring, and (2) portfolio
  navigation in the Niagara UI with Metasys staying hospital-only.
  Verified 2026-07-06: py_compile and run-smoke-test.sh rerun
  independently; facility tags confirmed on all 17 equipment entries and
  all 24 points via fresh server; all 10 office points generated in-range
  with zero `bas_sim.py` changes (plan assumption held); Niagara portfolio
  tree markers confirmed on the live page; Metasys source and live page
  confirmed free of office references; `fault_library.json` untouched
  (9 hospital faults); git HEAD unchanged, nothing staged.
**Approval scope:** Local synthetic lab only — additive changes to
  `data/input/equipment.json`, `data/input/points.json`,
  `data/input/alarm_rules.json`, `frontend/bas_api.py`,
  `frontend/static/niagara.html`, new `sequences/` docs
**Source finding:** Operator's stated goal (2026-07-01 conversation): "we
  have multiple buildings we are in charge of... let's build a badass BAS
  and navigate it as a badass DDC HVAC controls tech." Sub-project 2 of the
  portfolio-expansion brainstorm (sub-project 1, trouble-call engine, shipped
  as BP-006). This is the foundation slice — office equipment/points/
  sequences plus portfolio navigation; office-specific fault library
  entries are a follow-up BP-008, matching how the hospital's own fault
  library (BP-006) came after its foundation (BUILD-001).
**Target:** `data/input/equipment.json`, `data/input/points.json`,
  `data/input/alarm_rules.json`, `frontend/bas_api.py`,
  `frontend/static/niagara.html`, `sequences/RTU-1-SOO.md` (new),
  `sequences/VAV-301-SOO.md` (new)
**Owner:** ot-build-agent (codex worker)

---

## Judgment Calls Made While J Was Away — Confirm On Review

1. **Facility schema.** `equipment.json`'s single `"facility"` object
   becomes a `"facilities"` list (hospital + office), with every
   equipment/supervisory/front-end entry tagged `"facility": "hospital"`,
   `"office"`, or `"portfolio"` (for shared infrastructure like the
   Niagara Supervisor). Verified before drafting: nothing in
   `bas_api.py` or `bas_sim.py` reads the old singular `"facility"` key
   programmatically — it was decorative. The HTML pages hardcode facility
   names in their own markup, not from this file. This restructuring is
   safe but is a schema change worth a look.
2. **Portfolio navigation lives in Niagara, not a new front-end.** The
   office building is added as a second JACE (`JACE-OFFICE-01`) under the
   existing Niagara Supervisor (`N4-SUP-01`), alongside the hospital's
   existing `JACE-OT-01`. The Niagara Station tree becomes portfolio-wide.
   The Metasys UI stays hospital-only — unchanged. Rationale: this mirrors
   how real multi-building portfolios are actually navigated (one Niagara
   Supervisor federating JACEs across sites, while a hospital's Metasys
   system stays vendor-locked to that one building). No new front-end
   equipment or new UI page needed.

If either call is wrong, say so before this goes to the worker — the
facility-tag rename touches every entry in `equipment.json` and would be
annoying to unwind after implementation.

---

## Why This Build Exists

BP-006 proved the trouble-call training loop against a single hospital.
The stated goal is broader: the operator is responsible for multiple real
buildings and wants to navigate a portfolio like a working DDC tech would
— which in the real world usually means one supervisory front-end (Niagara)
managing several sites, each with its own equipment mix and its own
"personality" of faults. A hospital's faults are life-safety-driven
(pressure, humidity, sterile fields). An office building's faults are
comfort/energy-driven (economizer stuck, reheat stuck open, chiller/boiler
issues) — teaching the contrast is the point, not just adding more content.

---

## Approved Context

Worker may use:

- `data/input/equipment.json`, `points.json`, `alarm_rules.json` — existing
  hospital patterns as the template for the office building's entries
- `sequences/AHU-OR-1-SOO.md` — existing SOO doc as the format template
  (worker should also read the two new SOO docs already drafted at
  `sequences/RTU-1-SOO.md` and `sequences/VAV-301-SOO.md` — write these
  files only if they don't already exist; they were pre-written as part of
  this plan's drafting and should not be overwritten)
- `frontend/bas_api.py`, `frontend/static/niagara.html` — existing
  FastAPI/Station-tree patterns

Worker must not use:

- Real credentials, real facility data, external network access
- git operations (no stage, commit, push, or branch)
- `frontend/static/metasys.html` — explicitly unchanged, stays hospital-only
- `simulator/bas_sim.py` — confirmed not required for this slice; point
  generation is already generic over `points.json` (see Judgment Calls).
  If the worker finds a reason `bas_sim.py` must change, stop and report
  it rather than proceeding — that would mean an assumption in this plan
  was wrong.
- Office-specific fault library entries in `data/input/fault_library.json`
  (BP-008, not this slice)
- Any scoring/gamification/CLI changes

---

## Proposed Change

### 1. `data/input/equipment.json` — facility restructuring + office equipment

Restructure `"facility"` (object) → `"facilities"` (list):

```json
"facilities": [
  {"id": "hospital", "name": "NAS JAX Regional Medical Center", "beds": 180,
   "critical_spaces": ["OR Suite", "ICU", "Isolation Rooms", "Pharmacy", "Imaging", "Sterile Processing", "ED Trauma"]},
  {"id": "office", "name": "Riverside Office Tower", "floors": 8,
   "critical_spaces": ["Data Closet"]}
]
```

Tag every existing hospital equipment/supervisory/front-end entry with
`"facility": "hospital"`. Add new equipment (all `"facility": "office"`,
`"purdue_level": 1`):

- `RTU-1` — type AHU (rooftop VAV w/ economizer), serves "Office Floors 3-8", vendor Johnson Controls, controller `JCI-FEC-RTU1`
- `VAV-301` — type VAV, serves "Floor 3 Open Office", vendor Johnson Controls, controller `JCI-VMA-301`
- `CHILLER-1` — type Air-Cooled Chiller, serves "Building Loop", vendor Carrier, controller `CAR-CH1`
- `BOILER-1` — type Condensing Boiler, serves "Building Loop", vendor Carrier, controller `CAR-BLR1`

Add new supervisory entry: `JACE-OFFICE-01` (Niagara JACE, vendor Tridium,
`purdue_level: 2`, `facility: "office"`). Tag the existing `JACE-OT-01`
with `facility: "hospital"` for clarity. Tag `N4-SUP-01` (existing,
front_end) with `facility: "portfolio"` — it now oversees both JACEs.
`MET-ADS-01` and `TRN-SC-01` stay `facility: "hospital"`, unchanged
otherwise.

### 2. `data/input/points.json` — office points

Add 10 points, each tagged `"facility": "office"` (add a `facility` field
to every existing hospital point too, tagged `"hospital"`, for consistency):

| Point | Equipment | Type | Units | normal_min | normal_max | writable | critical | trend_interval_sec |
|---|---|---|---|---|---|---|---|---|
| RTU1_SAT | RTU-1 | AI | F | 52 | 58 | false | false | 300 |
| RTU1_SAT_SP | RTU-1 | AV | F | 54 | 56 | true | false | 300 |
| RTU1_SUPPLY_FAN_CMD | RTU-1 | BO | bool | 0 | 1 | true | false | 300 |
| RTU1_OA_DAMPER_POS | RTU-1 | AO | % | 10 | 100 | true | false | 300 |
| RTU1_MA_TEMP | RTU-1 | AI | F | 55 | 75 | false | false | 300 |
| VAV301_TEMP | VAV-301 | AI | F | 70 | 74 | false | false | 60 |
| VAV301_TEMP_SP | VAV-301 | AV | F | 71 | 73 | true | false | 60 |
| VAV301_REHEAT_VLV_POS | VAV-301 | AO | % | 0 | 30 | true | false | 60 |
| CHILLER1_CHW_SUPPLY_TEMP | CHILLER-1 | AI | F | 42 | 46 | false | true | 300 |
| BOILER1_HW_SUPPLY_TEMP | BOILER-1 | AI | F | 140 | 150 | false | true | 300 |

### 3. `data/input/alarm_rules.json` — office alarm rules

Add:

- `CHILLER1_CHW_SUPPLY_TEMP`, outside_normal, priority `high`, "Chiller-1 chilled water supply temperature abnormal"
- `BOILER1_HW_SUPPLY_TEMP`, outside_normal, priority `high`, "Boiler-1 hot water supply temperature abnormal"
- `VAV301_TEMP`, outside_normal, priority `medium`, "VAV-301 zone temperature outside comfort range" (medium, not critical — comfort fault, not life-safety, per `VAV-301-SOO.md`)

### 4. `frontend/bas_api.py` — pass through facility field

`GET /api/points`, `GET /api/points/{name}`, and `GET /api/equipment`
already loop through `points.json`/`equipment.json` entries — add the
`facility` field to each returned entry (pure pass-through, no new
endpoints, no new logic).

### 5. `frontend/static/niagara.html` — portfolio Station tree

Restructure the Station tree rendering: top level shows `N4-SUP-01`
(Portfolio Supervisor), branching into `JACE-OT-01 (Hospital)` and
`JACE-OFFICE-01 (Office)`, each expanding to that facility's equipment
and points — grouped client-side using the new `facility` field from
`GET /api/points` / `GET /api/equipment`. Points/Alarms/Trends/Technician
Panel/Trouble Call tabs stay functionally the same, just scoped to
whichever facility's equipment is selected in the tree (or show both,
worker's call on the cleanest UX — document whichever is chosen).

---

## Files In Scope

- `data/input/equipment.json`
- `data/input/points.json`
- `data/input/alarm_rules.json`
- `frontend/bas_api.py`
- `frontend/static/niagara.html`
- `sequences/RTU-1-SOO.md` (pre-written, see Approved Context)
- `sequences/VAV-301-SOO.md` (pre-written, see Approved Context)

## Out Of Scope

- `frontend/static/metasys.html` — stays hospital-only
- `simulator/bas_sim.py` — not required (see Judgment Calls); stop and
  report if this assumption is wrong
- `data/input/fault_library.json` — office faults are BP-008
- `bas_console.py`, scoring/gamification, git operations

---

## Acceptance Checks

- `python3 -m py_compile simulator/bas_sim.py frontend/bas_api.py bas_console.py` exits 0.
- `scripts/run-smoke-test.sh` still passes (proves existing hospital scenarios are unaffected by the new points).
- `python3 simulator/bas_sim.py --scenario normal --steps 4` succeeds and produces sane baseline values for all 10 new office points (within their `normal_min`/`normal_max`) with no simulator code changes required.
- `GET /api/equipment` returns both facilities' equipment, each entry carrying a `facility` field.
- `GET /api/points` returns all points (hospital + office), each carrying a `facility` field.
- `GET /api/alarms` — trigger an office alarm condition (e.g. run normal enough times or verify rule wiring) and confirm office alarm rules fire with correct priority.
- `/niagara` in a browser (or via HTML source inspection) shows a Station tree with `N4-SUP-01` at the top, `JACE-OT-01` and `JACE-OFFICE-01` as children, each with its own equipment underneath.
- `/metasys` unchanged — still hospital-only, no office equipment visible.
- No real facility data, PHI, or real credentials in any file.

---

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Facility tagging completeness | `GET /api/equipment` and `GET /api/points`, check every entry | Every entry has a non-null `facility` field |
| Hospital scenarios unaffected | `scripts/run-smoke-test.sh` | Passes exactly as before this build |
| Office baseline values sane | `python3 simulator/bas_sim.py --scenario normal --steps 8`, inspect `latest_points.json` for the 10 new points | All within their `normal_min`/`normal_max` range |
| Niagara portfolio tree | Load `/niagara`, expand `N4-SUP-01` | Both JACEs visible with correct equipment underneath |

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Portfolio (not single-building) navigation exists | `BUILD/4-completedbuilds/BP-007-...md` (once verified) | `niagara.html` Station tree structure, `GET /api/equipment` facility field |
| Office building has a distinct equipment/fault character from the hospital | same | `equipment.json`, `points.json`, `sequences/RTU-1-SOO.md`, `sequences/VAV-301-SOO.md` |

---

## Residual Risk

- Office equipment has no fault library entries yet — trouble-call mode
  stays hospital-only until BP-008. Acceptable; explicitly the next slice.
- The Niagara UI change is the largest UI restructuring since BP-002 — the
  worker should preserve existing tab behavior (Points/Alarms/Trends/
  Technician Panel/Trouble Call) rather than rewrite them, only changing
  how equipment is grouped/selected at the top of the page.
- `CHILLER-1`/`BOILER-1` are simplified representations (no condenser
  water loop, no staging logic) — fine for a training lab, not a real
  chiller plant control sequence.

---

## Worker Instructions

Before editing, confirm:

1. `sequences/RTU-1-SOO.md` and `sequences/VAV-301-SOO.md` already exist
   (pre-written) — do not overwrite them.
2. `data/input/equipment.json` still has the old singular `"facility"`
   key (not yet restructured).
3. None of the 10 new office point names already exist in `points.json`.

Build in order: equipment.json restructuring → points.json additions →
alarm_rules.json additions → bas_api.py facility pass-through → niagara.html
Station tree. Run acceptance checks after each step.

Report back with: acceptance-check output, list of files changed, and any
deviation from this plan with a reason — especially if `bas_sim.py`
turned out to need changes after all. Do not stage, commit, or push. Do
not mark this BP `COMPLETE` or move it to `2-approvedbuilds/` — J reviews
the two judgment calls above first.
