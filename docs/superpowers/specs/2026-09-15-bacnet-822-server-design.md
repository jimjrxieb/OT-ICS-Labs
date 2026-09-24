# Building 822 BACnet/IP Server — Design

- date: 2026-09-15
- status: approved for planning
- supersedes: nothing
- related: `docs/superpowers/specs/2026-09-10-building-822-trane-baseline-design.md`

## Goal

Put Building 822 on the wire. Today the building exists only inside the
simulator and its own front end: the physics are real, the topology is
modeled in data, but nothing outside this repo can see or command it.

After this work, a real BACnet supervisor — YABE, Niagara, or an actual
Tracer SC+ — discovers 822 as a routed BACnet internetwork, reads its
points, writes a valve at priority 8, and watches supply air respond.

The acceptance sentence for the whole design:

> Command -> controller resolves the command -> actuator moves ->
> physical process changes -> sensor proves the response.

If a write does not move the building, this design has failed, however
correct the protocol layer is.

## Non-Goals

This is the plant underneath a supervisory system, not the supervisory
system. Explicitly out of scope:

- Areas, schedules, occupancy, alarm routing, data-log configuration,
  reports, floorplans, user permissions. None of that is on the wire;
  it is application-layer product that lives above this layer.
- Any claim of being, replacing, or reimplementing Tracer Synchrony.
- Trane equipment templates or Trane device identity. The simulated
  devices use vendor identifier 999, matching the existing
  `bacnet_device.py`, and will appear to any real
  supervisor as generic third-party BACnet devices requiring manual
  point binding. Emulating Trane's registered vendor identity or device
  profile is deliberately rejected: it is an IP gray area, it depends on
  unpublished templates, and it buys presentation rather than behavior.
- Changing the hospital or office buildings in any way.

## Decisions

Decisions are recorded with the option chosen and the reason, so a later
reader can tell a deliberate choice from an accident. D1-D4 are below;
D5 (two writers, one building) sits with the runtime it constrains, and
D6 (cause injection only) sits with the companion milestone it governs.

### D1. Full routed topology, not a flat device list

Two BACnet routers with virtual MS/TP networks behind them, rather than
63 flat IP devices or two aggregate devices.

Reason: the routed shape is what a real job looks like, and the
vocabulary it teaches — trunk, MAC address, network number, "did the SC
route it" — is the vocabulary the operator will hear in the field. A
flat list teaches object access but not topology.

### D2. The device owns the control loop, in-process

One process holds the priority arrays and drives `model822.step_822()`
on a timer. Rejected: routing writes through the FastAPI command
endpoint, and racing on `operator_overrides.json` from two processes.

Reason: it mirrors reality, where the field controller holds both the
priority array and the control loop. It also makes the priority array
load-bearing rather than decorative — the resolved `presentValue` is
literally the input to the physics. The cost is a second driver of the
822 state, addressed by D5.

### D3. BBMD plus documented mirrored-networking switch

Build BBMD and Foreign Device Registration into the server. Separately
document the WSL2 `networkingMode=mirrored` change rather than making
it now.

Reason: the development host runs WSL2 in NAT mode, where UDP broadcast
does not cross between Windows and the VM, and inbound UDP cannot be
forwarded with `netsh portproxy` (TCP only). BBMD/FDR makes a Windows
BACnet client work today with no environment change, and BBMD/FDR is
itself a real skill in BACnet/IP work across subnet boundaries. Mirrored
mode is required only for a physical supervisor on the LAN to discover
the host, is a one-line change the operator can make when needed, and
carries a small risk to the Docker bridge that the existing stack uses.

### D4. New server for 822 only

Write `open-source-stack/bacnet822.py`. Leave `bacnet_device.py`
untouched.

Reason: the existing bridge is a deliberately simple read-only teaching
example serving hospital points, and the trouble-call and 2AM flows
depend on the current behavior. Writes against the hospital could not
be made meaningful anyway — those points come from the open-loop
scenario engine, not a physics model, so a write there would be inert.
Unifying the two servers would produce inconsistent write semantics
across buildings.

