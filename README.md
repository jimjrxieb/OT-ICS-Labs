# Synthetic BAS/OT Training Lab — Hospital, Office, and Building 822

[![ci](https://github.com/jimjrxieb/OT-ICS-Labs/actions/workflows/ci.yml/badge.svg)](https://github.com/jimjrxieb/OT-ICS-Labs/actions/workflows/ci.yml)
[![security](https://github.com/jimjrxieb/OT-ICS-Labs/actions/workflows/security.yml/badge.svg)](https://github.com/jimjrxieb/OT-ICS-Labs/actions/workflows/security.yml)
[![codeql](https://github.com/jimjrxieb/OT-ICS-Labs/actions/workflows/codeql.yml/badge.svg)](https://github.com/jimjrxieb/OT-ICS-Labs/actions/workflows/codeql.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/jimjrxieb/OT-ICS-Labs/badge)](https://scorecard.dev/viewer/?uri=github.com/jimjrxieb/OT-ICS-Labs)

A runnable, fully synthetic building automation system (BAS) lab for
practicing DDC controls troubleshooting. Three fictional buildings — a
180-bed regional hospital, an 8-floor office tower, and **Building 822**,
a barracks with a physics-driven plant model and its own routed BACnet/IP
network — served by Metasys-style, Niagara-style, and Tracer SC-style
browser front ends, a real BACnet/MQTT/InfluxDB/Grafana data pipeline, a
15-fault trouble-call training mode, Niagara N4 practice editors, and an
adversarial "2AM Call" chaos game where an AI agent actually breaks the
running system and you find it.

Everything is synthetic. No real facility, network, points, credentials,
or vendor data anywhere in this repo — and none may ever be added.

---

## Prerequisites

- Python 3.11+ and `pip`
- Node.js (tested with v22) — `scripts/run-smoke-test.sh` runs a JavaScript self-test
- A modern browser
- *(Optional, for the live pipeline and the 2AM Call game)* Docker with the
  compose plugin (`docker compose version` should work)
- *(Optional, for the 2AM Call game and design projects)* an AI coding
  agent CLI — Claude Code, Codex, or similar

## Quick Start

**Fastest path:** if you use an AI coding agent (Claude Code, Codex,
Gemini CLI), open it at this repo's root and paste
`ai-dev-prompts/1-setup-and-verify.md` — it installs, starts, and
health-checks everything for you. Manual path:

```bash
# 1. Install front-end dependencies
pip install -r requirements.txt

# 2. Generate baseline data and start the BAS front end (port 8001)
python3 simulator/bas_sim.py --scenario normal --steps 12
scripts/start-frontend.sh
```

`data/output/` doesn't ship with the repo; step 2 creates it.

Then open:

| URL | What it is |
|---|---|
| `http://localhost:8001/` | Landing page |
| `http://localhost:8001/metasys` | Metasys ADS-style operator view (hospital) |
| `http://localhost:8001/niagara` | Niagara Workbench-style view — **portfolio tree, hospital + office**, with the N4 practice editors |
| `http://localhost:8001/tracer` | Tracer SC-style front end for **Building 822** — connection › trunk › controller › point browser, plus the chiller panel |
| `http://localhost:8001/docs` | API docs (FastAPI) |

Niagara study guide (static page, port 8080 by default):
`scripts/start-niagara-guide.sh`.

Optional — start the live data pipeline (BACnet device on :47808, MQTT,
InfluxDB, Grafana on :3000, Node-RED on :1880):

```bash
pip install -r open-source-stack/requirements.txt
open-source-stack/start-stack.sh      # stop later with stop-stack.sh
```

Sanity check any time: `scripts/run-smoke-test.sh`. It also runs the
Building 822 BACnet server's self-test, so it needs **both**
requirement files installed — `requirements.txt` and
`open-source-stack/requirements.txt` (for `bacpypes3`) — even if you
never start the live pipeline.

---

## What You Can Do

### 1. Operate the BAS
Browse the point tree, alarms, and trends in any front end. The
**Technician Panel** tab lets you command writable points and release
overrides (role-gated: pick `technician` or `admin`). Every action is
logged to `data/output/operator_actions.jsonl`.

### 2. Trouble Call training (no AI needed)
Open the Metasys or Niagara front end → **Trouble Call** tab →
*Request Trouble Call*. You get a symptom only ("Floor 3 tenants report
their space has been getting warmer all morning"). Investigate using
Points/Alarms/Trends, then submit equipment + root-cause category.
You're graded, shown the answer, and told what the data was telling you.
15 faults across the hospital and office — sensor failures, stuck
actuators, plant failures, a JACE comms loss, and one compound fault
modeled on a real field failure (fouled CHW strainer + leaking valve
actuator → condensate drain safety trip). Two faults deliberately share
the same symptom so only the trends can tell you upstream from
downstream.

### 3. Niagara N4 practice (no AI needed)
`/niagara` is organized like Workbench: Property Sheet, Alarm Console,
History Extension, Technician Panel, Schedule, Wire Sheet, Platform,
and Px Graphics tabs.

- **Wire Sheets** — create a sheet, add blocks (Constant, PointRef,
  PointWriteRef, ScheduleRef, Compare, Select, And/Or/Not) with their
  settings, link output slots to input slots, and watch the resolved
  values update live. A `PointWriteRef` output drives its point: the lab
  resolves each point by override → Wire Sheet → schedule → simulator
  (a teaching convention, not a full priority array), allows one writer
  per point, and shows a visible fault when a sheet's output is invalid.
- **Px Graphics** — create a page and place widgets bound to live points.
- **Backup and restore** — take a backup of a sheet or page, change it,
  and restore it. Every restore is validated first, backs up the current
  version, and is audited. The **Platform** tab takes a full station
  backup.

Saves, backups, and restores need the `technician` or `admin` role. For
the concepts behind the tabs, run the Niagara study guide
(`scripts/start-niagara-guide.sh`) or read `docs/niagara.md`.

### 4. Building 822: physics and field verification
Building 822 is a synthetic barracks: four wings on three floors, 13
makeup-air units, 36 fan-coil units, 12 hallway sensors, an air-cooled
helical-rotary chiller, and a chilled-water loop with lead/standby
pumps. Unlike the other two buildings, its values come from a coupled
thermal/hydronic model with real psychrometrics — you break *causes*,
and the physics produces the symptoms.

```bash
# Inject a cause for one simulator run, e.g. a leaking valve body on the
# P1 pump branch that bleeds the chilled-water loop down
python3 simulator/bas_sim.py --steps 180 --knob CHW-822:p1_tdv_leak_gpm=1.5

# Walk out and look: instruments that read what the BAS cannot see
python3 scripts/field-verify.py read-gauge          # loop pressure at the pump suction
python3 scripts/field-verify.py clamp-amps P1       # is the pump actually loaded?
python3 scripts/field-verify.py walk-pumproom       # what do you see when you walk in?
python3 scripts/field-verify.py inspect-valve P1_TDV
python3 scripts/field-verify.py verify-travel MAU04 # did the actuator physically move?

# Put the plant back after a fault demo
python3 simulator/model822.py --restore-healthy-plant
```

Physical plant state (loop pressure, air in the loop, water on the
floor, a latched chiller trip) persists between runs; fault knobs do
not. `bas_sim.py` warns when it loads a faulted plant without knobs.

To see the building on the wire, run it as a routed BACnet/IP
internetwork — two supervisory routers, four MS/TP trunks, 50 field
controllers, 448 objects — and point any BACnet client (YABE, a Niagara
station) at it:

```bash
python3 open-source-stack/bacnet822.py --bbmd   # routers on UDP 47809 and 47810
```

The devices use placeholder vendor ID 999 and are not Trane devices; a
real supervisor sees generic third-party controllers. See
`docs/bacnet-822.md` for the device map.

### 5. The 2AM Call game (AI agent required)
The trouble-call faults are simulated data. The 2AM game breaks the
**actual running system** — killing the BACnet device, stopping the MQTT
broker, hanging the historian, leaving phantom operator overrides — and
you troubleshoot for real with `docker`, logs, Grafana, and the BAS UIs.

Open your AI agent CLI at this repo's root and paste
`ai-dev-prompts/2-2am-call.md` — or just say:

```
Read BREAK/BREAK.md and follow it. 2am call, level 1.
```

The agent secretly breaks something (writing a sealed answer file first),
pages you like a night dispatcher, grades your diagnosis honestly, and
verifies your fix. Levels 1–3; level 3 deals two simultaneous faults
where one masks the other. Your record accumulates in
`BREAK/call-log.md`. **Requires the docker stack running** for the
live-break menu.

### 6. Design projects (AI agent required)

The other half of the job: not fixing the building — engineering it.
An AI agent plays senior engineer / EOR: it issues a project brief
(a renovation or addition to one of the buildings, with owner-furnished
drawings that are wrong in places), you survey the live lab against the
drawings, produce the engineering package — points list, sequence of
operations, valve/damper schedule, BOM, panel layout, network riser —
and carry it through submittal review to approval. Revise-and-resubmit,
RFIs, honest disposition codes.

Open your AI agent CLI at this repo's root and paste
`ai-dev-prompts/6-design-project.md` — or just say:

```
Read DESIGN/DESIGN.md and follow it. New project, level 1.
```

Three briefs ship with the lab (levels 1–3); the rulebook also lets the
agent author new ones. The answer-key rubrics are never published: the
agent seals a rubric in `DESIGN/sealed/` before reviewing, and both the
rubrics and your record (`DESIGN/review-log.md`) stay local. Self-QA
any submittal with `python3 scripts/validate-submittal.py
DESIGN/submittals/P-XX/rev-A`. The docker stack is optional here — the
front ends are enough for site surveys.

**Approved designs get built.** Once a package is stamped APPROVED,
`python3 scripts/merge-submittal.py DESIGN/submittals/P-XX/rev-N --apply`
merges your equipment, points, and alarms into the live inventories
(backup and merge log included; dry run without `--apply`). Re-run the
simulator and your equipment appears in the front ends, trends, alarms —
and can take trouble calls and 2AM breaks like everything you didn't
design.

---

## The Buildings

| | NAS JAX Regional Medical Center (synthetic) | Riverside Office Tower (synthetic) | Building 822 (synthetic) |
|---|---|---|---|
| Character | Life-safety-driven: OR temp/humidity, isolation room pressure, sterile spaces | Comfort/energy-driven: economizer, reheat, tenant complaints | Humidity-driven barracks: dedicated outdoor air plus room fan coils |
| Equipment | OR + ICU AHUs, OR VAV, isolation room pressure controller, CHW + HW plants | Rooftop VAV AHU w/ economizer, VAV w/ reheat, air-cooled chiller, condensing boiler | 13 MAUs, 36 FCUs, 12 hallway sensors, air-cooled chiller, CHW loop with lead/standby pumps |
| Data | Scenario/fault engine | Scenario/fault engine | Coupled thermal/hydronic physics with psychrometrics |
| Front end | Metasys (vendor-locked) + Niagara | Niagara only — federated under the portfolio Supervisor | Tracer SC-style (`/tracer`) + routed BACnet/IP server |
| Alarm posture | `critical` on life-safety points | `medium`/`high` — nothing here hurts a patient | Comfort and plant alarms; the chiller diagnostic is local to its panel |

## Repo Map

| Path | Purpose |
|---|---|
| `simulator/bas_sim.py` | Dependency-free data engine — scenarios and fault injection (`--scenario`, `--fault`, `--knob`) |
| `simulator/model822.py`, `psychro.py` | Building 822 physics model and psychrometrics |
| `simulator/testdata/` | Building 822 regression baseline (checked by the smoke test) |
| `data/input/` | Synthetic inventories: equipment, points, alarm rules, **fault_library.json** (15 faults), schedules, Wire Sheets, Px pages, stations, 822 weather |
| `data/output/` | Generated at runtime, not in git: point snapshots, alarms, trends, operator/trouble-call logs, backups |
| `frontend/` | FastAPI backend + Metasys/Niagara/Tracer/landing HTML (no build tools, no CDN) |
| `open-source-stack/` | Docker pipeline: Mosquitto, InfluxDB, Grafana, Node-RED + BACnet device & Influx bridge + the Building 822 BACnet/IP server |
| `BREAK/` | The 2AM Call game: `BREAK.md` (agent rulebook), `sealed/` (hidden answers, local only), `call-log.md` |
| `DESIGN/` | The design-assist track: `DESIGN.md` (EOR rulebook), `briefs/`, `templates/`, `submittals/`; `sealed/` rubrics and `review-log.md` stay local |
| `ai-dev-prompts/` | **Copy-paste prompts for any AI agent** — setup/deploy, play the 2AM game, repair the lab, add your own war-story fault, teardown, design projects |
| `sequences/` | Synthetic sequences of operation per equipment |
| `bas_console.py` | Terminal CLI client for the same API |
| `scripts/` | `start-frontend.sh`, `run-smoke-test.sh`, `field-verify.py`, `start-niagara-guide.sh`, submittal `validate-`/`merge-submittal.py`, Building 822 tooling (`gen-822-inventory.py`, `bacnet822-client.py`, `tune-822.py`, `model822-regression.py`) |
| `docs/` | Architecture, Building 822 BACnet map, chiller/cooling tower notes, Niagara guide and study page, vision checklist, design specs and plans (`docs/superpowers/`), repository security settings |
| `governance/` (`BUILD/`, `COMPLY/`, `evidence/`), `safety/` | Governance and methodology records — how this lab was specified, approved, built, and verified (CBBP: Comply → Build → Break → Prove). Optional reading; some internal docs reference the author's larger consulting framework and won't resolve outside it. |
| `.github/` | CI, security scanning, CodeQL, Scorecard, and Dependabot configuration |
| `agent.md` | Role guide for an AI agent doing a DevSecOps assessment or browser UI verification of this lab |
| `SECURITY.md` | How to report a vulnerability |

## Security & CI

Every push and pull request to `main` runs:

- **Smoke test** on a clean checkout (`ci.yml`), plus a CycloneDX SBOM
  artifact on pushes to `main`.
- **Security scans** (`security.yml`): Gitleaks over the full git
  history, Bandit, Semgrep, Trivy, Grype, Hadolint, zizmor (audits the
  workflows themselves), and Dependency Review on pull requests. A
  secret, a HIGH/CRITICAL vulnerability, or a high-severity SAST or
  workflow finding fails the run; everything else is reported in the
  repository's Security tab.
- **CodeQL** for Python and JavaScript (`codeql.yml`), and **OpenSSF
  Scorecard** weekly (`scorecard.yml`).

Actions are pinned to commit SHAs, scanner binaries are checksum-verified,
and Dependabot proposes weekly updates for actions, Python packages, and
container images. Report vulnerabilities privately as described in
[SECURITY.md](SECURITY.md). Repository settings that no file can enforce
are listed in `docs/repo-security-settings.md`.

## Safety & Data Boundary

- Everything binds to `127.0.0.1` only. This is a local lab, not a service.
- Synthetic data only — never add real hospital/facility data, PHI,
  credentials, IPs, hostnames, vendor remote-access details, or real
  Metasys/Niagara/Tracer exports/screenshots.
- The 2AM agent's rulebook (`BREAK/BREAK.md`) hard-limits breaks to this
  repo, reversible actions only, with restore commands recorded before
  every break.
- Nothing here is a real design sequence or code/life-safety approval,
  and none of the front ends is, or replaces, a vendor product.
