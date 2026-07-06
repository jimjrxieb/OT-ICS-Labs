#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "Stopping BAS Open Source Stack..."
docker compose down

echo "Volumes preserved (InfluxDB data, Grafana dashboards, Node-RED state)."
echo "To also remove volumes: docker compose down -v"