## Topology

One process presents two routers and 62 devices on four virtual MS/TP
networks. Membership and parentage come from `data/input/equipment.json`
and are not hardcoded.

```
BACnet/IP  <host>:47809   (IP network 0)
|
+- SC-822-01   device 822001   [router]
|   +- network 1  "MSTP-01-A"   7 devices, MAC 1-7
|   |    822011..822016  UC400-MAU-01..06
|   |    822017          UC400-CHW-822
|   +- network 2  "MSTP-01-B"  24 devices, MAC 1-24
|        822101..822124  18 fan coil units + 6 hallway sensors
|
+- SC-822-02   device 822002   [router]
|   +- network 3  "MSTP-02-A"   7 devices, MAC 1-7   -> 822021..822027
|   +- network 4  "MSTP-02-B"  24 devices, MAC 1-24  -> 822201..822224
|
+- CHILLER-RTAC-822 -- absent by design. Not a BACnet device.
```

Device instance numbers read as `822` + role + MAC and sit well inside
the 22-bit BACnet limit of 4194302.

### The chiller is deliberately off-network

`CHILLER-RTAC-822` has `parent: null` in the inventory and the existing
`/api/chiller/822` endpoint reports `integration: "None -- local display
only, no BACnet to SC-822"`. This is a teaching detail, not an
omission: chiller data that is not integrated must be read at the unit.

The server MUST NOT create any object for the ten `RTAC822_*` points,
and the self-test MUST assert their absence. A future decision to
integrate the chiller is a design change, not a bug fix.

## Object Model

Point types in `data/input/points.json` already map one-to-one onto
BACnet object types. Each device carries a Device object plus the points
whose `equipment` field matches it: 12 point objects for a makeup air unit, 6
for a fan coil, 2 for a hallway sensor, each alongside that device's
own Device object.

| Point type | BACnet object   | Commandable        |
|------------|-----------------|--------------------|
| `AI`       | AnalogInput     | no                 |
| `AV`       | AnalogValue     | when `writable`    |
| `AO`       | AnalogOutput    | always             |
| `BI`       | BinaryInput     | no                 |
| `BO`       | BinaryOutput    | always             |
| `MV`       | MultiStateValue | when `writable`    |

- `objectName` is the point name (`MAU01_SAT`) so it cross-references
  the Tracer, Metasys and Niagara front ends.
- `description` carries human text.
- `units` derives from the point's `units` field: `F` ->
  `degreesFahrenheit`, `%` -> `percent`, `bool` -> `noUnits`.
- MultiStateValue objects carry `numberOfStates` 5 and `stateText`
  Off / Auto / Low / Mid / High, matching `FAN_MODE_FLOW` in
  `model822.py`.

Of the 421 points, 162 are writable and therefore commandable.

## Priority Semantics

This is the central teaching mechanism of the design, and it is wired to
the physics rather than simulated on top of it.

- The device's own control loop writes its output to `priorityArray[16]`
  every step.
- An operator writes at priority 8 (Manual Operator), which wins.
- `presentValue` resolves to the lowest-index non-null slot, falling
  back to `relinquishDefault` when the array is empty.
- Writing Null at a priority relinquishes that slot — the release action
  in supervisory front ends — and control falls back to the loop's
  value at 16.

The resolved `presentValue` of each commandable object is the override
input to `model822.step_822()`. Overriding and releasing a valve is
therefore the same mechanism the building already uses, not a parallel
one.

## Runtime

A single asyncio task in `bacnet822.py`, once per tick:

1. Read resolved `presentValue` of all commandable objects and build the
   overrides mapping in the shape `step_822()` expects:
   `{point_name: {"value": v}}`.
