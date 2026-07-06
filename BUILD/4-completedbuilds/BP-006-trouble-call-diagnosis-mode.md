# BUILD Plan BP-006 — Trouble-Call Diagnosis Training Mode

**Status:** COMPLETE
**Approved by:** J — 2026-07-01. Brainstormed collaboratively including
  fault #9 sourced from the operator's real field experience (dirty
  strainer + leaking actuator → condensate drain safety trip). Verified
  2026-07-01: py_compile and run-smoke-test.sh rerun independently; fault
  #9 forced via `?fault_id=` on a freshly started server and its full trend
  signature (STRAINER_DP climb, CHW_VLV_POS pinned at 88%, DRAIN_SWITCH
  0→1, FAN_CMD forced off, high-priority alarm) re-confirmed directly, not
  by reusing worker-reported output; 409 single-ticket lock and diagnose/
  clear flow re-tested; confirmed no role param on trouble-call routes and
  `bas_console.py` untouched; `git status` confirmed no staged/committed
  changes.
**Approval scope:** Local synthetic lab only — additive changes to
  `simulator/bas_sim.py`, `data/input/`, `frontend/bas_api.py`,
  `frontend/static/metasys.html`, `frontend/static/niagara.html`; new files
  under `data/output/`
**Source finding:** Learning objective — apprentice DDC technician wants to
  master control navigation and fault diagnosis before touching real
  hospital/portfolio equipment. Redirects effort from BUILD-003 (Step 2 OT
  security, parked mid-slice) back to Step 1 mastery-building. Fault #9 is
  a real field-reported fault (dirty CHW strainer + leaking valve actuator
  → condensate drain safety trip), brainstormed and approved 2026-07-01.
**Target:** `simulator/bas_sim.py`, `data/input/points.json`,
  `data/input/fault_library.json` (new), `frontend/bas_api.py`,
  `frontend/static/metasys.html`, `frontend/static/niagara.html`
**Owner:** ot-build-agent (codex worker)

---

## Why This Build Exists

BP-001 through BP-005 gave the lab read navigation (Metasys/Niagara point,
alarm, trend views), a command/release loop (BP-004), and a role gate on
that loop (BP-005). None of that builds diagnostic reasoning — the actual
skill a DDC apprentice needs. This build adds a "trouble-call" mode: you
get a symptom only, investigate using the tools you already have (points,
alarms, trends), submit a structured diagnosis, and get graded with an
explanation of what the data was telling you.

Fault #9 is not synthetic-only invention — it's a real fault pattern
(dirty strainer restricting CHW flow, a leaking valve actuator not fully
closing, resulting excess/prolonged condensate production, drain pan float
switch trip, safety shutdown) confirmed against the operator's own field
experience. It's deliberately a compound fault — two weak signals precede
the obvious alarm — to teach root-cause chaining, not just alarm-reading.

---

## Approved Context

Worker may use:

- `simulator/bas_sim.py` — existing scenario-generation code (`scenario_value`
  and related functions) as the pattern for fault injection; extending this
  file is in scope for this build (unlike BP-004/BP-005, which excluded it)
- `data/input/points.json` — add new points, do not remove/rename existing ones
- `frontend/bas_api.py`, `frontend/static/metasys.html`,
  `frontend/static/niagara.html` — existing FastAPI/UI patterns from
  BP-002/BP-004/BP-005 (tabs, fetch-based JS, `data_boundary` tagging)

Worker must not use:

- Real credentials, real facility data, external network access
- git operations (no stage, commit, push, or branch)
- Any multi-building/portfolio expansion (separate future BP)
- Any scoring, leveling, or gamification beyond the correct/incorrect +
  explanation grading described below
- Changes to `bas_console.py` (CLI support for trouble calls is a future
  add-on, not this slice)
- Role-gating on trouble-call endpoints (this is training/investigation,
  not commanding real equipment — open to any role, unlike BP-005's
  command/release gate)
- The remaining BUILD-003 OT-security docs (still parked, unrelated)

---

