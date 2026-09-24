# BUILD Plan BP-002 — Metasys/Niagara Synthetic Front-End

**Status:** APPROVED
**Approved by:** J / 2026-06-26
**Approval scope:** Local synthetic lab only — new files under `slot-3/` only
**Source finding:** `COMPLY/scope-statement.md` vendor stack (Metasys, Niagara, Trane);
  `COMPLY/answered-questionnaire.md` §2 BAS Architecture; learning objective for
  NAS JAX DDC work and Niagara journeyman readiness
**Target:** `slot-3/frontend/`, `slot-3/bas_console.py`, `slot-3/requirements.txt`
**Owner:** ot-build-agent

---

## Why This Build Exists

The COMPLY scope names three BAS platforms in use at the synthetic hospital:
Metasys (main front end), Niagara (integration supervisor), and Trane (selected
AHUs). The simulator core (`bas_sim.py`) emits the data those front-ends would
display, but there is no way to interact with it as an operator would.

This build creates two synthetic front-end experiences on top of the existing
simulator:

1. A **Metasys-style operator view** — how a Metasys ADS/ADX operator logs in,
   browses the Site > Network > Equipment > Point hierarchy, reads point values,
   views alarms, and reads trends.

2. A **Niagara Workbench-style view** — how a Niagara Supervisor / JACE
   engineer navigates a Station > Component tree using ORD-path concepts,
   reads point values, and views active alarms.

Both views are served by one FastAPI application and backed by the same
simulator output files. A terminal CLI (`bas_console.py`) connects to the
same API so an operator — or an AI agent — can work the system from the
command line.

This is a learning lab. The goal is hands-on fluency with Metasys and Niagara
navigation concepts before touching the real systems at NAS JAX.

---

## Approved Context

Worker may use:

- `slot-3/simulator/bas_sim.py` — data engine (read, do not modify)
- `slot-3/data/input/` and `slot-3/data/output/` — point inventory and live output
- `slot-3/sequences/` — SOO context for display labels
- `slot-3/COMPLY/scope-statement.md` — equipment names, space names, vendor roles
- `fastapi`, `uvicorn` Python packages (install via `requirements.txt`)

Worker must not use:

- Real hospital data, PHI, real credentials, real vendor hostnames or IPs
- Real Metasys or Niagara screenshots, diagrams, or configuration exports
- External network access
- git operations (no stage, commit, push, or branch)

---

## Proposed Change

### Step 1 — FastAPI backend (`slot-3/frontend/bas_api.py`)

Single FastAPI app on port 8001. Reads `data/output/` files on each request
(no database). Exposes:

- `GET /api/points` — all current point values, organized by equipment
- `GET /api/points/{point_name}` — single point value + metadata
- `GET /api/alarms` — all active alarms from `alarms.jsonl`
- `GET /api/trends/{point_name}` — trend rows for a point from `trends.csv`
- `GET /api/scenarios` — list of available simulator scenarios
- `POST /api/run/{scenario}` — trigger `bas_sim.py` for a given scenario
  and return a summary (steps defaults to 12)

### Step 2 — Metasys browser UI (`slot-3/frontend/static/metasys.html`)

Single-page HTML/CSS/JS file. No build tools, no npm, no external CDN calls.

Layout:
- **Header**: "NAS JAX Regional Hospital — Metasys ADS" banner, simulated
  operator login name, current scenario badge.
- **Left nav**: Site tree — `NAS JAX Hospital > BAS Network > [Equipment]`.
  Clicking equipment filters the point table.
- **Main panel**: Point table showing point name, current value, units, status
  (normal/alarm). Rows with active alarms highlighted in amber/red by priority.
- **Alarms tab**: Active alarm list — timestamp, point, equipment, priority,
  message. "Acknowledge" button per row (synthetic — marks row as acked in
  the UI session only, no backend write).
- **Trends tab**: Select a point from dropdown, show last 12 trend rows as
  an HTML table. Simple inline sparkline using `<canvas>` (no library).
- **Run Scenario panel**: Dropdown of four scenarios + "Run" button. Calls
  `POST /api/run/{scenario}`, refreshes point table.

Terminology throughout uses Metasys language: "ADS", "Network Engine",
"Field Device", "Object", "Attribute", "Priority Array", "COV".

### Step 3 — Niagara browser UI (`slot-3/frontend/static/niagara.html`)

Same single-page pattern, different layout and terminology.

Layout:
- **Header**: "NAS JAX Regional Hospital — Niagara Supervisor" banner.
- **Left nav**: Station tree — `NAS_JAX_Supervisor > Drivers > BACnet >
  [JACE / Controller] > [Point]`. ORD-path breadcrumb shown at top.
- **Main panel**: Point table. Same data, Niagara column names: "Ord",
  "Facets", "Out", "Status", "Flags".
- **Alarms tab**: Alarm table with Niagara language — "AlarmClass",
  "SourceState", "AckState", "NormalTime".
- **Trends tab**: Same as Metasys but labels use "History Extension",
  "Capacity", "Record Count".
- **Run Scenario panel**: Same as Metasys tab.

Terminology throughout uses Niagara/Tridium language: "Station", "JACE",
"Module", "ORD", "Slot", "BajaScript", "Workbench", "Fox protocol",
"History Extension".

### Step 4 — Index page (`slot-3/frontend/static/index.html`)

Simple landing page. Two cards: "Open Metasys ADS" and "Open Niagara
Workbench". Links to `metasys.html` and `niagara.html`. Brief one-line
description of each platform's role in the synthetic hospital.

