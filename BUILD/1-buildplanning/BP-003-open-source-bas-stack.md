# BUILD Plan BP-003 — Open Source BAS Stack

**Status:** DRAFT
**Approved by:** — (awaiting J review)
**Approval scope:** Local synthetic lab only — new files under `slot-3/open-source-stack/` and config files only
**Source finding:** `COMPLY/scope-statement.md` open source stack gap (added 2026-06-26);
  `COMPLY/answered-questionnaire.md` §2 BAS Architecture open source row;
  `GP-CONSULTING/OT-SEC/2-BUILD/SOURCE-OF-TRUTH.md` Step 1 open source stack addition
**Target:** `slot-3/open-source-stack/`
**Owner:** ot-build-agent

---

## Why This Build Exists

The COMPLY scope names three enterprise BAS platforms (Metasys, Niagara, Trane) but the
lab currently has no way to teach BACnet protocol behavior — only synthetic file output.

The open source stack fixes this. It wires the same path a real JACE or Network Engine
uses when it polls a field controller:

```
bas_sim.py (data engine)
  -> bacpypes3 BACnet/IP device (localhost:47808)
     <- Node-RED BACnet Read-Property request (node-red-contrib-bacnet)
        -> MQTT publish to Mosquitto broker (localhost:1883)
           -> InfluxDB write (localhost:8086)
              <- Grafana dashboard (localhost:3000)
```

Each tool in this chain teaches a concept that maps directly to real BAS work:

| Tool | Concept it teaches | Real-world equivalent |
|---|---|---|
| bacpypes3 | BACnet object model, device ID, Read-Property, COV Subscribe | Metasys SNE, Niagara JACE as a BACnet server |
| Node-RED | Visual flow programming, poll intervals, BACnet node config | Niagara programming engine, Px graphics wiring |
| MQTT | Pub/sub topic structure, broker, subscriber | Niagara Fox, BACnet/SC |
| InfluxDB | Time-series schema, measurement/tag/field model | Metasys/Niagara historian |
| Grafana | Dashboard panels, alert thresholds, time-range queries | Metasys Trend Viewer, Niagara History Extension |

This is exactly the open source play used in the GP-Copilot security stack
(Semgrep for Checkmarx, Trivy for Prisma Cloud, Falco for Sysdig). Same principle —
open source covers the 80%, teaches the real protocol, no license required.

---

## Approved Context

Worker may use:

- `slot-3/simulator/bas_sim.py` — data engine (read, do not modify)
- `slot-3/data/input/` — point and equipment inventory for BACnet object naming
- `bacpypes3`, `paho-mqtt`, `influxdb-client` Python packages
- Node-RED, Mosquitto, InfluxDB, Grafana installed via Docker Compose or apt
- Synthetic point names and equipment IDs from `equipment.json` and `points.json`

Worker must not use:

- Real hospital data, PHI, real credentials, real vendor hostnames or IPs
- External network access during implementation
- git operations (no stage, commit, push, or branch)

---

## Proposed Change

### Step 1 — Docker Compose stack (`slot-3/open-source-stack/docker-compose.yml`)

Single compose file standing up:
- `mosquitto` — MQTT broker, port 1883
- `influxdb` — time-series DB, port 8086, org `bas-lab`, bucket `bas-trends`
- `grafana` — dashboard, port 3000, pre-configured InfluxDB datasource
- `nodered` — Node-RED, port 1880, with `node-red-contrib-bacnet` and
  `node-red-contrib-influxdb` pre-installed

All services bind localhost only (`127.0.0.1`). No external port exposure.

### Step 2 — bacpypes3 BACnet/IP device (`slot-3/open-source-stack/bacnet_device.py`)

Python script that:
- Reads `data/output/latest_points.json` on startup (and on SIGHUP/interval refresh)
- Creates one BACnet `AnalogInputObject` or `BinaryInputObject` per point,
  using the point name as the object name and setting `presentValue` from the snapshot
- Runs a BACnet/IP application on `localhost:47808`, device ID `1001`
- Accepts Read-Property requests from Node-RED
- Refresh loop: re-reads `latest_points.json` every 30 seconds so running the
  simulator updates live values without restarting the BACnet device

### Step 3 — Node-RED flow (`slot-3/open-source-stack/flows/bas-poll-flow.json`)

Exported Node-RED flow (JSON) that:
- Polls the bacpypes3 device every 60 seconds via BACnet Read-Property
- Reads all 11 points by object ID
- Publishes each reading to MQTT topic `bas/points/<point_name>`
- Writes each reading to InfluxDB `bas-trends` bucket, measurement `point_readings`,
  tags `equipment` and `scenario`, field `value`
- Includes a dashboard tab showing a live table of current point values and
  a simple alert node for any value outside normal range

### Step 4 — Grafana provisioning (`slot-3/open-source-stack/grafana/`)

Provisioned datasource and dashboard JSON so Grafana starts pre-wired:
- `provisioning/datasources/influxdb.yaml` — InfluxDB datasource, Flux query language
- `provisioning/dashboards/bas-overview.json` — Hospital BAS overview dashboard with:
  - One time-series panel per critical point (OR temp, isolation pressure, CHW supply temp, OR humidity)
  - Alert threshold lines at normal_min/normal_max
  - Scenario variable dropdown

