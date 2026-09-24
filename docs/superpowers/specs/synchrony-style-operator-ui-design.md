# Synchrony-Style Operator UI — Design

- date: 2026-09-17
- status: **approved 2026-09-22** — see Decisions below. No implementation
  work specific to this approved UI phase has started (the repo's dirty
  tree has unrelated in-progress Niagara-vocabulary work — schedules,
  wire sheets, Px pages, platform admin, `/tracer`'s Setpoints tab — none
  of it part of this spec).
- supersedes: nothing; extends `docs/superpowers/specs/2026-09-15-bacnet-822-server-design.md`
  (the BACnet server) and its Companion Milestone section (fault injection, W1-W6)
- source: J's 32-section brief, verified line-by-line against the actual codebase
  before anything here was written down

## How To Read This Document

J's brief is exhaustive and prescriptive by design — page hierarchy, terminology,
column names, example screens. This document does not re-litigate those choices.
Its job is the one J asked for in Section 32: **inspect the repo, and say
precisely which requested thing already exists, which needs new backend work,
and which should be a labeled placeholder** — then lay out pages, data model,
roles, test plan, risks, and a phased sequence on top of that ground truth.

Every claim below was checked against running code or live data during this
session, not assumed from the brief's examples. Several of the brief's example
values and names do not match this codebase exactly (wing names, FCU point
names, the role list) — each mismatch is called out where it occurs, with a
recommendation, not silently corrected.

---

## 1. The One Decision That Shapes Everything Else

Section 10 of the brief says, twice, in capitals: **"DO NOT bypass existing
BACnet semantics."** It asks for a real Priority Array 1-16, a real
Controlling Priority, a real Relinquish Default, and a Release that "writes
Null to priority 8" so "Present Value resolves to the next active priority,
typically the controller loop at priority 16."

That is not decorative language — it describes exactly how `bacnet822.py`
already works. But it directly conflicts with a decision made earlier this
build cycle: J chose the **decorative, file-based command panel** over a
browser-to-BACnet client specifically so fault-injection reps (`bas_sim.py
--knob ...`) would work without the BACnet server running — a mode the two
are mutually exclusive in today (`bas_sim.py` refuses to drive 822 while
`bacnet822.py` holds the lock, and vice versa).

Verified directly in `frontend/bas_api.py`'s `command_point()`: today's web
override is **one flat `{value, reason, operator, role, timestamp}` slot per
point** in `operator_overrides.json`. There is no priority concept at all.
The only place a real 16-slot BACnet priority array exists is inside
`bacnet822.py`'s own bacpypes3 objects — live only while that process runs.

**Three ways to resolve this, and the choice changes a lot of downstream
work:**

