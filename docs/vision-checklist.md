# BAS-SIM Vision Checklist

## A Flight Simulator for HVAC, DDC, BACnet, and Niagara Technicians

- **Document status:** vision and implementation checklist
- **Created:** 2026-09-22
- **Status last verified:** 2026-09-23, on branches `feat/wiresheet-config-fields`
  and `feat/wiresheet-point-writes` (sections 4, 12.3–12.6, 12.10, 13, 18, 23
  reviewed; other sections unchanged)
- **Target:** `GP-SECLAB/target-application/BAS-SIM`
- **Primary learner:** a working controls technician preparing for Niagara 4
  TCP Level 1 while developing senior-level HVAC/DDC troubleshooting skill
- **Data boundary:** entirely synthetic; governed by `safety/data-boundary.md`

**Status legend.** `[x]` = completed and verified in the running lab, with
the verification named. `[ ] Partial:` = some of it works; the note says what
is missing. `[ ] Unverified:` = code exists but was not exercised in the
latest review. A plain `[ ]` = not built.

---

## 1. The Vision in One Sentence

Build a living, synthetic building where the trainee reports for a shift,
connects to the BAS, discovers problems from imperfect evidence, chooses BAS
and field actions, repairs the actual cause, watches the physics recover, and
proves the work—while also completing Niagara engineering tasks that are
graded from the artifacts produced rather than from memorized answers.

This should feel less like a quiz website and more like a flight simulator:

```text
hidden cause
  -> physical consequences
  -> controller observations
  -> BACnet/Niagara evidence
  -> trainee investigation
  -> field or software intervention
  -> time-dependent recovery
  -> verified closeout
```

The system must answer the question:

> Can the trainee diagnose and restore a believable building—not merely name
> a fault after being shown a convenient set of symptoms?

---

## 2. What the Learner Is Trying to Become

The target is not a button-clicking BAS operator. The target is a technician
who can move confidently between four views of the same problem:

1. **HVAC mechanic:** understands air, water, refrigerant, heat transfer,
   safeties, mechanical failure, and safe field practice.
2. **DDC controls technician:** understands sensors, outputs, actuators,
   feedback, sequences, PID loops, schedules, overrides, alarms, and trends.
3. **Network/BACnet technician:** understands devices, instances, MACs,
   trunks, routing, priority arrays, discovery, communications failures, and
   what the protocol does and does not prove.
4. **Niagara engineer/operator:** can navigate, inspect, build, bind, wire,
   secure, back up, troubleshoot, and document a station.

Senior-level behavior means the learner can:

- translate a complaint into testable hypotheses;
- separate a controller's command from physical proof;
- choose the next observation that eliminates the most possibilities;
- avoid unsafe or destructive action;
- repair causes instead of suppressing symptoms;
- recognize interacting faults and misleading evidence;
- explain the failure to an operator, mechanic, engineer, and manager;
- leave the system in normal automatic control with evidence of recovery.

---

## 3. The Kubernetes/CKA Analogy

The desired training model is the BAS equivalent of a live CKA exercise.

| Kubernetes performance task | BAS-SIM equivalent |
|---|---|
| Receive a broken cluster | Receive a building at the beginning of a shift |
| Inspect status/events/logs | Inspect BAS points, alarms, trends, and topology |
| Enter node-level diagnostics | Perform field measurements and inspections |
| Change the broken resource | Repair mechanical, controls, or network cause |
| Wait for readiness/health | Watch temperatures, flows, pressures, and alarms recover |
| Automated state validation | Grade physical recovery, configuration, safety, and closeout |
| Create an HPA/Helm release | Build a schedule, Wire Sheet, Px page, alarm/history, or role model |
| Fix a nonresponsive API server | Diagnose an offline JACE, duplicate address, broken binding, or certificate issue |

The analogy is about **performance-based learning**, not identical technology.
Niagara is not Kubernetes, a JACE is not literally a node, and a Supervisor
is not a consensus control plane.

---

## 4. Current State Versus Destination

### Current strengths

- [x] Synthetic hospital and office inventories
- [x] Browser-based Metasys-style and Niagara-style views
- [x] Fifteen scripted hospital/office trouble-call faults
- [x] Alarm, trend, point, equipment, and action data
- [x] File-backed commands and releases with role attribution
- [x] Building 822 coupled thermal/hydronic physics
- [x] Cause-level Building 822 knobs
- [x] BACnet/IP server with routed topology and real priority arrays
- [x] Building 822 command-to-physical-response behavior
- [x] Separate command, actuator travel, and feedback realities for MAU valves
- [x] Hidden physical truth and basic field-verification CLI
- [x] Read-only Niagara Schedule and Platform demonstrations
- [x] Wire Sheet and Px editors: create, add and configure blocks/widgets,
  link, save, reload, back up, and restore one sheet/page — verified
  2026-09-23 through the browser UI and the API
- [x] Wire Sheet `PointWriteRef` outputs resolve onto point values at the
  supervisor level (Property Sheet, Px, Schedule views), verified 2026-09-23
  in the API and browser. Sources resolve in the lab's precedence convention:
  operator override (8) > Wire Sheet write (10) > schedule baseline (16) >
  simulator. This borrows priority-slot vocabulary and is **not** a complete
  Niagara/BACnet priority array (one Wire Sheet level, no relinquish default,
  no min on/off). One writer per point; `PointRef` reads only the underlying
  value, so cross-sheet chaining is unsupported. A failed evaluation or an
  invalid output faults the whole sheet, releases all its writes, and shows
  as a fault.
- [x] Real configuration snapshot/backup action
- [x] Visual Niagara study guide and scenario explanations

### Current limitations

- [ ] Trouble calls still end primarily in selecting equipment/category.
- [ ] Field inspections are not yet a complete browser workflow.
- [ ] Most repair actions are not modeled as first-class actions.
- [ ] Scenario state is not a durable action/evidence graph.
- [ ] The trainee cannot yet make many unsafe, irrelevant, or inefficient
  choices and see their consequences.
