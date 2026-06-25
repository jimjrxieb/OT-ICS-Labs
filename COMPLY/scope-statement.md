# Synthetic Hospital BAS Scope Statement

## Scope

This lab covers a fictional 180-bed regional hospital BAS used to model and
validate BAS operator and OT security readiness. In scope:

- Emergency department trauma bays.
- ICU and patient comfort zones.
- OR suite environmental control.
- Airborne isolation room pressure control.
- Pharmacy temperature monitoring.
- Imaging equipment-room cooling.
- Sterile processing ventilation.
- Central chilled-water and hot-water loops.
- BAS operator front end, supervisory controllers, selected field controllers,
  alarms, trends, remote access pattern, backups, and monitoring handoff.

## Vendor/Program Stack

| Vendor/program | Synthetic role |
|---|---|
| Johnson Controls Metasys | Main BAS front end, ADS/ADX-style server, SNE/SNC-style supervisory engines, SCT archive concept. |
| Trane | Tracer SC+ for selected AHUs/RTUs, Tracer TU service-tool concept, unit controllers. |
| Tridium Niagara | Integration supervisor, JACE edge controllers, Workbench engineering access concept. |
| CMMS/ticketing | Work orders, after-hours escalation, change records. |
| SIEM/logging | Step 2 target for auth, remote access, firewall, alarm, backup, and change telemetry. |

## Explicit Exclusions

- Real hospital systems.
- Real base facilities.
- PHI or patient records.
- Real credentials, hostnames, IPs, serial numbers, screenshots, diagrams, or
  vendor remote-access details.
- Fire alarm, nurse call, medical devices, elevators, and life-safety systems.
- Production testing or active scanning.
- Code or life-safety compliance approval.

## Current Synthetic Gaps

| Gap | Risk | Recommendation | Route |
|---|---|---|---|
| Restore has not been tested. | Backup claims are unsupported. | Add lab restore-validation procedure and evidence record. | BUILD -> PROVE |
| Shared vendor account exists in synthetic current state. | Poor attribution for high-authority access. | Replace with named vendor users and access review. | BUILD -> MONITOR |
| Zone/conduit map is first-pass only. | Segmentation claims are not detailed enough. | Build zone/conduit matrix with allowed protocols. | BUILD -> BREAK |
| No tabletop exercise yet. | Incident path is unproven. | Run synthetic isolation pressure loss + remote access anomaly tabletop. | BREAK -> PROVE |
| No AI guardrail yet. | AI may be applied before BAS/security foundation is ready. | Park AI to Step 3 and require advisory-only policy. | Future BUILD |

## Human-Owned Decisions

- Any code/life-safety statement.
- Any production hospital change.
- Any real vendor access process.
- Any real hospital evidence handling.
- Any risk acceptance or customer-facing final finding.