### Step 5 — Mosquitto config (`slot-3/open-source-stack/mosquitto/mosquitto.conf`)

Minimal config: listener on 1883, allow anonymous, log to stdout. Localhost only.

### Step 6 — Launcher and README

- `slot-3/open-source-stack/start-stack.sh` — `docker compose up -d`, prints all URLs
- `slot-3/open-source-stack/stop-stack.sh` — `docker compose down`
- `slot-3/open-source-stack/README.md` — explains each tool, its port, its BAS role,
  and maps each to an enterprise equivalent (the open source stack table from COMPLY)

---

## Files In Scope

- `slot-3/open-source-stack/` (new directory, all contents)
  - `docker-compose.yml`
  - `bacnet_device.py`
  - `flows/bas-poll-flow.json`
  - `grafana/provisioning/datasources/influxdb.yaml`
  - `grafana/provisioning/dashboards/bas-overview.json`
  - `mosquitto/mosquitto.conf`
  - `start-stack.sh`
  - `stop-stack.sh`
  - `README.md`

---

## Out Of Scope

- `slot-3/simulator/bas_sim.py` — no changes
- `slot-3/frontend/` — existing FastAPI UI unchanged
- `slot-3/bas_console.py` — unchanged (may add `mqtt` command in a future BP)
- Step 2 OT security layer
- Step 3 AI-assist layer
- Any real BAS, external network, or production system

---

## Acceptance Checks

- `docker compose up -d` completes without error from `slot-3/open-source-stack/`.
- `curl http://localhost:1880` returns Node-RED UI (HTTP 200).
- `curl http://localhost:3000` returns Grafana login (HTTP 200).
- `curl http://localhost:8086/ping` returns HTTP 204 (InfluxDB healthy).
- `mosquitto_sub -t 'bas/#' -C 1` (or equivalent Python) receives a message
  within 90 seconds of Node-RED flow deploying.
- `python3 bacnet_device.py` starts and accepts a Read-Property request:
  ```bash
  python3 -c "
  import asyncio, bacpypes3
  # read present value of AHU_OR1_SAT from device 1001
  " 
  ```
  (or equivalent bacpypes3 read-property call returns a float)
- Grafana Hospital BAS Overview dashboard loads and shows at least one panel
  with data after running a simulator scenario and waiting one poll cycle.
- `python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12`
  followed by a 30-second wait results in updated values visible in Grafana.
- Smoke test still passes: `bash scripts/run-smoke-test.sh`
- No real facility data, credentials, or external network calls in any file.

---

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| BACnet Read-Property round-trip | `bacnet_device.py` running + bacpypes3 read client | presentValue returned for each of 11 points |
| Node-RED → MQTT → InfluxDB flow | Run `chilled_water_degraded`, wait 60s, query InfluxDB | CHW_SUPPLY_TEMP values > 46 F present in `bas-trends` bucket |
| Grafana alarm threshold fires | CHW_SUPPLY_TEMP trend panel | Red threshold line crossed, alert annotation visible |
| Normal scenario clears | Run `normal`, wait 60s | All points within threshold bands in Grafana |

---

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| BACnet/IP protocol stack runs in lab | `BUILD/4-completedbuilds/BP-003-open-source-bas-stack.md` | `open-source-stack/bacnet_device.py`, bacpypes3 read-property output |
| Node-RED polls BACnet and writes to InfluxDB | Same | `open-source-stack/flows/bas-poll-flow.json`, InfluxDB query result |
| Grafana visualizes BAS trends with alert thresholds | Same | `open-source-stack/grafana/provisioning/dashboards/bas-overview.json` |
| Open source stack covers enterprise BAS visualization layer | `COMPLY/scope-statement.md` open source table | All five tools running per acceptance checks |

---

## Residual Risk

- bacpypes3 BACnet/IP device runs on localhost only. It is not exposed to any
  real network. No real BACnet device will discover or respond to it.
- Docker containers bind to 127.0.0.1 only. If Docker host networking changes,
  verify ports remain localhost-bound before continuing.
- Node-RED `node-red-contrib-bacnet` installs at container build time. If the
  package is unavailable, fall back to an MQTT-only flow that reads from
  `latest_points.json` directly.
- Grafana dashboard JSON is provisioned but may need manual panel adjustment
  if InfluxDB Flux query syntax changes between versions.

---

## Worker Instructions

Before building, confirm:

1. Docker and Docker Compose are available: `docker --version && docker compose version`
2. Port 47808 (UDP), 1883, 1880, 3000, 8086 are free on localhost.
3. `slot-3/data/output/latest_points.json` exists (run a scenario first if not).
4. `slot-3/open-source-stack/` does not exist yet (new directory).
5. `bacpypes3` Python package can be installed: `pip install bacpypes3`

Build in order: compose file → bacnet_device.py → mosquitto config → start stack →
Node-RED flow → Grafana provisioning → launcher scripts → README.
Run acceptance checks after each major step before proceeding.