### Step 5 — Terminal CLI (`slot-3/bas_console.py`)

Standalone Python script using the `cmd` stdlib module (no extra deps).
Connects to the FastAPI server at `http://localhost:8001`.

Commands:

```
login metasys      — set active platform to Metasys, print ADS banner
login niagara      — set active platform to Niagara, print Supervisor banner
ls                 — list equipment (Metasys: Network Engine view;
                     Niagara: Station tree view)
ls <equipment>     — list points under that equipment
get <point_name>   — print current value, units, status
alarms             — print active alarm list in platform terminology
trends <point>     — print last 12 trend rows for a point
run <scenario>     — trigger simulator scenario, print summary
help               — print command reference
exit               — quit
```

Output format uses platform-appropriate terminology depending on active login.

### Step 6 — Requirements and launch script

- `slot-3/requirements.txt` — `fastapi`, `uvicorn[standard]`
- `slot-3/scripts/start-frontend.sh` — installs deps if not present,
  starts `uvicorn frontend.bas_api:app --host 0.0.0.0 --port 8001 --reload`
- `slot-3/scripts/run-smoke-test.sh` — updated to add a curl check:
  `curl -s http://localhost:8001/api/points | python3 -m json.tool > /dev/null`
  (only if server is running — smoke test must still pass without server up)

---

## Files In Scope

- `slot-3/frontend/` (new directory)
  - `slot-3/frontend/bas_api.py`
  - `slot-3/frontend/static/index.html`
  - `slot-3/frontend/static/metasys.html`
  - `slot-3/frontend/static/niagara.html`
- `slot-3/bas_console.py` (new)
- `slot-3/requirements.txt` (new)
- `slot-3/scripts/start-frontend.sh` (new)

---

## Out Of Scope

- `slot-3/simulator/bas_sim.py` — no changes
- `slot-3/data/input/` — no changes
- `slot-3/scripts/run-smoke-test.sh` — no changes (smoke test stays pure Python)
- Step 2 OT security layer
- Step 3 AI-assist layer
- Any real BAS, network access, or production system

---

## Acceptance Checks

- `pip install -r slot-3/requirements.txt` completes without error.
- `uvicorn frontend.bas_api:app --port 8001` starts from `slot-3/`.
- `curl http://localhost:8001/api/points` returns JSON with point data.
- `curl http://localhost:8001/api/alarms` returns JSON.
- `curl -X POST http://localhost:8001/api/run/chilled_water_degraded` returns
  scenario summary JSON.
- Browser opens `http://localhost:8001` and shows index landing page.
- `http://localhost:8001/metasys.html` loads, shows point table with equipment
  nav, alarms tab, trends tab, and scenario run panel.
- `http://localhost:8001/niagara.html` loads with Niagara ORD-path nav and
  Niagara terminology throughout.
- `python3 bas_console.py` starts from `slot-3/`, `login metasys` prints ADS
  banner, `ls` lists equipment, `get AHU_OR1_SAT` returns a value, `alarms`
  prints alarm list, `exit` quits cleanly.
- `python3 bas_console.py` with `login niagara` shows Niagara station tree
  and Niagara terminology.
- Smoke test still passes: `bash scripts/run-smoke-test.sh`
- No real facility data, PHI, or real credentials appear in any file.

---

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Metasys UI shows alarm on chilled_water_degraded | Run scenario via UI, check alarms tab | CHW_SUPPLY_TEMP and AHU_OR1_SAT alarms appear with correct priority |
| Niagara UI ORD path navigation | Browse Station tree in niagara.html | All equipment from `equipment.json` appear as JACE/controller nodes |
| CLI alarm acknowledgment flow | `run chilled_water_degraded`, then `alarms` in console | Alarm list populated; `ack` command marks row without server write |
| Trends data accuracy | `trends CHW_SUPPLY_TEMP` in console after degraded run | 12 rows returned, values show degradation progression |

---

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Metasys-style operator interface exists and reads simulator output | `BUILD/4-completedbuilds/BP-002-metasys-niagara-sim.md` | `frontend/static/metasys.html`, `/api/points` JSON response |
| Niagara Workbench-style interface exists with ORD-path navigation | `BUILD/4-completedbuilds/BP-002-metasys-niagara-sim.md` | `frontend/static/niagara.html` |
| Terminal CLI navigates both platforms | `BUILD/4-completedbuilds/BP-002-metasys-niagara-sim.md` | `bas_console.py` |

---

## Residual Risk

- The UI uses synthetic terminology and layout inspired by Metasys and Niagara
  but does not replicate proprietary vendor software. It is a learning scaffold,
  not a certified simulation.
- No authentication on the FastAPI server — this is a local lab tool only.
  Do not expose port 8001 outside localhost.
- Alarm acknowledge is UI-only (session state). No backend write means
  acknowledged alarms reappear on page refresh. Acceptable for lab use.

---

## Worker Instructions

Before editing, confirm:

1. `slot-3/simulator/bas_sim.py` runs and produces output in `data/output/`.
2. `slot-3/data/input/points.json` and `equipment.json` are present and parseable.
3. No `slot-3/frontend/` directory exists yet (new).
4. No `slot-3/bas_console.py` exists yet (new).
5. No `slot-3/requirements.txt` exists yet (new).

Build in order: API → Metasys UI → Niagara UI → index → CLI → scripts.
Run acceptance checks after each step before moving to the next.

If any required field in this plan is missing, stop and report it.
