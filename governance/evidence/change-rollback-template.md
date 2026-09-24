# Change Rollback Template — BAS Control Change Reversal

**Data boundary:** Synthetic lab data only. No real hospital, PHI, or production system.
**Owner:** BAS Controls Lead
**Reviewer:** IT/OT Admin (if network or access change); Facilities Director (if critical space impacted)
**Evidence source:** `data/output/latest_points.json`, `data/output/alarms.jsonl`, this completed record
**Use this template when:** a BAS change produces unexpected behavior, new alarms, clinical complaint,
  or when the operator checkout check fails post-change.

---

## Rollback Header

| Field | Value |
|---|---|
| Work order / ticket ID | _(CMMS work order for original change)_ |
| Rollback initiated | _(YYYY-MM-DD HH:MM)_ |
| Operator initiating rollback | _(name)_ |
| Approver | _(name and role)_ |
| Equipment affected | _(e.g. AHU-OR-1, RM-ISO-201)_ |
| Points being rolled back | _(e.g. AHU_OR1_SAT_SP)_ |

---

## Rollback Trigger

What caused the rollback decision? Check all that apply.

- [ ] New critical alarm after change (`ISO201_PRESSURE`, `AHU_OR1_SAT`, `OR1_RH`, or `CHW_SUPPLY_TEMP`)
- [ ] Clinical staff complaint (OR temperature, isolation room pressure, humidity)
- [ ] Downstream space moving away from setpoint and not recovering after 10 minutes
- [ ] Actuator not responding to command
- [ ] Operator checkout check failed — specify which check: ___
- [ ] Unexpected second alarm category activated
- [ ] Other: ___

**Alarm snapshot at rollback decision:** `data/output/alarms.jsonl` — timestamp: ___

---

## Pre-Rollback State

Document current values before reverting — this is the evidence of what the failed state looked like.

| Point | Current (failed) value | Normal range | Delta from normal |
|---|---|---|---|
| `AHU_OR1_SAT` | ___ F | 53–57 F | ___ |
| `OR1_TEMP` | ___ F | 68–72 F | ___ |
| `OR1_RH` | ___ %RH | 30–60 %RH | ___ |
| `ISO201_PRESSURE` | ___ in.w.c. | -0.03 to -0.01 | ___ |
| `CHW_SUPPLY_TEMP` | ___ F | 42–46 F | ___ |

---

## Rollback Steps

| Step | Action | Point or component | Value set | Time |
|---|---|---|---|---|
| 1 | Revert changed point(s) to pre-change value | _(point name)_ | _(original value)_ | ___ |
| 2 | Confirm actuator responds | _(downstream actuator or output)_ | Returns to prior state | ___ |
| 3 | Confirm space trend recovering | _(space temp/pressure point)_ | Moving toward setpoint | ___ |
| 4 | Confirm no new alarms | `data/output/alarms.jsonl` | 0 new critical entries | ___ |

If a controller program was downloaded: restore from the SCT or Workbench backup per
`evidence/backup-restore-checklist.md`.

---

## Post-Rollback Validation

| Check | Point | Expected | Actual | Pass? |
|---|---|---|---|---|
| Rolled-back point at original value | _(point name)_ | _(original value)_ | ___ | ___ |
| OR discharge air temp recovered | `AHU_OR1_SAT` | 53–57 F | ___ | ___ |
| OR room conditions recovered | `OR1_TEMP`, `OR1_RH` | 68–72 F / 30–60 %RH | ___ / ___ | ___ |
| Isolation pressure negative | `ISO201_PRESSURE` | -0.03 to -0.01 | ___ | ___ |
| Active alarms cleared | `data/output/alarms.jsonl` | 0 critical remaining | ___ | ___ |

Run smoke test after rollback to confirm simulator baseline:

```bash
bash scripts/run-smoke-test.sh
```

Smoke test result: _(PASS / FAIL)_

---

## Rollback Outcome

| Field | Value |
|---|---|
| Rollback result | _(COMPLETE / PARTIAL / FAILED)_ |
| Time to normal operation | _(minutes from trigger to green)_ |
| Clinical notification required? | _(yes/no — if yes, document who was notified)_ |
| Root cause identified? | _(yes/no — describe if yes)_ |
| Follow-up work order | _(ticket ID or "none")_ |
| Operator sign-off | _(name + time)_ |
| Supervisor sign-off | _(name + time)_ |

---

## Residual Risk Note

State what remains after the rollback:

- Was the original change goal met? If not, route to a new work order.
- Was the root cause identified? If not, flag as open gap.
- Did the rollback expose a missing backup or procedure gap? Route to
  `evidence/backup-restore-checklist.md` or `COMPLY/scope-statement.md`.

---

## Acceptance Condition

PASS when:
- All post-rollback validation checks are in range.
- Active alarms cleared.
- Smoke test passes.
- Operator and supervisor have signed off.

FAIL when:
- System did not return to normal range after rollback steps.
- New alarms remain after rollback.
- Smoke test fails.
- Root cause is unknown and clinical impact occurred — escalate to incident response.