- [ ] The system does not consistently grade process, safety, or evidence.
- [ ] Many real-world cases exist only as written questions.
- [ ] Partial: Niagara construction editors are new and still need work.
  Hardened and verified 2026-09-23: config, reference validation, malformed
  input, backup/restore. Still missing: drag positioning and click-to-connect,
  editing or deleting existing blocks/widgets/links, and any Schedule editor
  (Schedules are read-only).
- [ ] Wire Sheet writes stop at the supervisor. Hospital/office physics does
  not respond to them (it doesn't respond to operator overrides either), so
  no Wire Sheet output yet produces a physical equipment response.
- [ ] Niagara exercises are not yet task cards with state-based grading.
- [ ] The lab cannot replace real licensed Workbench, JACE hardware, tools,
  meters, gauges, or supervised field experience.

### Destination

- [ ] One coherent shift-based training experience ties together the simulator,
  front end, BACnet, field actions, repair actions, Niagara tasks, and closeout.
- [ ] Every scored scenario contains hidden truth, causal behavior, evidence,
  safe actions, misleading alternatives, repair logic, recovery, and grading.
- [ ] Every N4 practical exercise starts from a known station state and is
  graded by inspecting the artifact the learner created or repaired.

---

## 5. Governing Training Principles

### 5.1 Causes, not painted symptoms

- [ ] Fault injection changes a physical, electrical, logic, configuration, or
  communications cause.
- [ ] Downstream symptoms are derived wherever the model can reasonably derive
  them.
- [ ] Direct point perturbation is reserved for explicitly modeled sensor,
  signal, mapping, or communications failures.
- [ ] A scenario author cannot declare mutually inconsistent evidence without
  an explicit deception mechanism such as biased sensing or stuck feedback.

> Break the cause. Physics creates the symptoms. Controllers observe the
> result. The technician proves the repair.

### 5.2 Command is not proof

The lab must keep these facts separate:

```text
software command
electrical output signal
actuator physical position
reported feedback
air/water/refrigerant movement
heat transfer
sensed value
displayed value
```

- [ ] Every scenario declares which layers are healthy, failed, hidden, or
  misleading.
- [ ] The UI never presents commanded value as proof of mechanical response.
- [ ] Field actions reveal only what that tool/action could actually reveal.

### 5.3 Inspection is not repair

- [ ] Inspecting a strainer does not clean it.
- [ ] Verifying valve travel does not free or replace the valve.
- [ ] Measuring voltage does not prove actuator travel.
- [ ] Reading a pressure gauge does not change system pressure.
- [ ] Opening a panel or entering a mechanical room creates an observation,
  not an automatic diagnosis.

### 5.4 Repair is not instant recovery

- [ ] Thermal mass, actuator slew, hydronic refill/purge, alarm delays, and
  network rediscovery create believable recovery time.
- [ ] The trainee must wait, trend, and verify rather than seeing an immediate
  green banner.
- [ ] A correct repair can still have an incomplete closeout if overrides,
  alarms, air, water, or temporary configuration remain unresolved.

### 5.5 Evidence outranks guessing

- [ ] The grader rewards observations supporting the conclusion.
- [ ] A lucky correct answer without evidence does not receive full credit.
- [ ] The learner must distinguish observation, inference, diagnosis, action,
  and verification in the closeout record.

### 5.6 Safety is part of competence

- [ ] Unsafe action is never required for success.
- [ ] A scenario can penalize or stop unsafe action.
- [ ] Standing water near energized equipment triggers a safety decision.
- [ ] LOTO, isolation, escalation, PPE, and site procedure are represented as
  decision points without pretending a browser grants real authority.
- [ ] The simulator never instructs a learner to touch live electrical,
  rotating, pressurized, hot, cold, or contaminated equipment.

---

## 6. The Daily Experience

### 6.1 Start of shift

The learner should be able to start a shift with one command and receive:

- [ ] synthetic date/time and weather;
- [ ] building occupancy/load state;
- [ ] overnight alarm count and priorities;
- [ ] active overrides and who placed them;
- [ ] equipment communication summary;
- [ ] unresolved tickets and turnover notes;
- [ ] maintenance work that may be relevant or distracting;
- [ ] no disclosure of hidden scenario truth.

### 6.2 Plug in and orient

- [ ] Choose the correct supervisory connection or station.
- [ ] Review network/device health.
- [ ] Read the alarm console without assuming every alarm is causal.
- [ ] Find the affected area/system/equipment.
- [ ] Establish what normal should look like from sequence and baseline.
- [ ] Create an initial hypothesis list.

### 6.3 Investigate

- [ ] Review live points.
- [ ] Build/select useful trends.
- [ ] Inspect priority arrays and active overrides.
- [ ] Compare command, status, and feedback.
- [ ] Inspect upstream and downstream equipment.
- [ ] Choose virtual field actions.
- [ ] Receive realistic observations, including normal/irrelevant findings.
- [ ] Revise hypotheses from evidence.

### 6.4 Intervene

- [ ] Apply an authorized temporary override when justified.
- [ ] Take a backup before configuration changes.
- [ ] Perform a mechanical repair, controls repair, or network correction.
- [ ] Respect isolation and safety prerequisites.
- [ ] Avoid actions outside the learner role.

### 6.5 Prove recovery

- [ ] Return control to automatic operation.
- [ ] Release every temporary override.
- [ ] Wait for realistic stabilization.
- [ ] Verify the original complaint is resolved.
- [ ] Verify no new alarm or secondary failure was introduced.
- [ ] Compare before/after evidence.

### 6.6 Close the call

- [ ] Fault/cause
- [ ] Evidence
- [ ] Corrective action
- [ ] Verification
- [ ] Preventive action
- [ ] Remaining risk or recommended follow-up
- [ ] One-sentence executive summary

---

## 7. Scenario Runtime Model

### 7.1 Required scenario definition

Every scenario needs:

- [ ] unique scenario ID and version;
- [ ] title hidden from the trainee until closeout;
- [ ] opening complaint written in operator language;
- [ ] facility, area, equipment, system, and affected points;
- [ ] difficulty level;
- [ ] prerequisites and required simulated subsystems;
- [ ] one or more hidden causes;
- [ ] initial physical and configuration state;
- [ ] distractors and background deficiencies;
- [ ] allowed actions by role;
- [ ] action prerequisites;
- [ ] action observations and state transitions;
- [ ] repair actions and side effects;
- [ ] unsafe/invalid action handling;
- [ ] recovery criteria and expected time;
- [ ] success, partial-success, and failure conditions;
- [ ] grading rubric;
- [ ] teaching notes and debrief;
- [ ] deterministic seed/replay information.

### 7.2 Scenario state machine

```text
AVAILABLE
  -> OPEN
  -> INVESTIGATING
  -> ISOLATED (when safety/energy control is required)
  -> REPAIRING
  -> RECOVERING
  -> READY_FOR_VERIFICATION
  -> CLOSED

Alternative terminal states:
  ABANDONED
  UNSAFE_STOP
  FAILED_VERIFICATION
```

- [ ] State transitions are server-controlled, not merely hidden buttons.
- [ ] Every transition is audit logged.
- [ ] Refreshing the browser does not reset the case.
- [ ] A scenario can be paused/resumed.
- [ ] Instructor reset is explicit and logged.

### 7.3 Action model

Every action should record:

```json
{
  "action_id": "verify-pump-dp",
  "actor": "BAS-OPR-01",
  "role": "technician",
  "target": "CHW822-P1",
  "started_at": "...",
  "duration_sim_minutes": 5,
  "prerequisites_met": true,
  "observation": "0.2 psid across operating pump",
  "state_changes": [],
  "safety_effect": 0,
  "diagnostic_cost": 2
}
```

Action families:

- [ ] BAS observation
- [ ] Trend creation/review
- [ ] Alarm acknowledgement/comment
- [ ] Override/command/release
- [ ] Network diagnostic
- [ ] Visual inspection
- [ ] Temperature measurement
- [ ] Pressure/differential-pressure measurement
- [ ] Flow measurement
- [ ] Electrical signal/current/voltage measurement
- [ ] Actuator travel verification
- [ ] Mechanical isolation/LOTO declaration
- [ ] Cleaning, tightening, bleeding, replacement, refill, purge
- [ ] Configuration edit
- [ ] Backup/restore
- [ ] Escalation/request for specialized support
- [ ] Wait/observe recovery
- [ ] Closeout submission

### 7.4 Evidence visibility

- [ ] Trainee API responses never include hidden causes or expected answers.
- [ ] Instructor role can view ground truth and scenario progress.
- [ ] A field observation is revealed only after its action is completed.
- [ ] Different tools can produce different precision and confidence.
- [ ] Faulty instruments or biased sensors are explicit scenario mechanisms,
  not arbitrary contradictions.
- [ ] The evidence record identifies source: BAS, field instrument, visual,
  documentation, operator report, or inference.

### 7.5 Time

- [ ] Wall time and simulated time are distinct.
- [ ] Actions consume simulated minutes.
- [ ] Weather/load/occupancy can change during the call.
- [ ] Delay matters for alarm persistence and recovery.
- [ ] Timescale is selectable for teaching without changing causal behavior.

---

## 8. Branching Diagnostic Interface

The interface should feel like an investigation workspace, not a multiple-
choice test.

### 8.1 Primary layout

- [ ] Left: building/system/equipment navigation
- [ ] Center: current BAS view, trend, schematic, or field location
- [ ] Right: hypotheses, evidence notebook, available actions
- [ ] Top: scenario time, weather/load, role, safety state
- [ ] Bottom: chronological action/evidence timeline

### 8.2 Diagnostic graph

- [ ] The trainee can open a diagnostic map showing actions already taken.
- [ ] Unchosen actions are available based on context, not displayed as a
  single obvious golden path.
- [ ] Branches can converge when multiple checks establish the same fact.
- [ ] Irrelevant actions return plausible normal observations.
- [ ] The graph does not reveal which branch is correct in advance.
- [ ] After closeout, instructor/debrief mode overlays the efficient path,
  unnecessary actions, unsafe actions, and missed evidence.

### 8.3 Hypothesis notebook

- [ ] Add/remove likely causes.
- [ ] Mark evidence supporting or contradicting each cause.
- [ ] Record confidence without exposing the answer.
- [ ] Promote a hypothesis to diagnosis only with cited evidence.
- [ ] Preserve hypothesis changes for debriefing reasoning quality.

---

## 9. HVAC/Mechanical Training Track

### 9.1 Hydronics

- [ ] Pump commanded but not rotating
- [ ] Pump rotating backward
- [ ] Broken coupling
- [ ] Damaged/eroded impeller
- [ ] Pump cavitation or inadequate suction
- [ ] Air-bound pump or coil
- [ ] Closed isolation valve
- [ ] Failed/rusted valve body leaking into mechanical room
- [ ] Plugged strainer with measurable differential pressure
- [ ] Open bypass causing low remote DP
- [ ] Failed check valve and reverse flow
- [ ] Low loop fill/pressure
- [ ] Bad DP transmitter versus real low DP
- [ ] Flow meter failure versus real zero flow
- [ ] Lead/lag staging failure
- [ ] Low-delta-T syndrome

### 9.2 Air systems

- [ ] Dirty filter
- [ ] Collapsed filter
- [ ] Broken or slipping belt
- [ ] Fan rotation wrong
- [ ] Fan command/status mismatch
- [ ] VFD fault or limited speed
- [ ] Closed/stuck damper
- [ ] Slipped damper linkage
- [ ] Excess outdoor air
- [ ] Infiltration or open door/load
- [ ] Duct obstruction
- [ ] Excess airflow reducing latent performance
- [ ] Low airflow causing coil freeze risk
- [ ] Simultaneous heating and cooling
- [ ] Poor sensor placement/stratification

### 9.3 Cooling coils and humidity

- [ ] Fouled coil
- [ ] Air-bound coil
- [ ] Warm entering chilled water
- [ ] Low water flow
- [ ] Poor valve authority
- [ ] Three-way valve mixing incorrectly
- [ ] Stuck actuator with honest feedback
- [ ] Stuck actuator with lying feedback
- [ ] Biased SAT or humidity sensor
- [ ] Excess airflow/contact-time problem
- [ ] Condensate drain restriction or safety trip
- [ ] Reheat masking or creating humidity behavior

### 9.4 Chillers and heat rejection

- [ ] Low evaporator flow lockout
- [ ] Condenser coil obstruction such as debris/trash bag
- [ ] Failed condenser fan
- [ ] Fouled condenser
- [ ] Circuit lockout
- [ ] Capacity limitation at high ambient
- [ ] Incorrect leaving-water setpoint
- [ ] Sensor error versus real temperature condition
- [ ] Repeated reset without correcting permissive
- [ ] Air-cooled versus water-cooled diagnostic differences

### 9.5 Heating

- [ ] Boiler flame failure
- [ ] Pump/flow permissive failure
- [ ] Hot-water valve failure
- [ ] Outdoor-air reset error
- [ ] Short cycling
- [ ] Freeze protection response
- [ ] Reheat failure
- [ ] Sensor or limit disagreement

---

## 10. DDC and Controls Training Track

### 10.1 Sensors and inputs

- [ ] Bias/offset
- [ ] Stuck value
- [ ] Open/short circuit
- [ ] Intermittent signal
- [ ] Wrong scaling
- [ ] Wrong engineering units
- [ ] Wrong sensor type/curve
- [ ] Poor location
- [ ] Shared/common reference problem
- [ ] BAS value differs from calibrated field measurement

### 10.2 Outputs and actuators

- [ ] Output command exists but no electrical signal
- [ ] Correct signal but no travel
- [ ] Correct travel but no process effect
- [ ] Reversed action
- [ ] Incorrect signal type/range
- [ ] Stuck or slipped linkage
- [ ] Failed feedback device
- [ ] Floating actuator timing/calibration problem
- [ ] Override held at unexpected priority

### 10.3 Sequences and loops

- [ ] Wrong setpoint
- [ ] Wrong action direction
- [ ] Excessive proportional gain
- [ ] Integral windup
- [ ] Missing deadband
- [ ] Missing actuator slew/time delay
- [ ] Competing control loops
- [ ] Bad enable/disable condition
- [ ] Safety interlock bypassed or miswired
- [ ] Schedule/occupancy conflict
- [ ] Reset strategy error
- [ ] Control logic is correct but mechanical plant cannot respond

### 10.4 Alarms and histories

- [ ] Alarm limit wrong
- [ ] Alarm attached to wrong point
- [ ] Alarm disabled
- [ ] Routing/class/recipient error
- [ ] Alarm acknowledgement without correction
- [ ] History extension absent
- [ ] Collection interval inappropriate
- [ ] COV threshold hides behavior
- [ ] Clock/time-zone mismatch
- [ ] Trend gaps caused by communications loss

---

## 11. BACnet and Network Training Track

- [ ] Duplicate BACnet device instance
- [ ] Duplicate BACnet MS/TP MAC
- [ ] Duplicate IP address
- [ ] Wrong IP subnet/gateway
- [ ] Wrong BACnet network number
- [ ] Wrong UDP port
- [ ] BBMD/FDR misconfiguration
- [ ] Missing or incorrect router reference
- [ ] MS/TP baud mismatch
- [ ] MS/TP polarity/wiring issue
- [ ] Token-passing degradation/noisy trunk
- [ ] Device offline behind a healthy router
- [ ] Entire trunk offline
- [ ] Object identifier/binding mismatch
- [ ] Priority-array conflict
- [ ] Relinquish failure or wrong priority
- [ ] Stale value caused by polling/subscription behavior
- [ ] Network symptom versus physical-process symptom separation

Every network scenario must distinguish:

- device visibility;
- object readability;
- write authorization;
- write acceptance;
- resolved command priority;
- physical response.

---

## 12. Niagara 4 Performance Track

The Niagara track should prepare for TCP Level 1 through repeated construction
and troubleshooting, then remain extensible to Levels 2 and 3.

### 12.1 Task format

Each task includes:

- [ ] starting station/project snapshot;
- [ ] plain-language work order;
- [ ] required outcomes, not click-by-click instructions;
- [ ] time budget;
- [ ] permitted tools and role;
- [ ] hidden automated checks;
- [ ] optional hints with score cost;
- [ ] final artifact and runtime validation;
- [ ] scenario questions explaining why the solution works.

### 12.2 Navigation and component model

- [ ] Navigate Supervisor, JACE, Config, Drivers, Services, and Files.
- [ ] Resolve and explain ORDs.
- [ ] Inspect Property Sheets, slots, actions, topics, status, and facets.
- [ ] Identify which station owns a component.
- [ ] Distinguish Platform from Station operations.

### 12.3 Driver/device/point work

- [ ] Create/configure a synthetic BACnet network.
- [ ] Discover a device.
- [ ] Discover/import proxy points.
- [ ] Configure names, facets, units, and writable behavior.
- [ ] Diagnose a faulted/stale proxy.
- [ ] Verify a write through to physical response. (Not met: Wire Sheet
  writes and operator overrides change the supervisor's point value only;
  hospital/office physics does not read them.)

### 12.4 Schedules and calendars

- [ ] Create Boolean schedule.
- [ ] Create weekly occupied periods.
- [ ] Add holiday/date exception.
- [x] Link schedule output to logic/setpoint selection, at the supervisor
  level. A Wire Sheet `ScheduleRef` → `Select` → `PointWriteRef` drives the
  setpoint point's value (verified 2026-09-23: `OR1_TEMP_SP` = 70 via
  wiresheet while occupied; an operator override wins; releasing it hands
  control back). No physical equipment response (see §12.3).
