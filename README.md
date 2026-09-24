# Synthetic BAS/OT Training Lab — Hospital + Office Portfolio

A runnable, fully synthetic building automation system (BAS) lab for
practicing DDC controls troubleshooting. Two fictional buildings — a
180-bed regional hospital and an 8-floor office tower — served by
Metasys-style and Niagara-style browser front ends, a real BACnet/MQTT/
InfluxDB/Grafana data pipeline, a 15-fault trouble-call training mode,
and an adversarial "2AM Call" chaos game where an AI agent actually
breaks the running system and you find it.

Everything is synthetic. No real facility, network, points, credentials,
or vendor data anywhere in this repo — and none may ever be added.

---

## Prerequisites

- Python 3.11+ and `pip`
- Node.js (tested with v22) — `scripts/run-smoke-test.sh` runs a JavaScript self-test
- Docker with the compose plugin (`docker compose version` should work)
- A modern browser
- *(Optional, for the 2AM Call game)* an AI coding agent CLI — Claude
  Code, Codex, or similar

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

Then open:

| URL | What it is |
|---|---|
| `http://localhost:8001/` | Landing page |
| `http://localhost:8001/metasys` | Metasys ADS-style operator view (hospital) |
| `http://localhost:8001/niagara` | Niagara Workbench-style view — **portfolio tree, both buildings** |
| `http://localhost:8001/docs` | API docs (FastAPI) |

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
Browse the point tree, alarms, and trends in either front end. The
**Technician Panel** tab lets you command writable points and release
overrides (role-gated: pick `technician` or `admin`). Every action is
logged to `data/output/operator_actions.jsonl`.

### 2. Trouble Call training (no AI needed)
Open either front end → **Trouble Call** tab → *Request Trouble Call*.
You get a symptom only ("Floor 3 tenants report their space has been
getting warmer all morning"). Investigate using Points/Alarms/Trends,
then submit equipment + root-cause category. You're graded, shown the
answer, and told what the data was telling you. 15 faults across both
buildings — sensor failures, stuck actuators, plant failures, a JACE
comms loss, and one compound fault modeled on a real field failure
(fouled CHW strainer + leaking valve actuator → condensate drain safety
trip). Two faults deliberately share the same symptom so only the trends
can tell you upstream from downstream.

### 3. The 2AM Call game (AI agent required)
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

---

## The Buildings

| | NAS JAX Regional Medical Center (synthetic) | Riverside Office Tower (synthetic) |
|---|---|---|
| Character | Life-safety-driven: OR temp/humidity, isolation room pressure, sterile spaces | Comfort/energy-driven: economizer, reheat, tenant complaints |
| Equipment | OR + ICU AHUs, OR VAV, isolation room pressure controller, CHW + HW plants | Rooftop VAV AHU w/ economizer, VAV w/ reheat, air-cooled chiller, condensing boiler |
| Front end | Metasys (vendor-locked) + Niagara | Niagara only — federated under the portfolio Supervisor |
| Alarm posture | `critical` on life-safety points | `medium`/`high` — nothing here hurts a patient |

## Repo Map

| Path | Purpose |
|---|---|
| `simulator/bas_sim.py` | Dependency-free data engine — scenarios and fault injection (`--scenario`, `--fault`) |
| `data/input/` | Synthetic inventories: equipment, points, alarm rules, **fault_library.json** (15 faults) |
| `data/output/` | Generated: point snapshots, alarms, trends, operator/trouble-call logs |
| `frontend/` | FastAPI backend + Metasys/Niagara/landing HTML (no build tools, no CDN) |
| `open-source-stack/` | Docker pipeline: Mosquitto, InfluxDB, Grafana, Node-RED + BACnet device & Influx bridge |
| `BREAK/` | The 2AM Call game: `BREAK.md` (agent rulebook), `sealed/` (hidden answers), `call-log.md` |
| `ai-dev-prompts/` | **Copy-paste prompts for any AI agent** — setup/deploy, play the 2AM game, repair the lab, add your own war-story fault, teardown |
| `sequences/` | Synthetic sequences of operation per equipment |
| `bas_console.py` | Terminal CLI client for the same API |
| `scripts/` | `start-frontend.sh`, `run-smoke-test.sh` |
| `governance/` (`BUILD/`, `COMPLY/`, `evidence/`), `docs/`, `safety/` | Governance and methodology records — how this lab was specified, approved, built, and verified (CBBP: Comply → Build → Break → Prove). Optional reading; some internal docs reference the author's larger consulting framework and won't resolve outside it. |

## Safety & Data Boundary

- Everything binds to `127.0.0.1` only. This is a local lab, not a service.
- Synthetic data only — never add real hospital/facility data, PHI,
  credentials, IPs, hostnames, vendor remote-access details, or real
  Metasys/Niagara exports/screenshots.
- The 2AM agent's rulebook (`BREAK/BREAK.md`) hard-limits breaks to this
  repo, reversible actions only, with restore commands recorded before
  every break.
- Nothing here is a real design sequence or code/life-safety approval.
