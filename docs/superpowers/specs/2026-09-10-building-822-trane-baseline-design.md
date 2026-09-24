# Building 822 — Trane Controls Baseline (Design Spec)

**Date:** 2026-09-10
**Status:** Draft for review
**Scope:** Spec 1 of 3 — healthy baseline only
**Target:** `GP-SECLAB/target-application/BAS-SIM`
**BUILD filing:** BP-009 (to be promoted through `BUILD/1-buildplanning/`)

---

## 1. Purpose

Build a synthetic Trane-controlled barracks — "Building 822" — that behaves
correctly when healthy, so the operator can establish what a working system
looks like before anything is broken against it.

The driving requirement, in the operator's words: *"just like when I plug my
work laptop into the building and receive readings — plugging into and logging
in and seeing what's going on."* Connection, authentication, navigation and
**response** are the deliverable. Faults are not.

This is round one of three. It exists to produce a trustworthy baseline; spec 2
turns that baseline into a fault surface.

### Why a new engine

`simulator/bas_sim.py` is open-loop and stateless. `normal_value()` generates
every point independently as `midpoint ± 12% jitter`; no point influences any
other. `operator_overrides.json` is a display-layer substitution in
`frontend/bas_api.py` — the simulator never reads it, so commanding a valve
changes one readout and moves nothing else. Scenarios are hardcoded per-point
formulas in an `if` chain.

That is adequate for the hospital and office, which are scripted
fault-diagnosis labs. It cannot satisfy "see how it responds." Building 822
therefore gets a coupled state model, scoped so the committed hospital and
office behavior is untouched.

---

## 2. Non-goals

Explicitly out of scope for spec 1:

- **Faults of any kind.** All model parameters ship at healthy values.
- **Tracer TU direct-connect service-tool mode.** Deferred to spec 3, gated
  deliberately — it mirrors the operator's real-world access gate.
- **Persistent degraded-building campaign mode.** Candidate for a later spec;
  not committed.
- **Changes to hospital or office behavior.** The existing engine path stays
  exactly as committed. No regression surface.
- **Niagara changes.** Niagara remains hospital-only. 822 gets a Tracer front
  end and nothing else.
- **Engineering-grade thermodynamics.** The model is teaching-grade: numbers
  must move correctly and for the right reasons. It is not a load calculation
  and must never be described as one.

---

## 3. Safety and data boundary

Inherits the repo boundary in `safety/data-boundary.md` and `README.md`, with
one addition specific to this build.

- Everything binds `127.0.0.1`. Local lab, not a service.
- All identifiers fictional. No real building numbers, IPs, MAC addresses,
  controller IDs, usernames, or base topology.
- **Chiller nameplate:** the model family (Trane RTAC, air-cooled helical
  rotary, ~155 nominal tons) and the public IOM reference (`RTAC-SVX01M-EN`)
  are used because they are published product literature and make the
  simulation faithful. The real unit's **serial number, CRC, and full option
  code string are deliberately excluded** — they identify one specific machine
  at a federal facility and add nothing to the simulator. 822's chiller carries
  a fictional serial.
- Wing-to-unit numbering is fictional and clean (`MAU-01`…`MAU-13`), by
  instruction. Real field numbering has been inconsistent across sources and
  must not be treated as design truth.

---

## 4. Inventory and topology

### 4.1 Schema change

`data/input/equipment.json` gains a `networks` list, and every device gains a
nullable `parent`. Hospital and office entries take `parent: null` and are
otherwise unmodified — the change is additive and backward-compatible.

```json
"networks": [
  {"id": "ETH-822",   "type": "ethernet",    "facility": "barracks822", "parent": null},
  {"id": "MSTP-01-A", "type": "bacnet_mstp", "facility": "barracks822", "parent": "SC-822-01"},
  {"id": "MSTP-01-B", "type": "bacnet_mstp", "facility": "barracks822", "parent": "SC-822-01"},
  {"id": "MSTP-02-A", "type": "bacnet_mstp", "facility": "barracks822", "parent": "SC-822-02"},
  {"id": "MSTP-02-B", "type": "bacnet_mstp", "facility": "barracks822", "parent": "SC-822-02"}
]
```

A new facility entry is appended:

```json
{"id": "barracks822", "name": "Building 822 (synthetic barracks)", "floors": 3,
 "wings": ["A", "B", "C", "D"], "critical_spaces": []}
```

### 4.2 Devices