- [ ] Prove effective value at test timestamps.
- [ ] Diagnose an unexpected exception or default value.

Status: Schedules are read-only in the UI and API today (GET only), so the
create/edit items above are not built.

### 12.5 Wire Sheets

- [x] Place and configure constants, point references, schedule references,
  comparisons, Boolean blocks, selectors, and output references. All 9 block
  types were built from the Add Block form in the browser on 2026-09-23.
  References are picked from the station's real points and schedules, and a
  save naming an unknown point or schedule is rejected. Placement uses typed
  x/y coordinates, not drag.
- [ ] Partial: Draw compatible links between explicit slots. Link slots are
  chosen from each block's declared slots, and the server rejects slots that
  don't exist. Value-type compatibility (number vs Boolean) is not checked,
  and there is no click-to-connect yet.
- [x] Reject invalid slots, duplicate links, and cycles — covered by the
  `frontend/wiresheets.py --self-test` cases in the smoke test.
- [x] Build occupied/unoccupied setpoint selection, at the supervisor level.
  Built in the browser; the selected setpoint drives the target point's value
  (verified 2026-09-23). Physical response is not modeled (§12.3).
- [ ] Partial: Build an equipment enable/interlock. `Compare`/`And`/`Not`/`Or`
  logic builds, and its output now drives a Boolean command point at the
  supervisor level (verified: `AHU_OR1_FAN_CMD` = 1 via wiresheet). Still
  missing for full interlock behavior: equipment physics doesn't respond to
  the command, and nothing proves the interlock trips and recovers.
