# BUILD Pipeline Status — Slot-3 Synthetic Hospital BAS

> Kanban board for the slot-3 BUILD phase. One question: **what is approved,
> what is in progress, and what is done?**
>
> Canonical pipeline: `1-buildplanning/` → `2-approvedbuilds/` → worker →
> `3-buildscodereview/` → `4-completedbuilds/` or `4R-remediationRebuilds/`

Last updated: 2026-07-06

---

## Stage Summary

| Stage | Contents |
|---|---|
| `1-buildplanning/` | `BP-001`–`BP-008` (all promoted) |
| `2-approvedbuilds/` | `BP-001`–`BP-008` |
| `3-buildscodereview/human-review/` | — |
| `4-completedbuilds/` | `BP-001`–`BP-008` |
| `4R-remediationRebuilds/` | — |
| `templates/` | `approved-build-template.md` |
| `work-packages/` | Legacy work packages (BUILD-001 through BUILD-004) — reference only |

---

## AWAITING APPROVAL

Nothing pending.

---

## IN PROGRESS

Nothing currently in progress.

---

## DONE

- **BP-008 — Office building fault library.** 2026-07-06. Implemented by
  codex worker, independently verified (own fault runs, fresh-server
  ticket flow). Pure data change — 6 office faults appended to
  `data/input/fault_library.json` (now 15 total, hospital 9 untouched):
  economizer damper stuck + reheat valve stuck open (identical symptom
  text — upstream/downstream trend drill), RTU SAT sensor failure,
  chiller capacity loss, boiler flame failure, JACE comms loss (first
  `comms_loss` fault — all 10 office points freeze, hospital unaffected,
  JACE offline alarm). Zero code changes; diagnosis dropdown auto-extended
  to all 10 equipment. Trouble-call mode now spans the full two-building
  portfolio.
  → `4-completedbuilds/BP-008-office-fault-library.md`

- **BP-007 — Portfolio expansion: office building + Niagara portfolio
  navigation.** 2026-07-06. Implemented by codex worker, independently
  verified (fresh server, own API/page checks). Second facility (Riverside
  Office Tower: RTU-1 w/ economizer, VAV-301 w/ reheat, CHILLER-1,
  BOILER-1 — 10 points, 3 alarm rules), `equipment.json` restructured to a
  `facilities` list with per-entry tags (`N4-SUP-01` = portfolio), Niagara
  Station tree is now a portfolio view (Supervisor → hospital JACE +
  office JACE, tabs scope to the selected node). Metasys stays
  hospital-only. Zero `bas_sim.py` changes needed — point generation was
  already generic. SOO docs: `sequences/RTU-1-SOO.md`,
  `sequences/VAV-301-SOO.md`. Office fault library deferred to BP-008.
  → `4-completedbuilds/BP-007-portfolio-office-building.md`

- **BP-006 — Trouble-call diagnosis training mode.** 2026-07-01. Implemented
  by codex worker, independently verified (fresh server, own trend/alarm
  checks, not reused worker output). Redirects focus from BUILD-003 (Step 2
  OT security, still parked mid-slice) back to Step 1 mastery-building: a
  fault library of 9 faults (including a real field-reported compound
  fault — dirty strainer + leaking actuator → condensate drain safety
  trip), fault injection in `bas_sim.py` via `--fault <id>`, trouble-call
  API with a one-ticket-at-a-time 409 lock, and a Trouble Call tab in both
  UIs. `bas_console.py` untouched, no role-gating added (by design), no
  git operations.
  → `4-completedbuilds/BP-006-trouble-call-diagnosis-mode.md`

- **BP-005 — Access role model & command authorization (Step 2, slice 1).**
  2026-07-01. Implemented by codex worker, independently verified (fresh
  server, own curl checks, not reused worker output). Adds
  `docs/access-role-model.md`, `docs/remote-access-workflow.md`, a role-gate
  on the BP-004 command/release endpoints (`technician`/`admin` only, 403
  otherwise), `GET /api/roles`, `role`/`operator_id` attribution in
  `operator_actions.jsonl`, and a role selector in the Technician Panel UI
  with visible 403 surfacing. Closes the "any caller can command any point"
  gap noted in BP-004's Residual Risk. `simulator/` and `data/input/`
  confirmed untouched; no git operations. Deferred to a later slice:
  Purdue/zone/conduit doc, incident/change workflow, real auth/MFA
  enforcement.
  → `4-completedbuilds/BP-005-access-role-model.md`

