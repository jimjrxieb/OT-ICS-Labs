# BREAK / PROVE Evidence Plan

## Purpose

This plan names what BREAK should validate and what PROVE should package after
slot-3 BUILD work lands.

## Step 1 Evidence

| Evidence | Path | Proves |
|---|---|---|
| Equipment inventory | `data/input/equipment.json` | Synthetic equipment scope exists. |
| Point inventory | `data/input/points.json` | BACnet-style point model exists. |
| Alarm rules | `data/input/alarm_rules.json` | Alarm criteria are explicit. |
| Trend plan | `data/input/trend_plan.json` | Trend evidence expectations exist. |
| Scenario summary | `data/output/scenario-summary.md` | Simulator run generated a readable summary. |
| Latest points | `data/output/latest_points.json` | Point snapshot is emitted. |
| Alarm output | `data/output/alarms.jsonl` | Alarm evidence is emitted. |
| Trend output | `data/output/trends.csv` | Trend evidence is emitted. |

## Step 2 Evidence

| Evidence | Planned path | Proves |
|---|---|---|
| Purdue map | `docs/purdue-zone-conduit.md` | BAS/IT/remote access boundary is described. |
| Role model | `docs/access-role-model.md` | Operator, technician, vendor, admin, and security roles are defined. |
| Remote access workflow | `docs/remote-access-workflow.md` | Approval, MFA flag, session logging, and denial cases are defined. |
| Backup/restore checklist | `evidence/backup-restore-checklist.md` | Recovery claim has evidence target. |
| Incident/change workflow | `docs/incident-change-workflow.md` | Response and rollback paths are defined. |

## Step 3 Evidence

| Evidence | Planned path | Proves |
|---|---|---|
| AI allowed-use policy | future | AI is advisory only and synthetic-data-only. |
| AI evidence summarization guardrail | future | AI output cannot become operational action without review. |

## BREAK Validation Questions

- Can the simulator generate normal and degraded BAS evidence?
- Are alarms and trends tied to synthetic points?
- Are Step 2 claims blocked until Step 1 evidence exists?
- Does remote access remain a workflow simulation, not a real access path?
- Is every artifact free of real facility data?

## PROVE Package Contents

- `BUILD/BUILD-PLAN.md`
- `BUILD/work-packages/*.md`
- `BUILD/guardrails/*.md`
- `BUILD/evidence-plan/*.md`
- relevant `data/input/*`
- relevant `data/output/*`
- relevant `docs/*`
- relevant `sequences/*`