- [ ] Troubleshoot a missing, wrong, or reversed link. (Runtime faults are
  now visible — banner, per-block status, and point flags — but no planted-
  fault exercise exists.)
- [x] Observe runtime slot values — the canvas shows each output slot's
  resolved value (browser-verified 2026-09-23).
- [x] Save, reload, back up, and restore. Verified 2026-09-23 in the browser
  (save → change → restore → reload) and in the API, including viewer denial
  and invalid backups (unrecorded, path traversal, missing sheet, bad
  reference, malformed, corrupt JSON) leaving the store byte-identical.
  Restore replaces only the selected sheet.

### 12.6 Px graphics

- [x] Create a page — verified via the API on 2026-09-23 (the create form uses
  the same endpoint).
- [ ] Partial: Place and reposition widgets. Widgets are placed at typed x/y
  (browser-verified). Existing widgets cannot be moved.
- [ ] Partial: Bind live points. Widget points are validated against the point
  inventory on save; live value rendering was not re-checked in the
  2026-09-23 review.
- [ ] Label command, status, feedback, setpoint, and sensor values honestly.
- [ ] Build an equipment schematic.
- [ ] Add navigation between pages.
- [ ] Diagnose broken/wrong ORDs.
- [ ] Verify values and commands at runtime.
- [x] Back up and restore a page — verified 2026-09-23 in the browser and the
  API, with the same checks as Wire Sheets.

