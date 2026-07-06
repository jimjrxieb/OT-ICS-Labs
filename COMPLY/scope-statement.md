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

### Enterprise Systems (Simulated)

| Vendor/program | Synthetic role |
|---|---|
| Johnson Controls Metasys | Main BAS front end, ADS/ADX-style server, SNE/SNC-style supervisory engines, SCT archive concept. |
| Trane | Tracer SC+ for selected AHUs/RTUs, Tracer TU service-tool concept, unit controllers. |
| Tridium Niagara | Integration supervisor, JACE edge controllers, Workbench engineering access concept. |
| CMMS/ticketing | Work orders, after-hours escalation, change records. |
| SIEM/logging | Step 2 target for auth, remote access, firewall, alarm, backup, and change telemetry. |

### Open Source Lab Stack (Runnable)

The open source stack covers the same functional layers as the enterprise tools above.
It runs locally, requires no licenses, and teaches the same protocols and concepts.

| Tool | What it does | Replaces in prod |
|---|---|---|
| bacpypes3 | Python BACnet/IP protocol stack — exposes simulator points as real BACnet objects on localhost | Metasys BACnet driver, Niagara BACnet driver |
| Node-RED | Visual flow programming, BACnet polling, logic wiring — mirrors Niagara programming model | Niagara programming engine, Metasys graphics engine |
| InfluxDB | Time-series database — stores trend data from Node-RED | Metasys historian, Niagara History Extension |
| Grafana | Time-series dashboards and alerting — visualizes InfluxDB trend data | Metasys Trend Viewer, Niagara History charts |
| MQTT / Mosquitto | IoT pub/sub messaging broker — bridges BACnet poll data to Node-RED and Grafana | Niagara Fox protocol bridge |

**Why this stack:** mirrors how real BAS integrators build open-protocol monitoring layers.
Node-RED + bacpypes3 is the same pattern used by independent controls contractors who need
to integrate across Metasys, Niagara, and Trane systems without vendor-specific tooling.
Building this in the lab teaches the real BACnet Read-Property request/response cycle —
the same interaction a JACE has with a field controller.

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
| Open source BAS stack not yet connected to simulator. | BACnet protocol learning gap; Grafana/Node-RED not wired to simulator output. | Add bacpypes3 BACnet/IP device layer, Node-RED polling flows, InfluxDB storage, Grafana dashboards. | BUILD (BP-003) |

## Human-Owned Decisions

- Any code/life-safety statement.
- Any production hospital change.
- Any real vendor access process.
- Any real hospital evidence handling.
- Any risk acceptance or customer-facing final finding.

