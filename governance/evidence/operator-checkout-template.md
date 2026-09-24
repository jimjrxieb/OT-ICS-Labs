# Operator Checkout Template — BAS Change Verification

**Data boundary:** Synthetic lab data only. No real hospital, PHI, or production system.
**Owner:** BAS Operator / BAS Controls Lead
**Evidence source:** `data/output/latest_points.json`, `data/output/trends.csv`, this completed record
**Use this template for:** setpoint changes, schedule changes, override commands, valve/damper tuning,
  controller program downloads, and any commanded change to a BAS point or sequence.

---

## Change Header

| Field | Value |
|---|---|
| Work order / ticket ID | _(CMMS work order number)_ |
| Date and time | _(YYYY-MM-DD HH:MM — local)_ |
| Operator performing change | _(name)_ |
| Supervisor / approver | _(name and role)_ |
| Equipment affected | _(e.g. AHU-OR-1, RM-ISO-201)_ |
| Points affected | _(e.g. AHU_OR1_SAT_SP, OR1_TEMP_SP)_ |
| Reason for change | _(clinical request / seasonal / corrective / preventive / test)_ |
| Critical space impact | _(yes/no — if yes, name the space: OR Suite, ICU, Isolation Room 201, etc.)_ |

---

## Pre-Change Checks

Verify current state before touching anything.

| Check | Point or source | Expected | Actual | Pass? |
|---|---|---|---|---|
| Discharge air temp in range | `AHU_OR1_SAT` | 53–57 F | ___ | ___ |
| OR room temp in range | `OR1_TEMP` | 68–72 F | ___ | ___ |
| OR humidity in range | `OR1_RH` | 30–60 %RH | ___ | ___ |
| Isolation room pressure negative | `ISO201_PRESSURE` | -0.03 to -0.01 in.w.c. | ___ | ___ |
| Chilled water supply temp in range | `CHW_SUPPLY_TEMP` | 42–46 F | ___ | ___ |
| No active critical alarms | `data/output/alarms.jsonl` | 0 critical | ___ | ___ |
| Fan running (if AHU work) | `AHU_OR1_FAN_CMD` | 1 (on) | ___ | ___ |

**Pre-change state snapshot:** `data/output/latest_points.json` — timestamp: ___

If any pre-change check fails, **stop and report to supervisor before proceeding.**

---

## Change Record

| Field | Value |
|---|---|
| Point(s) commanded | _(point name)_ |
| Previous value | _(value + units)_ |
| New value / command | _(value + units)_ |
| Change method | _(Metasys ADS / Niagara Workbench / Tracer SC+ / console)_ |
| Time of change | _(HH:MM)_ |

---

## Post-Change Response Check (Physical + Logical)

Wait for the system to respond — minimum 2 minutes for air-side, 5 minutes for plant loop.

| Check | Point | Expected after change | Actual | Pass? |
|---|---|---|---|---|
| Actuator/command responds | _(commanded point)_ | Value matches command | ___ | ___ |
| Downstream space responds | _(space temp or pressure point)_ | Moving toward setpoint | ___ | ___ |
| No new alarms generated | `data/output/alarms.jsonl` | No new entries | ___ | ___ |
| Adjacent spaces unaffected | _(relevant neighbor point)_ | Within normal range | ___ | ___ |

---

## Trend Review

Run the simulator for the relevant scenario and verify trend data reflects expected behavior.

```bash
python3 simulator/bas_sim.py --scenario normal --steps 12
```

| Point trended | Trend file | Rows reviewed | Behavior as expected? |
|---|---|---|---|
| _(point name)_ | `data/output/trends.csv` | 12 | _(yes/no — describe if no)_ |

---

## Closeout Note

| Field | Value |
|---|---|
| Change outcome | _(COMPLETED / ABORTED / PARTIAL)_ |
| System returned to normal operation? | _(yes/no)_ |
| Follow-up work order needed? | _(yes/no — if yes, ticket ID)_ |
| Operator sign-off | _(name + time)_ |
| Supervisor sign-off | _(name + time)_ |
| Rollback needed? | _(yes/no — if yes, complete change-rollback-template.md)_ |

---

## Acceptance Condition

PASS when:
- All pre-change checks were in range before the change.
- Post-change response check confirms actuator response and no new alarms.
- Trend data shows expected behavior for at least 12 steps.
- Closeout signed by operator and supervisor.

FAIL when:
- Any pre-change check was out of range and change proceeded without supervisor approval.
- New critical alarms generated after the change.
- Downstream space moved away from setpoint and did not recover.
- Rollback was required — complete `change-rollback-template.md`.
