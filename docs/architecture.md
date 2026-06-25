# Synthetic BAS Architecture

## Architecture Summary

```text
Hospital spaces and equipment
  -> sensors / actuators
  -> DDC field controllers
  -> BACnet MS/TP trunks and BACnet/IP
  -> supervisory controllers / JACEs / Trane SC+
  -> Metasys front end + Niagara Supervisor
  -> OT firewall / jump host / remote support boundary
  -> IT monitoring, ticketing, backup, and identity handoff
```

## Purdue Mapping

| Purdue level | Synthetic components |
|---|---|
| Level 0 | Temperature sensors, humidity sensors, pressure sensors, dampers, valves, fan status, safeties. |
| Level 1 | VAV controllers, AHU unit controllers, room pressure controllers, plant controllers. |
| Level 2 | Metasys SNE/SNC-style engines, Trane SC+, Niagara JACE. |
| Level 3 | Metasys server/front end, Niagara Supervisor, BAS operator workstation, trend/alarm services. |
| Level 3.5 | OT firewall, jump host, remote support broker, backup handoff. |
| Level 4 | Enterprise identity, SIEM/logging, CMMS/ticketing, reporting. |

## Protocols

| Protocol | Synthetic use |
|---|---|
| BACnet/IP | Supervisory and front-end BAS communications. |
| BACnet MS/TP | Field controller trunks for VAV and room controllers. |
| Modbus TCP | Central plant metering and selected packaged equipment. |
| Fox | Niagara station/supervisor concept. |
| N2 | Legacy wing assumption for migration planning only. |

## Initial Zones

| Zone | Components | Allowed conduit concept |
|---|---|---|
| Field control zone | VAVs, AHU controllers, room controllers | Field bus to supervisory controllers only. |
| Supervisory zone | SNE/SNC, Trane SC+, JACE | BACnet/IP to BAS front end; limited management from engineering workstation. |
| BAS operations zone | Metasys, Niagara Supervisor, operator workstation | Operator UI, trends, alarms, backups. |
| OT access zone | Jump host, remote support broker | Named user, MFA, ticket, session log, time-bound access. |
| Enterprise handoff | SIEM, CMMS, identity, backup | Logs/tickets/backups only; no direct field controller access. |