### 12.7 Alarms

- [ ] Add alarm extension.
- [ ] Configure limit, deadband, delay, priority/class, and message.
- [ ] Trigger and acknowledge alarm.
- [ ] Verify normal-to-alarm-to-normal lifecycle.
- [ ] Diagnose missing/routed-wrong alarms.

### 12.8 Histories

- [ ] Add interval history.
- [ ] Add COV history where appropriate.
- [ ] Choose collection interval/deadband.
- [ ] Generate and query records.
- [ ] Plot history on Px.
- [ ] Diagnose missing or misleading history.

### 12.9 Security

- [ ] Create synthetic user.
- [ ] Create role.
- [ ] Apply category.
- [ ] Grant minimum permissions.
- [ ] Prove one allowed and one denied action.
- [ ] Diagnose excessive or missing access.

### 12.10 Platform and lifecycle

- [x] Take backup before change. Take Backup exists in Platform, Wire Sheet,
  and Px. The editors also snapshot automatically before every save and
  restore (verified 2026-09-23). Each snapshot now gets its own directory;
  before 2026-09-23, snapshots in the same second overwrote each other.
- [ ] Unverified: Inspect station/platform metadata (the Platform tab lists the
  synthetic stations; not exercised in the latest review).
- [ ] Partial: Restore known-good configuration. Per-item restore works for Wire
  Sheets and Px pages (verified). There is no whole-station restore and no
  restore for schedules, points, or alarm rules.
- [ ] Compare before/after configuration.
- [ ] Practice certificate/module/license concepts without false claims that
  the synthetic UI is a real platform daemon.

---

## 13. Artifact-Based N4 Grading

The grader should inspect saved state and runtime behavior, not browser clicks.

Example task:

> Create an occupied schedule with a holiday exception. Use it in a Wire Sheet
> to select occupied/unoccupied SAT setpoints. Bind the schedule state,
> selected setpoint, current SAT, and fan status to a Px page. Add history to
> SAT and an alarm for failure to maintain setpoint. Back up before changes.

Automated checks:

- [ ] required backup predates edits;
- [ ] schedule exists with correct weekly periods;
- [ ] date exception exists and resolves correctly;
- [ ] required blocks exist;
- [ ] links connect the correct source and target slots;
- [ ] graph is acyclic;
- [ ] output writes/binds to the correct point;
- [ ] Px widgets bind to the correct points;
- [ ] history configuration produces records;
- [ ] alarm activates under injected failure and returns to normal;
- [ ] runtime setpoint changes correctly at occupied/unoccupied timestamps;
- [ ] no unrelated station objects were damaged;
- [ ] learner explains resolution order and failure behavior.