2. Call `model822.step_822(state, step, profile, overrides)`.
3. Write returned sensor values into the read-only AI/BI objects.
4. Write each control loop's output into `priorityArray[16]` of its
   commandable object.
5. Persist `data/output/state_822.json` and merge into
   `data/output/latest_points.json`, so `/tracer`, `/metasys` and
   `/niagara` stay live against the same building being commanded over
   BACnet.

### Timescale

`--timescale` expresses model minutes per real second.

- Default 30x — one model minute per two real seconds. A valve write
  shows movement within roughly 30 seconds and settles in a couple of
  minutes, which is the right cadence for learning and demonstration.
- `--timescale 1` gives real-time thermal response, for seeing how
  slowly a real building actually answers.

### D5. Two writers, one building

`bas_sim.py` also steps 822, and both running at once would corrupt the
shared state. `bacnet822.py` holds `data/output/.822-bacnet.lock`
containing its PID and start time for the duration of its run.
`bas_sim.py` gains a guard that skips 822 with an explicit message when
the lock is held, while continuing to run hospital and office normally.
A stale lock whose PID is not alive is ignored and replaced.

Trouble-call and 2AM flows on the other two buildings are unaffected.

### Audit

Every accepted WriteProperty appends one record to
`data/output/operator_actions.jsonl` in the existing schema, extended
with the BACnet-specific fields: object identifier, priority, source
address. Relinquish operations are logged as their own action rather
than as a write of null.

## Network Access

- `--bbmd` makes the IP port a BBMD with a broadcast distribution table.
  A Windows BACnet client registers as a foreign device to the host's
  WSL address on port 47809 and discovery then works through NAT with no
  environment change.
- `docs/bacnet-822.md` documents that path, the `networkingMode=mirrored`
  switch for when a physical supervisor on the LAN must discover the
  host, and a priority-array reference.
- Port 47809 is used rather than 47808 so the existing hospital device
  on 47808 keeps working alongside.

## Verification

Layered, cheapest first.

1. **Unit, no network.** Priority resolution as a pure function: write
   at 8 beats 16; Null at 8 falls back to 16; an empty array falls to
   `relinquishDefault`; an out-of-range priority is rejected.
2. **`--self-test`, offline.** Build the device tree without binding a
   socket and assert: 2 routers, 62 devices, 4 networks, correct object
   counts per equipment type, MAC assignment within 1-127, every device
   instance below 4194302, and no object anywhere for an `RTAC822_*`
   point.
3. **Integration, over the wire.** Using `scripts/bacnet822-client.py`:
   Who-Is returns 62 devices behind 2 routers; read `MAU01_SAT`; write
   `MAU01_CHW_VLV_CMD` 45.0 at priority 8; confirm `presentValue`
   resolves to 45.0; advance ticks; **confirm `MAU01_SAT` actually
   rose**; relinquish priority 8; confirm the loop recovers setpoint.
4. **Regression.** `scripts/run-smoke-test.sh` gains the integration
   sequence. Hospital and office output must remain byte-identical.

Step 3 is the acceptance test for the design. Protocol correctness
without a physical response is failure.

`scripts/bacnet822-client.py` is a test harness, not an operator
interface. It exists so the write path can be asserted automatically;
the intended human clients are external supervisors.

## Risks

1. **bacpypes3 0.0.102 routing behavior — the only real unknown.**
   Everything rests on multiple `Application` instances on virtual nodes
   behind a `NetworkServiceAccessPoint` behaving as expected. This is
   why the first task is a spike: one router, two devices, one write,
   proven end to end before 62 devices are built on top. If routing
   cannot be made to work cleanly, the fallback is the flat one-device-
   per-controller topology rejected in D1, which costs realism but not
   the acceptance test.
2. **Process footprint.** 62 applications and roughly 420 objects in one
   process. Expected to be fine; measured during the spike.
3. **Write storms.** A supervisor polling or writing aggressively could
   outpace the tick. Writes are absorbed into the priority array
   immediately and applied at the next tick; the array, not a queue, is
   the buffer.

