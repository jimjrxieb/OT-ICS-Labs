# BUILD Plan BP-005 — Access Role Model & Command Authorization (Step 2, slice 1)

**Status:** COMPLETE
**Approved by:** J — 2026-07-01. Verified 2026-07-01: py_compile and
  run-smoke-test.sh rerun independently; role-gate behavior (403 for
  viewer/operator/vendor, 200 for technician) re-confirmed against a freshly
  started server, not by reusing worker-reported output; `operator_actions.jsonl`
  attribution confirmed; `git diff --stat` on `simulator/` and `data/input/`
  confirmed empty; `git status` confirmed no staged/committed changes.
**Approval scope:** Local synthetic lab only — new docs plus additive changes
  to `frontend/bas_api.py`, `metasys.html`, `niagara.html` only
**Source finding:** `BUILD/work-packages/BUILD-003-step2-ot-security-layer.md`
  (Step 2 OT security layer); Residual Risk flagged in
  `BUILD/4-completedbuilds/BP-004-technician-command-release.md` — command/
  release endpoints ship with no role or authorization model
**Target:** `slot-3/docs/access-role-model.md` (new),
  `slot-3/docs/remote-access-workflow.md` (new),
  `slot-3/frontend/bas_api.py`, `slot-3/frontend/static/metasys.html`,
  `slot-3/frontend/static/niagara.html`
**Owner:** ot-build-agent (codex worker)

---

## Why This Build Exists

BP-004 added a Technician Panel that lets anyone hitting the API command any
writable point — there is no operator/technician/vendor distinction. This is
exactly the OT security gap the roadmap already calls out in BUILD-003 (Step
2): "Roles, approval, MFA flag, session logging, and denial cases are
documented" must exist before command authority is exercised for real.

This build is a deliberately small first slice of BUILD-003 — the role model
plus the minimum authorization gate needed to close the specific gap BP-004
opened. It does not attempt the full Step 2 scope in one shot:

- **In this slice:** role model doc, remote-access workflow doc, and a role
  check on the two write endpoints (`command`, `release`) plus attribution in
  the operator action log.
- **Deferred to a later BP:** Purdue/zone/conduit model (`docs/purdue-zone-
  conduit.md`), incident/change workflow doc, MFA enforcement (beyond a
  documented flag), and a real session/login system.

## Approved Context

Worker may use:

- `slot-3/frontend/bas_api.py` — existing FastAPI app (extend, do not
  restructure existing GET endpoints)
- `slot-3/frontend/static/metasys.html`, `niagara.html` — existing
  Technician Panel markup/JS from BP-004 (extend, do not rewrite)
- `slot-3/BUILD/work-packages/BUILD-003-step2-ot-security-layer.md` — role
  list and workflow fields to document (viewer, operator, technician,
  vendor, admin, security reviewer)

Worker must not use:

- Real credentials, real identity providers, real MFA integrations
- External network access
- git operations (no stage, commit, push, or branch)
- Any change to `simulator/bas_sim.py` or `data/input/`

## Proposed Change

### 1. `docs/access-role-model.md` (new)

Document six synthetic roles and what each may do against the lab API:

| Role | Read points/alarms/trends | Acknowledge alarms | Command/release points | Manage roles | Read audit log |
|---|---|---|---|---|---|
| viewer | yes | no | no | no | no |
| operator | yes | yes | no | no | no |
| technician | yes | yes | **yes** | no | no |
| vendor | yes (session-gated, see workflow doc) | no | no (documented as planned, not implemented this slice) | no | no |
| admin | yes | yes | yes | yes | yes |
| security reviewer | yes | no | no | no | yes |

Values are synthetic — no real usernames, directory groups, or credentials.

### 2. `docs/remote-access-workflow.md` (new)

