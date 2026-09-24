---
id: P-02
title: Hospital Pharmacy Compounding Suite Renovation
facility: hospital
level: 2
systems: [AHU, exhaust, room-pressure]
required_deliverables: [existing-conditions-survey.md, proposed_equipment.json, proposed_points.json, proposed_alarms.json, soo.md, valve-damper-schedule.md, bom.md, panel-layout.md]
---

# P-02 — Hospital Pharmacy Compounding Suite Renovation

*Synthetic training project. Fictional hospital, fictional pharmacy.
References to USP/ASHRAE-style requirements are training stand-ins, not
code compliance.*

## Owner Project Narrative

NAS JAX Regional Medical Center is renovating the inpatient pharmacy
into a compounding suite: a buffer room, an ante room, and a compounding
room. The pharmacy director's words: "compounding rooms shall be
negative to adjacent spaces for containment," continuous pressure
monitoring with alarms visible at the pharmacy front desk and the BAS
front end, and no interruptions to the rest of the hospital during
tie-in. Hospital alarm posture applies: anything protecting a patient or
a compounded product alarms **critical**.

## Mechanical Design Summary (design to this)

| Tag | Equipment | Serves | Notes |
|---|---|---|---|
| AHU-PH-1 | Dedicated AHU, CHW/HW coils | Pharmacy suite | tied to campus CHW/HW plants |
| EF-PH-1 | Exhaust fan (lead) | Compounding room exhaust | lead/lag pair |
| EF-PH-2 | Exhaust fan (lag/standby) | Compounding room exhaust | auto-failover on lead failure |
| RM-PH-BUF | Room pressure controls | Buffer room | **positive** per room schedule |
| RM-PH-CMP | Room pressure controls | Compounding room | see narrative |

Room schedule shows the buffer room at **+0.02 in.w.c.** to the ante
room. The ante room is listed as "transitional." Terminal HEPA on suite
supply. Suite dP instruments across each door.

## Owner-Furnished Drawing Set (as-built summary — verify on site)

- M-101 (2016 as-built): The existing pharmacy pressure monitor **already
  reports to the Metasys front end**; reuse the existing monitoring point
  where possible.
- M-501: Campus chilled water plant includes a **flow meter (point
  CHW_FLOW)** on the secondary loop — use it to verify spare capacity for
  the new AHU-PH-1 coil.
- M-502: Heating water supply temperature setpoint is
  **operator-adjustable from the BAS front end**; coordinate reset
  schedule with the new AHU's HW coil demand.

## Contract Scope Notes

- BAS contractor: AHU-PH-1 controls, exhaust lead/lag, all three rooms'
  pressure monitoring/alarming, front-desk annunciation, graphics.
- Fume hood / primary engineering controls: by others. Exclude.
- Tie-ins to campus plants: monitoring only; plant sequencing unchanged.
