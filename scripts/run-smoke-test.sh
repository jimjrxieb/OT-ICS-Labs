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

python3 simulator/psychro.py --self-test
python3 simulator/model822.py --self-test
python3 scripts/model822-regression.py --check
python3 scripts/field-verify.py --self-test
python3 simulator/scenario_kernel.py --self-test
python3 scripts/gen-822-inventory.py --self-test
python3 frontend/px_pages.py --self-test
python3 frontend/wiresheets.py --self-test
python3 frontend/platform_admin.py --self-test
node scripts/test-niagara-editor-js.mjs
python3 simulator/bas_sim.py --scenario normal --steps 60
test -s data/output/state_822.json
python3 -c "
import json
s = json.load(open('data/output/latest_points.json'))
s = s['points']          # latest_points.json nests points under 'points'
for p in ('MAU01_SAT','CHW822_BLDG_DT','HALL_A1_RH','RTAC822_EVAP_LVG_TEMP'):
    assert p in s, 'missing 822 point: ' + p
print('822 points present')
"

python3 open-source-stack/bacnet822.py --self-test

echo "slot-3 BAS simulator smoke test passed"