## Files

New:
- `open-source-stack/bacnet822.py`
- `scripts/bacnet822-client.py`
- `docs/bacnet-822.md`

Modified:
- `simulator/bas_sim.py` — lock guard only
- `scripts/run-smoke-test.sh` — integration sequence

No new dependencies: `bacpypes3==0.0.102` is already pinned in
`open-source-stack/requirements.txt`.

No git operations at any point. Per the lab's standing rule, the
operator owns git.

## Data Boundary

Everything here is synthetic, consistent with `safety/data-boundary.md`.
No real facility, vendor, network or credential data enters this work.
The simulated devices must not claim a real vendor's identity.

## Next Milestone — Out Of Scope Here

The milestone after this one is supervisory operator-workflow parity in
`/tracer`, not additional protocol complexity. Recommended sequence,
each its own design conversation:

1. **Override panel** — present value, controlling priority, priority
   array 1-16, relinquish default, release. Nearly free once this design
   ships, because the arrays become real objects rather than a UI
   fiction. Highest value per unit of work.
2. **Data logs** — trend selection over existing trends plumbing.
3. **Alarms** — low supply air, command/status mismatch, sensor out of
   range, valve at 100 percent without recovery.
4. **Schedules and Areas** — requires an occupancy model the physics
   does not yet have. Its own design conversation.

`/tracer` is currently modeled on the Tracer SC generation. If it moves
toward Synchrony-era workflow, its navigation frame of reference changes
too. Build that against navigation labels observed directly on a real
screen rather than against secondhand descriptions.


---

## Companion Milestone — Fault Injection And Troubleshooting Training Mode

**Scope status: recorded here, NOT in this spec's plan.** This is its own
spec and its own plan. It is written down now because it changes nothing
about the BACnet work and everything about what the BACnet work is *for*,
and because part of it is already built and must not be rebuilt.

### Governing principle

> The fault injector breaks the **cause**. Physics creates the
> **symptoms**. BACnet exposes the **evidence**. The operator diagnoses
> the evidence and proves the repair.

An injector must never write a temperature, pressure, flow or valve
position directly. Doing so teaches fault trivia — "dirty strainer = the
answer" — instead of the actual skill, which is deciding what evidence
eliminates the wrong hypotheses and what physical response proves the
repair worked.

The same separation governs the AI layer. Four nouns must stay distinct
throughout: **measured**, **calculated**, **setpoint**, **commanded**.

### What already exists — do not rebuild

`model822.py` already implements cause-level injection through its
`knobs` parameter, plumbed per-device by `_knobs_for(knobs, device)` and
already exercised by the module self-test:

| Knob | Device scope | Models |
|------|--------------|--------|
| `strainer_resistance` 0..1 | `CHW-822` | fouled strainer, flow loss |
| `p1_running` / `p2_running` | `CHW-822` | pump availability |
| `coil_fouling` 0..1 | per MAU/FCU | degraded heat transfer |
| `air_bound` bool | per MAU/FCU | airlocked coil |
| `condenser_fouling` 0..1 | chiller | rejection degradation |
| `capacity_limit` 0..1 | chiller | derate |
| `condenser_fan_failed[]` | chiller | per-circuit fan loss |
| `circuit_locked_out[]` | chiller | per-circuit lockout |

Also already built: the 15-fault trouble-call library
(`data/input/fault_library.json`), its dealing/grading API
(`/api/trouble-calls/*`), the interview-driven authoring prompt
(`ai-dev-prompts/4-add-a-fault.md`), and deterministic hourly weather
profiles in `data/input/weather_822.json`.

### D6. Cause injection for 822, and only cause injection

The repo currently contains two injection philosophies. The hospital and
office faults perturb **points** — `drift`, `stuck`, `step`,
`noise_flatline`, `forces`. Building 822 perturbs **causes**, via knobs.

