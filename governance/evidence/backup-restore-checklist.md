# Backup and Restore Checklist — Synthetic Regional Medical Center BAS

**Data boundary:** Synthetic lab data only. No real hospital, PHI, or production system.
**Owner:** BAS Controls Lead
**Reviewer:** IT/OT Admin
**Evidence source:** `slot-3/data/output/` (simulator run log), this completed checklist
**Last validated restore:** NOT YET RUN — see residual risk

---

## BAS Components in Backup Scope

| Component ID | Type | Vendor | Backup Target | Backup Method | Frequency |
|---|---|---|---|---|---|
| MET-ADS-01 | Metasys server | Johnson Controls | Database + SCT archive | Metasys SCT export to backup share | Weekly |
| MET-SNE-01 | Supervisory network engine | Johnson Controls | Controller configuration | Metasys SCT device backup | Weekly |
| N4-SUP-01 | Niagara Supervisor | Tridium | Station `.dist` file | Workbench station backup | Weekly |
| JACE-OT-01 | Niagara JACE | Tridium | JACE station `.dist` | Workbench JACE backup | Weekly |
| TRN-SC-01 | Tracer SC+ | Trane | Unit configuration | Tracer SC+ config export | Monthly |
| JCI-FEC-OR1 | AHU-OR-1 field controller | Johnson Controls | Controller program + config | SCT device export | After any change |
| JACE-RPC-ISO201 | RM-ISO-201 room pressure controller | Tridium | Station slot config | Workbench backup | After any change |

---

## Pre-Backup Checklist

- [ ] Confirm backup storage path is accessible and has sufficient space
- [ ] Confirm no active alarms on `AHU-OR-1`, `RM-ISO-201`, or `CHW-PLANT-1` that indicate unstable state
- [ ] Confirm all critical points are in normal range before backup
      (reference: `data/output/latest_points.json` — check `OR1_RH`, `ISO201_PRESSURE`, `CHW_SUPPLY_TEMP`)
- [ ] Document backup run ID (ISO timestamp) and operator name in this checklist
- [ ] Confirm BAS server (`MET-ADS-01`, `N4-SUP-01`) is not mid-upgrade or mid-sync

---

## Backup Execution Record

| Field | Value |
|---|---|
| Run ID | _(ISO timestamp — e.g. 20260626T120000Z)_ |
| Operator | _(name)_ |
| Date | _(YYYY-MM-DD)_ |
| Backup files written | _(list paths)_ |
| Backup size | _(MB)_ |
| Verification hash or file count | _(value)_ |

---

## Restore Procedure

> **Lab note:** This procedure is synthetic. It documents the expected steps.
> A restore has not been executed in this lab — that is a known gap (see residual risk).

1. **Trigger condition:** BAS server data loss, controller program corruption, or post-incident recovery.
2. **Approval required:** BAS Controls Lead + IT/OT Admin + Facilities Director sign-off before restore.
3. **Pre-restore snapshot:** Document current alarm state from `data/output/alarms.jsonl`.
4. **Restore steps:**
   - MET-ADS-01: restore SCT archive to known-good backup, re-commission devices.
   - N4-SUP-01 / JACE-OT-01: restore `.dist` file via Workbench, verify station starts.
   - TRN-SC-01: restore config export via Tracer service tool.
   - Field controllers: re-download programs via SCT or Workbench.
5. **Post-restore validation:**
   - [ ] All critical points reading (`ISO201_PRESSURE`, `AHU_OR1_SAT`, `OR1_RH`, `CHW_SUPPLY_TEMP`)
   - [ ] No unexpected alarms in alarm panel
   - [ ] Trend data resuming for all critical points
   - [ ] Operator can log in to Metasys ADS and Niagara Supervisor

---

## Restore Execution Record

| Field | Value |
|---|---|
| Restore run ID | _(ISO timestamp)_ |
| Restored from backup dated | _(date)_ |
| Operator | _(name)_ |
| Approval obtained from | _(names and roles)_ |
| Critical points validated | _(pass/fail per point)_ |
| Alarms post-restore | _(count and list)_ |
| Restore result | _(PASS / FAIL / PARTIAL)_ |

---

## Acceptance Condition

PASS when:
- All components in scope have a dated backup on file.
- Post-restore validation shows all critical points reading within normal range.
- No unexpected alarms remain after restore.

FAIL when:
- Any component backup is missing or older than the defined frequency.
- Post-restore validation cannot confirm critical point readings.
- Restore results in new alarms not present before the restore.

---

## Residual Risk

- **Restore has not been tested in this lab.** The procedure above documents expected steps
  only. Until a restore-test run is executed and this record is completed, backup claims
  are unsupported. Route to PROVE once a restore test is run.
- Shared vendor account still exists as a synthetic current-state gap (see
  `COMPLY/scope-statement.md`). Backup access using the shared account is not attributed.