| Layer | Devices | Count |
|---|---|---|
| Supervisory | `SC-822-01`, `SC-822-02` — Tracer SC+, on `ETH-822` | 2 |
| Field trunks | `MSTP-01-A/B`, `MSTP-02-A/B` — BACnet MS/TP | 4 |
| Makeup air | `UC400-MAU-01` … `UC400-MAU-13` | 13 |
| Room level | `UC-FCU-<wing><floor><nn>` — 3 per wing-floor | 36 |
| Hallway sensing | `HALL-<wing><floor>` — temp + RH | 12 |
| CHW service entrance | `CHW-822` — pumps `P-1`/`P-2`, strainer, headers | 1 |
| Chiller | `CHILLER-RTAC-822` — **off-tree**, fictional serial | 1 |

### 4.3 Assignment

Deterministic and fictional:

| Wing | MAUs (one per floor) | FCUs |
|---|---|---|
| A | `MAU-01`, `MAU-02`, `MAU-03` | `A101`–`A303`, 9 |
| B | `MAU-04`, `MAU-05`, `MAU-06` | `B101`–`B303`, 9 |
| C | `MAU-07`, `MAU-08`, `MAU-09` | `C101`–`C303`, 9 |
| D | `MAU-10`, `MAU-11`, `MAU-12` | `D101`–`D303`, 9 |
| Lobby | `MAU-13` | — |

Trunk membership, balanced:

| Trunk | Members |
|---|---|
| `MSTP-01-A` | `UC400-MAU-01` … `-06` |
| `MSTP-01-B` | 18 wing A/B FCU controllers |
| `MSTP-02-A` | `UC400-MAU-07` … `-13` |
| `MSTP-02-B` | 18 wing C/D FCU controllers |

### 4.4 Points

Naming follows the existing convention (`AHU_OR1_SAT` → `MAU01_SAT`).

| Group | Points each | Instances | Total |
|---|---|---|---|
| MAU | SAT, SAT_SP, SA_RH, EAT, EA_RH, FAN_CMD, FAN_STATUS, OA_DMPR_CMD, OA_DMPR_POS, CHW_VLV_CMD, CHW_VLV_POS, COIL_DT | 13 | 156 |
| FCU | SPACE_TEMP, SPACE_TEMP_SP, FAN_MODE, FAN_STATUS, CHW_VLV_CMD, CHW_VLV_POS | 36 | 216 |
| Hallway | TEMP, RH | 12 | 24 |
| CHW entrance | ENT_SUP_TEMP, ENT_RET_TEMP, BLDG_DT, BLDG_DP, STRAINER_DP, P1_CMD, P1_STATUS, P2_CMD, P2_STATUS | 1 | 9 |
| Device comm | status per SC and per trunk | 6 | 6 |
| Chiller (off-tree) | EVAP_ENT_TEMP, EVAP_LVG_TEMP, EVAP_LVG_SP, AMBIENT_TEMP, PCT_CAPACITY, CKT1_STATUS, CKT2_STATUS, CKT1_FAN_STATUS, CKT2_FAN_STATUS, ACTIVE_DIAG | 1 | 10 |
| | | **Total** | **421** |

`FAN_MODE` is a multistate value (`Off/Auto/Low/Mid/High`), which the existing
point schema does not yet express — `type: "MV"` with a `states` list is added.

**Note for review:** an earlier estimate in conversation said ~200, then ~350.
Counted properly it is 421. This is not a performance problem — at roughly 68
bytes per point-step, a 12-step run produces ~350 KB of `trends.csv` — but
`trend_plan.json` intervals should be used deliberately: MAU diagnostic points
at 60s, FCU space temps and valve positions at 300s. If a leaner inventory is
preferred, dropping `FCU_FAN_STATUS` and `MAU_EA_RH` removes 49 points.

### 4.5 Generation

36 FCUs × 6 points is not hand-authorable. `scripts/gen-822-inventory.py`
emits the equipment, network, point and alarm-rule entries deterministically.

The generator is a **build tool, not a runtime dependency**. Its output is
committed as ordinary JSON so the inventory stays readable, diffable, and
hand-editable for any single unit afterward. Re-running it must be idempotent
and must never touch hospital or office records.

---

## 5. State model

New module `simulator/model822.py`, invoked by `bas_sim.py` only for
`facility: barracks822`. State persists across steps in
`data/output/state_822.json` so thermal mass is meaningful.