- **BP-004 — Technician command/release panel.** 2026-07-01. J approved
  (retroactive filing — implementation preceded the BP). Command/release
  endpoints and override storage in `frontend/bas_api.py`, Technician Panel
  tab in `metasys.html`/`niagara.html`, operator action logging to
  `data/output/operator_actions.jsonl`, `start-frontend.sh` fixed to
  127.0.0.1-only bind with no silent dependency install. Human-Owned Stops
  wording in `BUILD-PLAN.md` clarified: "point overrides" now scoped to
  real/production systems, not the synthetic simulator.
  → `4-completedbuilds/BP-004-technician-command-release.md`

- **BP-003 — Open source BAS stack.** 2026-06-29. J approved.
  Docker Compose stack: Mosquitto (1883) + InfluxDB (8086) + Grafana (3000) + Node-RED (1880).
  `bacnet_device.py` — bacpypes3 BACnet/IP device, serves all 11 points as BACnet objects on localhost:47808.
  `influx_bridge.py` — reads latest_points.json every 30s, publishes MQTT + writes InfluxDB directly.
  Grafana provisioned with Hospital BAS Overview dashboard (4 panels: OR SAT, CHW, ISO pressure, humidity).
  Node-RED flow: BAS Pipeline (MQTT subscribe + annotate) + Trigger Scenarios (POST → FastAPI).
  All launcher scripts executable, all services bind to 127.0.0.1 only.
  → `4-completedbuilds/BP-003-open-source-bas-stack.md`
  Files: `open-source-stack/` (docker-compose.yml, bacnet_device.py, influx_bridge.py,
  influx_bridge.py, flows/, grafana/, mosquitto/, nodered/, start-stack.sh, stop-stack.sh, README.md)

- **BP-002 — Metasys/Niagara synthetic front-end.** 2026-06-26.
  FastAPI backend, Metasys browser UI, Niagara Workbench browser UI,
  index landing page, `bas_console.py` terminal CLI. All acceptance checks passed.
  → `4-completedbuilds/BP-002-metasys-niagara-sim.md`
  Files: `frontend/bas_api.py`, `frontend/static/{index,metasys,niagara}.html`,
  `bas_console.py`, `requirements.txt`, `scripts/start-frontend.sh`

- **BP-001 — Evidence templates.** 2026-06-26.
  Five operator-ready markdown templates anchored to simulator output.
  All acceptance checks passed. Smoke test passes.
  → `4-completedbuilds/BP-001-evidence-templates.md`
  Evidence: `evidence/backup-restore-checklist.md`,
  `evidence/operator-checkout-template.md`,
  `evidence/change-rollback-template.md`,
  `evidence/scenario-evidence-index.md`,
  `docs/evidence-generation.md`

- **BUILD-001 — BAS simulator foundation.**
  `data/input/` inventory files, `simulator/bas_sim.py`, `scripts/run-smoke-test.sh`.
  All four scenarios pass. Smoke test passes.
  → `work-packages/BUILD-001-step1-bas-simulator-foundation.md`

---

## Next Action

BREAK phase opened 2026-07-06: `BREAK/BREAK.md` is the "2am call" chaos-game
rulebook for worker agents (live-stack breaks + BAS-layer breaks, sealed
answers, J restores, call log). Not a BUILD item — it's the CBBP BREAK
phase exercising what BUILD shipped.

BP-008 done — the full portfolio trouble-call queue is live
(`scripts/start-frontend.sh` → `/niagara` or `/metasys` → Trouble Call
tab; 15 faults across both buildings). No BP in flight. Future
candidates, in no committed order: schedules/occupancy simulation
("misbehaving because of a schedule, not a fault"), graphics-binding
exercise, oscillation injection mode (enables boiler short-cycling),
resume BUILD-003 Step 2 OT-security slices, or Step 3 AI-assist scoping
(BUILD-004, parked — needs Step 2 evidence first).