Decision: 822 keeps cause injection exclusively and never adopts point
perturbation. The legacy point-perturbation faults stay as they are for
the buildings that already use them; they are not a model to follow.

Reason: point perturbation cannot produce a coherent diagnosis, because
the downstream evidence is asserted rather than derived. Cause injection
produces the full causal chain for free — a restricted strainer drives
flow down, which drives coil delta-T down, which drives supply air up,
which drives the valve toward saturation, which is what the operator
actually reads. Only the second kind can be diagnosed rather than
memorized.

### New work — not yet planned

- [ ] **W1. Two parallel realities: physical truth vs BAS truth.**
  The largest item and the reason this is its own spec. Today every
  sensor reads the physical value exactly and every actuator reaches its
  commanded position. Real calls turn on the gap between them. Needs a
  sensor/actuator transduction layer with its own knobs — `sensor_bias`,
  `sensor_stuck`, `actuator_slip` — so the model can hold, for example,
  physical supply air at 55.1 F while the controller believes 58.6 F, or
  command 100 percent and read back 97 percent feedback while the
  physical valve sits at 35 percent. The control loop must run on the
  *believed* value, because that is what makes the building behave wrongly
  in a way that is diagnosable. Field measurement commands (W2) are then
  the only way to see physical truth.

- [ ] **W2. Field action surface.** Commands such as `inspect MAU04
  filter`, `measure MAU04 chw-entering-temp`, `verify MAU04
  valve-travel`, `clean MAU04 strainer`, `bleed MAU04 coil`. Rules:
  inspect is not repair, every action returns an observation whether or
  not it is relevant, and repair is not instant recovery — a cleaned
  strainer restores flow and the building then takes simulated minutes
  to stabilize. The existing 30x timescale is what makes walking back to
  the workstation and watching recovery worth doing.

- [ ] **W3. Living loads.** Weather waves already exist. Occupancy does
  not, and neither does sensor noise. Add a deterministic occupancy
  profile and small bounded noise on sensed values so trends read as
  alive rather than as a spreadsheet. Noise must be seeded and
  reproducible — a training scenario has to be replayable.

- [ ] **W4. Difficulty tiers.** Single fault, no misleading symptoms.
  Then one root fault plus real-but-irrelevant deficiencies (a slightly
  dirty filter, a loose-but-serviceable belt) to defeat parts-cannon
  troubleshooting. Then interacting faults — a hydronic restriction plus
  a biased supply-air sensor — where the repair genuinely improves the
  building and the BAS still looks wrong.

- [ ] **W5. Closeout discipline.** Every session ends with fault,
  evidence, corrective action, verification, and preventive action, plus
  a one-sentence executive summary. Three roles in one exercise: what
  failed and why it matters (consultant), what the BAS and field
  evidence proved (DDC tech), what prevents recurrence (PM). Any override
  taken during the call must be released before closeout, and the
  closeout must fail if one is still held.

- [ ] **W6. AI authority boundary.** An AI supervisory layer gets READ
  (trends, alarms, present values, priority arrays, equipment state),
  PROPOSE (likely causes, troubleshooting sequence, points to inspect),
  and SCENARIO AUTHORITY (inject faults, change occupancy and weather).
  It gets **no direct write authority to control loops**. A later,
  explicitly separate mode may grant bounded write authority for the
  purpose of studying what happens when the reasoning is wrong.

  > AI advises. Deterministic controllers control. Physics decides the
  > result. The human authorizes intervention.

  This aligns with the rank boundaries already governing this repo, where
  automated authority stops at C-rank and B/S-rank decisions stay human.

### Why this is its own spec

W1 alone changes the shape of every point in the model, because it
splits each one into a physical value and a believed value. That is a
larger change than the entire BACnet server described above, and it must
not ride along with it. The BACnet work ships first and stands alone; a
fault injected through the existing knobs is already visible over BACnet
the day the server works, because the physics is the same physics.