## Proposed Change

### 1. Fault library (`data/input/fault_library.json`, new)

Nine fault definitions, each with: `fault_id`, `equipment`, `category`
(one of `sensor_failure`, `actuator_stuck`, `mechanical_failure`,
`control_loop_fault`, `comms_loss`), `symptom_text` (shown to the
apprentice, never reveals the cause), `affected_points`, `injection`
(how `bas_sim.py` should perturb point values over the run), `correct_equipment`,
`correct_category`, and `explanation` (the "tell" — what in the data
should have pointed to the right answer).

`injection` is a list of one or more per-point directives, each with:
`point` (name), `mode` (`drift` | `stuck` | `step` | `noise_flatline`),
`rate_per_step` (for `drift` — signed float added each step),
`start_step` (int — when the perturbation begins), and optionally
`forces` (a dict of side effects applied once a threshold is crossed,
e.g. `{"AHU_OR1_FAN_CMD": 0}` plus `"raise_alarm": {"priority": "high",
"message": "..."}`). Example, fault 1:

```json
{
  "fault_id": "AHU_OR1_SAT_SENSOR_DRIFT",
  "equipment": "AHU-OR-1",
  "category": "sensor_failure",
  "symptom_text": "OR-1 staff reporting the room feels colder than the thermostat suggests.",
  "affected_points": ["AHU_OR1_SAT"],
  "injection": [
    {"point": "AHU_OR1_SAT", "mode": "drift", "rate_per_step": -0.4, "start_step": 3}
  ],
  "correct_equipment": "AHU-OR-1",
  "correct_category": "sensor_failure",
  "explanation": "AHU_OR1_SAT drifted downward independent of OR1_TEMP and setpoint — classic stuck/miscalibrated sensor."
}
```

Fault 9's `injection` uses two `drift`-mode directives (`AHU_OR1_STRAINER_DP`
climbing, `AHU_OR1_CHW_VLV_POS` pinned high) plus a `stuck`-mode directive
on `AHU_OR1_DRAIN_SWITCH` that flips from 0 to 1 at a `start_step` after
the other two have visibly diverged, with `forces: {"AHU_OR1_FAN_CMD": 0,
"raise_alarm": {"priority": "high", "message": "AHU-OR-1 condensate pan
high-level safety trip"}}` triggered the step the switch flips. This is
the concrete pattern the worker should follow for all 9 fault definitions
— exact per-fault rates/thresholds are the worker's judgment call as long
as the resulting trends are visually distinguishable per equipment/fault.

Faults:

1. `AHU_OR1_SAT_SENSOR_DRIFT` — sensor_failure — `AHU_OR1_SAT` drifts
   independent of `OR1_TEMP`/setpoint.
2. `AHU_OR1_FAN_FAILURE` — mechanical_failure — fan commanded on, no
   cooling effect on `AHU_OR1_SAT`.
3. `VAV_OR101_DAMPER_STUCK` — actuator_stuck — `OR1_TEMP` diverges from
   setpoint despite AHU running normally.
4. `ISO201_EXHAUST_FAILURE` — mechanical_failure — `ISO201_PRESSURE`
   drifts positive (loss of negative pressure).
5. `ISO201_EXH_CMD_MISMATCH` — actuator_stuck — commanded state and
   actual pressure response disagree.
6. `CHW_PLANT_LOW_DELTA_T` — actuator_stuck — `CHW_SUPPLY_TEMP` rises,
   `CHW_DIFF_PRESSURE` drops, valve not modulating correctly.
7. `HW_PLANT_SENSOR_FAILURE` — sensor_failure — `HW_SUPPLY_TEMP` flatlines
   or spikes independent of load.
8. `OR1_RH_SENSOR_VS_REAL_EXCURSION` — paired fault: one variant is a
   sensor fault on `OR1_RH` (flatlined reading, no correlation to
   `AHU_OR1_SAT` behavior), the other is a real humidity excursion
   (consistent with the existing `or_humidity_excursion` scenario
   physics). Randomly picks one variant per ticket — teaches
   distinguishing "sensor lying" from "real problem."
