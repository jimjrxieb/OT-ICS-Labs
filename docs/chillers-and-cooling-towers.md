# Chillers & Cooling Towers — Mechanical & Controls Study Guide

The mechanical half of the plant this lab's BAS points describe. Where
`docs/niagara.md` teaches the platform, this file teaches the equipment
the platform is watching — what a chiller and a cooling tower actually
are, how they work, what breaks, and what a controls tech is expected to
know versus what belongs to mechanical/water-treatment.

**Grounded in what's here:** this lab now models both sides of the
air-cooled/water-cooled fork. Air-cooled: `CHILLER-1` (office tower,
Carrier) and `CHILLER-RTAC-822` (Trane RTAC-style, ~155 ton, two
independent refrigerant circuits). Water-cooled, hospital-scale, with a
tower: `CHILLER-HOSP-1`/`CHILLER-HOSP-2` under `CHW-PLANT-1` — an N+1
pair of water-cooled screw chillers (lead/standby, same pattern as
Building 822's `CHW822_P1`/`P2` pump lead/lag) — served by dedicated
condenser water pumps `CWP-1`/`CWP-2` and a shared 2-cell
`COOLING-TOWER-1`. The `CHW_PLANT_LOW_DELTA_T` fault is a textbook
**low-delta-T** case on the CHW side; `COOLING_TOWER_1_FOULED_FILL` is
the tower-side equivalent — reduced heat rejection forcing the lead
chiller to work harder for the same output. Both are diagnosable live in
`/niagara` or `/metasys` today. See the controls case study at the
bottom for the low-delta-T walkthrough.

---

## 1. What They Are

| | Purpose |
| --- | --- |
| **Chiller** | A packaged refrigeration machine that removes heat from a chilled water (CHW) loop and rejects it elsewhere, so that loop can absorb heat from air handlers, VAVs with reheat/cooling coils, and fan coils throughout a building. |
| **Cooling tower** | A heat-rejection device that cools **condenser water** back down by evaporating a small fraction of it into outdoor air, so a water-cooled chiller's condenser has somewhere cold to dump heat. It doesn't cool the building directly — it cools the water that cools the chiller. |

**Air-cooled vs. water-cooled chiller** — the fork that decides whether
a tower exists at all:

| | Air-cooled (this lab) | Water-cooled |
| --- | --- | --- |
| Rejects heat to | Ambient air, via condenser coil + fans on the unit itself | Condenser water loop → cooling tower → ambient air |
| Needs a cooling tower? | No | Yes |
| Typical efficiency | Lower (ambient dry-bulb limited) | Higher (condenser water tracks the lower wet-bulb temp) |
| Typical size range | Smaller-to-mid (rooftop, packaged) | Mid-to-large (central plants, campuses, hospitals) |
| Common compressor types | Scroll, screw | Screw, centrifugal (incl. magnetic-bearing/oil-free) |
| Maintenance burden | Lower (no tower water treatment) | Higher (tower + condenser water chemistry, Legionella risk) |
| This lab's examples | `CHILLER-1`, `CHILLER-RTAC-822` | — (not modeled) |

---

## 2. How They Work

### The refrigeration cycle

Every chiller — air- or water-cooled — runs the same four-step cycle:

```text
Evaporator (absorbs heat from CHW, refrigerant boils, low pressure)
  -> Compressor (raises refrigerant pressure/temperature)
  -> Condenser (rejects heat to air or condenser water, refrigerant condenses)
  -> Expansion device (drops pressure, refrigerant cools)
  -> back to Evaporator
```

The evaporator is where the *building's* water gets cold; the condenser
is where the heat actually leaves the system — to ambient air directly
(air-cooled) or to condenser water (water-cooled, then to the tower).

### Compressor types

| Type | Notes |
| --- | --- |
| Reciprocating | Older/small tonnage, piston-based. Largely legacy at this point. |
| Scroll | Common in small-to-mid packaged units (like `CHILLER-1`'s class). Simple, few moving parts, staged via multiple scrolls. |
| Screw | Common in mid-to-large air- and water-cooled machines (RTAC-class units like `CHILLER-RTAC-822` are typically screw). Good part-load performance with slide-valve or VSD capacity control. |
| Centrifugal | Large water-cooled plants. Efficient at full load; prone to **surge** at low load/high lift if not managed. |
| Magnetic-bearing / oil-free centrifugal | Modern high-efficiency variant (e.g. Danfoss Turbocor, Smardt) — no oil system, VSD-driven, excellent part-load efficiency, but the bearing/VSD electronics are a different failure mode than a conventional machine. |

### Cooling tower operating principle

A tower cools condenser water by **evaporating a small percentage of
it** into the airstream moving through the tower — not by simple contact
cooling. That's why a tower can cool water *below* the outdoor
dry-bulb temperature: it's chasing the outdoor **wet-bulb** temperature
instead, which is always lower (except at 100% RH).

| Term | Meaning |
| --- | --- |
| **Range** | Condenser water temperature drop across the tower (entering − leaving). Reflects the *load*. |
| **Approach** | Leaving condenser water temperature minus outdoor wet-bulb. Reflects the *tower's effectiveness* — a fouled or undersized tower has a bigger approach. |
| **Open circuit** | Condenser water directly contacts outdoor air and evaporates in the tower fill — most common, cheapest, but the water picks up dirt/biological contamination from the air. |
| **Closed circuit** | Condenser water stays in a closed coil inside the tower; a separate spray water circuit does the evaporating. Cleaner condenser water, more equipment, more cost. |
| **Counterflow / crossflow** | Whether air moves opposite to (counterflow) or across (crossflow) the falling water inside the fill — a design/layout distinction, not something a BAS tech controls. |

### The two loops, end to end

```text
CHW loop (this lab's front ends show this side):
  Chiller evaporator -> CHW pump(s) -> AHU/VAV/FCU cooling coils -> back to evaporator
  (this lab: CHW-PLANT-1 / CHILLER-1 -> AHU-OR-1, RTU-1, VAV-301, FCU-822, etc.)

Condenser water loop (water-cooled only -- not modeled in this lab):
  Chiller condenser -> condenser water pump (CWP) -> cooling tower -> back to condenser
```

---

## 3. Components

### Chiller

| Component | Role |
| --- | --- |
| Compressor | Moves and pressurizes refrigerant — the "engine" of the cycle. |
| Evaporator | Shell-and-tube or plate heat exchanger where refrigerant absorbs heat from CHW. |
| Condenser | Air-cooled coil + fans, or a shell-and-tube bundle cooled by condenser water. |
| Expansion device | TXV, electronic expansion valve (EEV), or fixed orifice — meters refrigerant flow, drops pressure. |
| Refrigerant circuit(s) | Larger machines split capacity across 2+ independent circuits (this lab's `CHILLER-RTAC-822` has CKT1/CKT2) so one circuit can fail without losing the whole unit. |
| Oil management system | Larger machines separate/return oil that migrates with refrigerant — critical to compressor lubrication. |
| Purge unit | Low-pressure centrifugal machines (R-123/R-1233zd) run *below* atmospheric pressure in the evaporator, so air/moisture leaks in rather than refrigerant leaking out — the purge unit removes that air. |
| VSD (variable-speed drive) | Modulates compressor speed for part-load efficiency, on VSD-equipped machines. |
| Unit controller | The chiller's own onboard microprocessor panel (Trane Tracer UC800, Carrier ComfortLink, York OptiView/YorkTalk, Danfoss Turbocor controller, etc.) — runs safeties and local sequencing, and is what the BAS actually talks to. |

### Cooling tower

| Component | Role |
| --- | --- |
| Fill (media) | Splash bars or film-pack sheets that maximize water-to-air contact surface for evaporation. |
| Fan(s) + motor | Draws or forces air through the fill. Often two-speed or VFD-driven for capacity control. |
| Drift eliminators | Baffles that catch water droplets before they leave with the exhaust air — minimizes water loss and drift-related liability (Legionella carry-over risk). |
| Basin (sump) | Collects cooled water at the bottom before it's pumped back to the condenser. |
| Makeup valve/float | Replaces water lost to evaporation, drift, and blowdown. |
| Blowdown/bleed line | Deliberately dumps a small stream of concentrated water to control mineral buildup from evaporation (see water treatment, below). |
| Distribution/spray nozzles | Spreads incoming hot water evenly across the fill. |
| Basin heater | Prevents the basin from freezing in cold weather when the tower is idle. |
| Tower bypass valve | Blends hot condenser water directly back to the pump (bypassing the tower) in cold weather to prevent freezing the fill/basin — a freeze-protection control point, not a capacity control. |

### Plant / water-side

| Component | Role |
| --- | --- |
| CHW pumps (primary/secondary or variable primary) | Circulate chilled water between chiller(s) and the building loads. |
| Condenser water pumps (CWP) | Circulate condenser water between chiller(s) and the tower (water-cooled only). |
| Plate/shell-and-tube heat exchanger | Isolates loops (e.g. a waterside economizer, or a campus loop from a building loop) without mixing water chemistry. |
| Water treatment (chemical feed, side-stream filtration, conductivity controller) | Controls scaling, corrosion, and biological growth in open condenser water loops — a specialty/vendor scope, not a BAS scope, though the BAS often trends the data. |

---

## 4. Preventative Maintenance

| System | Task | Typical frequency |
| --- | --- | --- |
| Chiller | Oil analysis (larger machines) | Annual, or per OEM |
| Chiller | Refrigerant leak check / tightness testing (EPA 608 compliance) | Quarterly–annual depending on charge size |
| Chiller | Condenser coil cleaning (air-cooled) | Annual, more in dusty/coastal environments |
| Chiller | Eddy-current tube testing (water-cooled bundles) | Annual or per OEM |
| Chiller | Compressor vibration analysis | Annual |
| Chiller | Purge unit run-time log review (low-pressure centrifugal) | Monthly |
| Chiller | Motor megohm (insulation resistance) test | Annual |
| Chiller | Starter/VSD contact and electrical inspection | Annual |
| Chiller | Full performance test (approach temps, kW/ton) | Annual |
| Cooling tower | Fill inspection/cleaning (scale, algae, debris) | Quarterly–annual |
| Cooling tower | Basin cleaning | Quarterly–annual, more if open to debris |
| Cooling tower | Water treatment monitoring (conductivity, biocide dosing, **Legionella risk management**) | Continuous/automated + periodic lab sampling |
| Cooling tower | Fan belt/gearbox lubrication (or VFD/direct-drive inspection) | Quarterly |
| Cooling tower | Drift eliminator inspection | Annual |
| Cooling tower | Nozzle inspection for clogging | Annual |
| Cooling tower | Structural/corrosion inspection | Annual |
| Cooling tower | Winterization (basin heater check, bypass valve function test) | Pre-season, annual |

---

## 5. Common Problems

| System | Symptom | Likely cause |
| --- | --- | --- |
| Chiller | High head pressure trip | Fouled/dirty condenser coil (air-cooled) or scaled condenser tubes (water-cooled); low condenser water flow |
| Chiller | Low refrigerant charge alarm / capacity shortfall | Leak — often at fittings, braze joints, or a failing shaft seal |
| Chiller | Low evaporator temp / freeze protection trip | Low CHW flow (closed valve, failed pump, air-bound loop) |
| Chiller | Compressor short-cycling | Oversized machine for the load, bad staging logic, or a nuisance safety trip |
| Chiller | Surge (centrifugal only) | Low load combined with high lift (large condenser-to-evaporator temperature difference) — needs hot-gas bypass or better staging, not just "run it slower" |
| Chiller | Oil migration / slugging | Refrigerant returning to the compressor as liquid instead of vapor — often a low-load or piping design issue |
| Chiller | Refrigerant/oil sample shows acid or moisture | Early warning of compressor motor insulation breakdown — the classic "catch it before a burnout" lab test |
| Cooling tower | Reduced heat rejection / rising condenser water temp | Scaled or fouled fill — the tower equivalent of a dirty coil |
| Cooling tower | Algae / biological growth, elevated Legionella risk | Inadequate biocide dosing, stagnant water, sunlight exposure |
| Cooling tower | Fan vibration or noise | Bearing wear, belt slippage, ice buildup, or blade imbalance |
| Cooling tower | Basin overflow or low level | Stuck makeup valve/float |
| Cooling tower | Freeze damage (winter) | Basin heater failure, or bypass valve not functioning during a cold snap with the tower idle |
| Cooling tower | Excess water/chemical consumption | Drift eliminators damaged or missing, or blowdown set too aggressively |
| Plant (either) | Cavitation in pumps | Low NPSH — often a strainer clogged or a level/pressure problem upstream |
| Plant (either) | Uneven flow / "hot spots" | Poor water distribution, balancing valves out of adjustment |

---

## 6. The Controls Side

This is the layer a BAS/controls tech actually touches. The mechanical
detail above explains *why* the sequences below exist.

### Chiller plant sequencing

- **Lead/lag staging** — with multiple chillers, the plant sequence
  decides which one runs first (lead) and when to bring on the next
  (lag), usually based on % capacity or load trend, not just a fixed
  setpoint. Rotates lead duty to even out runtime.
- **CHW supply temperature reset** — raising the CHW setpoint when
  outdoor temp or building load is low saves compressor energy, since a
  chiller works less hard to make 48°F water than 42°F water. Common
  reset strategies: OA-temperature reset, or reset based on the most
  "starved" zone's valve position (a control-loop-aware approach, closer
  to ASHRAE Guideline 36 practice than a fixed schedule).
- **Condenser water reset** (water-cooled only) — running the tower
  colder than the chiller strictly needs *usually* saves more chiller
  compressor energy than it costs in tower fan energy — a genuine
  plant-level optimization strategy, not just "run the tower as cold as
  possible."
- **Pump staging & control** — primary/secondary or variable-primary CHW
  pumping is staged with the chillers, and secondary/distribution pumps
  are typically VFD-controlled off **differential pressure** at a
  critical loop location — this lab's `CHW_DIFF_PRESSURE` point is
  exactly that kind of signal.
- **Interlocks and safeties** — a chiller should never be commanded to
  start without CHW flow proven (and condenser water flow proven, for
  water-cooled machines). Flow switches and high/low pressure safeties
  are frequently **hardwired** into the unit's own safety chain, not
  just BAS logic — the BAS enable command is a request, not a guarantee
  the machine runs.
- **Isolation valve sequencing** — multi-chiller plants open a chiller's
  isolation valve *before* starting it and close it after it stops, to
  avoid dead-heading or reverse flow through an idle machine.

### Packaged chiller integration reality

Most packaged chillers (Trane, Carrier, York, Daikin) ship with an
onboard microprocessor panel that already runs the refrigeration cycle
and safeties — the BAS integration is almost always **binding to
points the factory panel already computes**, over BACnet MS/TP,
BACnet/IP, or Modbus, rather than writing new control logic. This lab's
`CHILLER-RTAC-822` mirrors that reality directly:

| Point | What it represents |
| --- | --- |
| `RTAC822_EVAP_LVG_TEMP` / `RTAC822_EVAP_LVG_SP` | Leaving chilled water temp and its setpoint — the number the rest of the plant actually cares about |
| `RTAC822_PCT_CAPACITY` | The unit's own computed loading — useful for staging logic in a multi-chiller plant |
| `RTAC822_CKT1_STATUS` / `RTAC822_CKT2_STATUS` | Per-circuit run status — a two-circuit machine can be "half broken" and still running |
| `RTAC822_CKT1_FAN_STATUS` / `RTAC822_CKT2_FAN_STATUS` | Condenser fan status per circuit (air-cooled) |
| `RTAC822_AMBIENT_TEMP` | What the unit is rejecting heat against — explains why capacity/efficiency varies by time of day |
| `RTAC822_ACTIVE_DIAG` | The unit's own fault/diagnostic code, exposed as a multistate — read it, don't try to re-diagnose the refrigeration cycle from the BAS side |

Per `docs/bacnet-822.md`, this unit is deliberately **off-tree** — no
BACnet integration to the supervisory controller, local display only —
which is itself realistic: not every piece of mechanical equipment on a
real job is BAS-integrated, and knowing what *isn't* on the network is
as important as knowing what is.

### Cooling tower controls (water-cooled plants)

- **Fan staging/VFD speed control** — modulates off leaving condenser
  water temperature (or condenser water supply setpoint), not off
  outdoor conditions directly.
- **Tower bypass valve** — a freeze-protection control, not a capacity
  control: blends hot condenser water back to the pump suction in cold
  weather so the idle tower fill/basin doesn't freeze.
- **Basin heater staging** — typically enabled below a basin or outdoor
  air temperature threshold, disabled once the tower is running (flowing
  water doesn't freeze as easily as static water).
- **Alarms a BAS commonly carries**: high/low basin level, freeze stat
  trip, fan status feedback mismatch (commanded on, status shows off —
  the same "commanded vs. actual" pattern this lab's technician panel
  already teaches for any writable point).
- **What the BAS is *not* responsible for**: water chemistry, biocide
  dosing, and Legionella remediation are a water-treatment vendor's
  scope — the BAS's job there is trending (basin temp, conductivity if
  metered) and alarming on the mechanical side, not chemistry.

### Case study: Low-Delta-T Syndrome

The classic chilled-water plant diagnostic, and this lab's
`CHW_PLANT_LOW_DELTA_T` fault plays it out directly.

**What it looks like mechanically:** the CHW supply temperature is
fine, but the **return** temperature creeps toward the supply
temperature — the delta-T across the plant shrinks. Coils are moving
more *flow* than they need to extract the same heat, because valves are
riding too far open (poor coil control, oversized valves with poor
authority, or a control-loop tuning problem) instead of an appropriately
narrow flow doing more *work* per gallon.

**Why it matters:** a shrinking delta-T forces pumps to move more GPM
to deliver the same cooling — which drives differential pressure down,
which drives VFD-controlled secondary pumps to speed up, which burns
pump energy and can eventually starve the plant of capacity even though
the chiller itself is healthy.

**What it looks like on the BAS:** exactly the two points this lab's
fault touches — `CHW_SUPPLY_TEMP` drifting up (plant working harder to
hold setpoint) while `CHW_DIFF_PRESSURE` drifts down (more flow being
pulled through the loop) — with a valve that's stuck open rather than
modulating. The trend view, not a single point-in-time reading, is what
actually reveals it: this is a *shape* diagnosis, not a threshold
alarm.

---

## 7. Hospital-Scale Plants — Why This Job Is Different

A hospital central plant isn't just a bigger office chiller plant — the
load profile, the redundancy requirements, and the regulatory burden
are all different in kind, not just degree. This section is what a
comfort-cooling background doesn't automatically prepare you for.

### Why hospitals almost always run water-cooled

| Driver | Why it pushes toward water-cooled + tower |
| --- | --- |
| Continuous load | Hospitals run cooling 24/7/365 — ORs, sterile processing, and server/imaging rooms don't coast down at night or on weekends the way an office does. Efficiency at full *and* part load matters far more when the plant never really shuts off. |
| Scale | Hospital plants are commonly hundreds to 1000+ tons. Centrifugal and screw water-cooled machines are meaningfully more efficient than air-cooled at that size, and the efficiency gap compounds over a 20–30 year plant life. |
| Simultaneous heating + cooling | OR suites frequently need dehumidification even when it's cool outside, and reheat coils run alongside active cooling — central plants with heat-recovery options are far more practical at this scale than packaged rooftop equipment. |
| Space and noise | The air-cooled equivalent of a 600-ton plant would need enormous roof area and would be loud — a mechanical/penthouse central plant with a tower array is quieter and more consolidated. |
| Total cost of ownership | Higher first cost, but hospitals are long-horizon owner-operators (not a developer flipping the building), so the lifecycle efficiency win actually gets captured by whoever pays the utility bill. |

### Redundancy — N+1 is the floor, not the goal

Loss of cooling or humidity control in an OR, ICU, or isolation room is
an infection-control and life-safety event, not a comfort complaint —
so hospital central plants are designed to keep running through a
single failure, by rule, not just by good practice:

- **N+1 chillers** — plants are commonly sized so any *one* chiller can
  be down (failure or maintenance) while the rest still carry full
  design load. Larger/more critical facilities go further (N+2, or a
  fully split plant across two physically separated mechanical rooms).
- **Multi-cell towers** — a tower is typically built as multiple cells
  sharing one basin, so one cell can be isolated and drained for
  cleaning or fill replacement without losing all heat rejection
  capacity.
- **Cross-connected headers and standby pumps** — CHW and condenser
  water pumps are arranged so a single pump failure doesn't collapse
  the loop; standby pumps and header isolation valves are part of the
  redundancy story, not just the chillers themselves.
- **The design basis is codified**, not left to a mechanical engineer's
  judgment call alone — **FGI's Guidelines for Design and Construction
  of Hospitals** and **ASHRAE 170 (Ventilation of Health Care
  Facilities)** set minimum reliability and environmental-control
  requirements for critical spaces, which flow down into how much
  redundancy the central plant needs to carry.

### Legionella and the Water Management Plan (ASHRAE 188)

This is the single biggest way a hospital cooling tower differs from
any other tower, and it's compliance-driven, not optional:

- Cooling towers are a well-documented **Legionella** source — the
  drift/aerosol from an open-circuit tower can carry the bacteria if
  the water isn't properly treated, and outbreaks traced to cooling
  towers are part of the reason this is taken so seriously.
- **ASHRAE 188** ("Legionellosis: Risk Management for Building Water
  Systems") is the industry standard requiring a formal, documented
  **Water Management Plan (WMP)** for building water systems —
  cooling towers are always in scope.
- **CMS (Centers for Medicare & Medicaid Services)** requires
  healthcare facilities to have a water management policy addressing
  Legionella risk, referencing ASHRAE 188 and CDC guidance, as a
  **condition of participation** — hospitals are surveyed and can be
  cited on this. It is a real audit item, not a nice-to-have.
- What a controls/facilities tech actually touches: routine testing
  logs (conductivity, biocide residual, periodic culture sampling where
  required), documented disinfection procedures, drift eliminator
  condition (less drift = less aerosolized risk), and **maintaining the
  paper/data trail that proves the plan was followed** — auditors want
  evidence, not just a policy on a shelf. If that sounds familiar,
  it's the same "no orphaned findings, no undated artifacts" discipline
  this project's own audit-trail standard already runs on — the
  hospital-facilities version of the same habit.

### Emergency power — not everything rides the generator

- **NFPA 99** (Health Care Facilities Code) and **NFPA 110** (Emergency
  and Standby Power Systems) govern how a hospital's backup power is
  structured. The **Essential Electrical System** is split into
  branches — Life Safety, Critical, and Equipment — and HVAC/plant
  equipment supporting critical spaces is fed from the branch its
  classification requires, with defined transfer-time limits.
- **Generators don't usually carry the whole chiller plant.** Full
  plant tonnage on standby power is expensive and often impractical, so
  most hospitals run a deliberately reduced **"emergency cooling"**
  mode during an outage — enough capacity for ORs, ICU, isolation
  rooms, pharmacy, blood bank, and similar critical spaces, while
  general patient rooms and office areas get shed.
- **Load shedding is a controls sequence, not just an electrical one**
  — the BAS plant logic needs an "on generator" mode that stages only
  the equipment the emergency branch can actually carry, and isolates
  or de-prioritizes the rest. This is exactly the kind of sequence a
  controls tech is expected to understand and troubleshoot, even though
  the electrical distribution itself belongs to the electricians.
- Whatever cooling-tower fans/pumps *are* on emergency power get
  exercised as part of **NFPA 110's monthly/annual generator testing**
  — if the tower fan doesn't pick up load cleanly during a generator
  test, that's a real finding, not a paperwork gap.

### Where this lives in the lab today

- **N+1 in practice:** `CHILLER-HOSP-1` (lead, `CHILLERHOSP1_RUN_CMD`
  normally `1`) and `CHILLER-HOSP-2` (standby, `CHILLERHOSP2_RUN_CMD`
  normally `0`) — the same lead/standby pattern Building 822 already
  uses for its `CHW822_P1`/`P2` pumps, just at the chiller level. Try
  commanding the lead to `0` and the standby to `1` from the Technician
  Panel (a plain release just falls back to the computed baseline, which
  is still "on" for the lead — you have to actively command it off to
  simulate taking it down for service).
- **Approach, visible as a trend:** `COOLING-TOWER-1`'s `CT1_BASIN_TEMP`
  is the tower's leaving-water temperature — under normal operation it
  and `CHILLERHOSP1_CW_ENT_TEMP` just independently vary in the same
  85–95°F band (this lab's simulator doesn't model a live physical
  coupling between them). Run the `COOLING_TOWER_1_FOULED_FILL` trouble
  call and watch them in the History Extension / trend view instead —
  the fault is what deliberately drifts both *together*, which is the
  actual tell: a real fouled-fill event moves the tower and the
  chiller's entering condenser water in the same direction, not just
  two independently noisy readings.
- **The life-safety alarm instinct still applies one level down:**
  `ISO201_PRESSURE` and `ISO201_EXH_CMD` are marked `critical` in
  `data/input/points.json` for the same reason the central plant gets
  N+1 redundancy — losing control of either isn't a comfort complaint,
  it's a life-safety and infection-control event. The plant-level and
  room-level versions of that instinct are both clickable here now.
