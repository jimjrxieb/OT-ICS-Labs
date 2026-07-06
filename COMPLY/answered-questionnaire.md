# Synthetic COMPLY Questionnaire Answers

> Source questionnaire:
> `GP-OP-TECH/1-COMPLY/artifacts/intake-questionnaires/bas-ics/00-hospital-bas-consultant-intake.md`

## Data Boundary

All answers are synthetic. The facility, device names, point names, networks,
vendors, alarm records, and operating values are fictional lab data.

## 1. Facility And Mission

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| What kind of facility is this? | 180-bed regional hospital supporting emergency care, surgery, ICU, pharmacy, imaging, sterile processing, and administrative areas. | `COMPLY/scope-statement.md` |
| Which spaces are critical for patient care? | OR suite, ICU, airborne isolation rooms, sterile processing, pharmacy clean storage, imaging equipment rooms, ED trauma bays. | `data/input/equipment.json` |
| What environmental conditions must be maintained? | ORs target 68-72 F and 30-60% RH; isolation rooms require negative pressure; pharmacy storage targets 68-77 F; ICU targets stable comfort and ventilation. | `data/input/points.json`, `sequences/` |
| What happens if BAS fails? | Procedure delays, loss of isolation pressure, humidity excursions, comfort complaints, possible equipment impact, and after-hours escalation. | `COMPLY/scope-statement.md` |

## 2. BAS Architecture

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| What BAS platform is used? | Mixed stack: Metasys is the main BAS front end, Trane controls selected AHUs/RTUs, and Niagara integrates cross-vendor systems. Lab open source layer: bacpypes3 + Node-RED + Grafana/InfluxDB mirrors the same functional architecture without vendor licensing. | `docs/architecture.md`, `COMPLY/scope-statement.md` |
| What are the main layers? | Field controllers at Purdue L1, supervisory engines/JACEs at L2, BAS servers/front ends at L3, firewall/jump host at L3.5, IT monitoring/ticketing at L4. In the open source lab stack: bacpypes3 acts as the L1/L2 BACnet device, Node-RED acts as the L2/L3 polling and logic layer, Grafana/InfluxDB acts as the L3/L4 visualization and historian. | `docs/architecture.md` |
| Which protocols are used? | BACnet/IP, BACnet MS/TP, Modbus TCP for plant meters, Niagara Fox between stations, and legacy N2 assumption for one older wing. In the lab: bacpypes3 speaks real BACnet/IP on localhost; Node-RED uses the `node-red-contrib-bacnet` module for Read-Property requests; MQTT bridges data to Grafana. | `docs/architecture.md` |
| Are field buses separated from BAS/IP? | Yes in the synthetic target: MS/TP trunks terminate at supervisory controllers; BACnet/IP rides a BAS VLAN; IT access crosses a firewall/jump host. | `docs/architecture.md` |
| Where does BAS touch IT? | AD-authenticated operator accounts, jump host for vendor support, SIEM log handoff, ticketing/CMMS handoff, backup storage. Open source lab adds: Node-RED dashboard on port 1880, Grafana on port 3000, InfluxDB on port 8086 — all localhost only. | `docs/architecture.md` |
| What open source tools cover the enterprise BAS stack in this lab? | bacpypes3 replaces BACnet drivers; Node-RED replaces Niagara programming/polling; InfluxDB replaces the Metasys/Niagara historian; Grafana replaces Metasys Trend Viewer and Niagara History Extension; MQTT/Mosquitto replaces Niagara Fox bridge. Same concepts, open protocols, no licenses. | `COMPLY/scope-statement.md` open source stack table |

## 3. Asset And Point Inventory

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| Do you have a BAS asset inventory? | Yes. Synthetic inventory includes Metasys server, Niagara Supervisor, JACEs, Trane SC+, AHU controllers, VAV controllers, plant gateway, and operator workstation. | `data/input/equipment.json` |
| Do you have a points list? | Yes. Initial point list covers AHU-1, OR-1, ISO-1, CHW loop, HW loop, and selected VAVs. | `data/input/points.json` |
| Which points are writable? | Temperature setpoints, occupancy schedules, fan commands, valve/damper commands, static pressure setpoints, and selected mode commands. | `data/input/points.json` |
| Which points are critical? | Isolation pressure, OR humidity, discharge air temperature, chilled water supply temperature, AHU fan status, safeties, and room temperature alarms. | `data/input/points.json` |

