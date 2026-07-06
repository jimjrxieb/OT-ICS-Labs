# Slot-3 BUILD Plan - Synthetic Hospital BAS Simulator

## Authority

The source of truth for this BUILD is:

```text
/home/jimmie/linkops-industries/GP-copilot/GP-CONSULTING/OT-SEC/2-BUILD
```

This folder is the implementation queue:

```text
/home/jimmie/linkops-industries/GP-copilot/GP-SECLAB/target-application/slot-3/BUILD
```

## Current Milestone

Step 1 is active: build, simulate, troubleshoot, and document synthetic hospital
BAS behavior.

Step 2 is planned: add OT security layer after Step 1 emits operator evidence.

Step 3 is parked: add AI-assist layer only after Step 1 and Step 2 have
evidence and human review.

## Build Tasks

| ID | Step | Task | Implementation path | Acceptance criteria |
|---|---:|---|---|---|
| BUILD-001 | 1 | Synthetic facility, equipment, controller, and point inventory. | `data/input/` | `equipment.json`, `points.json`, `alarm_rules.json`, and `trend_plan.json` parse and contain synthetic BAS objects. |
| BUILD-002 | 1 | BAS simulator core. | `simulator/bas_sim.py` | `python3 simulator/bas_sim.py --scenario normal --steps 12` writes output files. |
| BUILD-003 | 1 | Operator scenarios. | `simulator/bas_sim.py`, `data/output/` | Normal, chilled-water degraded, isolation pressure loss, and OR humidity excursion scenarios emit expected outputs. |
| BUILD-004 | 1 | Alarm, trend, and summary evidence. | `data/output/` | Simulator writes `latest_points.json`, `alarms.jsonl`, `trends.csv`, and `scenario-summary.md`. |
| BUILD-005 | 1 | Backup, checkout, change, and rollback templates. | `evidence/`, `docs/`, `BUILD/evidence-plan/` | Templates define backup target, restore check, operator checkout, rollback, and evidence paths. |
| BUILD-006 | 2 | Purdue and zone/conduit model. | `docs/`, `BUILD/work-packages/` | L1/L2/L3/L3.5/L4 mapping and conduits are documented with no real network values. |
| BUILD-007 | 2 | Remote-access and role workflow. | `docs/`, `BUILD/guardrails/`, future simulator audit mode | Roles, approval, MFA flag, session logging, and denial cases are documented. |
| BUILD-008 | 2 | Audit, logging, backup/restore, and incident evidence. | `data/output/`, `evidence/`, `BUILD/evidence-plan/` | Audit events and backup/restore evidence expectations are named before BREAK. |
| BUILD-009 | 3 | AI-assist allowed-use and evidence summarization guardrails. | Future only | Advisory-only, synthetic-data-only, human-review-required scope exists before implementation. |

## Dev Acceptance

Dev is allowed to prove only local simulator behavior.

Required checks:

```bash
python3 simulator/bas_sim.py --scenario normal --steps 12
python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12
python3 simulator/bas_sim.py --scenario isolation_pressure_loss --steps 12
python3 simulator/bas_sim.py --scenario or_humidity_excursion --steps 12
scripts/run-smoke-test.sh
```

Pass conditions:

- command exits cleanly,
- output files are generated,
- output files state or inherit the synthetic lab boundary,
- no real facility values are introduced.

## Staging Acceptance

Staging is a stricter configuration of the same synthetic simulator. It must
prove the guardrails before BREAK:

- Step 1 evidence exists before Step 2 claims,
- Purdue map exists before segmentation claims,
- role model exists before remote-access claims,
- backup/restore evidence plan exists before recovery claims,
- audit evidence exists before accountability claims,
- no generated artifact contains real client/facility data.

## Human-Owned Stops

- Real hospital evidence.
- Real vendor access.
- Production BAS testing.
- Active network scanning.
- Controller writes, point overrides, schedules, setpoints, or sequence
  changes against real/production systems. (Synthetic simulator command/
  release — e.g. BP-004 — is in scope for the lab and does not require this
  stop; it still requires its own BP review before implementation.)
- Code/life-safety approval.
- Any production-readiness claim.

## Work Package Queue

| Work package | Status |
|---|---|
| `work-packages/BUILD-001-step1-bas-simulator-foundation.md` | active/planned |
| `work-packages/BUILD-002-step1-evidence-and-templates.md` | planned |
| `work-packages/BUILD-003-step2-ot-security-layer.md` | planned |
| `work-packages/BUILD-004-step3-ai-assist-parked.md` | parked |

## Evidence Plan

Evidence expectations are recorded under:

```text
BUILD/evidence-plan/
```

BREAK validates behavior. PROVE packages evidence. BUILD does not claim a
control is validated or proven by itself.