9. `AHU_OR1_DRAIN_SAFETY_TRIP` — mechanical_failure (compound) —
   `AHU_OR1_STRAINER_DP` climbs gradually (fouling), `AHU_OR1_CHW_VLV_POS`
   stays abnormally high/stuck even as `AHU_OR1_SAT` shows setpoint
   satisfied (valve leaking by), then partway through the run
   `AHU_OR1_DRAIN_SWITCH` flips to 1, forcing `AHU_OR1_FAN_CMD` to 0 and
   raising a high-priority safety alarm. `symptom_text`: *"AHU-OR-1
   tripped off overnight, high-priority alarm active, OR staff want it
   back online."* Full credit requires citing both precursor signals in
   the explanation match, not just the drain switch trip.

### 2. New points (`data/input/points.json`)

Add to `AHU-OR-1`:

- `AHU_OR1_CHW_VLV_POS` (AI) — chilled water valve position feedback, 0-100%
- `AHU_OR1_STRAINER_DP` (AI) — differential pressure across the coil's CHW strainer, psid
- `AHU_OR1_DRAIN_SWITCH` (BI) — condensate pan float switch, 0 = dry, 1 = tripped

### 3. Fault injection (`simulator/bas_sim.py`)

Add a `--fault <fault_id>` mode alongside the existing `--scenario` mode
(mutually exclusive). Reads `fault_library.json`, applies the named
fault's `injection` spec to point generation the same way `scenario_value`
already applies scenario physics, and honors any forced-value/alarm side
effects (e.g., fault #9 forcing `AHU_OR1_FAN_CMD` to 0 and injecting a
high-priority alarm once `AHU_OR1_DRAIN_SWITCH` trips). Writes
`latest_points.json`, `alarms.jsonl`, `trends.csv` exactly as scenario
runs already do — no new output format.

### 4. Backend API (`frontend/bas_api.py`)

- `POST /api/trouble-calls/new` — if `data/output/trouble_call_active.json`
  exists and is undiagnosed, return `409` with its `symptom_text` (one
  ticket open at a time). Otherwise pick a fault (random, or `?fault_id=`
  to force one for testing), run `bas_sim.py --fault <id>`, write the
  active-ticket file (ticket_id, fault_id, opened_at — server-side only),
  and return `ticket_id` + `symptom_text` + the equipment/category option
  lists for the dropdowns. Never returns answer fields.
- `GET /api/trouble-calls/active` — re-fetch the open ticket's
  `symptom_text` (for page refresh), no answer fields.
- `POST /api/trouble-calls/{ticket_id}/diagnose` — body: `guessed_equipment`,
  `guessed_category`. Grades against the fault's stored answer, deletes
  the active-ticket file, appends a record to
  `data/output/trouble_call_log.jsonl` (ticket_id, fault_id, guess,
  correct bool, opened_at, answered_at), returns `{correct,
  actual_equipment, actual_category, explanation}`.
- `GET /api/trouble-calls/history` — last 20 entries from the log.

### 5. Frontend (`metasys.html`, `niagara.html`)

New "Trouble Call" tab:

- No active ticket → "Request Trouble Call" button.
- Active ticket → symptom banner, reminder to check Points/Alarms/Trends
  tabs, diagnosis form (equipment dropdown, category dropdown, Submit).
- After submit → Correct/Incorrect banner, actual equipment/category,
  explanation text, "Request Trouble Call" button reappears.
- History table below: last 20 tickets (fault vs. guess vs. correct/incorrect).

Platform-appropriate terminology throughout, matching the existing pattern.

---

## Files In Scope

- `simulator/bas_sim.py`
- `data/input/points.json`
- `data/input/fault_library.json` (new)
- `frontend/bas_api.py`
- `frontend/static/metasys.html`
- `frontend/static/niagara.html`
- `data/output/trouble_call_active.json` (new, generated)
- `data/output/trouble_call_log.jsonl` (new, generated)

