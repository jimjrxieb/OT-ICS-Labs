# BUILD Plan BP-008 — Office Building Fault Library

**Status:** APPROVED
**Approved by:** J — 2026-07-06
**Approval scope:** Local synthetic lab only — one data file:
  `data/input/fault_library.json` (additive entries only)
**Source finding:** BP-007 Residual Risk: "Office equipment has no fault
  library entries yet — trouble-call mode stays hospital-only until
  BP-008." This is that slice. Continues the operator's mastery goal:
  comfort/energy faults in an office building present differently from
  the hospital's life-safety faults, and learning that contrast is the
  skill.
**Target:** `data/input/fault_library.json`
**Owner:** ot-build-agent (codex worker)

---

## Why This Build Exists

BP-007 added the Riverside Office Tower (RTU-1, VAV-301, CHILLER-1,
BOILER-1, 10 points, 3 alarm rules) but trouble-call mode can only deal
hospital tickets. This build adds 6 office faults so the ticket queue
spans the whole portfolio.

Design notes confirmed against the code before drafting (verifier
pre-checked; worker does not need to re-derive):

- `_equipment_options()` in `frontend/bas_api.py` builds the diagnosis
  dropdown from the fault library's `correct_equipment` set — office
  equipment appears automatically once these entries exist. **No code
  changes are needed anywhere.** This BP is one data file.
- `bas_sim.py` supports injection modes `drift`, `stuck`, `step`,
  `noise_flatline`, plus per-directive `forces` (including `raise_alarm`).
  All six faults below are expressible with existing modes. Oscillation
  is NOT supported — which is why the boiler fault is a flame failure
  (drift down), not short-cycling.

## Approved Context

Worker may use:

- `data/input/fault_library.json` — existing 9 hospital entries as the
  exact schema template (see BP-006 for the schema definition)
- `data/input/points.json` — the 10 office points' names and normal
  ranges (added in BP-007)
- `sequences/RTU-1-SOO.md`, `sequences/VAV-301-SOO.md` — troubleshooting
  signal language for the explanation fields

Worker must not use:

- Any file other than `data/input/fault_library.json` — if any other file
  seems to need a change, STOP and report it; a plan assumption was wrong
- git operations; real facility data; external network access

---

## Proposed Change — 6 New Fault Entries

All entries follow the BP-006 schema exactly. Exact rates/values are the
worker's judgment within the guidance below; signatures must be visually
distinguishable in trends.

1. **`RTU1_ECON_DAMPER_STUCK`** — actuator_stuck — RTU-1.
   `RTU1_OA_DAMPER_POS` stuck at minimum (~10%) from an early step while
   `RTU1_MA_TEMP` drifts up toward return-air temperature (~74+) and
   `RTU1_SAT` drifts above setpoint as mechanical cooling falls behind.
   `symptom_text`: "Floor 3 tenants report their space has been getting
   warmer all morning." (Deliberately the SAME symptom as fault 2 — the
   apprentice must use trends to tell upstream from downstream.)
   Explanation: damper position not responding + mixed-air temp tracking
   return air = economizer actuator, an upstream RTU problem, not the zone.

2. **`VAV301_REHEAT_STUCK_OPEN`** — actuator_stuck — VAV-301.
   `VAV301_REHEAT_VLV_POS` stuck at ~95% (far above its 0–30 normal band)
   while `VAV301_TEMP` drifts up past 76. RTU-1 points stay normal.
   `symptom_text`: identical to fault 1. Explanation: RTU discharge temp
   normal but the zone overheats with the reheat valve pinned open — the
   fault is at the box, downstream, not the RTU.

3. **`RTU1_SAT_SENSOR_FAILURE`** — sensor_failure — RTU-1.
   `RTU1_SAT` flatlines (`stuck` mode) at a fixed value from an early
   step — identical readings step after step while `RTU1_MA_TEMP` and
   zone temps keep moving normally. `symptom_text`: "Energy report shows
   RTU-1 discharge temp hasn't moved in days; something seems off."
   Explanation: a live thermistor always shows noise — a perfectly flat
   trend line is a dead/failed sensor, not a steady system.

4. **`CHILLER1_CAPACITY_LOSS`** — mechanical_failure — CHILLER-1.
   `CHILLER1_CHW_SUPPLY_TEMP` drifts up past its 46 F alarm limit
   (triggering the BP-007 alarm rule) while `RTU1_SAT` drifts up in
   sympathy — a plant problem cascading downstream. `symptom_text`:
   "Multiple office floors warm this afternoon; RTU seems to be running
   flat out." Explanation: when everything downstream is starving at
   once, look upstream at the plant — CHW supply temp is the giveaway.

5. **`BOILER1_FLAME_FAILURE`** — mechanical_failure — BOILER-1.
   `BOILER1_HW_SUPPLY_TEMP` drifts down out of its 140–150 band
   (triggering the BP-007 alarm rule) while `VAV301_REHEAT_VLV_POS`
   drifts up as the box calls for more heat it can't get.
   `symptom_text`: "Morning warm-up complaints — zones cold, reheat
   running hard but not recovering." Explanation: valves open + falling
   HW supply temp = the heat source itself, not the distribution.

