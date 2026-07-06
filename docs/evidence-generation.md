# Evidence Generation — Slot-3 Synthetic Hospital BAS

**Data boundary:** Synthetic lab data only. No real hospital, PHI, or production system.
**Owner:** BAS Controls Lead / BREAK Engineer
**Purpose:** Explains how to run the simulator to generate evidence, what each output file
  contains, and how the evidence templates in `evidence/` map to simulator output.

---

## Prerequisites

Python 3.8+ is required. No packages to install — the simulator uses the standard library only.

```bash
python3 --version   # must be 3.8+
```

Run all commands from the `slot-3/` root directory.

---

## Running the Simulator

The simulator is `simulator/bas_sim.py`. It reads input from `data/input/` and
writes output to `data/output/`. Every run overwrites the output files.

### Available Scenarios

| Scenario flag | What it simulates |
|---|---|
| `normal` | All systems operating within normal range. Baseline. |
| `chilled_water_degraded` | CHW supply temp rising, differential pressure falling, OR conditions drifting. |
| `isolation_pressure_loss` | ISO-201 room pressure drifting toward zero. Life-safety critical alarm. |
| `or_humidity_excursion` | OR-1 relative humidity rising above surgical limits. |

### Command Reference

```bash
# Run normal scenario, 12 steps (1 step = 1 synthetic minute)
python3 simulator/bas_sim.py --scenario normal --steps 12

# Run chilled water degradation
python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12

# Run isolation room pressure loss
python3 simulator/bas_sim.py --scenario isolation_pressure_loss --steps 12

# Run OR humidity excursion
python3 simulator/bas_sim.py --scenario or_humidity_excursion --steps 12

# Run with a specific random seed (for reproducible output)
python3 simulator/bas_sim.py --scenario normal --steps 12 --seed 42

# Smoke test — runs normal + chilled_water_degraded + isolation_pressure_loss
bash scripts/run-smoke-test.sh
```

---

## Output Files

All output is written to `data/output/`. Each run overwrites these four files.

### `latest_points.json`

Final step point snapshot. Use for: pre/post-change state evidence, operator checkout
pre-change check, alarm dashboard baseline.

```json
{
  "scenario": "chilled_water_degraded",
  "generated_at": "2026-06-26T12:00:00+00:00",
  "data_boundary": "synthetic lab data only",
  "points": {
    "AHU_OR1_SAT": 62.1,
    "CHW_SUPPLY_TEMP": 51.8,
    ...
  }
}
```

Key fields:
- `data_boundary` — always `"synthetic lab data only"`. Must be present for PROVE.
- `generated_at` — ISO 8601 timestamp of the run.
- `points` — map of point name to final step value.

### `alarms.jsonl`

One JSON object per line, one line per alarm event across all steps. Empty if no alarms.
Use for: alarm count verification, BREAK validation, operator alarm acknowledgment practice.

```jsonl
{"equipment": "RM-ISO-201", "message": "Isolation Room 201 pressure not negative", "normal_max": -0.01, "normal_min": -0.03, "point": "ISO201_PRESSURE", "priority": "critical", "timestamp": "2026-06-25T12:00:00+00:00", "units": "in.w.c.", "value": -0.008}
```

Key fields:
- `priority` — `"critical"`, `"high"`, or `"medium"`.
- `point` — the BAS point that triggered the alarm.
- `equipment` — the equipment the point belongs to.
- `value` / `normal_min` / `normal_max` — what was measured vs. what was expected.

### `trends.csv`

One row per point per step. 11 points × 12 steps = 132 rows per run.
Use for: trend review in operator checkout, BREAK trend accuracy checks, sparkline data for UI.

```
timestamp,scenario,point,equipment,value,units
2026-06-25T12:00:00+00:00,normal,AHU_OR1_SAT,AHU-OR-1,55.234,F
```

Key columns:
- `timestamp` — ISO 8601, increments by 1 minute per step.
- `point` — matches point names in `data/input/points.json`.
- `value` — synthetic sensor reading for that step.

### `scenario-summary.md`

Human-readable summary: snapshot count, trend row count, alarm count, per-alarm breakdown.
Use for: quick BREAK/PROVE summary artifact, verifying expected alarm counts against
`evidence/scenario-evidence-index.md`.

---

## How Evidence Templates Map to Simulator Output

| Template | Simulator output it references | How to use |
|---|---|---|
| `evidence/backup-restore-checklist.md` | `latest_points.json` (pre-backup state check) | Run `normal` scenario, record point values in pre-backup checklist before any backup procedure |
| `evidence/operator-checkout-template.md` | `latest_points.json` (pre-change check) + `trends.csv` (trend review) + `alarms.jsonl` (post-change alarm check) | Run `normal` before the change; run the relevant scenario after the change; fill in template fields from output |
| `evidence/change-rollback-template.md` | `alarms.jsonl` (rollback trigger alarm snapshot) + `latest_points.json` (pre-rollback state) | Run the degraded scenario to simulate the failed state; fill in pre-rollback values from output; run `normal` again to simulate rollback success |
| `evidence/scenario-evidence-index.md` | All four output files for all four scenarios | Run all four scenarios; use index to verify expected alarm counts and trend row counts match actual output |

---

## Workflow: BREAK Validation

Use this sequence during the BREAK phase to validate simulator evidence:

```bash
# 1. Run all four scenarios
python3 simulator/bas_sim.py --scenario normal --steps 12
python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12
python3 simulator/bas_sim.py --scenario isolation_pressure_loss --steps 12
python3 simulator/bas_sim.py --scenario or_humidity_excursion --steps 12

# 2. Run smoke test
bash scripts/run-smoke-test.sh

# 3. Verify alarm counts against scenario-evidence-index.md
python3 -c "
import json
alarms = [json.loads(l) for l in open('data/output/alarms.jsonl') if l.strip()]
by_priority = {}
for a in alarms:
    by_priority[a['priority']] = by_priority.get(a['priority'], 0) + 1
print(by_priority)
"

# 4. Verify trend row count
python3 -c "
import csv
rows = list(csv.DictReader(open('data/output/trends.csv')))
print(f'Trend rows: {len(rows)} (expected 132)')
"

# 5. Verify data boundary tag
python3 -c "
import json
snap = json.loads(open('data/output/latest_points.json').read())
print('data_boundary:', snap.get('data_boundary'))
"
```

All checks should pass before BREAK evidence is cited in a PROVE artifact.
