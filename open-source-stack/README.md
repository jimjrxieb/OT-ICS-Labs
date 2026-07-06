# Open Source BAS Stack — NAS JAX Hospital Lab

Open source tools covering the same functional layers as Metasys/Niagara/Trane
in a real hospital BAS. No licenses. Real protocols. Same concepts.

---

## The Stack

| Tool | Port | BAS Role | Replaces in Prod |
|---|---|---|---|
| **bacnet_device.py** | 47808 UDP | BACnet/IP server — exposes all 11 points as real BACnet objects | Metasys SNE, Niagara JACE as BACnet server |
| **MQTT / Mosquitto** | 1883 | Pub/sub broker — bridge publishes `bas/points/<name>` every 30s | Niagara Fox protocol bridge |
| **influx_bridge.py** | (host script) | Reads simulator output, publishes MQTT, writes to InfluxDB | Niagara history service, Metasys historian |
| **InfluxDB** | 8086 | Time-series database — stores every point reading | Metasys/Niagara historian |
| **Grafana** | 3000 | Dashboards with alarm thresholds — Hospital BAS Overview | Metasys Trend Viewer, Niagara History Extension |
| **Node-RED** | 1880 | Visual flow programming — mirrors Niagara programming model | Niagara programming engine |

## Data Flow

```
bas_sim.py  →  latest_points.json  →  influx_bridge.py
                                             │
                               ┌─────────────┴────────────┐
                               ▼                          ▼
                      MQTT (Mosquitto)              InfluxDB v2
                      bas/points/<name>             bucket: bas-trends
                           │
                           ▼
                      Node-RED subscribes
                      (live dashboard, scenario triggers)

                      InfluxDB → Grafana
                      (Hospital BAS Overview dashboard)
```

## Quick Start

```bash
# 1. Start the Docker stack (from slot-3/ directory)
bash open-source-stack/start-stack.sh

# 2. Install Python deps (first time only)
pip install -r open-source-stack/requirements.txt

# 3. Run the BACnet device (Terminal 1)
python3 open-source-stack/bacnet_device.py

# 4. Run the data bridge (Terminal 2)
python3 open-source-stack/influx_bridge.py

# 5. Trigger a scenario (Terminal 3)
python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12

# 6. Open Grafana
# http://localhost:3000  →  Hospital BAS Overview
# Login: admin / baslab2026
# Data appears within 30 seconds of the bridge running.
```

## URLs After `start-stack.sh`

| Service | URL | Login |
|---|---|---|
| Node-RED | http://localhost:1880 | none (open) |
| Grafana | http://localhost:3000 | admin / baslab2026 |
| InfluxDB UI | http://localhost:8086 | admin / baslab2026 |
| MQTT broker | localhost:1883 | none (anonymous) |

## What Each Tool Teaches

### bacnet_device.py — BACnet Protocol

The Python `bacpypes3` library creates a real BACnet/IP device:
- **Device instance 1001** — unique identifier on the BACnet network (like an IP address)
- **Object types** — `analogInput` for float values (temperatures, pressures), `binaryInput` for on/off (fan commands, dampers)
- **presentValue** — the live engineering value. This is the property a JACE reads with a `Read-Property` request
- **Engineering units** — `degreesFahrenheit`, `percentRelativeHumidity`, `inchesOfWater`

This is the exact same interaction your JACE at NAS JAX has with an AHU controller.
The JACE sends a BACnet `Read-Property-Request`, the controller sends back the `presentValue`.
bacpypes3 teaches you what's inside that exchange.

### Node-RED — Visual Programming

Node-RED's flow-based programming is functionally identical to Niagara's programming engine:
- **Inject nodes** = Niagara schedule/trigger wires
- **Function nodes** = Niagara logic blocks (PID, comparators, programs)
- **MQTT in/out** = Niagara pub/sub drivers
- **HTTP request nodes** = Niagara web service connectors

The "Trigger Scenarios" tab lets you click a button in Node-RED to POST to the FastAPI
and run a simulator scenario — same as clicking "Execute" in Niagara Workbench.

### InfluxDB — Time-Series Database

Measurement `point_readings`, tags `point_name` / `equipment` / `scenario` / `alarm_state`.

Flux query example (Grafana query editor):
```flux
from(bucket: "bas-trends")
  |> range(start: -1h)
  |> filter(fn: (r) => r._measurement == "point_readings")
  |> filter(fn: (r) => r.point_name == "CHW_SUPPLY_TEMP")
  |> filter(fn: (r) => r._field == "value")
```

### Grafana — Trend Viewer

The Hospital BAS Overview dashboard has 4 panels:
- **OR Supply Air Temperature** — AHU_OR1_SAT, red threshold at 61°F
- **CHW Supply Temperature** — CHW_SUPPLY_TEMP, red threshold at 50°F (chilled_water_degraded scenario)
- **Isolation Room 201 Pressure** — ISO201_PRESSURE, red above 0 (must stay negative)
- **OR Suite Humidity** — OR1_RH, red above 65%RH

This is what you'd see in Metasys Trend Viewer or Niagara History Extension but
built on open source tools with no JCI or Tridium license required.

## Scenarios and What They Show in Grafana

| Scenario | Command | What appears in Grafana |
|---|---|---|
| Normal | `python3 simulator/bas_sim.py --scenario normal --steps 12` | All panels in green band |
| Chilled water degraded | `--scenario chilled_water_degraded --steps 12` | CHW_SUPPLY_TEMP climbs through red threshold |
| Isolation pressure loss | `--scenario isolation_pressure_loss --steps 12` | ISO201_PRESSURE rises toward 0 then crosses |
| OR humidity excursion | `--scenario or_humidity_excursion --steps 12` | OR1_RH climbs into red band |

## Stopping

```bash
bash open-source-stack/stop-stack.sh
# Volumes are preserved (InfluxDB data, Grafana state, Node-RED flows).
# To wipe everything: docker compose down -v
```

## Troubleshooting

**InfluxDB not reachable** — wait 15s after `start-stack.sh`. InfluxDB init takes longer than other services.

**influx_bridge.py says "Cannot connect to MQTT"** — ensure `start-stack.sh` completed. Check `docker compose ps`.

**Grafana shows "No data"** — influx_bridge.py must be running AND a scenario must have run recently.
The bridge writes every 30s; Grafana's default range is "last 1 hour".

**bacnet_device.py API error** — bacpypes3 API changes between minor versions.
Check: `python3 -c "import bacpypes3; print(bacpypes3.__version__)"`.
Target version: 0.0.102. If different, adjust the Application.create() call per the bacpypes3 changelog.

**Node-RED "Trigger Scenarios" tab gets connection refused** — the FastAPI must be running on port 8001:
`bash scripts/start-frontend.sh`

## Credentials (lab only — never real credentials)

All credentials are synthetic, local-only, and have no access to real systems.

| Service | Username | Password | Token |
|---|---|---|---|
| InfluxDB | admin | baslab2026 | baslab-local-token-2026 |
| Grafana | admin | baslab2026 | — |

## Security Note

All Docker services bind to `127.0.0.1` only.
Port 47808 (bacnet_device.py) also binds to `127.0.0.1`.
Nothing in this stack is accessible outside localhost.
No PHI, no real hospital data, no real credentials, no production systems.