Status (2026-09-23): **no grader exists; none of these checks is implemented.**
Some building blocks are in place: a timestamped backup log and an operator
audit log (inputs for "backup predates edits"), and save-time validation that
Wire Sheet references name real points and schedules and that sheets are
acyclic. Validation at save is not grading. Since 2026-09-23, Wire Sheet
outputs resolve onto points at the supervisor level, so a future grader could
inspect which sheet writes which point. That is an input to grading, not
grading: "output writes/binds to the correct point" stays unchecked until a
grader checks it against a task's requirements.

---

## 14. Difficulty Model

### Level 1: direct

- [ ] One root cause
- [ ] No deceptive sensor/feedback
- [ ] Clear complaint
- [ ] Minimal background alarms
- [ ] Required evidence available through obvious tools

### Level 2: realistic

- [ ] One root cause
- [ ] Multiple plausible hypotheses
- [ ] Normal but irrelevant deficiencies
- [ ] Background alarms and maintenance notes
- [ ] Requires trend comparison or field proof

### Level 3: interacting

- [ ] Two or more interacting causes
- [ ] Repairing one cause improves but does not normalize the system
- [ ] Sensor/feedback deception may be present
- [ ] Time/load affects visibility
- [ ] Requires disciplined override and closeout management

### Level 4: senior/incident lead

- [ ] Multiple systems or buildings affected
- [ ] Controls, network, and mechanical evidence overlap
- [ ] Must prioritize safety and operational impact
- [ ] Must delegate/escalate appropriately
- [ ] Must produce technical and executive closeouts

---

## 15. Grading Model

Suggested 100-point rubric:

| Dimension | Points | Examples |
|---|---:|---|
| Safety | 20 | isolation, LOTO decision, avoids unsafe access/action |
| Diagnosis | 20 | correct causal reasoning, separates symptom from cause |
| Evidence | 15 | cites relevant BAS/field evidence, verifies instruments |
| Efficiency | 10 | high-information checks, avoids parts cannon/reset loops |
| Technical execution | 15 | correct repair/configuration and authorized method |
| Recovery verification | 10 | waits, trends, releases overrides, tests under load |
| Closeout | 10 | clear cause/action/proof/prevention and remaining risk |

Rules:

- [ ] Unsafe critical action can cap or fail a score regardless of diagnosis.
- [ ] Correct lucky guess without evidence cannot score full diagnosis points.
- [ ] Excessive hint use reduces score but never blocks learning.
- [ ] Alternative valid diagnostic paths receive credit.
- [ ] Rubrics are versioned with scenario definitions.
- [ ] Debrief distinguishes wrong action from reasonable action that produced
  a normal result.

---

## 16. Instructor and Authoring Experience

### Instructor dashboard

- [ ] Start scenario by ID/difficulty/seed.
- [ ] Observe hidden ground truth.
- [ ] Watch trainee actions and hypotheses in real time.
- [ ] Pause/resume simulated time.
- [ ] Inject optional complication.
- [ ] Provide a logged hint.
- [ ] End/reset scenario.
- [ ] Review score and timeline.
- [ ] Replay the case from the trainee perspective.

### Scenario authoring

- [ ] Declarative JSON/YAML schema with validation.
- [ ] Human-readable scenario documentation generated from schema.
- [ ] Preview visible versus hidden fields by role.
- [ ] Validate referenced equipment, points, actions, and repair targets.
- [ ] Detect unreachable states and missing success paths.
- [ ] Run deterministic headless scenario tests.
- [ ] Package scenario without real facility data.
- [ ] Version/migrate scenario schema safely.

### Scenario author acceptance

- [ ] Cause is physically/logically coherent.
- [ ] At least two hypotheses are initially plausible.
- [ ] At least one safe path proves the cause.
- [ ] Repair changes the modeled cause.
- [ ] Recovery is derived and time-dependent.
- [ ] Closeout can be objectively graded.
- [ ] Debrief teaches a reusable principle.

---

## 17. Persistence and Data Model

Proposed additive files (names are illustrative until designed):

```text
data/scenarios/                 versioned scenario definitions
data/output/session.json        active shift/scenario state
data/output/action-log.jsonl    immutable trainee action timeline
data/output/evidence-log.jsonl  observations revealed during session
data/output/hypotheses.json     trainee hypothesis notebook
data/output/closeouts.jsonl     completed structured closeouts
data/output/scores.jsonl        rubric results and debrief metadata
data/output/n4-workspaces/      per-exercise editable station artifacts
```

- [ ] Writes are atomic.
- [ ] Corrupt/missing state fails safely.
- [ ] Generated state stays out of canonical scenario definitions.
- [ ] Instructor ground truth is never returned to trainee endpoints.
- [ ] Session replay is possible from seed + initial state + action log.
- [ ] Existing hospital/office/822 output contracts remain compatible.

---

## 18. API Surface Checklist

Illustrative resources:

### Shift/session

- [ ] `POST /api/training/sessions`
- [ ] `GET /api/training/sessions/active`
- [ ] `POST /api/training/sessions/{id}/pause`
- [ ] `POST /api/training/sessions/{id}/resume`
- [ ] `POST /api/training/sessions/{id}/reset` (instructor only)

### Investigation

- [ ] `GET /api/training/sessions/{id}/briefing`
- [ ] `GET /api/training/sessions/{id}/actions`
- [ ] `POST /api/training/sessions/{id}/actions/{action_id}`
- [ ] `GET /api/training/sessions/{id}/evidence`
- [ ] `PUT /api/training/sessions/{id}/hypotheses`

### Repair and closeout

- [ ] `POST /api/training/sessions/{id}/repairs/{repair_id}`
- [ ] `GET /api/training/sessions/{id}/recovery`
- [ ] `POST /api/training/sessions/{id}/closeout`
- [ ] `GET /api/training/sessions/{id}/debrief`

### N4 performance tasks

- [ ] `POST /api/n4/tasks/{task_id}/start`
- [ ] `GET /api/n4/tasks/active`
- [ ] Partial: CRUD for authorized schedules/Wire Sheets/Px pages/extensions/security.
  Wire Sheets and Px pages have create, read, save, backup, list-backups, and
  restore. There is no delete. Schedules are read-only; extensions and
  security are not built.