6. **`OFFICE_JACE_COMMS_LOSS`** — comms_loss — JACE-OFFICE-01.
   ALL 10 office points flatline (`stuck` mode, one directive per point,
   each pinned at a plausible in-range value) from an early step, with a
   `raise_alarm` force on one directive: priority `high`, message
   "JACE-OFFICE-01 offline — office building points stale". Hospital
   points unaffected. `symptom_text`: "Office building tenants calling
   about comfort, but every office point on the front end reads exactly
   the same as an hour ago." Explanation: every point on one JACE frozen
   simultaneously is never 10 coincident sensor failures — it's the
   controller or its network. First use of the `comms_loss` category.
   `correct_equipment`: `JACE-OFFICE-01` (appears in the dropdown
   automatically via `_equipment_options`).

---

## Files In Scope

- `data/input/fault_library.json` (additive — the 9 hospital entries must
  remain byte-identical)

## Out Of Scope

- Every other file. No code changes, no UI changes, no new points, no
  alarm-rule changes, no simulator changes, no git operations.

---

## Acceptance Checks

- `python3 -c "import json; d=json.load(open('data/input/fault_library.json')); print(len(d))"` → 15.
- The 9 original hospital entries unchanged (compare fault_ids and spot-check one entry's content).
- `scripts/run-smoke-test.sh` still passes.
- Each of the 6 new faults runs: `python3 simulator/bas_sim.py --fault <id> --steps 12` exits cleanly for all six.
- Signature spot-checks from `trends.csv` after each run (show actual values):
  - `RTU1_ECON_DAMPER_STUCK`: damper pinned ~10, `RTU1_MA_TEMP` rising.
  - `VAV301_REHEAT_STUCK_OPEN`: valve ~95, `VAV301_TEMP` rising, RTU1_SAT normal.
  - `RTU1_SAT_SENSOR_FAILURE`: `RTU1_SAT` identical across steps, `RTU1_MA_TEMP` still varying.
  - `CHILLER1_CAPACITY_LOSS`: CHW supply temp crosses 46 and the high-priority alarm from the BP-007 rule appears in `alarms.jsonl`.
  - `BOILER1_FLAME_FAILURE`: HW supply temp falls below 140, alarm fires, reheat valve rising.
  - `OFFICE_JACE_COMMS_LOSS`: all 10 office points identical across steps, hospital points still varying, JACE offline alarm present.
- Faults 1 and 2 have identical `symptom_text` (the upstream/downstream drill).
- Live server: `POST /api/trouble-calls/new?fault_id=VAV301_REHEAT_STUCK_OPEN` returns the shared symptom text, `equipment_options` now includes RTU-1, VAV-301, CHILLER-1, BOILER-1, and JACE-OFFICE-01, and a correct diagnose flow works end to end.
- No real facility data, PHI, or credentials.

---

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Upstream/downstream drill | Run faults 1 and 2, compare trends | Same symptom, distinguishable only by RTU vs. zone point behavior |
| Comms loss vs. sensor failure | Compare fault 6 trends to fault 3 trends | One frozen point = sensor; all points on one JACE frozen = comms |
| Hospital library regression | Force a hospital fault (e.g. `AHU_OR1_DRAIN_SAFETY_TRIP`) after the file change | Identical behavior to BP-006 verification |
| Dropdown auto-extension | `GET /api/trouble-calls/active` options | Office equipment present with zero code changes |

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Trouble-call training spans the full portfolio | `BUILD/4-completedbuilds/BP-008-...md` (once verified) | `fault_library.json` (15 entries), trouble-call flow output |
| Office faults teach comfort/energy vs. life-safety contrast | same | Faults 1/2 shared-symptom pair; alarm priorities (medium/high vs. the hospital's critical) |

---

## Residual Risk

- Random fault selection now draws from 15 entries across two buildings —
  hospital faults become proportionally rarer per ticket. Acceptable;
  `?fault_id=` exists for targeted practice.
- Boiler short-cycling (oscillation) remains unmodelable until the
  injection engine grows an oscillation mode — noted for a future BP if
  wanted.
- Fault 6 pins office points at fixed in-range values; a sharp eye could
  notice the values are *too* clean. Acceptable — that is in fact the
  real-world tell for stale data.

---

## Worker Instructions

Before editing, confirm:

1. `data/input/fault_library.json` has exactly 9 entries, all hospital.
2. The 10 office point names from BP-007 exist in `data/input/points.json`.
3. `_equipment_options()` in `frontend/bas_api.py` derives from
   `correct_equipment` (no code change needed for the dropdown).

Add the 6 entries, then run all acceptance checks. Report back with:
acceptance-check output (actual trend values, not pass/fail claims), and
any deviation with a reason. If anything outside `fault_library.json`
seems to need a change, stop and report instead of proceeding. Do not
stage, commit, or push. Do not mark this BP `COMPLETE` — that happens
after independent verification.
