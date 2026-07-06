# BUILD-001 - Step 1 BAS Simulator Foundation

| Field | Value |
|---|---|
| Roadmap step | `1 BAS simulator` |
| Status | `active/planned` |
| Source plan | `GP-CONSULTING/OT-SEC/2-BUILD/1-buildplanning/slot-3/BUILD-20260626-001-bas-simulator-dev-staging-foundation.md` |
| Data class | `synthetic internal` |
| Human review | `yes before completion claim` |

## Source Requirement

Build a synthetic hospital BAS simulator that can emit equipment, point,
alarm, trend, and scenario evidence before any OT security controls are claimed.

## Implementation Scope

- `data/input/equipment.json`
- `data/input/points.json`
- `data/input/alarm_rules.json`
- `data/input/trend_plan.json`
- `simulator/bas_sim.py`
- `data/output/`
- `scripts/run-smoke-test.sh`

## Dev Acceptance

```bash
python3 simulator/bas_sim.py --scenario normal --steps 12
python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12
python3 simulator/bas_sim.py --scenario isolation_pressure_loss --steps 12
python3 simulator/bas_sim.py --scenario or_humidity_excursion --steps 12
scripts/run-smoke-test.sh
```

Pass when outputs exist and remain synthetic.

## Staging Acceptance

- Run all scenarios with deterministic seeds.
- Confirm output files exist.
- Confirm no real facility identifiers are present.
- Confirm Step 2 claims remain planned unless security artifacts exist.

## BREAK Validation

BREAK should verify scenario outputs, alarm generation, trend rows, and
synthetic boundary statements.

## PROVE Evidence

- `data/input/*.json`
- `data/output/latest_points.json`
- `data/output/alarms.jsonl`
- `data/output/trends.csv`
- `data/output/scenario-summary.md`

## Rollback / Abandon

Revert simulator input or code changes and regenerate outputs from the last
known-good seeded run.