### 5.1 The chain

Each arrow is a place a fault can later live:

```
weather ─→ chiller ─→ CHW loop ─→ coil ─→ leaving air ─→ space ─→ sensor ─→ UC400 ─→ MS/TP ─→ SC ─→ screen
                                    ▲                                                              │
                                    └────────────── valve position ←───────────────────────────────┘
```

### 5.2 Sub-models

**Weather.** `data/input/weather_822.json` carries a design summer day and a
shoulder day as hourly dry-bulb and RH profiles. Deterministic, seeded,
selected per run. It exists because an air-cooled chiller and a latent load
problem are the same seasonal story.

**Chiller (RTAC, air-cooled).** Available capacity is nominal derated by
ambient dry-bulb and condenser health. If available capacity meets building
load, leaving water holds setpoint; if it does not, leaving water drifts up.
This is the causal origin of warm entering water — it is computed, never typed.

**CHW loop.** Building flow from pump status and strainer resistance.
Three-way valves at the coils, so building flow is roughly constant and the
valves modulate mixing — a failed three-way therefore yields full flow and no
cooling, which must remain distinguishable from no flow at all. Return
temperature is supply plus total heat picked up; **building ΔT falls out of
the model rather than being assigned.**

**Coil (per MAU and per FCU).** Entering air is the damper-weighted mix of
outdoor and return conditions. Capacity is a function of valve position,
entering water temperature, entering air temperature and humidity, fouling
factor and air-bound factor. Capacity is split into **sensible and latent**
via a coil bypass factor and apparatus dew point. This split is required, not
optional: without it every fault collapses into a single temperature symptom
and "the space is cool but the hallway is at 72% RH" cannot be represented.

**Coil capacity is finite.** Each coil has a maximum Btu/h; past it, leaving air
is both warmer *and* wetter. This is not a detail — it is the mechanism behind
the field observation that backing the dampers from wide open toward half
improved dehumidification. With an unbounded coil, opening the damper produces
*more* dehumidification and the observed fix cannot be represented.

**Fan.** MAU fans are fixed-speed — airflow is constant when commanded on.
FCU `FAN_MODE` scales airflow across Off/Low/Mid/High, with Auto driven by
space demand.

**Space.** First-order lag on thermal mass plus internal gains, so space
temperature trails supply air the way it does in the field.

**Hallway.** RH derived from serving-MAU leaving-air condition plus
infiltration. This is where a latent failure becomes visible.

### 5.3 Fault knobs (healthy in spec 1)

Present in the schema now so spec 2 changes values, not structure:

| Knob | Healthy | Lives on |
|---|---|---|
| `coil_fouling` | `0.0` | MAU, FCU |
| `air_bound` | `false` | MAU, FCU |
| `strainer_resistance` | `0.0` | CHW-822 |
| `three_way_position_error` | `0.0` | MAU, FCU |
| `valve_authority` | `1.0` | MAU, FCU |
| `sensor_offset` | `0.0` | any AI point |
| `condenser_fouling` | `0.0` | chiller |
| `condenser_fan_failed` | `[]` | chiller |
| `circuit_locked_out` | `[]` | chiller |
| `capacity_limit` | `1.0` | chiller |

### 5.4 Command feedback

`model822.py` reads `data/output/operator_overrides.json` and applies overrides
**for 822 points only** before stepping the model. Commanding a valve moves the
coil; releasing hands control back to the model. Hospital and office overrides
retain their existing display-only behavior — the fix is scoped so it cannot
regress committed work.

### 5.6 Control loops (added 2026-09-11 during planning)

The spec implied this by giving every MAU a `SAT_SP` point, but never said it:
**each MAU modulates its CHW valve to hold supply air setpoint, and each FCU
modulates to hold space temperature.** Without the loop there is nothing to
"respond" — the valve would sit wherever it was left.

The loop is what makes the lab teach. Healthy looks like *setpoint held with the
valve part open*. Every failure mode looks like *valve pegged and supply air
drifting away from setpoint* — which is the field signature that separates a
control problem from a capacity problem.

Three properties are required, not optional:

- **Deadband**, so the valve is not hunting on sensor noise.
- **Conditional anti-windup** — integrate only when not pushing further into a
  stop. Clamping the accumulator instead was tried in prototype and prevents the
  loop from ever reaching setpoint.