- [ ] `POST /api/n4/tasks/{task_id}/grade`
- [ ] `GET /api/n4/tasks/{task_id}/results`

All write endpoints require:

- [ ] Partial: schema validation;
- [ ] Partial: role authorization;
- [ ] Partial: audit record;
- [ ] Partial: backup-before-overwrite where applicable;
- [ ] Partial: clean 4xx response without corrupting saved state;
- [ ] Partial: tests for malformed references/types/cycles/duplicates.

All six are met for the Wire Sheet and Px editor endpoints (create, save,
backup, restore), verified 2026-09-23. Other write endpoints (point commands,
trouble calls, platform backup) have not been reviewed against this list.

---

## 19. Initial Flagship Scenarios

### S-001: Pump room flood / zero flow

Opening evidence:

- chiller off on low evaporator flow;
- pump command and status on;
- GPM reads zero;
- CHW temperatures drift;
- mechanical room inspection reveals standing water.

Hidden cause:

- rusted/failed valve body at pump leaking the loop down.

Required learning:

- run status does not prove delivered flow;
- visible water changes the safety response;
- refilling before isolation worsens the leak;
- repair requires isolation, replacement, refill/purge, restart, flow/DP
  verification, chiller reset, and recovery trend.

Acceptance:

- [ ] Unsafe approach/refill action is penalized.
- [ ] Multiple reasonable preliminary checks are supported.
- [ ] Leak is discoverable only through an appropriate field inspection.
- [ ] Repair stops water loss rather than changing the flow reading directly.
- [ ] Loop recovery requires refill/purge and simulated time.

### S-002: Condenser airflow obstruction

Hidden cause:

- debris/trash bag blocks an air-cooled condenser coil.

Derived symptoms:

- poor heat rejection;
- rising condensing condition/compressor burden;
- reduced available capacity;
- supply/CHW temperature drift;
- saturated cooling demand;
- possible high-pressure diagnostic.

Acceptance:

- [ ] Retuning/setpoint changes do not repair capacity.
- [ ] Visual inspection reveals obstruction.
- [ ] Removal restores airflow and capacity over time.

### S-003: Unit 4 excess airflow / high humidity

Hidden cause:

- excessive airflow across finite cooling coil capacity.

Derived symptoms:

- acceptable or marginal dry-bulb temperature;
- elevated humidity/dew point;
- insufficient leaving-air depression/dehumidification;
- high airflow/static/fan output;
- control valve may be highly commanded.

Acceptance:

- [ ] Trainee compares sensible and latent evidence.
- [ ] Competing causes remain possible until CHW, coil, OA, infiltration, and
  sensor evidence are checked.
- [ ] Correct airflow correction improves latent performance through physics.

### S-004: Lying valve feedback

- [ ] Command near 100%
- [ ] Feedback near 96-98%
- [ ] Physical valve near 15-35%
- [ ] Correct electrical output signal
- [ ] Warm SAT and saturated loop
- [ ] Requires physical travel verification

### S-005: Duplicate BACnet device instance

- [ ] Intermittent/wrong device resolution
- [ ] Points appear under unexpected device or go stale
- [ ] Network remains partially healthy
- [ ] Trainee must compare device identity and network evidence
- [ ] Correction requires unique instance and rediscovery/rebinding proof

### S-006: Stale Px binding

- [ ] Field controller and proxy are current
- [ ] Property Sheet is correct
- [ ] Px widget remains stale/wrong
- [ ] Incorrect ORD/binding is the cause
- [ ] Repair is graded from binding and runtime display

### S-007: Schedule exception surprise

- [ ] Equipment remains in unoccupied state during expected occupied hours
- [ ] Weekly schedule looks correct
- [ ] Date exception controls effective output
- [ ] Trainee must inspect effective value/source, not only weekly pattern

### S-008: Priority-array override left behind

- [ ] Control loop calculates correct output at priority 16
- [ ] Old priority-8 command remains controlling
- [ ] Operator note/time identifies previous intervention
- [ ] Correct resolution is justified relinquish, not loop retuning

---

## 20. Content Scale Goal

Do not hand-author “hundreds of alarms” as hundreds of unrelated scripts.
Build composable causes, contexts, and distractors.

```text
30 root causes
x 5 equipment/system contexts
x 3 load/weather states
x 3 evidence-quality modes
x 3 difficulty/distractor sets
= thousands of replayable combinations
```

- [ ] Root cause modules define causal changes.
- [ ] Context modules map causes onto compatible equipment.
- [ ] Environment modules supply weather/load/occupancy.
- [ ] Evidence modules add bias, failed feedback, or communications loss.
- [ ] Distractor modules add real but non-causal deficiencies.
- [ ] Scenario seeds make combinations reproducible.
- [ ] Curated flagship scenarios coexist with generated practice variants.

---

## 21. Testing Strategy

### Pure model tests

- [ ] Each cause changes expected physical variables monotonically/coherently.
- [ ] Repair removes cause rather than overwriting symptoms.
- [ ] Recovery follows expected time behavior.
- [ ] Hidden truth never leaks into normal points.

### Scenario graph tests

- [ ] Every scenario has at least one safe successful path.
- [ ] No action references missing equipment/points.
- [ ] No terminal state is accidentally unreachable.
- [ ] Unsafe actions behave as declared.
- [ ] Replay with same seed is deterministic.

### API tests

- [ ] Authorization and role filtering
- [ ] Invalid payloads return 4xx and preserve state
- [ ] Concurrent/duplicate actions are handled
- [ ] Refresh/restart preserves active session
- [ ] Instructor-only truth is protected server-side

### UI tests

- [ ] Rendering functions tested against realistic data
- [ ] Keyboard-accessible investigation/actions
- [ ] No answer revealed before closeout
- [ ] Responsive desktop/tablet behavior
- [ ] Clear separation of BAS observation, field observation, and inference