**Option A — Priority-aware file store (recommended).** Replace the flat
override with a per-point 16-slot array in `operator_overrides.json` itself:
`{"MAU04_CHW_VLV_CMD": {"priority": [null, null, ..., 45.0, null, ..., null]}}`
(index 7 = priority 8). `bas_sim.py`'s override resolution becomes "lowest
non-null wins," matching BACnet's own rule, and the control loop's own output
always lands at index 15 (priority 16) — the same convention `bacnet822.py`
already uses. This gives every UI screen honest priority-array behavior
**in both modes**, reps and live-BACnet, with one shared mental model. Cost:
a real, non-trivial change to `bas_sim.py`'s override plumbing and to every
existing consumer of `operator_overrides.json` (`bas_api.py`'s command/release
endpoints, `model822.py`'s `ov()` helper).

**Option B — Real BACnet client in `bas_api.py`.** The web app becomes a
bacpypes3 client (reusing `bacnet822-client.py`'s proven `connect`/`locate`
code), doing genuine ReadProperty/WriteProperty over the wire. Fully honest
— zero simulated priority logic — but **only works while `bacnet822.py` is
running**, which reopens the exact tension J resolved before ("I need the
decoration... that's how I'll get my reps in"). This was the design I
proposed earlier in this session and J explicitly redirected away from.

**Option C — Cosmetic priority display only.** Keep the single-value
override, but have the UI *show* "Priority 8 (Manual Operator)" as a fixed
label whenever an override is active, and "Priority 16 (Control Loop)"
otherwise. No real array, no real resolution rule. Fastest, but it is
exactly the kind of decoration-presented-as-mechanism the rest of this whole
build has deliberately avoided, and it will teach the wrong instinct — the
same failure mode as showing a fabricated diagnosis instead of derived
symptoms.

**Recommendation: Option A.** It is more backend work than C, but it is the
only option that makes Section 10's override dialog, Section 9's priority
array display, and the reps-mode fault-injection workflow all true at the
same time, in both operating modes. Flagging this as the first thing to
confirm before anything else in this spec is built — it changes the data
model for every commandable point on every page.

---

## 2. Existing Architecture — What Is Actually Here

| Layer | File | Confirmed |
|---|---|---|
| Physics | `simulator/model822.py` (613 lines) | Coupled thermal model, knob-based fault injection, `sensor_offset` knob already exists (see §4) |
| Batch simulator | `simulator/bas_sim.py` (515 lines) | `--knob EQUIPMENT:KEY=VALUE` (built this session), `--fault` (older, hospital/office only), lock-aware 822 observe/drive split |
| BACnet server | `open-source-stack/bacnet822.py` (746 lines) | 2 routers, 50 controllers, 448 objects, 162 commandable, real priority arrays, audit logging |
| BACnet test client | `scripts/bacnet822-client.py` (174 lines) | Proven `connect`/`locate`/read/write/release — the reusable piece for Option B if ever chosen |
| Web API | `frontend/bas_api.py` (693 lines) | FastAPI, file-based state (`latest_points.json`, `operator_overrides.json`, `alarms.jsonl`, `trends.csv`, `operator_actions.jsonl`) |
| Web UI | `frontend/static/tracer.html` (451 lines) | Tracer-SC-era operator view: connect screen, device tree, 5 tabs (Summary/Points/Trends/Alarms/**Setpoints**, added this session), type-aware command controls |
| Other UIs | `metasys.html` (752), `niagara.html` (829) | Hospital/office only; `niagara.html` has a working portfolio-tree pattern worth studying, not reusing directly (different scope) |
| Fault design | `docs/superpowers/specs/2026-09-15-bacnet-822-server-design.md`, Companion Milestone (W1-W6) | **This is the authority for Sections 21-23 of J's brief.** Not re-derived here — referenced. |

**This document adds a UI layer. It does not replace or duplicate any of the
above.** Per Section 30 of the brief, one Building 822 state, every screen
reads and writes it.

## 3. Existing APIs (Full Inventory)

Confirmed via direct grep of `bas_api.py`, all 20 routes:

```
GET  /                              GET  /metasys           GET  /niagara
GET  /api/points                    GET  /api/points/{name} GET  /api/alarms
GET  /api/trends/{name}             GET  /api/scenarios     GET  /api/equipment
GET  /api/roles                     GET  /api/operator-actions
POST /api/trouble-calls/new         GET  /api/trouble-calls/active
POST /api/trouble-calls/{id}/diagnose   GET  /api/trouble-calls/history
POST /api/points/{name}/command     POST /api/points/{name}/release
POST /api/run/{scenario}            GET  /api/topology      GET  /api/chiller/822
GET  /tracer
```

**`/api/points` and `/api/points/{name}` already return `states`** (added
this session) — Section 9's Points table and Section 6's dropdowns need no
new field for multi-state points.

**The existing trouble-call system (`/api/trouble-calls/*`) is a different
mechanic than Sections 21-22 need**, and this matters: it opens a ticket,
runs `bas_sim.py --fault <id>` (the **point-perturbation** fault library —
`data/input/fault_library.json`, hospital/office only, never wired to 822),
and grades a **multiple-choice guess** (equipment + category). It has no
concept of field inspection sub-actions, repair actions, or a physics
recovery loop. Section 31's acceptance scenario — trend, check overrides,
field-inspect filter/belt/CHW temps/strainer, clean strainer, watch recovery,
four-part closeout — **cannot be built on this endpoint set**. It needs new
endpoints, built on the `--knob` mechanism already proven this session, not
a retrofit of the multiple-choice grader. The existing system's ticket
lifecycle (open/active/diagnose/history, one file-backed active ticket) is a
reasonable *pattern* to imitate for the new one, not code to extend.

## 4. What The Brief Assumes That Does Not Match The Data

Corrected here so later sections build on fact, not the brief's example
values:

- **Wings are A/B/C/D, not "A West/A East/B Wing/C Wing."** Confirmed:
  `WINGS = ("A","B","C","D")` in both `model822.py` and
  `gen-822-inventory.py`, 3 floors, 3 rooms each, plus a separate LOBBY zone
  served by MAU-13. Section 14's Areas hierarchy should use the real
  4-wings-plus-lobby structure, not invented wing names.
- **FCUs have no discharge air temperature, no humidity sensor, and no "air
  valve"** — verified the full 7-point set:
  `SPACE_TEMP, SPACE_TEMP_SP, FAN_MODE, FAN_STATUS, CHW_VLV_CMD, CHW_VLV_POS,
  CFM`. Section 5's Spaces table asks for "Discharge Air Temperature,"
  "Air Valve Position," and implies per-space humidity — none exist for an
  FCU (ventilation and dehumidification are the MAU's job upstream, per
  `sequences/FCU-822-SOO.md`). Recommendation: Spaces columns map to
  `CHW_VLV_POS` where "Air Valve Position" is asked for, and the Space
  Detail's "Humidity if available" is honestly **not available** for an FCU
  zone — only at the hallway sensor and MAU level.
- **Occupancy does not exist anywhere** — no point, no physics input.
  Confirmed by grep across `model822.py` and `points.json`. This matches
  W3 in the fault-injection companion spec, already flagged as unbuilt.
  Section 13 (Schedules) and Section 14 (Areas) must ship as UI/data-model
  only, explicitly labeled non-functional, exactly as J's own brief already
  anticipates ("clearly label physical occupancy integration as pending").
- **The role list doesn't match.** Live roles (`ROLES` in `bas_api.py`):
  `viewer, operator, technician, vendor, admin, security reviewer`. The
  brief proposes `Operator, Technician, Administrator, Training Instructor`.
  `vendor` and `security reviewer` belong to a different exercise in this
  lab (not BAS operator training) and must not be broken. Recommendation:
  add `training instructor` as a **new** role; map the brief's
  `Administrator` onto the existing `admin`; keep `vendor` and
  `security reviewer` untouched and simply outside this UI's concern. See
  §8 (Role Model).
- **Sensor bias partially already exists.** `sensor_offset` is a real knob,
  read in both the MAU and FCU loops (`model822.py:433,490`), applied to the
  *displayed* SAT/space-temp reading. Section 23's second example
  ("Physical SAT 55.2°F / Displayed 59.1°F") is **already possible** via
  `--knob MAU04:sensor_offset=3.9` — it just isn't exposed anywhere in the UI
  or the field-inspection surface yet.
- **Actuator position feedback does not exist.** Confirmed:
  `pts[..._CHW_VLV_POS] = round(valve, 1)` and `..._OA_DMPR_POS] =
  round(damper, 1)` — POS is hard-set equal to CMD, always, everywhere.
  Section 23's first example (slipped linkage: command 100%, physical 31%,
  feedback 96%) **cannot happen today**. This needs a new knob (e.g.
  `actuator_slip_pct`) and a code change to both the MAU and FCU valve/damper
  assignment lines — small, well-scoped, but real new physics work, not a UI
  task.

## 5. Existing Reusable UI Components

From `tracer.html`, confirmed working and unit-tested this session (15
assertions against real point shapes, run in `node`):

- `valueControlHtml(p, id)` — type-aware control (On/Off select for BO,
  named-state select for MV, number+units for everything else). **Reuse
  directly** for Points, Spaces, Equipment Detail, and the Override dialog.
- `currentValueLabel(p)` — human-readable current value (`On`/`Low`/`65.4 F`
  instead of raw `1`/`2`/`65.4`). Reuse for every table in the new UI.
- `pointOptionLabel(p)` — self-describing dropdown option text. Reuse in
  Points page filtering.
- The connect flow (`S.node`/`S.role`/`S.op`, `/api/topology?from=`) already
  encodes "what you see depends on where you plug in." Section 3's global
  nav / Section 20's tree need to decide whether to **keep** that
  connection-scoping model (matching real BACnet supervisory practice) or
  **drop it** for an always-fully-visible Synchrony-style app (matching how
  Synchrony itself behaves once logged in — it doesn't ask you to pick a
  router first). Recommendation: drop the connect-gate for this new UI
  (log in with a role, see the whole building, matching Synchrony), and
  preserve `/tracer`'s existing connect-scoped experience unchanged as the
  separate "practice reading a real BACnet supervisor" exercise it already
  is. Building both into one page would blur two different lessons.
- `wireCommandPanel`/`wireSetpoints` (this session's work) — the
  command/release network call, 403-handling, and post-command refresh
  pattern generalizes directly to every new page with a command control.

## 6. Data Model Changes Required

1. **Priority-aware override store** (§1, Option A) — the load-bearing
   change. Touches `operator_overrides.json`'s shape, `bas_sim.py`'s `ov()`
   resolution, `bas_api.py`'s command/release endpoints.
2. **`actuator_slip_pct` knob** (§4) — new knob in `COIL_KNOB_DEFAULTS`,
   applied where `_CHW_VLV_POS`/`_OA_DMPR_POS` are currently hard-mirrored to
   command.
3. **A "field measurement" query path** — Section 5's core requirement
   (displayed value vs. physical truth) needs a way to ask the model for the
   *true* value at a point independent of `sensor_offset`. Today `t_lvg_f`
   (physical) and `t_lvg_f + offset` (displayed) both exist inside
   `step_822()`'s local scope but only the offset version is ever written to
   `pts`. Needs a small, additive change: also emit the pre-offset value
   under a separate key (e.g. `_SAT__PHYSICAL`) when `sensor_offset != 0`,
   or a dedicated endpoint that recomputes it on demand. Recommendation:
   the dedicated endpoint — it keeps `points.json`'s schema and the BACnet
   object count untouched, and "physical truth" should never be visible on
   an ordinary Points/Spaces read, only through an explicit Field
   Inspection action (matching Section 22's "Inspection must not equal
   repair" discipline).
4. **Areas/Schedules data model** — new, additive JSON (e.g.
   `data/input/areas.json`, `data/input/schedules.json`), scoped to the real
   4-wings-plus-lobby structure. UI + storage only; no physics linkage until
   occupancy exists in the model (W3).
5. **Trouble-call v2 ticket schema** — extends the existing ticket pattern
   (`ticket_id`, `opened_at`, fault reference) with: field-inspection log
   (action, result, timestamp), repair actions taken, override state at
   open/close, and the four-part closeout (`fault`, `evidence`,
   `corrective_action`, `verification`, `preventive_action` — matching
   Section 31 exactly). New file, new endpoints; does not touch the
   existing hospital/office trouble-call system.
6. **Training Instructor ground truth view** — Section 26 requires this role
   see the hidden fault/knob state trainees must not. That state already
   exists (it's just the `--knob` arguments used to open the ticket); this
   is a read endpoint gated by role, not new physics.

## 7. Page Hierarchy And Screen-By-Screen Status

Legend: ✅ exists and reusable · 🔧 needs backend work (scoped above) · 🧱
placeholder only (say so on screen, per Section 24's own instruction)

| Section | Page | Status | Notes |
|---|---|---|---|
| 2 | Global nav bar | 🔧 new | Outdoor Conditions reads `weather_822.json`/model output (data exists); Alarms badge reads `/api/alarms` (exists) |
| 4 | Building Summary | 🔧 new | Every number on it is a re-aggregation of `/api/points`, `/api/alarms`, `/api/topology` — no new data, new page |
| 5 | Spaces | 🔧 new page, ✅ data mostly exists | Per §4: no discharge-air-temp/humidity/air-valve on FCUs — map honestly, don't invent |
| 5 | Space Detail (BAS vs physical) | 🔧 needs data model #3 | The headline feature of the whole brief; do not ship without it |
| 6-7 | Equipment / Equipment Detail | ✅ mostly, 🔧 process schematic | Point grouping (Status/Temps/Airflow/Hydronic/...) is a display concern only; process diagram is new original SVG (see note below the table) |
| 8 | Systems | 🔧 new, thin | "CHW System → MAU01..06" is a straight readout of `equipment.json`'s `parent`/`trunk` fields, already present |
| 9 | Points | ✅ mostly | Table + filters is new UI over an existing, already-complete API; Priority Array block needs data model #1 |
| 10 | Overrides + All Items in Override | 🔧 needs data model #1 | The other headline feature; §1 is the prerequisite decision |
| 11 | Alarms | ✅ data, 🔧 UI | `/api/alarms` exists; Acknowledge/Comment are new — need new fields in `alarms.jsonl` or a companion file |
| 12 | Data Logs | ✅ data, 🔧 UI + one new field | `trends.csv` already IS the historical log; "Create Data Log" as a concept (interval, active/disable) needs a small config file — the underlying capture already runs every simulator step |
| 13 | Schedules | 🧱 placeholder | No occupancy in physics (§4). Build the UI and data model; every screen states "Training Module — Not Yet Modeled" for behavioral effect, per Section 24's own rule |
| 14 | Areas | 🧱 mostly placeholder | Grouping/display: real, using actual wings. Occupancy-driven behavior: placeholder, same reason as Schedules |
| 15 | Reports | 🧱 mostly placeholder | Points/Override/Alarm reports are straightforward exports of existing data (real). Site/VAS/Chiller reports: placeholder |
| 16 | Alarm Configuration | 🔧 new | `alarm_rules.json` already has the right shape (point/condition/priority) — needs a write path + audit log entry per change |
| 17 | Tools | 🔧 new page, mixed | Operator Actions (✅ `/api/operator-actions` exists), Active Overrides (🔧 #1), Communication Status (✅ `/api/topology`), BACnet Network View (✅), Troubleshooting Mode → Section 21/22 of the brief, see §9 below (🔧 new) |
| 18 | Installation | ✅ data-complete | `/api/topology` already has routers/trunks/devices/online-state — this page is a read-only view of data that already exists in full |

**Equipment Detail process schematic (Section 7 of the brief):** an original
SVG flow diagram per equipment type — for an MAU, Outdoor Air → Damper →
Filter → Cooling Coil → Supply Fan → Supply Air, each stage annotated with
its live value, grouped into the eight operator categories the brief
specifies (Status/Temperatures/Airflow/Hydronic/Commands/Feedback/Setpoints/
Diagnostics). No new data — every value already exists in `/api/points`;
this is a rendering task (map points to diagram positions and category
groups), plus one hand-drawn schematic asset per equipment type (MAU, FCU,
CHW loop). Satisfies Section 27's "graphics should be original schematic
drawings" directly.
| 19 | Devices | ✅ data mostly | Device instance/MAC/network from `bacnet822.py`'s `build_tree()` — **not currently exposed over HTTP**, needs one new endpoint that calls `build_tree()` and serializes it (small; `build_tree()` is a pure function already, no new physics) |
| 20 | Navigation Tree | 🔧 new | Real hierarchy exists in `equipment.json`; Favorites needs new client state — recommend `localStorage`, per-browser, not server-persisted (no user accounts to hang it on yet) |
| 21-22 | Trouble Call / Field Mode | 🔧 new, builds on `--knob` | This is the Companion Milestone (W1-W6) UI. Do not re-derive the fault philosophy here — implement against that spec |
| 23 | BAS vs Field truth | 🔧 data model #2, #3 | The single most technically important item in the whole brief |
| 25 | Auditability | ✅ mostly | `operator_actions.jsonl` schema already matches most of what's asked; extend for new action types (schedule/config/repair), don't replace |
| 26 | Roles | 🔧 small addition | See §4 and §8 |

## 8. Role Model

Reconciling the brief's four roles against the six that exist:

| Brief's role | Maps to | Notes |
|---|---|---|
| Operator | `operator` (exists) | View, ack alarms, temporary pre-approved overrides, schedules |
| Technician | `technician` (exists) | Already the role `_require_command_role` authorizes for writes |
| Administrator | `admin` (exists) | Config, users, alarm config, installation |
| Training Instructor | **new role**, add to `ROLES` | Sees hidden fault/knob ground truth (data model #6); starts/stops scenarios; reset building |
| — | `vendor`, `security reviewer` | Unrelated to this UI. Do not touch, do not surface in this app's role picker. |

Trainee-facing roles (`operator`, `technician`) must never receive the
ground-truth fields from data model #6 in any API response they can reach —
this is a server-side filter, not a UI hide, matching Section 26's own
"MUST NOT see" language.

## 9. Troubleshooting Integration

Authority: `docs/superpowers/specs/2026-09-15-bacnet-822-server-design.md`,
Companion Milestone, especially the governing principle already agreed
there:

> The fault injector breaks the cause. Physics creates the symptoms. BACnet
> exposes the evidence. The operator diagnoses the evidence and proves the
> repair.

Section 21-22 of this brief is that spec's **W1 (physical/BAS truth), W2
(field action surface), W4 (difficulty tiers), W5 (closeout)** made
concrete as UI screens, plus a scenario ticket lifecycle modeled on the
existing trouble-call system's *pattern* (not its code — see §3). W6 (AI
authority boundary: read/propose/scenario-authority, no direct write) is
unaffected by this UI work and stays a separate concern for whichever LLM
eventually plays that role.

**Level 1/2/3 difficulty** (single fault / fault+distractors /
interacting faults) is new — nothing today distinguishes difficulty tiers.
Recommend encoding it as metadata on the scenario definition (which knobs
fire, real vs. decoy field-inspection findings), not as separate code paths.

## 10. Test Plan

Following this repo's own convention — no pytest, `--self-test` flags and a
smoke-test script — every new backend surface gets:

- A `--self-test` on any new pure-Python module (matching `model822.py`,
  `gen-822-inventory.py`, `bacnet822.py`).
- New endpoints added to `scripts/run-smoke-test.sh` only for offline,
  fast checks (schema/self-test style) — never anything requiring a running
  server or the ~1-minute acceptance cadence, matching the existing rule
  that keeps the smoke test fast.
- **Every new JS rendering function gets the same node-based assertion
  treatment used this session** for `valueControlHtml`/`currentValueLabel`
  — extract the script, `node --check` for syntax, then real assertions
  against realistic point shapes before calling any page done. This caught
  real bugs before they reached a browser; it should be standard for every
  phase, not a one-off.
- **The Section 31 acceptance scenario, verbatim, is the final integration
  test for Phase H.** It should be scripted (not just eyeballed) once the
  full workflow exists: alarm → equipment → trend → override-check → field
  inspection → repair → recovery → closeout, asserting the closeout record's
  four fields are populated and non-empty.
- Every phase's checkpoint (per §11 below) re-runs the full existing smoke
  test and confirms hospital/office and the existing `/tracer`/`/metasys`/
  `/niagara` pages are unaffected, per the brief's own Section 30 rule.

## 11. Risks

1. **Scope.** This is, honestly, several weeks of work fully built — 8
   phases, ~20 screens, a new data-truth layer, a new priority-array engine,
   a new trouble-call system. J's own Section 30 already breaks it into
   phases; §12 below adopts that breakdown directly rather than proposing a
   different one. Recommend each phase become its **own** implementation
   plan (via `writing-plans`) once approved here, not one giant plan — this
   spec stays the single source of truth for the whole vision, per Section
   32's request for one file.
2. **The Option A/B/C decision (§1) blocks Phase C entirely** and touches
   data Phase B's Points page displays. It should be confirmed before Phase
   B starts, not deferred to Phase C, or Phase B's Points page will need
   rework.
3. **Physics changes (actuator slip, sensor-bias exposure) are the riskiest
   line items** — they touch `model822.py`, which has an existing,
   passing, cited-in-four-places self-test (`458 points` assertion) and
   feeds the already-proven BACnet acceptance test. Any change here must
   re-run that acceptance test, not just the self-test, per this repo's own
   established discipline this session.
4. **Two UIs, one philosophy, different scopes.** `/tracer` is deliberately
   "what you see depends on where you connect" (real BACnet supervisory
   practice). This new UI is deliberately "log in, see everything"
   (Synchrony-style operator practice). Keeping them as two honestly
   different exercises (§5) is a decision, not an oversight — mixing them
   would teach a wrong lesson about how either system actually works.
5. **Trane-identity risk is low but real.** The brief is explicit and
   correct about avoiding logos/proprietary graphics/false claims; the one
   place to watch is terminology drift into anything that reads as a
   verbatim Trane screen layout rather than the *publicly documented
   information architecture* the brief asks for. Recommend one explicit
   disclaimer string, matching the pattern already used in `docs/bacnet-822.md`
   §1, rendered once on first load of the new UI.

## 12. Implementation Sequence

Adopting J's own Section 30 phase breakdown directly — it is already
correctly ordered (shell → operator core → control workflow → evidence →
operations → supervisory → technician → training). Two changes to the
stated order, both load-bearing:

- **The §1 decision (Option A/B/C) must be confirmed before Phase B**, not
  during Phase C, because Phase B's Points page needs to know its own data
  shape.
- **Data model items #2 and #3 (actuator slip, field-measurement path)
  land in Phase A**, not B — assigned explicitly, not left as an either/or.
  Both are physics/backend-only with no UI, so they belong in the phase
  that has no page dependencies yet, and land quietly so the mechanism is
  exercised and proven for weeks before Phase H's training integration
  puts real weight on it.

**Phase table (confirmed by J, 2026-09-22).** Reconstructed from §7's
page-hierarchy status table and §8's role model — not transcribed from
Section 30 of the original brief, which is not saved as a file anywhere
in this repo. J reviewed and confirmed as-is.

| Phase | Name | Scope | Prerequisites | Completion boundary |
|---|---|---|---|---|
| **A** | Shell | Drop the connect-gate (Decision 2), login/role picker incl. new `training instructor` role, global nav bar (§2), nav-tree skeleton (§20). Backend-only, no-UI groundwork: `actuator_slip_pct` knob, field-truth query path (data model #2/#3). | None — first phase | App loads, role-gated, empty content pages route correctly; new knob + field-truth endpoint pass `--self-test`; existing smoke test + BACnet acceptance test still pass |
| **B** | Operator core | Building Summary (§4), Spaces + Space Detail incl. BAS-vs-physical (§5, consumes Phase A's field-truth endpoint), Equipment/Equipment Detail + process schematic (§6-7), Systems (§8), Points incl. Priority Array block (§9) | §1 decision (Option A) backend must land here — the priority-array store in `operator_overrides.json`, since Points' display depends on it | The four core "look at the building" pages render live data correctly for all four confirmed roles; Points page shows real priority arrays |
| **C** | Control workflow | Overrides page + "All Items in Override" (§10) — the write path on top of Phase B's priority-array backend | Phase B's priority-array store | Operator can place/release a priority-8 override through the UI and see it resolve correctly against the control loop (priority 16, synthesized not persisted) |
| **D** | Evidence | Alarms UI incl. Acknowledge/Comment (§11), Data Logs UI + "Create Data Log" config (§12), Auditability extension for new action types (§25) | None new | Alarm ack/comment and data-log creation round-trip through `alarms.jsonl`/config file; `operator_actions.jsonl` covers new action types |
| **E** | Operations | Schedules (§13, placeholder — no occupancy model), Areas using real 4-wings-plus-lobby (§14, Decision 3), Reports (§15), Alarm Configuration write path (§16), Tools minus Troubleshooting Mode (§17) | Areas structure decision (already made) | Placeholder pages clearly labeled "Training Module — Not Yet Modeled"; alarm config changes get audit-logged; reports export real data where data exists |
| **F** | Supervisory | Installation (§18), Devices + new `build_tree()` endpoint (§19), BACnet Network View / Communication Status (§17 remainder) | None new | Devices/Installation pages show live BACnet topology; no placeholder content (§7 marks this section data-complete) |
| **G** | Technician | Trouble Call / Field Mode (§21-22, new ticket system built on `--knob`, not the old fault-library grader), BAS-vs-Field-truth UI exposure (§23), Troubleshooting Mode in Tools | Phase A's field-truth endpoint; Phase C's override UI (field mode needs an override-check step) | Section 31's acceptance scenario runs start-to-finish through the UI, closeout record's four fields populate |
| **H** | Training | Training Instructor ground-truth view (§8, §26), role finalization, final integration pass | All prior phases | Section 31 acceptance scenario scripted as an automated check (§10 Test Plan), not just eyeballed; hospital/office and existing `/tracer`/`/metasys`/`/niagara` confirmed unaffected |

Each phase, on completion, gets its own `writing-plans` document, executed
the way every prior task this session was: TDD where there's a pure
function to test, real assertions (not just syntax checks) for new JS, the
existing smoke test re-run and passing, and the BACnet acceptance test
re-run whenever `model822.py` is touched.

---

## Decisions (confirmed by J, 2026-09-22)

All five recommendations confirmed as written:

1. **§1 — Option A**, priority-aware file store. Load-bearing decision —
   `operator_overrides.json` becomes a real 16-slot priority array,
   `bas_sim.py`'s override resolution becomes "lowest non-null wins."
   Priority 16 (the control loop's own output) is **synthesized on read,
   never persisted** — matching today's `ov()` behavior
   (`simulator/model822.py:442-445`), which already returns the computed
   fallback in-memory and never writes it back. Only explicit operator/
   external commands (priorities 1-15, primarily 8) get written into
   `operator_overrides.json`. This keeps the override file a record of
   *interventions*, not a second continuously-updated mirror of
   simulator state. Touches `bas_api.py`'s command/release endpoints and
   `model822.py`'s `ov()` helper. Must land before Phase B's Points page
   is built.
2. **§5 — drop the connect-gate** for the new UI. Log in with a role, see
   the whole building (Synchrony-style). `/tracer` keeps its existing
   connect-scoped flow unchanged as the separate "read a real BACnet
   supervisor" exercise.
3. **§4 — Areas** use the real 4-wings-plus-lobby structure
   (`WINGS = ("A","B","C","D")` + LOBBY/MAU-13), not the brief's invented
   wing names.
4. **§10 — Favorites** persisted in browser `localStorage`, per-browser,
   revisit only if a real login/account system gets built.
5. **§12 — execution model confirmed**: this spec stays the single source
   of truth for the whole vision. Each phase (A–H) gets its own
   `writing-plans` document at the time that phase actually starts, not
   all up front.

**Next action:** write the Phase A implementation plan. Phase A carries
data model items #2 (`actuator_slip_pct` knob) and #3 (field-truth query
path), landed quietly with no UI, so the mechanism is proven well before
Phase H's training integration.
