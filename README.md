# Slot 3 -- Synthetic Hospital BAS/OT Simulator

This slot contains the runnable synthetic hospital BAS/OT simulator for the
GP-OP-TECH capstone. The target is a fictional base-adjacent hospital model
inspired by the kind of mission-critical healthcare facility J works around,
but it does not describe a real hospital, real base, real network, real points,
real diagrams, or real vendor access.

## Quick Start

Run one synthetic scenario:

```bash
python3 simulator/bas_sim.py --scenario normal --steps 12
python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12
python3 simulator/bas_sim.py --scenario isolation_pressure_loss --steps 12
```

Outputs land in:

```text
data/output/
```

## What Is In Scope

| Area | Synthetic scope |
|---|---|
| Facility | 180-bed regional hospital with ED, OR suite, ICU, pharmacy, imaging, sterile processing, and central plant. |
| BAS vendors | Johnson Controls Metasys for main BAS, Trane for selected AHUs/RTUs, Tridium Niagara as integration/supervisory layer. |
| Protocols | BACnet/IP, BACnet MS/TP, Modbus TCP for plant metering, legacy N2 as a documented assumption only. |
| Equipment | AHUs, VAVs, exhaust fans, chilled-water loop, hot-water loop, isolation rooms, OR environmental control. |
| Security focus | Purdue mapping, zones/conduits, remote access, access review, backups, logs, alarms, trends, change control. |

## Relationship To GP-OP-TECH

- `GP-OP-TECH/` defines the consulting framework, CBBP method, BAS/ICS control
  mappings, evidence templates, and capstone package.
- `GP-SECLAB/target-application/slot-3/` is where the runnable simulator should
  live.
- `GP-OP-TECH/capstones/hospital-bas-security-lab/` packages the simulator work
  into a portfolio-ready capstone.

## Build Order

1. Build, simulate, troubleshoot, and align hospital BAS behavior to code/standards.
2. Add OT security layer.
3. Add AI layer.

Current slot-3 state: Step 1 scaffold is active. Step 2 and Step 3 are defined
as future layers.

## Folder Map

| Path | Purpose |
|---|---|
| `COMPLY/answered-questionnaire.md` | Synthetic answers to the BAS/OT consultant intake. |
| `COMPLY/scope-statement.md` | Scope, exclusions, and recommendations. |
| `data/input/` | Synthetic equipment, controller, point, alarm, and trend definitions. |
| `simulator/bas_sim.py` | Standard-library simulator that generates point snapshots, alarms, and trends. |
| `sequences/` | Synthetic sequences of operation. |
| `docs/architecture.md` | BAS/Purdue architecture and vendor stack. |
| `BUILD/BUILD-PLAN.md` | Build tasks for the next implementation pass. |
| `evidence/` | Placeholder for synthetic PROVE artifacts. |
| `safety/` | Safety and data-boundary notes. |

## Data Boundary

Synthetic data only. Do not place real hospital diagrams, points lists,
screenshots, logs, credentials, vendor access details, IPs, or hostnames here.

## Legacy Content

The existing `crewai-updated-tutorial-hierarchical/` folder is legacy learning
material and is not the BAS simulator.