### End-to-end acceptance

- [ ] Start shift
- [ ] Discover complaint from alarm/turnover
- [ ] Inspect BAS and trends
- [ ] Choose field actions
- [ ] Identify and isolate cause
- [ ] Repair
- [ ] Observe recovery
- [ ] Release overrides
- [ ] Close out
- [ ] Receive evidence-based grade and debrief

---

## 22. Safety, Ethics, and Product Boundaries

- [ ] Synthetic facilities, identities, network values, and credentials only.
- [ ] No real customer data, screenshots, exports, addresses, or access paths.
- [ ] No active testing against real BAS or hospital networks.
- [ ] No claim that this is Tridium Workbench, Tracer Synchrony, Metasys, or an
  official certification product.
- [ ] No proprietary vendor artwork, templates, identities, or exam questions.
- [ ] Scenario questions are original and concept-based.
- [ ] The lab supplements authorized training and supervised field work.
- [ ] Mechanical/electrical safety prompts defer to employer/site procedure.
- [ ] Life-safety sequences are never treated as approved engineering designs.

---

## 23. Recommended Delivery Phases

### Phase 0: Preserve and baseline

- [ ] Inventory current features and tests.
- [ ] Separate generated output from canonical inputs.
- [ ] Document browser/BACnet simulator ownership modes.
- [ ] Partial: Stabilize current Px/Wire Sheet editors and malformed-input recovery.
  Malformed shapes, bad config, and unknown references return 4xx without
  changing state (verified 2026-09-23). Editing or deleting existing items is
  not built.
- [ ] Partial: Establish backup/rollback before new training persistence.
  Per-item rollback works for Wire Sheets and Px pages only.

### Phase 1: Scenario kernel

- [ ] Scenario schema
- [ ] Session state machine
- [ ] Action/evidence log
- [ ] Role-filtered truth boundary
- [ ] Pause/resume/reset/replay
- [ ] Headless deterministic tests

### Phase 2: Field action framework

- [ ] Field locations and instruments
- [ ] Visual, temperature, pressure, flow, signal, and travel observations
- [ ] Safety prerequisites
- [ ] Time/cost model
- [ ] Evidence notebook

### Phase 3: Repair and recovery

- [ ] Repair actions mutate causes
- [ ] Isolation/LOTO workflow
- [ ] Recovery timers/physics
- [ ] Override-release gate
- [ ] Structured closeout and grading

### Phase 4: First flagship HVAC cases

- [ ] Pump-room leak
- [ ] Condenser obstruction
- [ ] Excess airflow/high humidity
- [ ] Lying valve feedback
- [ ] End-to-end UI and acceptance scripts

### Phase 5: DDC/BACnet cases

- [ ] Sensor/input/output failures
- [ ] Sequence/PID cases
- [ ] Priority conflicts
- [ ] Duplicate identities/addressing/routing
- [ ] Binding and communications cases

### Phase 6: N4 performance-task framework

- [ ] Isolated task workspaces. Now more pressing: with one writer per point,
  the shipped `RTU1_OCCUPANCY_SETBACK` sheet owns `RTU1_SAT_SP` and
  `VAV301_TEMP_SP`, so a learner building §13's SAT-setpoint task on the
  shared station gets a writer-conflict error unless the task starts from its
  own workspace or snapshot.
- [ ] Partial: Stable Schedule/Wire Sheet/Px CRUD (see §18 status)
- [ ] Artifact grader
- [ ] Backup-before-change checks
- [ ] Task timer, hints, results, reset

### Phase 7: N4 Level 1 curriculum

- [ ] Navigation/component model
- [ ] Drivers/devices/points
- [ ] Schedules
- [ ] Wire Sheets
- [ ] Px
- [ ] Alarms/histories
- [ ] Security
- [ ] Platform backup/restore concepts
- [ ] Scenario question bank generated from original task material

### Phase 8: Scale and instructor tooling

- [ ] Composable cause/context/distractor engine
- [ ] Scenario author validator
- [ ] Instructor dashboard
- [ ] Progress history and competency map
- [ ] Difficulty adaptation
- [ ] Level 2/3 extension points

---

## 24. Definition of “It Works”

The vision is achieved when a learner can complete both of these without being
told the answer.

### Technician acceptance story

> I start a morning shift and see a low-flow chiller lockout. The BAS says the
> pump is running, but flow is zero. I compare points and trends, verify the
> gauges, enter the virtual mechanical room, recognize the standing-water
> hazard, isolate the equipment, locate the leaking valve, repair it, refill
> and purge the loop, restore pumping, verify DP/GPM, reset the chiller, watch
> temperatures recover, release every override, and close the ticket with
> evidence. The simulator grades my safety, reasoning, repair, and proof.

### Niagara acceptance story

> I receive a work order and a clean task workspace. I take a backup, create a
> schedule and exception, build and link the control logic, bind a Px graphic,
> configure alarm/history behavior, apply least privilege, induce the test
> condition, and prove the station responds. The grader inspects the saved
> artifacts and runtime behavior. It tells me exactly which requirements pass
> or fail without caring which sequence of clicks I used.

If those experiences are real, repeatable, safe, evidence-driven, and grounded
in the same synthetic building state, BAS-SIM has become the intended training
platform.

---

## 25. Next Decisions

- [ ] Confirm this document as the north-star vision.
- [ ] Decide whether the existing Synchrony-style UI becomes the primary
  investigation shell or whether training receives its own route/application.
- [ ] Select the first flagship scenario (recommended: pump-room leak).
- [ ] Write the scenario-kernel design before adding more UI screens.
- [ ] Obtain the authorized N4 TCP Level 1 course agenda/provider syllabus and
  map every lab task to a published domain without copying exam content.
- [ ] Decide how real Workbench/JACE access will complement, rather than be
  falsely replaced by, this synthetic lab.
