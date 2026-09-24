---
id: P-03
title: Hospital OR Wing Addition (OR-3 / OR-4)
facility: hospital
level: 3
systems: [AHU, VAV, room-pressure, plant, network]
required_deliverables: [existing-conditions-survey.md, proposed_equipment.json, proposed_points.json, proposed_alarms.json, soo.md, valve-damper-schedule.md, bom.md, panel-layout.md, network-riser.md]
---

# P-03 — Hospital OR Wing Addition

*Synthetic training project. Fictional hospital. ASHRAE-170-style
requirements below are training stand-ins, not code compliance.*

## Owner Project Narrative

The medical center is adding a two-OR surgical wing (OR-3, OR-4) with
sterile core expansion. Surgery requirements, per the owner's design
standard: each OR individually monitored for temperature, humidity, and
**positive pressure to adjacent spaces**, all alarmed critical at the
Metasys front end and the surgery board. The wing must ride through a
single network failure without losing local control. Metasys remains the
hospital front end, federated under the portfolio Niagara Supervisor.

## Mechanical Design Summary (design to this)

| Tag | Equipment | Serves | Notes |
|---|---|---|---|
| AHU-OR-2 | AHU, CHW/HW, humidifier | OR-3, OR-4, sterile core | campus plant tie-ins |
| VAV-OR-103 | Pressure-independent VAV | OR-3 | off AHU-OR-2 |
| VAV-OR-104 | Pressure-independent VAV | OR-4 | off AHU-OR-2 |
| RM-OR-3 | Room pressure monitor | OR-3 | door dP |
| RM-OR-4 | Room pressure monitor | OR-4 | door dP |
| CH-2 | Water-cooled chiller (Trane) | Campus CHW plant expansion | packaged controls, **Modbus TCP** interface |
| JACE-3 | Supervisory controller | New wing | new field trunks land here |

The room schedule lists OR temp/pressure instruments per OR.
**Humidity sensors are not shown for the ORs** (schedule note: "RH by
BAS as required").

## Owner-Furnished Drawing Set (as-built summary — verify on site)

- M-601 (2014 as-built): Existing OR air handler AHU-OR-1 is a
  **Johnson Controls unit on a JCI FEC controller**; new AHU-OR-2
  controls "to match existing OR AHU standard."
- M-602 riser: Isolation room 201 pressure monitor is a **standalone
  local panel, not networked** — "future BAS integration by others."
- M-603: Central plant metering is integrated over **BACnet/IP**; the
  new chiller CH-2 "shall integrate per the existing plant metering
  standard."
- M-604: OR-1 **has no humidity monitoring today**; all OR humidity
  instrumentation on this project is new scope.

## Contract Scope Notes

- BAS contractor: AHU-OR-2 + terminal controls, OR pressure/temp/RH
  monitoring and alarms, JACE-3, network riser for the wing, graphics,
  checkout, and integration of CH-2 **monitoring** points.
- **Chiller unit controls and sequencing by chiller manufacturer**
  (packaged). *(But see mechanical summary: the plant expansion basis
  of design says "BAS shall sequence lead/lag chillers." Resolve scope
  before pricing controls you may not own.)*
- Life-safety separation: the owner's standard requires OR-serving
  equipment on dedicated field trunks — do not daisy-chain OR terminals
  with non-OR devices.
