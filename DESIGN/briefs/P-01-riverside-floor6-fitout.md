---
id: P-01
title: Riverside Floor 6 Tenant Fit-Out
facility: office
level: 1
systems: [VAV, reheat]
required_deliverables: [existing-conditions-survey.md, proposed_equipment.json, proposed_points.json, soo.md]
---

# P-01 — Riverside Floor 6 Tenant Fit-Out

*Synthetic training project. Fictional building, fictional tenant.*

## Owner Project Narrative

Riverside Office Tower has signed a full-floor lease with a law firm for
floor 6. The buildout: open office areas north and south, four perimeter
private offices, and a 40-seat conference/training room. The owner wants
zone controls "matching the rest of the tower" and reminds the team of
two standing requirements: the tower sustainability standard (unoccupied
setback, 55 F heating / 85 F cooling, schedule from the supervisor) and
"code-minimum ventilation controls per ASHRAE 62.1" for assembly-type
spaces.

## Mechanical Design Summary (by the mechanical engineer — design to this)

| Tag | Equipment | Serves | Notes |
|---|---|---|---|
| VAV-601 | VAV w/ HW reheat | Floor 6 open office north | off existing RTU-1 riser |
| VAV-602 | VAV w/ HW reheat | Floor 6 open office south | off existing RTU-1 riser |
| VAV-603 | VAV w/ HW reheat | Perimeter offices west pair | off existing RTU-1 riser |
| VAV-604 | VAV w/ HW reheat | Conference/training room (40 occ.) | off existing RTU-1 riser |
| VAV-605 | VAV w/ HW reheat | Perimeter offices east pair | off existing RTU-1 riser |
| VAV-606 | VAV w/ HW reheat | Reception / corridor | off existing RTU-1 riser |

Hot water from the existing BOILER-1 building loop. No RTU capacity
changes in scope.

## Owner-Furnished Drawing Set (as-built summary — verify on site)

- M-001 (2019 as-built): Rooftop unit RTU-1 is a VAV air handler with
  economizer **serving office floors 2 through 8** via a medium-pressure
  riser with taps at each floor.
- M-402: Existing tower zone terminals are **Siemens 550-series
  controllers on the legacy P1 field bus**, supervised from the tower
  front end. New terminals "to match existing where practical."
- The tower BAS front end is a Niagara Supervisor; the hospital campus
  federates it (reference only, out of scope).

## Contract Scope Notes

- BAS contractor: controls for the six new VAV terminals, integration
  into the existing tower supervisor, graphics update, point-to-point
  checkout.
- Reheat valves furnished by BAS contractor, installed by mechanical.
- Point naming shall follow the tower's existing convention.
