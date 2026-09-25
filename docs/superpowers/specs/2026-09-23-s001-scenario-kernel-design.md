# S-001 Scenario Kernel — Design

- **Date:** 2026-09-23
- **Status:** Design for review. Nothing here is implemented.
- **Direction sources:** `docs/chatgpt-chats.md` §5 (Priority 1), §6.1 (S-001),
  §13 (architecture/testing), §14 workstreams B and C, §17 (first task),
  §18.2 (one deliverable per session). Status of existing features: see
  `docs/vision-checklist.md` (this spec does not restate it).
- **Baseline:** `main` at `642d33e` (clean checkout passes the smoke test).

## 1. Outcome

A trainee starts an unseen shift case, gets only a complaint and legitimately
available evidence, investigates the real Building 822 model, makes safety
decisions, repairs the physical cause, waits through modeled recovery,
releases temporary commands, and submits a cited closeout that the server
verifies against **model state**, not against a success flag or a category
guess. The case survives refresh/restart, replays deterministically, and
never shows the hidden cause to trainee-facing endpoints before debrief.

S-001 is the first and only case in this slice: *low-flow chiller trip with
water in the pump room*, caused by a leaking valve body that bleeds the
chilled-water loop down.

## 2. Decisions already made

| Decision | Choice |
|---|---|
| Time | **Action-driven simulated clock.** Actions cost simulated minutes; `wait N` steps the physics. No background loop. |
| Surface | **Server-owned session API + one minimal Shift page.** BAS evidence comes from the existing `/tracer`, Property Sheet, and chiller walk-up views. |
| Existing Trouble Call | **Untouched.** The 15 hospital/office faults keep their one-shot flow. |
| Building | **Building 822** (§4 of the direction doc: reuse, don't fork a parallel building). |

## 3. Non-goals for this slice

- Weighted rubric scoring (100-point model, §15) — workstream D. This slice
  records everything D needs and runs objective pass/fail verification.
- Any other scenario, variant seeds beyond S-001's own, instructor dashboard,
  or UI polish.
- Concurrent sessions. One active session owns Building 822 at a time.
- Real procedures. Every safety step is a *simulated decision*; real
  isolation, LOTO, and electrical work defer to employer training and site
  rules (§5.3, §12). The UI says so.

## 4. Where S-001 does not fit the current model (the §17 check)

| Gap | Today | Needed for S-001 |
|---|---|---|
| Chiller ignores flow | `chiller_step()` holds leaving water at setpoint even at 0 GPM | Evaporator **flow proof**: trip on sustained low flow, latching diagnostic, manual reset that only holds if flow is proven |
| No loop inventory | Flow = pump on/off × strainer resistance | Loop **static pressure** from water inventory; leak removes water; makeup/fill adds it; low pressure air-binds the pump and flow collapses while the pump still "runs" |
| Pump status = command | `P1_STATUS` mirrors `P1_CMD` | Keep that (a current switch proves the motor turns, not that water moves) — this *is* the lesson |
| No field-only water evidence | Field channel covers valve travel only | Pump-room walk (standing water, where, how much, energized equipment nearby), loop pressure gauge, pump amps, valve inspection |
| Instant chilled-water temperature | Loop temperature = chiller leaving water, instantly | First-order **loop thermal mass** so trip and recovery take modeled time |
| Faults last one CLI run | Knobs are per-invocation (`--knob`) | Session-persisted cause state |
| Nobody owns time | `bas_sim.py` steps from a loop index; BACnet server steps on its own clock | Session clock owns 822 stepping while a session is active |

**Behavior change to accept:** once the chiller has flow proof, the existing
knobs `CHW-822:p1_running=false` (with P2 off) or a high
`strainer_resistance` will trip the chiller. That is physically correct and
intended; affected self-tests are updated, not worked around.

## 5. Architecture

```text
data/input/scenarios/S-001.json            (trainee-safe definition)
data/input/scenarios/S-001.instructor.json (hidden cause, timeline, answers)
            |
simulator/scenario_kernel.py  -- pure: lifecycle, actions, prerequisites,
            |                    replay; no HTTP, no file paths
simulator/model822.py         -- physics (additions in §7), unchanged API
            |
frontend/sessions.py          -- file store (atomic), ownership lock,
            |                    snapshot/restore via platform_admin
frontend/bas_api.py           -- /api/sessions/* routes, role checks, audit
frontend/static/shift.html    -- minimal Shift page
```

- **Pure core, thin shell.** `scenario_kernel.py` takes (definition, truth,
  state, action) → (new state, observation, log record). It is self-tested
  like `wiresheets.py`. The API layer only loads, authorizes, persists, and
  audits.
- **One building.** The kernel steps 822 through `model822.step_822` and the
  same point/ground-truth write path `bas_sim.py` uses (refactored into a
  shared function, not copied), so `/tracer`, `/api/points`, and the chiller
  walk-up show the session's building with no session-specific code.

### 5.1 Ownership of Building 822

- Starting a session requires that nobody else steps 822:
  - refuse (409) if `.822-bacnet.lock` is held by a live process;
  - write `.822-session.lock` (session id + PID-free marker; sessions are not
    processes).
- `bas_sim.py` and `bacnet822.py` treat `.822-session.lock` exactly like the
  BACnet lock: skip stepping 822 (and `bacnet822.py` refuses to start).
- Before the session's first step, snapshot 822 state
  (`state_822.json`, `.822-ground-truth.json`, and the 822 entries of
  `operator_overrides.json`) with `platform_admin.snapshot_single_file`-style
  backups. **Close or abandon restores that snapshot** and removes the lock.
  Hospital/office state is never touched.

### 5.2 Files

```text
data/output/sessions/<session_id>/
  session.json      trainee-visible state: lifecycle, clock, notebook, closeout
  truth.json        instructor-only: seed, knobs timeline, scoring facts
  actions.jsonl     append-only action/evidence records
  snapshot/         pre-session 822 files (restore source)
```

Writes are atomic (temp file + rename). `session.json` stores a hash of the
model state after each record so replay can prove it reproduces the same
building.

## 6. Kernel

### 6.1 Lifecycle (server-owned)

```text
OPEN -> INVESTIGATING -> ISOLATED -> REPAIRING -> RECOVERING
     -> READY_FOR_VERIFICATION -> CLOSED
side exits: UNSAFE_STOP, FAILED_VERIFICATION (returns to RECOVERING), ABANDONED
```

Transitions come from actions and model state, never from the client:
e.g. `ISOLATED` when the leaking section is isolated; `RECOVERING` when the
cause is removed and flow is proven; `READY_FOR_VERIFICATION` only when the
§8 checks would pass. `UNSAFE_STOP` is terminal for scoring but still gets a
debrief.

### 6.2 Actions

Each catalog action declares:

| Field | Meaning |
|---|---|
| `action_id`, `label` | Stable id; trainee-facing wording that does not reveal the cause |
| `roles` | Who may perform it (trainee actions: `technician`) |
| `time_cost_min` | Simulated minutes the physics advances |
| `prerequisites` | Predicates over session + model state (e.g. `P1 de-energized`) |
| `safety` | `safe`, `requires_decision`, or `unsafe` (→ `UNSAFE_STOP` if taken) |
| `effect` | Knob/state changes (repairs) or an observation read (field actions) |
| `evidence_type` | `bas_value`, `field_measurement`, `visual_inspection`, `operator_report`, `documentation`, `technician_inference` |

Every executed action appends a record: actor, role, simulated time and wall
time, target, prerequisites checked, observation returned, actual state
changes, safety decision, diagnostic cost. A failed prerequisite is recorded
too and changes nothing.

**BAS evidence** is captured by *pinning*: the trainee pins a point; the
server records that point's actual value at the current simulated minute.
Evidence is grounded in model history, not typed in.

### 6.3 Hypothesis notebook

Hypotheses (free text + status) link to supporting and contradicting
evidence record ids. Stored in `session.json`; used by closeout citations.

### 6.4 Determinism and replay

Session = (definition version, truth seed, initial-state recipe, ordered
action records). `replay(session)` rebuilds the model from cold start plus the
recipe and re-applies the actions; it must reproduce every stored state hash.
Randomness only comes from the truth seed.

## 7. S-001 physics additions (`model822.py`)

Implemented names (phase 1, authoritative over the names below):
`p1_tdv_leak_gpm`, `p1_branch_isolated`, `makeup_valve_open`, continuous
`air_frac`, and `resets` / `unproven_resets`.

All constants go in `TUNING` and are **synthetic engineering assumptions**,
labeled as such in code comments. Defaults are healthy, so existing behavior
is unchanged unless a knob is set (except the §4 flow-proof change).

1. **Loop inventory / static pressure.** `state["chw"]["loop_psig"]`
   (default `LOOP_FILL_PSIG`, e.g. 15). Each step:
   `psig -= leak_gpm * STEP_MINUTES * LOOP_PSI_PER_GAL`, plus makeup when the
   fill valve is open and pressure is below the PRV setting
   (`MAKEUP_GPM`). New CHW knobs: `leak_gpm` (0), `leak_location`
   (`null`), `makeup_valve_open` (false in S-001 — synthetic assumption: fill
   isolated, so the loop bleeds down; configurable).
2. **Air-binding.** Below `PUMP_MIN_SUCTION_PSIG` flow degrades toward zero
   over a few minutes; after refill, flow stays degraded until air is purged
   (`air_bound` state flag, cleared by a purge action).
3. **Evaporator flow proof.** If GPM < `EVAP_MIN_FLOW_FRAC` × design for
   `FLOW_PROOF_DELAY_MIN`, the chiller trips: diagnostic `LowEvapFlow`,
   **latching** (manual reset). A reset with flow proven clears it and the
   chiller restarts after `CHILLER_RESTART_MIN`; a reset without flow re-trips
   after the proof delay and increments `reset_attempts` (repeated reset
   without correcting the permissive, checklist §9.4).
4. **Loop thermal mass.** Loop water temperature moves toward chiller leaving
   water (or warms with load when the chiller is off) with a first-order lag
   (`LOOP_TAU_MIN`), so the trip and the recovery take visible time.
5. **Pump-room water.** `state["plant_room"]["water_gal"]` accumulates leaked
   water (the leak location is in the pump room for S-001).
6. **Field observations** (extend the existing hidden-truth channel, never
   BAS points): pump-room walk (water present, approximate area/depth, near
   energized pump motor/disconnect), loop pressure gauge at pump suction, pump
   motor amps (low when air-bound), valve body inspection (weeping, corrosion)
   per valve.

Model self-tests: leak lowers pressure at the configured rate; low pressure
air-binds the pump and zeroes flow while status stays on; flow proof trips
after the delay; reset without flow re-trips and counts; healthy defaults
reproduce today's outputs (regression against a stored baseline).

## 8. The S-001 case

**Complaint (trainee-visible):** Front desk, 06:40: "Halls on all floors are
warm and muggy since early this morning; room units are blowing but it's not
cold."

**Hidden truth (instructor-only):** the body of the P1 branch balancing /
check (triple-duty) valve — which sits *between* the P1 branch suction and
discharge isolation valves, so closing those isolates it — corrodes through
~3 hours before shift; leak rate from the truth seed within a
configured band; fill valve isolated; loop bleeds down, P1 air-binds, flow
drops, chiller trips `LowEvapFlow`, loop warms, MAU/FCU capacity collapses.

**Available evidence (not the answer):** BAS shows P1 command/status ON,
`CHW822_GPM` near 0, low building DP, rising supply temperature, warm/humid
halls. The chiller is local-display only (existing design): its diagnostic
is visible by walking to the chiller panel, not on the BAS. Loop pressure is
**field-only** (gauge), which is part of the lesson.

**Action catalog (v1):**

| Group | Actions |
|---|---|
| Look | pin BAS point; walk to chiller panel; walk pump room; read suction gauge; clamp P1/P2 amps; inspect a named valve; check strainer (normal — distractor); check MAU04 valve travel (normal — distractor) |
| Decide | report water hazard / escalate; de-energize P1 (simulated LOTO decision); de-energize P2 |
| Repair | close P1 branch isolation valves (isolates the leaking valve); replace leaking valve body (requires P1 branch isolated and de-energized); open / close the fill (makeup) valve; purge air at high-point vent; start P2 / restore P1 |
| Control | reset chiller (manual); release overrides (existing endpoints) |
| Time | wait N minutes (1–60) |

**Safety gates:**
- Working on or next to P1 while water is on the floor and P1 is energized →
  `unsafe` → `UNSAFE_STOP`. De-energizing first, or escalating, satisfies it.
- Closing isolation valves on a running pump → allowed, recorded as a
  dead-head consequence (pump overheat flag), not silently prevented.
- The fill (makeup) valve is manual (owner decision, 2026-09-24): open and
  close are separate actions. Left open while the leak is active, the PRV
  holds loop pressure while water on the floor keeps rising — a fill masks a
  leak. Closed again, the loop bleeds down. Refill does not fix a leak.
- Resetting the chiller without proven flow re-trips and is counted.

**Recovery criteria (server-verified at closeout, from model state):**
leak rate 0 (valve replaced or section isolated with lead pump on the
healthy path); loop holding fill pressure with the fill valve closed, through the stabilization window; air purged; flow ≥ proof
threshold; chiller running without active diagnostic; loop supply within
`±2 °F` of setpoint for a stabilization window (e.g. 20 simulated minutes);
no session-created operator overrides still active; no new failure (no
dead-head flag, no second trip during the window). Hall temperature/RH are
reported as trending, not pass/fail — halls lag, and a nominal reading at
one moment can be inconclusive (§5.3).

## 9. Closeout

The §5.4 schema, captured as structured fields: complaint and expected
baseline; safety/operational impact and decisions; root cause and competing
causes excluded **with evidence record ids**; corrective action and
authority; before/after observations and stabilization window; override
release confirmation; remaining risk and owner; PM task with acceptance
criteria; crew register paragraph; one-sentence executive register (no
invented dollar figures).

On submit the server runs the §8 criteria. All pass → `CLOSED`. Any fail →
`FAILED_VERIFICATION` with the exact failed criteria, then back to
`RECOVERING`. Citations must reference real record ids in this session.

**Debrief** (only after `CLOSED`, `UNSAFE_STOP`, or `ABANDONED`): the hidden
cause and timeline, the trainee's action log against it, safety decisions,
reset attempts, time to diagnosis and recovery. Weighted scoring is D.

## 10. API

| Method + path | Role | Notes |
|---|---|---|
| `POST /api/sessions?scenario_id=S-001` | technician | 409 if a session is active or BACnet owns 822 |
| `GET /api/sessions/active` | any | Trainee view: complaint, lifecycle, clock, action labels, notebook, evidence |
| `POST /api/sessions/{id}/actions/{action_id}` | per action | Observation + record id; failed prerequisite = 400, nothing changes |
| `POST /api/sessions/{id}/wait?minutes=N` | technician | 1–60 |
| `PUT /api/sessions/{id}/hypotheses` | technician | Validated references |
| `POST /api/sessions/{id}/closeout` | technician | Runs verification |
| `GET /api/sessions/{id}/debrief` | technician, instructor | 403 before a terminal state |
| `GET /api/sessions/{id}/truth` | **instructor** | Hidden cause, knobs, timeline |
| `POST /api/sessions/{id}/reset`, `/abandon` | **instructor** | Restores the 822 snapshot; logged |

**Auth change to review:** add an `instructor` role to `ROLES`. It is *not*
added to `AUTHORIZED_TO_COMMAND` (it sees truth; it does not command
points). Existing endpoints are unaffected.

Every mutating route: role check, input validation, state-preserving 4xx,
audit record in `operator_actions.jsonl` (action names only — no cause
text), backup-before-overwrite where it replaces files.

## 11. Hidden-truth boundary

- `truth.json` and `S-001.instructor.json` are read only by the kernel and
  the instructor routes.
- Trainee payloads, error messages, audit entries, and the Shift page never
  contain knob names, the leak location, the word "leak" from truth, or
  expected answers before a terminal state. (Observations can *show* water
  on the floor — that is evidence, not the answer.)
- Test: run a full scripted session and assert no trainee-facing response
  contains any forbidden token from the truth file before debrief.
- This is a local lab: the instructor file is in the repo, like
  `BREAK/sealed/`. The boundary is the API/UI, and that is what is tested.

## 12. Shift page (`/shift`)

Plain HTML/JS like the other pages: complaint and clock; lifecycle badge;
action buttons grouped as in §8 (disabled with the reason when a
prerequisite fails); "wait N minutes"; evidence list with pin buttons;
hypothesis notebook; closeout form; debrief after close. Links out to
`/tracer` and the chiller walk-up for BAS evidence. A banner states that
safety steps are simulated decisions, not procedures.

## 13. Testing (what "done" requires)

- **Physics self-tests** (§7) and a healthy-default regression.
- **Kernel self-tests:** lifecycle transitions only via actions/state;
  prerequisite failures change nothing; unsafe action → `UNSAFE_STOP`;
  refill-before-isolate re-leaks; reset loop counted; replay reproduces all
  state hashes.
- **API tests (live, like this week's):** role denials; malformed input;
  409 when BACnet owns 822; restart the server mid-session and continue;
  hidden-truth leak scan; close/abandon restores the 822 snapshot exactly.
- **End-to-end (Playwright):** the §5.5 acceptance path — two plausible
  investigations, at least one normal distractor result, safe isolation,
  repair, refill, purge, reset, wait, release, cited closeout → `CLOSED`;
  plus an unsafe branch (→ `UNSAFE_STOP`) and a premature closeout
  (→ `FAILED_VERIFICATION` naming the failed criteria).
- **Regression:** existing smoke test, editor suites, and the 15-fault
  Trouble Call still pass.

## 14. Rollback

Additive: new files, new routes, new role, new physics knobs with healthy
defaults. Ending or abandoning a session restores the pre-session 822
snapshot. Reverting the slice's commits removes sessions entirely; the only
lasting behavior change is chiller flow proof (§4), which lives in its own
commit so it can be reverted independently.

## 15. Delivery phases (one per session, §18.2)

1. **Physics** — §7 additions + self-tests + healthy regression. Exit: model
   reproduces S-001 symptoms from the cause knobs alone, via CLI.
2. **Kernel** — `scenario_kernel.py` + S-001 definition/truth files +
   replay. Exit: a scripted session reaches `CLOSED` and `UNSAFE_STOP` in
   self-tests; replay reproduces hashes.
3. **API + ownership** — routes, instructor role, locks, snapshot/restore,
   audit. Exit: live API tests incl. restart and leak scan.
4. **Shift page + acceptance** — `/shift` and the Playwright §5.5 run.
   Exit: end-to-end pass; checklist updated only for what was demonstrated.

## 16. Open items (need owner input before the phase that uses them)

- Leak-rate band and fill/PRV settings are synthetic assumptions; an
  instructor should confirm the S-001 sequence is safe under the simulated
  conditions (§6.1 of the direction doc).
- Whether the instructor role should be a separate login concept later
  (today roles are self-declared lab roles).
