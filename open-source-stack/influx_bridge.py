#!/usr/bin/env python3
"""
BAS Data Bridge — NAS JAX BAS Lab

Reads ../data/output/latest_points.json every 30 seconds.
For each point, publishes to MQTT and writes to InfluxDB.

Data path this teaches:
  bas_sim.py → latest_points.json → influx_bridge.py
                                          │
                            ┌─────────────┴────────────┐
                            ▼                          ▼
                   MQTT topic                   InfluxDB v2
                   bas/points/<name>            bucket: bas-trends
                   (Mosquitto:1883)             measurement: point_readings
                        │
                        ▼
                   Node-RED subscribes
                   (dashboard, alerts)

Enterprise equivalent:
  Niagara JACE polls field controller, publishes to Niagara history + alarm service
  Metasys SNE polls BACnet field device, writes to Metasys historian

Usage:
  pip install paho-mqtt influxdb-client
  Start docker stack first: bash open-source-stack/start-stack.sh
  cd slot-3/
  python3 open-source-stack/influx_bridge.py

Run scenarios to update values:
  python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12
"""
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("influx_bridge")

SLOT3_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = SLOT3_ROOT / "data" / "output" / "latest_points.json"

MQTT_HOST = "localhost"
MQTT_PORT = 1883
MQTT_TOPIC_PREFIX = "bas/points"

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "baslab-local-token-2026"
INFLUX_ORG = "bas-lab"
INFLUX_BUCKET = "bas-trends"

POLL_INTERVAL = 30  # seconds

# Maps point_name → equipment_id (from data/input/equipment.json)
EQUIPMENT_MAP = {
    "AHU_OR1_SAT": "AHU-OR-1",
    "AHU_OR1_SAT_SP": "AHU-OR-1",
    "AHU_OR1_FAN_CMD": "AHU-OR-1",
    "OR1_TEMP": "VAV-OR-101",
    "OR1_RH": "VAV-OR-101",
    "OR1_TEMP_SP": "VAV-OR-101",
    "ISO201_PRESSURE": "RM-ISO-201",
    "ISO201_EXH_CMD": "RM-ISO-201",
    "CHW_SUPPLY_TEMP": "CHW-PLANT-1",
    "CHW_DIFF_PRESSURE": "CHW-PLANT-1",
    "HW_SUPPLY_TEMP": "HW-PLANT-1",
}

# Normal operating ranges for alarm state tagging
NORMAL_RANGES = {
    "AHU_OR1_SAT": (52.0, 60.0),
    "AHU_OR1_SAT_SP": (50.0, 60.0),
    "OR1_TEMP": (68.0, 75.0),
    "OR1_TEMP_SP": (68.0, 73.0),
    "OR1_RH": (20.0, 60.0),
    "ISO201_PRESSURE": (-0.05, -0.005),
    "CHW_SUPPLY_TEMP": (42.0, 48.0),
    "CHW_DIFF_PRESSURE": (8.0, 22.0),
    "HW_SUPPLY_TEMP": (130.0, 165.0),
}


def load_snapshot() -> dict | None:
    if not DATA_FILE.exists():
        log.warning("latest_points.json not found — run a scenario first")
        return None
    with DATA_FILE.open() as f:
        return json.load(f)


def alarm_state(name: str, value: float) -> str:
    if name not in NORMAL_RANGES:
        return "NORMAL"
    lo, hi = NORMAL_RANGES[name]
    return "NORMAL" if lo <= value <= hi else "ALARM"


def run(mqtt_client, influx_write_api):
    log.info("Bridge running — polling every %ds", POLL_INTERVAL)
    while True:
        snapshot = load_snapshot()
        if snapshot:
            points = snapshot.get("points", {})
            scenario = snapshot.get("scenario", "unknown")
            ts = datetime.now(timezone.utc)

            published = 0
            written = 0

            for name, raw in points.items():
                value = float(raw)
                equip = EQUIPMENT_MAP.get(name, "UNKNOWN")
                state = alarm_state(name, value)

                payload = {
                    "point_name": name,
                    "value": value,
                    "equipment": equip,
                    "alarm_state": state,
                    "scenario": scenario,
                    "timestamp": ts.isoformat(),
                }

                # Publish to MQTT
                topic = f"{MQTT_TOPIC_PREFIX}/{name}"
                result = mqtt_client.publish(topic, json.dumps(payload), qos=0)
                if result.rc == 0:
                    published += 1

                # Write to InfluxDB
                try:
                    from influxdb_client import Point as InfluxPoint

                    p = (
                        InfluxPoint("point_readings")
                        .tag("point_name", name)
                        .tag("equipment", equip)
                        .tag("scenario", scenario)
                        .tag("alarm_state", state)
                        .field("value", value)
                        .time(ts)
                    )
                    influx_write_api.write(bucket=INFLUX_BUCKET, record=p)
                    written += 1
                except Exception as exc:
                    log.warning("InfluxDB write failed for %s: %s", name, exc)

            log.info(
                "scenario=%-30s  MQTT %d/%d  InfluxDB %d/%d  alarms=%d",
                scenario,
                published,
                len(points),
                written,
                len(points),
                sum(1 for n, v in points.items() if alarm_state(n, float(v)) == "ALARM"),
            )

        time.sleep(POLL_INTERVAL)


def main():
    try:
        import paho.mqtt.client as mqtt_lib
    except ImportError:
        log.error("paho-mqtt not installed. Run: pip install paho-mqtt==2.1.0")
        sys.exit(1)

    try:
        from influxdb_client import InfluxDBClient
        from influxdb_client.client.write_api import SYNCHRONOUS
    except ImportError:
        log.error("influxdb-client not installed. Run: pip install influxdb-client==1.45.0")
        sys.exit(1)

    # MQTT setup
    mqtt = mqtt_lib.Client(mqtt_lib.CallbackAPIVersion.VERSION2, client_id="bas-bridge")

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            log.info("MQTT connected to %s:%d", MQTT_HOST, MQTT_PORT)
        else:
            log.error("MQTT connect failed: rc=%s", reason_code)

    mqtt.on_connect = on_connect

    try:
        mqtt.connect(MQTT_HOST, MQTT_PORT, keepalive=60)
    except Exception as exc:
        log.error("Cannot connect to MQTT at %s:%d — is the stack running?", MQTT_HOST, MQTT_PORT)
        log.error("  Start with: bash open-source-stack/start-stack.sh")
        log.error("  Error: %s", exc)
        sys.exit(1)

    mqtt.loop_start()

    # InfluxDB setup
    try:
        influx = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        write_api = influx.write_api(write_options=SYNCHRONOUS)
        # Verify connection
        influx.ping()
        log.info("InfluxDB connected at %s", INFLUX_URL)
    except Exception as exc:
        log.error("Cannot connect to InfluxDB at %s — is the stack running?", INFLUX_URL)
        log.error("  Start with: bash open-source-stack/start-stack.sh")
        log.error("  Error: %s", exc)
        sys.exit(1)

    try:
        run(mqtt, write_api)
    except KeyboardInterrupt:
        log.info("Bridge stopped")
    finally:
        mqtt.loop_stop()
        mqtt.disconnect()
        influx.close()


if __name__ == "__main__":
    main()
