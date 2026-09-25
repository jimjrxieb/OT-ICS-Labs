# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A runnable, fully synthetic building automation system (BAS/OT) training
lab — two fictional buildings (a hospital and an office tower) served by
Metasys-style and Niagara-style browser front ends, a real BACnet/MQTT/
InfluxDB/Grafana data pipeline, a 15-fault trouble-call training mode,
and an adversarial "2AM Call" game where an AI agent breaks the running
system and the human finds it. It lives under `GP-SECLAB/target-application/`
inside the larger GP-Copilot MSSP framework but is self-contained and
does not depend on the rest of the monorepo.

**Everything is synthetic.** No real facility, network, points,
credentials, or vendor data may ever be added (`safety/data-boundary.md`
governs). Everything binds to `127.0.0.1` only — this is a local lab,
not a service.

## Commands

```bash
# Install & baseline data
pip install -r requirements.txt
python3 simulator/bas_sim.py --scenario normal --steps 12
scripts/start-frontend.sh                       # FastAPI on :8001, --reload

# Optional live pipeline (BACnet :47808, MQTT, InfluxDB, Grafana :3000, Node-RED :1880)
pip install -r open-source-stack/requirements.txt
open-source-stack/start-stack.sh                 # stop: open-source-stack/stop-stack.sh

# Smoke test (also the closest thing to a test suite — run after any change
# to simulator/, model822.py, psychro.py, or the 822 inventory generator)
scripts/run-smoke-test.sh

# Self-tests for individual modules (what run-smoke-test.sh calls)
python3 simulator/psychro.py --self-test
python3 simulator/model822.py --self-test
python3 scripts/gen-822-inventory.py --self-test
python3 open-source-stack/bacnet822.py --self-test
python3 scripts/validate-submittal.py --self-test
python3 simulator/scenario_kernel.py --self-test      # S-001 scenario kernel

# Simulator CLI (dependency-free data engine)
python3 simulator/bas_sim.py --scenario {normal,chilled_water_degraded,isolation_pressure_loss,or_humidity_excursion}
python3 simulator/bas_sim.py --fault <ID>                    # from data/input/fault_library.json
python3 simulator/bas_sim.py --steps N --seed N --profile {design_summer,shoulder}
python3 simulator/bas_sim.py --knob EQUIPMENT:KEY=VALUE      # inject a Building 822 fault cause

# Building 822 BACnet/IP server (owns Building 822 state while running;
# bas_sim.py detects its lock file and skips stepping 822)
python3 open-source-stack/bacnet822.py --bbmd

# Design submittal tooling
python3 scripts/validate-submittal.py DESIGN/submittals/P-XX/rev-A
python3 scripts/merge-submittal.py DESIGN/submittals/P-XX/rev-N --apply   # dry-run without --apply
```

No linter or test framework is configured — `scripts/run-smoke-test.sh` is
the verification gate (`set -euo pipefail`, generate + assert files exist +
self-tests). Prove changes work by running it, not by adding a new
framework.

## Architecture

**Data flow:** `simulator/bas_sim.py` is a dependency-free physics/data
engine driven by `data/input/{equipment,points,alarm_rules}.json` and
`data/input/fault_library.json` (15 faults). It writes to `data/output/`
(`latest_points.json`, `trends.csv`, `alarms.jsonl`, `scenario-summary.md`,
`state_822.json`). `frontend/bas_api.py` (FastAPI) reads/writes those same
`data/output/` files — there is no database; JSON/JSONL/CSV files on disk
*are* the state. `frontend/static/*.html` (Metasys/Niagara/landing/tracer
views) are plain HTML/JS with no build step, served by FastAPI.

**Building 822** (`simulator/model822.py`, `simulator/psychro.py`,
`open-source-stack/bacnet822.py`) is a second, more detailed building
layered onto the same lab, with real psychrometrics and a routed BACnet/IP
server exposing 448 objects across 50 field controllers. `bacnet822.py`
and `bas_sim.py` share underlying state via a lock file
(`data/output/.822-bacnet.lock`) — only one owns 822 stepping at a time.
See `docs/bacnet-822.md` for the device topology.