## 4. Operations And Troubleshooting

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| How are alarms triaged? | Critical alarms route to facilities operator and after-hours lead; high alarms route to BAS operator; medium alarms create CMMS review tasks. | `data/input/alarm_rules.json` |
| How are trends used? | Critical rooms trend every minute in the simulator; major equipment trends every five minutes; plant loop values trend every five minutes. | `data/input/trend_plan.json` |
| How are overrides controlled? | Synthetic rule: every override needs work order, reason, expiration, operator, and rollback note. | `BUILD/BUILD-PLAN.md` |
| How are control changes checked out? | Synthetic rule: pre-check, change, physical/logical response check, trend review, rollback check, closeout note. | `BUILD/BUILD-PLAN.md` |

## 5. Remote Access

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| Who can remotely access BAS? | Named facilities operators, BAS controls lead, IT OT admin, approved vendor users for Metasys/Trane/Niagara support. | `COMPLY/scope-statement.md` |
| Is remote access logged? | Target state says yes: jump host session log, MFA event, ticket ID, start/end time, destination, and reviewer. | `BUILD/BUILD-PLAN.md` |
| Are shared accounts used? | Synthetic current state: one legacy shared vendor account is documented as a gap. | `COMPLY/scope-statement.md` |
| Can vendors reach controllers directly? | Target state says no; vendors land on jump host/front end only. Direct field-controller reach is a gap if discovered. | `docs/architecture.md` |

## 6. Backup, Patch, And Change

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| What BAS components are backed up? | Metasys database/SCT archive, Niagara stations, JACE backups, Trane SC+ backup, graphics, license records, and controller config exports. | `BUILD/BUILD-PLAN.md` |
| Has restore been tested? | Synthetic current state: not yet. This is a P1/P3 recommendation for BUILD/PROVE. | `COMPLY/scope-statement.md` |
| How are patches handled? | Target state uses risk-based maintenance windows, vendor compatibility review, test restore point, rollback, and after-hours approval. | `BUILD/BUILD-PLAN.md` |
| Who approves BAS changes? | Facilities controls lead approves operational changes; IT OT admin approves network/security changes; safety-impacting changes require human review. | `COMPLY/scope-statement.md` |

## 7. Security Monitoring And Incident Response

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| Are BAS logs collected centrally? | Target state collects BAS auth events, remote access logs, firewall events, backup jobs, alarm priority changes, and critical override events. | `BUILD/BUILD-PLAN.md` |
| Are BAS network events monitored? | Step 2 target state includes passive monitoring or SPAN/TAP lab equivalent for BACnet/IP visibility. | `BUILD/BUILD-PLAN.md` |
| What is the incident escalation path? | Operator -> facilities controls lead -> IT OT admin -> vendor support -> security incident lead when cyber indicators exist. | `COMPLY/scope-statement.md` |
| Are drills performed? | Synthetic current state: no drill yet. Recommendation is a tabletop around isolation pressure loss plus remote access anomaly. | `BUILD/BUILD-PLAN.md` |

## 8. Compliance And Standards

| Consultant question | Synthetic answer | Evidence artifact |
|---|---|---|
| Which standards are mandatory? | Lab uses IEC 62443, NIST SP 800-82, NIST CSF, selected NIST 800-53 families, and local code/standards review as human-owned. | `COMPLY/scope-statement.md` |
| Are systems mapped to zones/conduits? | Initial Purdue map exists; detailed zone/conduit matrix is a Step 2 BUILD task. | `docs/architecture.md` |
| Are control families mapped? | Initial families: AC, AU, CM, CP, IA, IR, RA, SC, SI, SR. | `COMPLY/scope-statement.md` |

## COMPLY Exit Status

Status: ready for Step 1 BUILD scaffold.

Open recommendations:

- Build restore-test evidence.
- Create detailed zone/conduit matrix.
- Replace legacy shared vendor account with named access model.
- Add tabletop exercise.
- Add simulator scenarios for alarm floods, stale trend gaps, and backup failure.