- **Actuator slew limiting.** Real valve actuators stroke over 90-150 seconds.
  Without a rate limit the loop limit-cycles 0↔100 %, because the coil responds
  within one step and the capacity limit makes plant gain very high near
  crossover. This is both the physical truth and the stability fix.

An operator override replaces the loop output for that point and releasing it
returns control to the loop.

### 5.5 Calibration targets

Drawn from the operator's field observations. These are acceptance tests, not
guidelines.

| Measure | Healthy | Degraded (spec 2 must be able to produce) |
|---|---|---|
| MAU supply air | mid-60s °F | mid-70s °F |
| Hallway RH | low-60s % | 70 %+ |
| Entering CHW | 44 °F | low-50s °F |
| Building CHW ΔT | 10–12 °F | 2–4 °F |

Spec 1 ships only the healthy column. The degraded column is recorded here so
the model is built with the right dynamic range and spec 2 does not discover
the physics cannot reach it.

---

## 6. Front end

New route `/tracer`, one static HTML file matching the existing pattern — no
build tools, no CDN, no external calls. `index.html` gains a third card.

### 6.1 Connect screen

The front door, because connection is the part of the workflow being modeled.
Before any data is shown, the operator selects a connection point:

| Connection point | Reaches |
|---|---|
| `SC-822-01` Ethernet | Wings A/B — Trunk A makeup air, Trunk B room controllers |
| `SC-822-02` Ethernet | Wings C/D and the lobby |
| Chiller local panel | The walk-up display only |

**Visibility is computed server-side.** `GET /api/topology?from=SC-822-01`
returns only what that connection point can reach. In spec 1 everything is
reachable and this appears to be a formality. It is not: it is the mechanism
that makes spec 2's disconnected-trunk fault honest. Unreachable controllers
must be **absent from the response**, not greyed out client-side. Implementing
visibility in the browser would make the later fault a lie.

Field laptops at the real site are browser-based, per the operator's lead
technician. A thick-client interface would be wrong.

### 6.2 Authentication

Reuses the existing BP-005 role model — `technician` or `admin` via
`GET /api/roles`, synthetic credentials, no real usernames. Roles gate
commanding and override release; 403 responses surface visibly. This is
existing, tested work being wired to a new facility, not rebuilt.

### 6.3 Navigation

Trane-shaped, with comm status on every node — the Network link made visible:

```
SC-822-01  ●online
 ├─ MS/TP Trunk A   ●6 of 6
 │   ├─ UC400-MAU-01  ●
 │   └─ UC400-MAU-02  ●
 └─ MS/TP Trunk B   ●18 of 18
     └─ UC-FCU-A101  ●
```

### 6.4 Views

**MAU view — the diagnostic row.** Not a point dump. One line carrying
entering air temp and RH, OA damper %, CHW valve %, supply air temp, supply
setpoint, **coil ΔT**, and leaving RH. That row is what separates a water
problem from an air problem from a coil problem. Point list, trends and alarms
sit behind tabs.

**CHW service entrance view.** Entering and return water, building ΔT,
strainer DP, pump command and status.

**Chiller walk-up display.** Evaporator entering and leaving water, leaving
setpoint, ambient, percent capacity, per-circuit status, active diagnostics.
Reached from the connect screen, **never from the tree** — the building has no
integration to it.

**FCU view.** Space temp and setpoint, fan mode, valve command and position.

### 6.5 New endpoints

| Endpoint | Returns |
|---|---|
| `GET /api/topology?from=<node>` | Reachable tree with per-node comm status |
| `GET /api/chiller/822` | Local display payload |

Everything else reuses what `bas_api.py` already serves.

---

## 7. Data flow

```
scripts/gen-822-inventory.py
        │ (build time, idempotent)
        ▼
data/input/{equipment,points,alarm_rules}.json + weather_822.json
        │
        ▼
simulator/bas_sim.py ──facility routing──► simulator/model822.py
        │                                        │
        │                                        ├─► data/output/state_822.json  (persists)
        │                                        └─◄ data/output/operator_overrides.json (822 only)
        ▼
data/output/{latest_points.json, trends.csv, alarms.jsonl}
        │
        ▼
frontend/bas_api.py ──► /tracer, /api/topology, /api/chiller/822
```

---

## 8. Error handling