**Live pipeline** (optional, `open-source-stack/`): a BACnet/IP device
(`bacnet_device.py`, port 47808) publishes to Mosquitto (MQTT), an
`influx_bridge.py` poll loop writes to InfluxDB, Grafana dashboards read
InfluxDB, Node-RED does integration/annotation. Docker Compose runs
Mosquitto/InfluxDB/Grafana/Node-RED as containers named `bas-*`; the
BACnet device and Influx bridge run as host processes, not containers.

**CBBP methodology** (Comply → Build → Break → Prove — the parent
GP-Copilot framework's engagement model, scoped down here to lab
construction): `governance/` (COMPLY, BUILD, evidence), `docs/`, `safety/` are
governance/methodology records of how the lab itself was specified and
built — read-only reference, not something to edit while doing lab tasks.
`BREAK/` and `DESIGN/` are the two *playable* tracks, each with its own
strict rulebook an agent must read in full before acting:

- **`BREAK/BREAK.md`** — the 2AM Call game. An agent secretly breaks the
  running system (writes a sealed answer file *before* breaking anything,
  in `BREAK/sealed/`), pages the human like a dispatcher, and grades their
  diagnosis. Hard guardrails: never touch git, blast radius is this repo
  only, only the whitelisted break menu (never edit `simulator/`,
  `frontend/*.py`, `*.html`, `open-source-stack/*.py`, or `data/input/`),
  every break must be proven reversible before it's used, nothing gets
  destroyed (no volume deletion, no `docker compose down -v`). Results
  accumulate in `BREAK/call-log.md`.
- **`DESIGN/DESIGN.md`** — the design-assist track. An agent plays
  senior engineer/EOR, issues a project brief with planted drawing
  discrepancies (rubric sealed in `DESIGN/sealed/` *before* the brief is
  written), reviews submittals in `DESIGN/submittals/P-XX/rev-*/` against
  that rubric, and only merges approved work into `data/input/` via
  `scripts/merge-submittal.py --apply`. Hard guardrails: never touch git,
  write only inside `DESIGN/`, never modify a brief/rubric mid-project,
  never quote the rubric in review comments. Results accumulate in
  `DESIGN/review-log.md`.

`ai-dev-prompts/` holds copy-paste prompts that launch each of these
workflows (setup, 2am-call, fix-my-lab, add-a-fault, teardown,
design-project) — each is self-contained about what to read.

## Repo map

| Path | Purpose |
|---|---|
| `simulator/bas_sim.py` | Dependency-free data engine — scenarios and fault injection |
| `simulator/model822.py`, `psychro.py` | Building 822 physics model |
| `data/input/` | Synthetic inventories: equipment, points, alarm rules, fault_library.json |
| `data/output/` | Generated: point snapshots, alarms, trends, operator/trouble-call logs |
| `frontend/` | FastAPI backend (`bas_api.py`) + Metasys/Niagara/tracer/landing HTML |
| `open-source-stack/` | Docker pipeline (Mosquitto, InfluxDB, Grafana, Node-RED) + BACnet device/bridge/822 server |
| `BREAK/` | The 2AM Call game: `BREAK.md` (rulebook), `sealed/`, `call-log.md` |
| `DESIGN/` | Design-assist track: `DESIGN.md` (rulebook), `briefs/`, `sealed/`, `templates/`, `submittals/`, `review-log.md` |
| `ai-dev-prompts/` | Copy-paste prompts for AI agents (setup, 2am game, repair, add-a-fault, teardown, design) |
| `sequences/` | Synthetic sequences of operation per equipment |
| `bas_console.py` | Terminal CLI client for the same API |
| `scripts/` | `start-frontend.sh`, `run-smoke-test.sh`, submittal validate/merge, 822 tooling |
| `docs/` | Architecture, BACnet-822 device map, access-role model, evidence generation, remote-access workflow |
| `governance/` (`BUILD/`, `COMPLY/`, `evidence/`), `safety/` | Governance/methodology records (how the lab was specified, approved, built, verified) — read-only reference |
