# Slot-3 BUILD Plan

## Current Milestone

Step 1: build, simulate, troubleshoot, and document synthetic hospital BAS
behavior.

## Build Tasks

| ID | Task | Acceptance criteria |
|---|---|---|
| BUILD-001 | Create synthetic facility/equipment/point inventory. | `data/input/equipment.json` and `points.json` exist and are readable. |
| BUILD-002 | Create basic BAS simulator. | `python3 simulator/bas_sim.py --scenario normal --steps 12` writes output files. |
| BUILD-003 | Add normal and degraded scenarios. | Normal, chilled-water degraded, and isolation pressure loss scenarios exist. |
| BUILD-004 | Create alarm and trend outputs. | Simulator writes `latest_points.json`, `alarms.jsonl`, and `trends.csv`. |
| BUILD-005 | Add backup/change/checkout templates. | Future pass creates templates under `evidence/` or `docs/`. |
| BUILD-006 | Add Step 2 security layer. | Future pass creates zone/conduit matrix, remote access procedure, access review, logging matrix. |
| BUILD-007 | Add Step 3 AI layer. | Future pass creates AI allowed-use policy and synthetic eval cases. |

## Human-Owned Stops

- Real hospital evidence.
- Real vendor access.
- Production BAS testing.
- Code/life-safety approval.

