# BUILD Plan BP-004 — Technician Command/Release Panel

**Status:** APPROVED — retroactive filing
**Approved by:** J — 2026-07-01. Human-Owned Stops wording in `BUILD-PLAN.md`
  clarified to scope "point overrides" to real/production systems; synthetic
  simulator command/release is in scope for this lab.
**Approval scope:** Local synthetic lab only — new files under `slot-3/` only
**Source finding:** Learning objective — hands-on DDC technician practice
  (command a writable point, verify override, release back to simulator)
  ahead of NAS JAX DDC work; extends `COMPLY/answered-questionnaire.md` §2
**Target:** `slot-3/frontend/bas_api.py`, `slot-3/frontend/static/metasys.html`,
  `slot-3/frontend/static/niagara.html`, `slot-3/scripts/start-frontend.sh`,
  `slot-3/README.md`
**Owner:** ot-build-agent

---

## Filing Note

This build was already implemented before a BP existed for it — it did not
go through `1-buildplanning/` → `2-approvedbuilds/` first, breaking the
pipeline discipline BP-001/002/003 followed. This document files it
retroactively for J review. No further code changes are proposed here;
this describes what is already on disk in the working tree (uncommitted).

---

## Why This Build Exists

BP-002 gave the Metasys/Niagara UIs read-only point, alarm, and trend
views. A DDC technician's actual job is commanding points — overriding a
damper, forcing an AHU stage, then releasing it back to auto — and reading
the results. Without a command/release loop, the lab only teaches
navigation, not the core technician skill.

This build adds a "Technician Panel" tab to both UIs: command a writable
point to a value, see it flagged as overridden, release it back to the
simulator snapshot, and see every action logged.

---

## Approved Context

Worker used:

- `slot-3/frontend/bas_api.py` — existing FastAPI app (extended, not replaced)
- `slot-3/data/input/points.json` — `writable` flag already present per point
- `slot-3/data/output/` — new files `operator_overrides.json`,
  `operator_actions.jsonl`

Worker did not use:

- Real hospital data, real credentials, real vendor hostnames or IPs
- External network access
- git operations

---

## Proposed Change (already implemented)

### 1. Backend (`frontend/bas_api.py`)

- `POST /api/points/{point_name}/command?value=&reason=` — rejects points
  where `writable` is `false` (400); coerces bool points to 0/1; stores the
  override in `data/output/operator_overrides.json`; appends a `command`
  event to `data/output/operator_actions.jsonl`.
- `POST /api/points/{point_name}/release` — clears the override for a
  point; appends a `release` event.
- `GET /api/operator-actions` — last 50 logged operator actions.
- `GET /api/points` and `GET /api/points/{point_name}` now overlay any
  active override on top of the simulator snapshot value and report
  `overridden` + `operator_note`.
- `POST /api/run/{scenario}` now clears all overrides on a fresh run
  (`_write_overrides({})`) so a new scenario starts clean.
- Every write endpoint tags its logged event with
  `"data_boundary": "synthetic lab operator action only"`.

### 2. Frontend (`metasys.html`, `niagara.html`)

- New "Technician Panel" tab: table of writable points with Command
  ON/OFF (bool points) or a setpoint input + Command button (analog
  points), plus a Release button per row. Overridden points show an
  `OVERRIDE` badge and the operator's reason.

### 3. Launch script (`scripts/start-frontend.sh`)

- No longer silently `pip install`s missing deps — now exits with an
  explicit instruction to run `pip install -r requirements.txt`.
- Binds `127.0.0.1` only (was `0.0.0.0`).

### 4. Docs

- `README.md` documents the Technician Panel and the two new
  `data/output/` files.

---

## Files In Scope

- `slot-3/frontend/bas_api.py`
- `slot-3/frontend/static/metasys.html`
- `slot-3/frontend/static/niagara.html`
- `slot-3/scripts/start-frontend.sh`
- `slot-3/README.md`
- `slot-3/data/output/operator_actions.jsonl` (new, generated)
- `slot-3/data/output/operator_overrides.json` (new, generated)

---

## Out Of Scope

- `slot-3/simulator/bas_sim.py` — no changes
- Role model, approval workflow, MFA flag, session logging (that is
  BUILD-003 / Step 2, still `planned` — see Residual Risk below)
- Step 3 AI-assist layer
- Any real BAS, network access, or production system

---

## Acceptance Checks

- `python3 -m py_compile simulator/bas_sim.py frontend/bas_api.py bas_console.py` — exits 0. **Verified.**
- `scripts/run-smoke-test.sh` — passes. **Verified.**
- `POST /api/points/{name}/command` on a writable point stores an
  override, `GET /api/points/{name}` reflects it, `POST .../release`
  clears it. **Verified via direct API call per worker report.**
- `POST /api/points/{name}/command` on a non-writable point returns 400.
- `data/output/operator_actions.jsonl` gets one line per command/release/
  run_scenario action.
- No real facility data, PHI, or real credentials appear in any file.

---

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Command a non-writable point | `POST /api/points/{readonly_point}/command?value=1` | 400 rejection |
| Command then run new scenario | Command a point, then `POST /api/run/normal` | Override cleared, point returns to simulator-driven value |
| Operator action audit trail | `GET /api/operator-actions` after a few commands | Every command/release event present with `data_boundary` tag |
| Unauthenticated access | `curl localhost:8001/api/points/{name}/command` from any local process | Succeeds — no auth exists yet (see Residual Risk) |

---

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Technician can command and release a synthetic point | `BUILD/4-completedbuilds/BP-004-...md` (once approved) | `data/output/operator_actions.jsonl`, `frontend/bas_api.py` |
| Every operator action is logged | same | `operator_actions.jsonl` entries with timestamp + data_boundary |

---

## Residual Risk

- **Human-Owned Stops conflict to resolve explicitly:** `BUILD/BUILD-PLAN.md`
  lists "Controller writes, point overrides, schedules, setpoints, or
  sequence changes" under Human-Owned Stops. This build implements point
  overrides — against the *synthetic simulator*, not a real controller.
  J should confirm whether that Human-Owned Stop was meant to cover
  simulated commands (in which case this needs rewording or an explicit
  carve-out) or only real/production systems (in which case this build is
  fine as scoped). Flagging rather than assuming.
- **No role model or approval workflow.** Anyone who can reach the API can
  command any writable point — there's no operator/technician/vendor
  distinction yet. BUILD-003 (Step 2, still `planned`) is where that
  belongs. Acceptable for a single-user local lab; not acceptable once
  Step 2 claims begin.
- **No authentication on the FastAPI server** (carried over from BP-002,
  still true). Local lab tool only — do not expose port 8001 beyond
  localhost.
- Override state lives in a flat JSON file with no locking — fine for a
  single local user, would race under concurrent access.

---

## Worker Instructions

N/A — implementation already complete. This filing exists so J can review
and either (a) approve into `2-approvedbuilds/` → `4-completedbuilds/` as-is,
(b) require changes before approval, or (c) reject and roll back.
