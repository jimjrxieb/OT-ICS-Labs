# Niagara by Tridium — Study Guide

A vocabulary and mental-model reference for learning Niagara N4, written
against what this lab actually models. Hands-on practice starts at
`http://localhost:8001/niagara` (see `frontend/static/niagara.html`). The
current page includes a portfolio Nav tree, ORDs, Property Sheets, an Alarm
Console, histories, schedules, live Wire Sheet evaluation, station/platform
views, real backup creation, and a bound Px graphic.

There is an important boundary: most of those views are currently
**observation exercises**, not engineering editors. The lab can resolve a
schedule, evaluate an existing Wire Sheet, render an existing Px page, and
take a platform-style backup. It cannot yet create or edit Px widgets, place
Wire Sheet blocks, draw links, edit schedules, discover/import field points,
or restore a backup through the browser. Do not mistake seeing a concept for
having practiced building it.

This is **not** a substitute for real Niagara Workbench time. It's a
map so the real thing's vocabulary isn't cold the first time you open
it. See `docs/architecture.md` for how this lab's synthetic buildings
map to the Purdue model; this file is the Niagara-specific layer on
top of that.

### Certification target (current as of 2026-09-22)

Tridium's current technical path is named by level, not by separate
"Technician" and "Programmer/Systems" credentials:

1. **Niagara 4 TCP Level 1 Foundations** — the first target for a new
   technician. Tridium describes it as a 40-hour beginner credential in
   which students create a simulated building-automation solution.
2. **TCP Level 2 Intermediate** — requires Level 1 and deepens Workbench and
   system-integration practice.
3. **TCP Level 3 Advanced** — advanced station, enterprise, query,
   certificate, and provisioning work.
4. **Niagara 4 Developer Certification** — a separate Java path for people
   writing custom Niagara modules and drivers. It is not the normal next step
   for a controls technician who wants stronger station-engineering skills.

The public catalog and agendas establish that the courses contain substantial
hands-on engineering work. They do not clearly document the exact final
assessment format, so this guide does not assume the test is exclusively
multiple-choice or exclusively practical. Prepare both ways: build and repair
artifacts, then explain the same decisions in scenario questions.

Official references:

- [Tridium University certification catalog](https://www.tridiumuniversity.com/student/catalog/list?category_ids=43822-amer-certification-courses)
- [Current TCP course descriptions and agendas](https://www.tridiumuniversity.com/student/page/3342702-tridium-amer-ilt-agendas)

---

## 1. Terms and Definitions

Grouped the way you'll actually encounter them, not alphabetically.

### The software itself

| Term | Definition |
| --- | --- |
| **Niagara Framework** | Tridium's platform for building supervisory/BAS software. Vendors (JCI Metasys via N-AX, Trane Tracer, Honeywell, etc.) build products on top of it or interoperate with it. |
| **Workbench** | The engineering/configuration desktop app. You use it to build, wire, and commission stations — it is a *tool*, not itself part of the running system. Closes when you close it; the station keeps running. |
| **Station** | A running Niagara application/process — a live database of Components plus the logic wiring them together. Every JACE and every Supervisor runs exactly one station. |
| **Platform** | The host-level layer *underneath* a station: OS, TCP/IP stack, installed modules, licenses, certificates. You administer the platform (install software, back up, reboot, apply a license) separately from editing the station's logic. |
| **Platform Daemon** | The background service on a host that Workbench actually talks to for platform-level operations (install, backup, restart) — exists whether or not a station is currently running. |
| **Fox** | Niagara's native station-to-station and Workbench-to-station protocol. When you "connect to a station" in Workbench, you're opening a Fox connection. |
| **BOG file** | The station's saved database file (`config.bog`) — the serialized component tree. |
| **Distribution (.dist) file** | A full backup of a station (BOG + files + platform info) bundled for restore or redeploy — the thing you actually take before touching a live station. |

### Structure and addressing

| Term | Definition |
| --- | --- |
| **Component** | The base building block of everything in a station — a device, a point, a schedule, a logic block, a graphic. Components live in a tree. |
| **Slot** | A named property, action, or topic on a Component — e.g. an `out` slot holding the current value. What you see listed on a Property Sheet. |
| **Property Sheet** | The default view of a Component: its slots and their current values, laid out as a form/table. The single most-used view in Workbench. |
| **Facets** | Metadata attached to a slot describing how to interpret/display it — units, precision, min/max, enum range. Same idea as this lab's `normal_min`/`normal_max`/`units` on a point. |
| **Nav Container / Nav Tree** | The hierarchical browse tree on the left of Workbench — Stations → Config → Drivers → Networks → Devices → Points, plus Schedules, Alarm, History services alongside them. |
| **ORD** (Object Resolution Descriptor) | A URI-style address that locates *anything* in Niagara — a station slot, a file, a history record, a history query. Looks like `station:\|slot:/Drivers/BacnetNetwork/AHU_1/SAT`. This lab's `niagara.html` renders these live in the ORD bar and per-row. |
| **BQL** (Baja Query Language) | A SQL-like query language for pulling sets of components/records out of a station or history database by ORD pattern. |

### Field integration

| Term | Definition |
| --- | --- |
| **Driver** | A module that speaks a specific field protocol — `BacnetNetwork`, `ModbusAsyncNetwork`, `LonNetwork`, `NiagaraNetwork` (Fox-to-Fox, for station-to-station). Lives under `Config/Drivers` in the Nav tree. |
| **Network** | An instance of a driver, representing one physical bus/segment — e.g. one `BacnetNetwork` per IP subnet or MS/TP trunk. |
| **Device** | A discovered field controller under a Network — a JACE, a VAV controller, a chiller controller. |
| **Point / Proxy Extension** | A Component that binds a *field* value (a BACnet object, a Modbus register) into the station's slot model. The proxy extension is the glue — read/write on the proxy slot round-trips to the real field device. This lab's `points.json` entries are the un-proxied version of the same idea. |
| **JACE** | Java Application Control Engine — Tridium's field-level hardware running a station close to the equipment (Level 2 in the Purdue model). Supervises drivers/devices directly. |
| **Supervisor** | A station (often on a server, not field hardware) that sits above one or more JACEs on a `NiagaraNetwork`, aggregating them into one portfolio view. This lab's `N4-SUP-01` in `niagara.html` plays this role. |

### Logic and behavior

| Term | Definition |
| --- | --- |
| **Wire Sheet** | The visual programming canvas: drag function blocks (And, Or, Add, Compare, Select, Ramp...) onto a sheet and draw **links** between their slots. This is how control sequences and interlocks actually get built in Niagara — not text code. |
| **Link** | A live connection from one Component's output slot to another's input slot, drawn on the Wire Sheet. Values flow through links every execution cycle. |
| **Program Object** | A block that runs actual scripted logic (historically NiagaraAX's Program Object with embedded BogScript/Java-ish logic; N4 leans more on composite logic + Wire Sheet, but Program Objects still exist for cases links can't express). Used sparingly — Wire Sheet composition is preferred where it's expressive enough. |
| **Composite/Logic block** | Reusable groups of wired-together blocks saved as a single reusable Component — Niagara's version of "a function." |
| **Schedule** | A Component that outputs a value on a time-of-day/day-of-week pattern — `BooleanSchedule` (occupied/unoccupied) or `NumericSchedule`/`EnumSchedule` (e.g. a setpoint that resets by time of day). Has a default weekly pattern plus **exceptions** for specific dates. |
| **Calendar** | A reusable set of dates (holidays, special events) that a Schedule's exceptions reference, so one holiday list can drive many schedules. |
| **Effective value / `out`** | What a Schedule (or any Component) is *actually* outputting right now, after weekly pattern + any active exception is resolved — this is what downstream links see. |
| **Tuning Policy** | Governs how aggressively a proxy point writes changes back to the field device (min write interval, deadband) — prevents flooding a slow field bus with every tiny simulated change. |

### Alarms and history

| Term | Definition |
| --- | --- |
| **AlarmService** | The station service that owns alarm generation, routing, and state (normal/alarm/acked/unacked). |
| **Alarm Class** | A named routing/priority bucket (e.g. `Critical`, `HighPriority`) that alarms are tagged with — determines escalation, sound, recipient routing. This lab's `priority` field (`critical`/`high`/`medium`) is the same idea in miniature. |
| **Alarm Console** | The live table of current alarm records — this lab's Alarm Console tab is a direct namesake. |
| **Alarm Recipient / Escalation** | A configured destination (email, pager, another alarm console) an Alarm Class routes to, optionally after a delay if not acknowledged. |
| **HistoryService** | The station service that owns time-series data collection and storage. |
| **History Extension** | Attached to a point to make it collect history — configured with a **collection policy**: interval (e.g. every 5 min) or COV (change-of-value, only log when the value moves more than a deadband). This lab's History Extension tab/trend data mirrors interval collection. |

### Presentation

| Term | Definition |
| --- | --- |
| **Px page / Px graphic** | A custom graphic page — floor plan, AHU schematic, dashboard — built by dragging bound widgets onto a canvas in Workbench's Px editor. What an operator actually looks at day to day, as opposed to the raw Nav tree. |
| **Bajaux widget** | The UI component framework Px graphics and Workbench views are built from. |

### Security and administration

| Term | Definition |
| --- | --- |
| **User** | An account on a station, with a role and (optionally) restricted categories. |
| **Role** | A named bundle of permissions assigned to users — what they're allowed to do. |
| **Category** | A tag applied to Components (by area, system, or sensitivity) used to scope what a Role can see/touch, independent of where the Component sits in the Nav tree. |
| **Permission** | A specific operate/admin/config right (read, write, invoke action, admin) — granted per Category, per Role. |
| **Provisioning** | Pushing software/config updates out to a fleet of JACEs from a Supervisor, station by station. |
| **Templates** | A saved, parameterized Component subtree (e.g. "one VAV box") that can be instantiated repeatedly — build the logic once, apply it to 40 VAVs. |

---

## 2. How It Fits Together (Flow)

```text
Field device (BACnet/Modbus object on a real controller)
  -> Driver / Network (BacnetNetwork, ModbusAsyncNetwork ...)
       discovers the device, learns its objects
  -> Point / Proxy Extension
       binds one field object to one Component slot ("out")
  -> Wire Sheet
       Links carry that value into function blocks (And/Compare/Select),
       Schedule outputs, and Program Objects -- this is where control
       sequences and interlocks are actually built
  -> Component tree (Config)
       the resulting live values, alarms, and setpoints live here,
       organized under the Nav Container
  -> AlarmService / HistoryService
       extensions on points/components generate alarm records and
       history records as values change or cross limits
  -> Px Graphics / Nav Tree
       operators view and command through bound graphics or the raw
       Property Sheet -- this is the only layer most day-2 users see
  -> Station (JACE)
       the whole tree above lives inside one running station process
  -> Fox  ->  NiagaraNetwork  ->  Supervisor station
       one or more JACE stations connect up to a Supervisor, which
       federates them into one portfolio Nav tree (this lab's N4-SUP-01)
  -> Workbench (engineering tool)
       connects over Fox to any station (JACE or Supervisor) to build,
       wire, and commission it -- not part of the running system itself
  -> Platform / Platform Daemon
       host-level layer under each station: install, license, backup,
       certificates, restart -- administered separately from station logic
```

Two directions worth keeping straight:

- **Bottom-up (data):** field value → proxy point → Wire Sheet logic →
  alarm/history extensions → graphics. This is what's actually running,
  continuously, whether or not anyone's looking at Workbench.
- **Top-down (engineering):** Workbench connects via Fox to a station and
  edits the tree that the bottom-up flow runs through. Nothing runs
  *inside* Workbench — closing it doesn't stop anything.

---

## 3. Niagara ↔ CKA/Kubernetes — Concept Bridge

You already have the Kubernetes mental model from CKA. Niagara maps onto
it more cleanly than you'd expect, because both are "declare a desired
state, wire independent components together, let a control loop keep it
true" systems. Where the analogy bends, it's called out.

| Niagara concept | Closest K8s/CKA concept | Why it maps |
| --- | --- | --- |
| **Supervisor station** | Control plane (API server) | Single pane of glass; subordinate stations report/connect up to it; nothing below it needs the Supervisor up to keep running. |
| **JACE (station)** | Node (kubelet + container runtime) | Runs its own local workload autonomously; keeps controlling equipment even if it loses its link to the Supervisor, same as a kubelet keeps running Pods if it loses the API server. |
| **Fox / NiagaraNetwork** | kubelet↔API server connection (watch/heartbeat) | The channel a subordinate uses to report status up and receive config down. |
| **Component** | API object (Pod, Deployment, ConfigMap...) | The addressable unit everything else operates on. |
| **Slot** | A field in an object's `spec`/`status` | Individual named value on a Component/object. |
| **Property Sheet** | `kubectl get -o yaml` / `kubectl describe` | The read/edit view of one object's current fields. |
| **ORD** (`station:\|slot:/Drivers/...`) | A K8s API path (`/apis/apps/v1/namespaces/ns/deployments/name`) | Both are URI-style, unambiguous addresses for one resource. |
| **Driver / Network** (BacnetNetwork...) | CNI plugin / cloud provider integration | The pluggable layer that lets the platform actually reach real infrastructure/devices it doesn't natively speak. |
| **Point / Proxy Extension** | PersistentVolumeClaim ↔ PersistentVolume binding | An abstract, in-platform object bound to a real external resource it reads/writes through. |
| **Wire Sheet + Links** | An Operator's reconcile loop, drawn visually | Declarative wiring of inputs → logic → outputs that keeps running continuously; a Wire Sheet *is* a reconcile loop, just built by dragging blocks instead of writing Go. |
| **Schedule** (Weekly + exceptions) | CronJob (+ a manual Job as an "exception") | Recurring time-based state change, with the exception/calendar mechanism playing the role of a one-off override. |
| **AlarmService / Alarm Class** | Events + Alertmanager routing tree | Alarm Class routing/escalation rules are functionally Alertmanager's routing config; the Alarm Console is the Events/Alertmanager UI. |
| **HistoryService / History Extension** | Prometheus + metrics-server scrape config | Enabling a History Extension on a point is like adding a scrape target — interval vs. COV collection is like scrape interval vs. only-on-change. |
| **Security Category / Permission / Role / User** | Namespace-scoped RBAC (Role, RoleBinding, ServiceAccount) | Near-exact match: Category scopes *what* (like a label selector/namespace), Permission is the verb, Role bundles verbs, User is the subject bound to a Role. |
| **Station backup (.dist file)** | `etcd` snapshot / Velero backup | Point-in-time capture of the whole declared-state tree for disaster recovery. |
| **Platform / Platform Daemon** | Node-level admin (systemd, containerd, kubeadm) | Host-level concerns (install, certs, restart) kept deliberately separate from workload-level (station/Pod) concerns. |
| **Templates** | Helm chart / Kustomize base | Reusable, parameterized object definition, instantiated many times (one VAV template → 40 VAV boxes; one chart → many releases). |
| **Workbench** | `kubectl` / the K8s Dashboard | The tool you use to observe and edit the system; not itself part of the running system — quitting it changes nothing running. |

**Where it doesn't map:** Niagara has no real equivalent of K8s
*scheduling* (bin-packing workloads onto nodes) — a JACE's "workload" is
fixed by what equipment it's wired to, not dynamically placed. And K8s
has no real equivalent of Niagara **licensing/certificates gating
features per host** — closest is a vendor's feature-gate flags, but it's
not a native concept.

The analogy is a memory aid, not an implementation claim. In particular, a
Supervisor is not a consensus control plane, a Wire Sheet is not an Operator
with Kubernetes reconciliation semantics, and a Niagara Category is not a
namespace. When troubleshooting, use Niagara's actual object, permission, and
runtime model.

---

## 4. What This Lab Teaches Today

| Area | Current practice | Important limit |
| --- | --- | --- |
| Nav and ORDs | Browse Supervisor → JACE → equipment → points and read the current ORD. | Synthetic component tree, not a real Fox session. |
| Property Sheets | Read live point values, metadata, writable state, and override state. | Not every Niagara slot/facet/status concept is modeled. |
| BACnet integration | Explore synthetic BACnet networks and Building 822's routed topology. | The Niagara page is not doing Workbench discovery/import. |
| Commands | Command and release eligible synthetic points with role attribution. | The role is self-declared; this is not production authentication. |
| Schedules | Resolve a weekly pattern, date exception, effective value, and linked-point baseline. | Browser editing and Building 822 occupancy physics are not implemented. |
| Wire Sheets | Watch existing blocks and links evaluate against live schedule/point context. | Read-only: no block placement, configuration, linking, or persistence yet. |
| Px | View one bound RTU schematic whose widgets resolve live point values. | Read-only: no widget placement, binding, or layout editing yet. |
| Alarms | Read current alarms and practice alarm-console navigation. | Full Niagara alarm lifecycle, classes, routing, and durable acknowledgement are not modeled. |
| Histories | Select points and inspect generated trend history. | Collection-extension editing, COV policies, rollups, and history maintenance are not modeled. |
| Platform | Inspect synthetic stations and take a real snapshot of selected lab configuration. | Host/module/license actions are representations; restore is not exposed in the UI. |
| Troubleshooting | Diagnose scripted hospital/office faults and inspect causal Building 822 behavior. | This complements Workbench practice; it is not part of Niagara itself. |

The data files behind these exercises are intentionally plain and inspectable:
`data/input/schedules.json`, `data/input/wiresheets.json`,
`data/input/px_pages.json`, and `data/input/stations.json`. Reading them is
useful for understanding the component relationships, but editing JSON by hand
does not count as completing a Workbench-style construction exercise.

---

## 5. Level 1 Mastery Loop

Use the same loop for every Niagara topic:

1. **Identify** the component in the Nav tree and state which station owns it.
2. **Inspect** its Property Sheet, facets, status, ORD, inputs, and outputs.
3. **Build or change** the smallest relevant artifact: a binding, schedule,
   block/link, alarm extension, history extension, Px widget, or permission.
4. **Prove runtime behavior** using live values—not just the saved
   configuration.
5. **Break one dependency** and diagnose the result from the downstream
   symptom.
6. **Back up, document, and restore or roll back** the change.
7. **Explain the scenario without the UI**: what owns the component, what
   resolves its value, what should happen next, and what evidence proves it.

That last step turns hands-on familiarity into certification readiness. If you
can perform a task but cannot explain ownership, resolution order, failure
effects, and recovery, the understanding is not yet durable.

### Initial practical outcomes

Before moving from Level 1 preparation to Level 2, be able to do these without
a recipe:

- Navigate Platform versus Station contexts and explain why they are separate.
- Create or restore a station backup before an engineering change.
- Discover a device, import a proxy point, set facets, and verify live status.
- Build occupied/unoccupied scheduling with a dated exception.
- Build and troubleshoot a small Wire Sheet with constants, logic, selection,
  and a controlled output.
- Add an alarm and a history extension, then prove each one generates the
  expected record.
- Build a Px equipment graphic, bind widgets, and verify that commands and
  status are not confused.
- Create a least-privilege user/role/category arrangement and test an allowed
  and a denied action.
- Diagnose a stale point by walking field device → driver/network → proxy →
  logic → alarm/history → graphic instead of guessing at the screen.

---

## 6. DDC-to-HVAC Troubleshooting Method

An excellent DDC technician troubleshoots the complete signal-and-energy
chain, not just the workstation:

```text
command -> electrical output -> actuator travel -> fluid/air movement
        -> heat transfer -> sensor response -> BAS display
```

Each arrow can fail independently. A pump status does not prove flow. Valve
feedback does not prove stem travel. Stem travel does not prove water flow.
Water flow does not prove useful heat transfer. A plausible BAS value does not
prove the sensor is honest.

For every call:

1. Define the complaint: what, where, when, and under what load.
2. Read the sequence and state what should happen.
3. Separate command from proof: status, current, travel, pressure, flow, and
   temperature are different evidence.
4. Follow electrical power, air, water, refrigerant, and heat until expected
   transfer stops.
5. Choose one observation that separates competing causes.
6. Repair the cause, release overrides, allow stabilization, and prove the
   original symptom is resolved.

Standing water around pumps, starters, disconnects, or energized equipment is
an electrical and mechanical hazard. Site emergency, isolation, LOTO, and
escalation procedures govern before testing or approaching the equipment.

## 7. Scenario Drills

### Chiller off on low flow

**Evidence:** chiller is off on low-flow safety, GPM is zero, pump status says
running, and the pump room is flooded.

- The BAS proves command/status and a flow-safety response; it does not prove
  the piping is intact or that the pump delivered flow.
- Cause families include a major leak or failed valve, broken coupling or
  impeller, closed valve, loss of prime/air binding, failed flow meter, or
  false run proof.
- The flooded room controls the response: follow emergency isolation and LOTO
  procedures first. Then verify the leak, pump rotation, valve position,
  differential pressure, and independent flow.
- Actual field finding: the valve at the pump had rusted through and leaked.
  Do not turn that finding into the false rule “zero GPM means rusty valve.”

### Trash bag blocking an outdoor coil

A blocked condenser coil loses heat-rejection airflow. Condensing temperature
and pressure rise, compressor work rises, and available cooling capacity
falls. Expected BAS evidence includes drifting supply temperature, saturated
cooling demand, worsening condenser approach, and possibly high-pressure or
condenser diagnostics. Prove the airflow path and fan operation, remove the
obstruction safely, and trend recovery. Retuning the control loop cannot
restore missing heat rejection.

### Excess airflow and poor dehumidification

At excessive airflow, coil contact time falls and a finite coil must process
more air mass. Leaving air may remain above the effective dew point, reducing
latent removal even while space dry-bulb temperature looks acceptable.
Compare CFM/static pressure, fan speed, entering/leaving dry bulb and RH,
dew point, CHW temperature and flow, valve position, and condensate.

Do not assume airflow is the only cause. Warm CHW, poor valve authority, a
dirty or air-bound coil, outdoor-air excess, infiltration, reheat sequencing,
and sensor bias can produce similar symptoms.

### Command and feedback look healthy; process does not respond

If a valve is commanded to 100% and reports 96% feedback while supply air
stays warm, check the actuator output signal, physically verify stem travel,
measure entering/leaving water and air temperatures, and verify differential
pressure or flow. Command, feedback, physical travel, fluid flow, and heat
transfer are five separate facts.

### Niagara point is correct in the controller but stale on Px

Walk device health → Network/driver → proxy status/tuning policy → station
logic/link → Px binding ORD → Supervisor/JACE connection. If the Property
Sheet is current while Px is stale, investigate above the proxy. If both are
stale, investigate the proxy, network, device, or field source.

### Oscillating zone

Before changing PID gains, rule out:

- mechanical causes: oversized valve, poor valve authority, sticking
  actuator, unstable plant pressure/temperature, excessive capacity;
- sensing/timing causes: poor sensor placement, noise or bias, sampling too
  fast for the thermal mass, transport delay, missing actuator slew;
- logic causes: wrong action direction, deadband error, integral windup,
  competing loops, schedule/override conflict, or bad gains.

### Closeout

An alarm clearing immediately after repair is not enough. Prove the original
complaint under a meaningful operating condition, allow thermal/hydronic
stabilization, trend command/feedback/process/setpoint and upstream conditions,
release temporary overrides, confirm normal control ownership, and document
corrective action, verification, prevention, and remaining risk.