---

## Out Of Scope

- Multi-building/portfolio expansion (separate future BP)
- `bas_console.py` CLI support for trouble calls
- Scoring, leveling, gamification beyond correct/incorrect + explanation
- Hint system
- Role-gating on trouble-call endpoints
- Remaining BUILD-003 OT-security docs (Purdue/zone/conduit, incident/change workflow)

---

## Acceptance Checks

- `python3 -m py_compile simulator/bas_sim.py frontend/bas_api.py bas_console.py` exits 0.
- `scripts/run-smoke-test.sh` still passes.
- `POST /api/trouble-calls/new` opens a ticket, returns `symptom_text` with no answer fields present.
- A second `POST /api/trouble-calls/new` while one is open returns `409` with the existing ticket's symptom text.
- `POST /api/trouble-calls/{id}/diagnose` grades correctly for both a right and a wrong guess, returns the explanation.
- After diagnosing, the active-ticket file clears and a new `/new` call succeeds.
- `data/output/trouble_call_log.jsonl` gains one entry per diagnosed ticket.
- Fault #9 verified end-to-end: `AHU_OR1_STRAINER_DP` climbs, `AHU_OR1_CHW_VLV_POS` stays abnormally high, `AHU_OR1_DRAIN_SWITCH` flips to 1 partway through the run, `AHU_OR1_FAN_CMD` forced to 0, high-priority alarm raised.
- Spot-check at least 3 of the 9 faults for distinct, plausible trend signatures (not just alarm text).
- Trouble Call tab renders and functions in both `metasys.html` and `niagara.html`.
- No real facility data, PHI, or real credentials in any file.

---

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Two tickets requested back to back | `POST /new` twice without diagnosing | Second call returns `409` with first ticket's symptom text, no second fault run triggered |
| Wrong diagnosis | `POST /diagnose` with an incorrect equipment/category pair | `correct: false`, actual answer + explanation returned, ticket still closes |
| Fault #9 precursor signals | `GET /api/trends/AHU_OR1_STRAINER_DP` and `.../AHU_OR1_CHW_VLV_POS` mid-run, before the drain switch trips | Both show abnormal trend before `AHU_OR1_DRAIN_SWITCH` flips |
| Sensor-vs-real-excursion pair | Run fault #8 several times | Both variants occur across repeated runs; each is diagnosable from its own distinct signature |

---

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Apprentice can practice fault diagnosis against realistic signatures | `BUILD/4-completedbuilds/BP-006-...md` (once verified) | `data/input/fault_library.json`, `trouble_call_log.jsonl` |
| Field-reported fault is faithfully modeled | same | Fault #9 definition + BREAK evidence above |

---

## Residual Risk

- Grading is exact-match on dropdown selections, no partial credit for a
  right equipment / wrong category (or vice versa) — acceptable for a v1
  training loop, could be refined later.
- Single-ticket lock is file-existence based, no concurrency control —
  fine for a single local user, would race under concurrent access.
- Still scoped to the original hospital only — portfolio expansion
  (office building + central plant) is explicitly the next BP after this one.
- Fault #8's random variant selection means a given practice session might
  not surface both variants — acceptable, real trouble calls aren't evenly
  distributed either.

---

## Worker Instructions

Before editing, confirm:

1. `frontend/bas_api.py` has the BP-004/BP-005 command/release/role
   endpoints already in place.
2. `data/input/points.json` does not already have `AHU_OR1_CHW_VLV_POS`,
   `AHU_OR1_STRAINER_DP`, or `AHU_OR1_DRAIN_SWITCH`.
3. `data/input/fault_library.json` does not already exist.

Build in order: points.json additions → fault_library.json → bas_sim.py
fault injection → backend API → frontend UI. Run acceptance checks after
each step.

Report back with: acceptance-check output (including the fault #9
end-to-end trend check), list of files changed, and any deviation from
this plan with a reason. Do not stage, commit, or push. Do not mark this
BP `COMPLETE` — that is J's call after independent verification.
