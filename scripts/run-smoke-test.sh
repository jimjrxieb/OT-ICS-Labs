#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 simulator/bas_sim.py --scenario normal --steps 4
test -s data/output/latest_points.json
test -s data/output/trends.csv
test -f data/output/alarms.jsonl

python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 8
test -s data/output/scenario-summary.md

python3 simulator/bas_sim.py --scenario isolation_pressure_loss --steps 8
test -s data/output/scenario-summary.md

python3 frontend/px_pages.py --self-test
python3 frontend/wiresheets.py --self-test
python3 frontend/platform_admin.py --self-test
node scripts/test-niagara-editor-js.mjs

echo "slot-3 BAS simulator smoke test passed"