| Condition | Behavior |
|---|---|
| `state_822.json` missing or corrupt | Cold-start from healthy defaults, log the cold start. Never crash the run. |
| Override value out of a point's range | Rejected at the API, existing BP-004/005 validation path. Model never sees it. |
| Override on a non-822 point | Existing display-only path, unchanged. |
| Physics produces NaN or ±inf | Clamp to the point's `normal_min`/`normal_max`, log a model warning. A silently wrong number is worse than a logged clamp. |
| Weather profile missing | Fall back to a fixed 78 °F / 60 % RH ambient and log it. |
| Topology request from an unknown node | 404, empty tree. Never a partial tree with no explanation. |
| Generator run against existing 822 records | Refuse unless `--force`. Never silently duplicate. |

---

## 9. Testing

**`model822.py --self-test`** — monotonicity and sanity, no fixtures:

- Valve position ↑ → supply air temp ↓
- OA damper ↑ at design summer conditions → leaving RH ↑
- Strainer resistance ↑ → building ΔT ↓
- Entering water temp ↑ → coil capacity ↓
- Fan Off → space temp drifts toward ambient
- Energy sanity: heat removed from air ≈ heat added to water, within tolerance
- No NaN or infinity across a full parameter sweep

**Calibration test** — a healthy 24-step run on the design summer day must
land inside the healthy column of §5.5. This is the test that says the model
is right, not merely consistent.

**Dynamic-range test** — with knobs set to their spec-2 values, the model must
be able to *reach* the degraded column. Proves the physics has the headroom
before spec 2 depends on it.

**Regression test** — a hospital and office run before and after this build
must produce identical output for the same seed. Step timestamps are already
deterministic — `bas_sim.py:266` uses a fixed `start` — so `trends.csv` and
`alarms.jsonl` compare byte-for-byte. The only wall-clock field is
`generated_at` in `latest_points.json` (`bas_sim.py:203`), which the comparison
excludes. This is the guard on "the existing engine is untouched," and it
should fail loudly if the routing change leaks.

**Generator test** — idempotent re-run produces no diff; `--force` against
existing records is refused without it.

**Smoke test** — `scripts/run-smoke-test.sh` extended to cover a 822 run and
a `/tracer` fetch.

---

## 10. File manifest

**New**

| Path | Purpose |
|---|---|
| `simulator/model822.py` | Coupled state model, ~300–500 lines |
| `scripts/gen-822-inventory.py` | Inventory generator, build tool |
| `data/input/weather_822.json` | Design summer and shoulder day profiles |
| `frontend/static/tracer.html` | Tracer SC front end |
| `sequences/MAU-822-SOO.md` | Sequence of operations, makeup air |
| `sequences/FCU-822-SOO.md` | Sequence of operations, room FCU |

**Modified**

| Path | Change |
|---|---|
| `data/input/equipment.json` | `networks` list, nullable `parent`, 822 facility and devices |
| `data/input/points.json` | 421 822 points, `MV` type with `states` |
| `data/input/alarm_rules.json` | 822 rules |
| `data/input/trend_plan.json` | 822 trend intervals |
| `simulator/bas_sim.py` | Facility routing to `model822`; no change to existing path |
| `frontend/bas_api.py` | `/tracer`, `/api/topology`, `/api/chiller/822` |
| `frontend/static/index.html` | Third building card |
| `scripts/run-smoke-test.sh` | 822 coverage |

**Untouched, deliberately:** `frontend/static/niagara.html`,
`frontend/static/metasys.html`, `BREAK/`, `DESIGN/`, all hospital and office
records.

---

## 11. Open questions

1. **CH530 or UC800 unit controls on the RTAC?** `RTAC-SVX01` spans both eras
   and the revision letter does not settle it. To be confirmed from the
   operator's manual, not guessed. It decides the chiller's local interface
   layout and whether BACnet integration would be an LCI-C comm module or
   native — which is directly the "why can't the building see the chiller"
   question that spec 2 builds on.
2. ~~**Point count 421, or trim to 372?**~~ **Resolved 2026-09-11: keep 421.**
   `FCU_FAN_STATUS` and `MAU_EA_RH` stay in; `EA_RH` is load-bearing for the
   latent diagnosis.

---

## 12. What comes next

| Spec | Contents |
|---|---|
| 2 | 822 fault library as parameter perturbations, plus the comms and blind-trunk class the topology unlocks. The surface Codex breaks against to generate tickets. |
| 3 | Tracer TU direct-connect service-tool mode. Gated last, mirroring the operator's real access gate. |
| Later, uncommitted | Persistent degraded-building campaign mode. |