Document (as a workflow, not necessarily all implemented in code this
slice): request → approval → MFA flag (boolean) → session start/end →
denial cases, using the vendor role as the example. State plainly which
parts are implemented in code this slice (none — this is documentation
scaffolding for BUILD-003's remaining slices) versus planned.

### 3. Backend authorization gate (`frontend/bas_api.py`)

- Add `role: str = Query(...)` to `POST /api/points/{point_name}/command`
  and `POST /api/points/{point_name}/release`.
- Add a `ROLES` constant listing the six roles and an `AUTHORIZED_TO_COMMAND
  = {"technician", "admin"}` set.
- Reject with `403` and a clear detail message if `role not in
  AUTHORIZED_TO_COMMAND`.
- Add `role` and an `operator_id` (free-text query param, default
  `"BAS-OPR-01"`) to every entry appended via `_append_operator_action`.
- Add `GET /api/roles` returning the role list for the UI dropdown.

### 4. Frontend role selector (`metasys.html`, `niagara.html`)

- Add a role `<select>` to the Technician Panel (populated from
  `GET /api/roles`), defaulting to `viewer`.
- Command/Release buttons pass the selected role as a query param.
- If the server returns 403, show the detail message inline instead of
  silently failing.

## Files In Scope

- `slot-3/docs/access-role-model.md` (new)
- `slot-3/docs/remote-access-workflow.md` (new)
- `slot-3/frontend/bas_api.py`
- `slot-3/frontend/static/metasys.html`
- `slot-3/frontend/static/niagara.html`

## Out Of Scope

- `slot-3/docs/purdue-zone-conduit.md` (future BP)
- `slot-3/docs/incident-change-workflow.md` (future BP)
- Real authentication, sessions, or MFA enforcement
- `simulator/bas_sim.py`, `data/input/`
- Step 3 AI-assist layer
- git operations

## Acceptance Checks

- `python3 -m py_compile frontend/bas_api.py` exits 0.
- `scripts/run-smoke-test.sh` still passes.
- `docs/access-role-model.md` exists and documents all 6 roles with a
  read/acknowledge/command/manage-roles/audit-read matrix.
- `docs/remote-access-workflow.md` exists and documents request, approval,
  MFA flag, session start/end, and at least one denial case.
- `POST /api/points/{writable_point}/command?value=1&role=viewer` → `403`.
- `POST /api/points/{writable_point}/command?value=1&role=technician` →
  `200`, override applied.
- `POST /api/points/{writable_point}/release?role=operator` → `403`.
- `POST /api/points/{writable_point}/release?role=technician` → `200`.
- `GET /api/roles` returns all 6 roles.
- New `operator_actions.jsonl` entries include `role` and `operator_id`.
- Metasys and Niagara Technician Panels show a role selector; a 403 from
  the server surfaces as visible text in the UI, not a silent no-op.
- No real facility data, PHI, or real credentials appear in any file.

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Non-technician commands a point | `POST .../command?role=viewer` | 403, no override written, no state change |
| Technician commands then releases | `POST .../command?role=technician` then `POST .../release?role=technician` | Override applied then cleared, both logged with role |
| Vendor role attempts command | `POST .../command?role=vendor` | 403 — vendor is read-only this slice per role matrix |
| Audit attribution | `GET /api/operator-actions` after mixed-role attempts | Every entry (including rejected ones only if logged — decide and document) carries `role` |

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Command authority is role-gated | `BUILD/4-completedbuilds/BP-005-...md` (once verified) | `frontend/bas_api.py` 403 paths, `docs/access-role-model.md` |
| Operator actions are attributable to a role | same | `operator_actions.jsonl` entries with `role` field |

## Residual Risk

- No real authentication — the `role` parameter is self-declared by the
  caller, not verified against an identity system. This closes the
  "any caller can command any point" gap from BP-004 but does not add real
  access control. Acceptable for a single-user local lab; a later BP must
  add real session/login before any claim of enforced RBAC.
- Vendor, admin, and security-reviewer roles are documented and
  role-gated at the API layer but have no dedicated UI workflow yet
  (approval requests, session logging) — that is explicitly deferred to a
  later BUILD-003 slice per `docs/remote-access-workflow.md`.
- MFA is a documented flag only, not enforced.

## Worker Instructions

Before editing, confirm:

1. `frontend/bas_api.py` has the `command_point` and `release_point`
   endpoints from BP-004 (`data/output/operator_overrides.json`,
   `operator_actions.jsonl`).
2. `docs/access-role-model.md` and `docs/remote-access-workflow.md` do not
   already exist.
3. No changes touch `simulator/bas_sim.py` or `data/input/`.

Build in order: role model doc → remote-access workflow doc → backend role
gate → frontend role selector. Run acceptance checks after each step.

Report back with: acceptance-check output, list of files changed, and any
deviation from this plan with a reason. Do not stage, commit, or push. Do
not mark this BP `COMPLETE` — that is J's call after independent
verification.
