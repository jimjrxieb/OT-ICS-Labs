#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SLOT3_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== BAS Open Source Stack — NAS JAX Lab ==="
echo

# Check Docker
if ! docker compose version &>/dev/null; then
    echo "ERROR: docker compose not found. Install Docker Desktop or docker-compose-plugin."
    exit 1
fi

# Check that a data file exists so the bridge has something to read
if [[ ! -f "$SLOT3_DIR/data/output/latest_points.json" ]]; then
    echo "INFO: No simulator output yet — running a normal scenario first..."
    cd "$SLOT3_DIR"
    python3 simulator/bas_sim.py --scenario normal --steps 12
    cd "$SCRIPT_DIR"
fi

echo "Starting containers..."
cd "$SCRIPT_DIR"
docker compose up -d --build

echo
echo "Waiting for services to be ready..."
sleep 8

# Health checks
PASS=0; FAIL=0

check() {
    local name=$1 url=$2 expected=$3
    code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null || echo "000")
    if [[ "$code" == "$expected" ]]; then
        echo "  [OK]   $name — $url"
        ((PASS++)) || true
    else
        echo "  [WAIT] $name — $url (HTTP $code, expected $expected)"
        ((FAIL++)) || true
    fi
}

check "Node-RED"   "http://localhost:1880" "200"
check "Grafana"    "http://localhost:3000" "200"
check "InfluxDB"   "http://localhost:8086/ping" "204"

echo

if [[ $FAIL -gt 0 ]]; then
    echo "Some services are still starting. Run again in 15s or check: docker compose logs"
fi

echo "=== Stack URLs ==="
echo "  Node-RED  http://localhost:1880  (visual flows, trigger scenarios)"
echo "  Grafana   http://localhost:3000  (trends, alarm thresholds — admin/baslab2026)"
echo "  InfluxDB  http://localhost:8086  (time-series DB — admin/baslab2026)"
echo "  MQTT      localhost:1883         (Mosquitto broker)"
echo

echo "=== Next steps ==="
echo "  1. Install Python deps (first time only):"
echo "       pip install -r open-source-stack/requirements.txt"
echo
echo "  2. Start the BACnet device (one terminal):"
echo "       cd $SLOT3_DIR"
echo "       python3 open-source-stack/bacnet_device.py"
echo
echo "  3. Start the data bridge (another terminal):"
echo "       cd $SLOT3_DIR"
echo "       python3 open-source-stack/influx_bridge.py"
echo
echo "  4. Run a scenario to generate data:"
echo "       python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12"
echo
echo "  5. Open Grafana at http://localhost:3000 → Hospital BAS Overview"
echo "     Data appears within 30 seconds of influx_bridge.py running."
echo
