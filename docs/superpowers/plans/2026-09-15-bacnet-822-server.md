# Building 822 BACnet/IP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Put Building 822 on the wire as a routed BACnet internetwork — two Tracer-SC-style routers and 62 field controllers — so a real supervisor can discover it, read points, command a valve at priority 8, and watch the physics respond.

**Architecture:** One process, `open-source-stack/bacnet822.py`, builds 64 bacpypes3 `Application` instances: two routers (each an IPv4 network port plus two virtual MS/TP network ports) and 62 devices bound to virtual networks. Commandable objects carry real priority arrays; the control loop writes at priority 16 by plain assignment and an operator write at 8 overrides it. Each tick, the resolved `presentValue` of every commandable object is fed to `model822.step_822()` as its overrides mapping, and the returned sensor values are pushed back into the read-only objects. The building answering a command is the acceptance criterion, not a side effect.

**Tech Stack:** Python 3.11+, `bacpypes3==0.0.102` (already pinned in `open-source-stack/requirements.txt` — no new dependencies). Standard library for everything else.

**Spec:** `docs/superpowers/specs/2026-09-15-bacnet-822-server-design.md` — read it before Task 1. The plan argues from the spec; where they disagree, the spec wins and you should stop and flag it.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Never run git.** No `add`, `commit`, `push`, `status`, `stash`, `checkout`. J owns git. Tasks end in a checkpoint, never a commit.
- **No new dependencies.** `bacpypes3==0.0.102` and the standard library only. Do not upgrade bacpypes3 — behavior below was verified against exactly this version.
- **No hardcoded absolute paths.** No `/home/jimmie` anywhere. Resolve paths from `Path(__file__).resolve().parents[N]`, matching `simulator/model822.py`.
- **Synthetic data only**, per `safety/data-boundary.md`. No real facility, vendor, network, or credential data.
- **Vendor identifier is 999.** Do not claim Trane's registered vendor identity.
- **Do not modify** `open-source-stack/bacnet_device.py`, `simulator/model822.py`, `simulator/psychro.py`, `frontend/bas_api.py`, or any file under `data/input/`. The only permitted modifications in this plan are to `simulator/bas_sim.py` (lock guard, Task 5) and `scripts/run-smoke-test.sh` (Task 8).
- **Port 47809**, not 47808. The hospital device on 47808 must keep working.
- **The chiller is not a BACnet device.** No object may be created for any `RTAC822_*` point. This is asserted by the self-test in Task 2.
- **Hospital and office output must not change.** Task 5 verifies this explicitly.

## Verified API Behavior

The following was confirmed by direct probe against the installed bacpypes3 0.0.102 during planning. Treat it as established fact, not guesswork.

- `bacpypes3.vlan.VirtualNetwork(network_name)` and `VirtualNode(addr, network_name)` exist. Networks are registered globally by name in `VirtualNetwork._networks`; creating two with the same name raises `ValueError`.
- `Application.from_object_list([...])` builds an application from a list of objects. A `NetworkPortObject` with `networkType=NetworkType.virtual` and `networkInterfaceName=<virtual network name>` binds that application to a virtual network; `networkNumber` > 0 makes the binding a routed network rather than the local one.
- `bacnetIPMode` supports `normal`, `foreign`, and `bbmd`; in bbmd mode the object's `bbmdBroadcastDistributionTable` entries are added as peers. BBMD is native — do not implement it by hand.
- Commandable objects (`AnalogOutputObject`, `AnalogValueObject`, `BinaryOutputObject`, `MultiStateValueObject`) mix in `bacpypes3.local.cmd.Commandable`, which supplies `priorityArray`, `relinquishDefault`, and `currentCommandPriority`.
- **Plain attribute assignment writes priority 16.** `obj.presentValue = 78.2` sets `priorityArray[15]`. This is exactly the control-loop-writes-at-16 behavior the spec requires. Do not write the array by hand.
- **Values must be typed.** `await obj.write_property("presentValue", Real(45.0), None, 8)` works; passing a raw Python `float` raises `TypeError: <class 'float'>` inside `PriorityValue.__init__`.
- **Relinquish requires an explicit `Null`.** `await obj.write_property("presentValue", Null(()), None, 8)` works. Passing Python `None` produces a `PriorityValue` with no branch set, and `recalculating()` then crashes with `TypeError: attribute name must be string, not 'NoneType'`. This is the single sharpest edge in the library — see Task 1 Step 5, which tests it over the wire.
- Objects run an async `_post_init`; construct them inside a running event loop (an `await asyncio.sleep(0)` after construction is enough in tests).
- `currentCommandPriority` is an `OptionalUnsigned`. Read it as: `None if cp is None or cp.null is not None else cp.unsigned`.

Verified transcript of the semantics this design depends on:

```
loop @16                  pv=78.2  ctrl=16
operator @8               pv=45.0  ctrl=8
loop writes 80 @16        pv=45.0  ctrl=8     <- 8 still wins
relinquish @8 (Null)      pv=80.0  ctrl=16    <- falls back to the loop
relinquish @16 too        pv=0.0   ctrl=None  <- relinquishDefault
```

## File Structure

| File | Responsibility |
|------|----------------|
| `open-source-stack/bacnet822.py` | Everything the server is: tree building, object factory, application assembly, step loop, audit, CLI. One file, matching the repo's existing single-file module convention (`model822.py`, `bacnet_device.py`). |
| `scripts/bacnet822-client.py` | Test harness only. Who-Is, read, write at priority, relinquish. Used by the acceptance test and the smoke test. Not an operator interface. |
| `docs/bacnet-822.md` | How to connect YABE through NAT via foreign-device registration, the mirrored-networking switch, the device/instance map, and a priority-array reference. |
| `simulator/bas_sim.py` | **Modified, Task 5 only:** lock guard so it skips 822 while the server owns it. |
| `scripts/run-smoke-test.sh` | **Modified, Task 8 only:** adds the acceptance sequence. |

`bacnet822.py` is expected to land around 600-700 lines, comparable to `model822.py` at 610. If it passes ~900, stop and flag it rather than continuing — the natural split is the object factory into `open-source-stack/bacnet822_objects.py`.

## Task Sequence

1. **Routing spike — go/no-go.** Throwaway. Proves bacpypes3 can route to virtual networks and that relinquish survives the wire.
2. **Device tree builder.** Offline, no sockets. The inventory becomes a validated tree.
3. **Object factory.** Points become BACnet objects with correct types, units, and priority arrays.
4. **Server assembly.** Tree plus objects become 64 running applications behind a BBMD.
5. **Step loop and lock guard.** The building starts answering.
6. **Audit logging.** Every write is recorded.
7. **Test client and acceptance test.** The command-to-physical-response chain is asserted.
8. **Smoke test and documentation.** It survives regression and you can connect to it.

Tasks 2 and 3 have no dependency on each other and may be done in either order. Everything else is sequential.

---

### Task 1: Routing reference and scale check

The API risk this task was originally written to retire has already been retired during planning: the routing pattern below was run end to end against bacpypes3 0.0.102 and works. What remains unproven is **scale** — the same pattern with 2 routers, 4 virtual networks, and 62 device applications in one process. That is this task's go/no-go.

**Files:**
- Create: `/tmp/.../scratchpad/spike_routing.py` (throwaway — your scratchpad directory, NOT the repo)
- Create: `/tmp/.../scratchpad/spike_scale.py` (throwaway)

**Interfaces:**
- Consumes: nothing.
- Produces: no code the repo keeps. Produces **findings** that Tasks 4 and 7 depend on: confirmed startup time and memory for 64 applications, and the confirmed constructor forms recorded below.

- [ ] **Step 1: Reproduce the reference topology**

Write `spike_routing.py` in your scratchpad with exactly this content. It is known-good — if it fails, the environment differs from the one this plan was written against and you should stop and report that rather than debugging onward.

```python
import asyncio
from bacpypes3.vlan import VirtualNetwork
from bacpypes3.app import Application
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.networkport import NetworkPortObject
from bacpypes3.local.analog import AnalogOutputObject
from bacpypes3.primitivedata import Real, Null, ObjectIdentifier
from bacpypes3.pdu import Address

IP = "172.28.94.51/20"          # replace with this host's eth0 CIDR
ROUTER_IP = "172.28.94.51:47809"
IPNET = 822                      # the BACnet network number of the IP network


def vport(oid, name, mac, netname, netnum):
    """A virtual (MS/TP-style) network port."""
    return NetworkPortObject(
        objectIdentifier=("network-port", oid), objectName=name,
        networkType="virtual", macAddress=bytes([mac]),
        networkInterfaceName=netname, networkNumber=netnum,
        networkNumberQuality="configured", protocolLevel="bacnet-application",
        statusFlags=[0, 0, 0, 0], reliability="no-fault-detected",
        outOfService=False, changesPending=False, linkSpeed=0.0)


async def main():
    VirtualNetwork("TRUNK-A")
    router = Application.from_object_list([
        DeviceObject(objectIdentifier=("device", 822001), objectName="SC-822-01",
                     vendorIdentifier=999, objectList=[]),
        NetworkPortObject(f"{IP}:47809", objectIdentifier=("network-port", 1),
                          objectName="ip", networkNumber=IPNET,
                          networkNumberQuality="configured"),
        vport(2, "trunk-a", 1, "TRUNK-A", 1)])

    valve = AnalogOutputObject(
        objectIdentifier=("analog-output", 1), objectName="MAU01_CHW_VLV_CMD",
        presentValue=0.0, units="percent", relinquishDefault=0.0)
    uc400 = Application.from_object_list([
        DeviceObject(objectIdentifier=("device", 822011), objectName="UC400-MAU-01",
                     vendorIdentifier=999, objectList=[]),
        vport(1, "mstp", 2, "TRUNK-A", 1), valve])

    client = Application.from_object_list([
        DeviceObject(objectIdentifier=("device", 999999), objectName="client",
                     vendorIdentifier=999, objectList=[]),
        NetworkPortObject(f"{IP}:47810", objectIdentifier=("network-port", 1),
                          objectName="ip")])
    await asyncio.sleep(0.4)

    # a same-host client cannot discover by broadcast (see Step 3) -- seed the route
    await client.nsap.update_router_references(None, Address(ROUTER_IP), [1])

    valve.presentValue = 78.2                      # control loop writes priority 16
    oid, dev = ObjectIdentifier("analog-output,1"), Address("1:2")

    print("READ pv              =", await client.read_property(dev, oid, "presentValue"))
    await client.write_property(dev, oid, "presentValue", Real(45.0), None, 8)
    print("WRITE @8  -> pv      =", valve.presentValue)
    valve.presentValue = 80.0
    print("loop 80 @16 -> pv    =", valve.presentValue, "(8 wins)")
    await client.write_property(dev, oid, "presentValue", Null(()), None, 8)
    print("RELINQUISH @8 -> pv  =", valve.presentValue, "(loop recovers)")
    print("read back over wire  =", await client.read_property(dev, oid, "presentValue"))

    for a in (client, uc400, router):
        a.close()

asyncio.run(main())
```

Replace `IP` and `ROUTER_IP` with this host's actual eth0 CIDR — get it with `ip -4 addr show eth0`. Do not use `127.0.0.1`; loopback does not carry the BACnet broadcast and the spike was validated on eth0.

- [ ] **Step 2: Run it and confirm the expected output**

Run: `python3 <scratchpad>/spike_routing.py`

Expected, exactly:

```
READ pv              = 78.19999694824219
WRITE @8  -> pv      = 45.0
loop 80 @16 -> pv    = 45.0 (8 wins)
RELINQUISH @8 -> pv  = 80.0 (loop recovers)
read back over wire  = 80.0
```

Note `78.19999694824219` — BACnet Real is float32. Every test in this plan compares floats with a tolerance, never `==`.

- [ ] **Step 3: Record these four constraints**

These were learned the hard way during planning. They are requirements for Tasks 4 and 7, not suggestions.

1. **The IPv4 network port must carry an explicit `networkNumber`.** Without it (or with `0`), the adapter has no integer network and the router raises `TypeError: integer network required` while building the return path for a routed response. Reads appear to hang and then abort with `no-response`.
2. **IPv4 ports use the positional address form** — `NetworkPortObject("172.28.94.51/20:47809", ...)`. `address` is a derived read-only property; passing `address=` as a keyword raises `AttributeError: not a sequence element: address`.
3. **Virtual ports use the keyword form** with `macAddress=bytes([mac])` and `networkInterfaceName=<VirtualNetwork name>`. The positional form rejects them with `TypeError: addr: IPv4 or IPv6 address expected`.
4. **A same-host client cannot discover by broadcast.** A BACnet/IP broadcast goes to the subnet broadcast address at the *sender's* port, so a client on 47810 never hears a server on 47809. Same-host clients must seed the route with `nsap.update_router_references(None, Address(router_ip), [nets])` and use unicast. A real supervisor on another host at 47808 discovers normally — this constraint applies only to the test harness in Task 7.

- [ ] **Step 4: Scale check — the actual go/no-go**

Write `spike_scale.py`: the same pattern, but build 2 routers, 4 virtual networks (`MSTP-01-A`, `MSTP-01-B`, `MSTP-02-A`, `MSTP-02-B`), and 62 device applications each holding 6 analog objects. Device instances and MACs do not need to be correct here — this measures cost, not correctness.

Measure and print:

```python
import time, resource
t0 = time.monotonic()
# ... build everything ...
print(f"startup: {time.monotonic() - t0:.2f}s")
print(f"maxrss:  {resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024:.0f} MiB")
```

Then, from a client, read one object on the *last* device created on network 4, to prove routing still resolves at full width.

- [ ] **Step 5: Go/no-go decision**

Run: `python3 <scratchpad>/spike_scale.py`

**GO** if all of: startup under 30 seconds, maxrss under 1 GiB, and the read against the last device on network 4 returns a value.

**NO-GO** if any fails. Do not proceed to Task 2. Report the numbers to J and state which of these the fallback should be:
- startup or memory is the problem → reduce to one `Application` per *trunk* holding all that trunk's objects (4 devices instead of 62), losing per-controller discovery.
- routing breaks at width → fall back to the flat 63-device IP topology rejected as D1 in the spec.

- [ ] **Step 6: Checkpoint**

Delete nothing — leave the scratchpad files for reference. Do not copy them into the repo; Task 4 writes the real thing. Do not commit. Report to J: the Step 2 output, the Step 5 numbers, and the GO/NO-GO. Wait for J's confirmation before Task 2.

---

### Task 2: Device tree builder

Turn the inventory files into a validated in-memory tree. No sockets, no bacpypes3 — pure data, so it is fast to test and impossible to get wrong silently.

**Files:**
- Create: `open-source-stack/bacnet822.py`
- Test: self-test inside the module, run as `python3 open-source-stack/bacnet822.py --self-test` (matching the convention in `simulator/model822.py` and `scripts/gen-822-inventory.py` — this repo does not use pytest)

**Interfaces:**
- Consumes: `data/input/equipment.json`, `data/input/points.json`.
- Produces, relied on by Tasks 3 and 4:
  - `FACILITY = "barracks822"`
  - `IP_NETWORK_NUMBER = 822`
  - `@dataclass DeviceSpec` with fields `instance: int`, `name: str`, `mac: int`, `trunk: str`, `network: int`, `equipment: list[str]`, `points: list[dict]` — one per **controller**, not per equipment row
  - `@dataclass TrunkSpec` with fields `name: str`, `network: int`, `router: str`, `devices: list[DeviceSpec]`
  - `@dataclass RouterSpec` with fields `instance: int`, `name: str`, `trunks: list[TrunkSpec]`, `points: list[dict]` — the supervisory status points (`SC82201_STATUS`, `MSTP01A_STATUS`, …) that belong to the SC itself rather than to any field controller
  - `build_tree() -> list[RouterSpec]`

- [ ] **Step 1: Write the failing self-test first**

Create `open-source-stack/bacnet822.py` containing only the self-test and a stub, so it fails for the right reason.

```python
#!/usr/bin/env python3
"""Building 822 BACnet/IP server.

Presents Building 822 as a routed BACnet internetwork: two Tracer-SC-style
routers, each with two virtual MS/TP trunks, carrying 50 field controllers.

Synthetic lab only. Vendor identifier 999 -- these are not Trane devices.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
OUTPUT_DIR = ROOT / "data" / "output"

FACILITY = "barracks822"
IP_NETWORK_NUMBER = 822
VENDOR_IDENTIFIER = 999

# trunk name -> (virtual network number, owning router instance, router name)
TRUNK_LAYOUT: dict[str, tuple[int, int, str]] = {
    "MSTP-01-A": (1, 822001, "SC-822-01"),
    "MSTP-01-B": (2, 822001, "SC-822-01"),
    "MSTP-02-A": (3, 822002, "SC-822-02"),
    "MSTP-02-B": (4, 822002, "SC-822-02"),
}

# trunk name -> first device instance on that trunk; MAC n gets base + n - 1
INSTANCE_BASE: dict[str, int] = {
    "MSTP-01-A": 822011,
    "MSTP-01-B": 822101,
    "MSTP-02-A": 822021,
    "MSTP-02-B": 822201,
}

MAX_DEVICE_INSTANCE = 4194302


def build_tree() -> list["RouterSpec"]:
    raise NotImplementedError


def _self_test() -> None:
    routers = build_tree()

    assert len(routers) == 2, f"expected 2 routers, got {len(routers)}"
    trunks = [t for r in routers for t in r.trunks]
    assert len(trunks) == 4, f"expected 4 trunks, got {len(trunks)}"

    devices = [d for t in trunks for d in t.devices]
    # 62 equipment rows, but 12 corridor sensors share a fan coil's controller,
    # so there are 50 controllers -- and a controller is what BACnet calls a device.
    assert len(devices) == 50, f"expected 50 devices, got {len(devices)}"

    by_trunk = {t.name: len(t.devices) for t in trunks}
    assert by_trunk == {"MSTP-01-A": 7, "MSTP-01-B": 18,
                        "MSTP-02-A": 7, "MSTP-02-B": 18}, by_trunk

    # the chiller is deliberately not a BACnet device -- spec, "Topology"
    for d in devices:
        assert not any("RTAC" in e for e in d.equipment), \
            f"chiller leaked onto the wire: {d.equipment}"
        for p in d.points:
            assert not p["point"].startswith("RTAC822_"), \
                f"chiller point leaked: {p['point']}"

    # MS/TP MAC addresses are 1..127, unique per trunk
    for t in trunks:
        macs = [d.mac for d in t.devices]
        assert all(1 <= m <= 127 for m in macs), f"{t.name} MAC out of range: {macs}"
        assert len(set(macs)) == len(macs), f"{t.name} duplicate MAC"

    # device instances are unique and legal
    instances = [d.instance for d in devices] + [r.instance for r in routers]
    assert len(set(instances)) == len(instances), "duplicate device instance"
    assert all(0 < i <= MAX_DEVICE_INSTANCE for i in instances), "instance out of range"

    # per-controller object counts, per the spec's Object Model section
    counts = sorted(len(d.points) for d in devices)
    assert counts.count(12) == 13, f"expected 13 twelve-point MAUs, got {counts.count(12)}"
    assert counts.count(9) == 1, f"expected 1 nine-point CHW entrance, got {counts.count(9)}"
    assert counts.count(8) == 12, f"expected 12 fan coils sharing a controller with a corridor sensor, got {counts.count(8)}"
    assert counts.count(6) == 24, f"expected 24 fan coils alone, got {counts.count(6)}"

    # 421 rows exist for barracks822 in points.json. They split three ways:
    #   405 field-controller points   -> on the wire, under their device
    #     6 supervisory points        -> on the wire, under their router
    #    10 chiller points            -> deliberately NOT on the wire
    device_points = sum(len(d.points) for d in devices)
    router_points = sum(len(r.points) for r in routers)
    assert device_points == 405, f"expected 405 device points, got {device_points}"
    assert router_points == 6, f"expected 6 supervisory points, got {router_points}"
    print(f"SELF-TEST PASS (bacnet822 tree: 2 routers, 4 trunks, {len(devices)} "
          f"devices, {device_points} device + {router_points} supervisory objects)")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print("nothing to run yet", file=sys.stderr)
        sys.exit(1)
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 open-source-stack/bacnet822.py --self-test`
Expected: `NotImplementedError` from `build_tree`.

- [ ] **Step 3: Add the dataclasses and implement build_tree**

Insert above `build_tree` and replace the stub:

```python
@dataclass
class DeviceSpec:
    """One physical controller on a trunk.

    A controller can serve more than one piece of equipment: 12 corridor
    sensors are wired into an adjacent fan coil's UC400 rather than getting
    their own controller, which is how it is actually done in the field.
    `equipment` therefore lists every equipment id this controller serves,
    and `points` is the union of their points.
    """
    instance: int
    name: str
    mac: int
    trunk: str
    network: int
    equipment: list[str] = field(default_factory=list)
    points: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class TrunkSpec:
    name: str
    network: int
    router: str
    devices: list[DeviceSpec] = field(default_factory=list)


@dataclass
class RouterSpec:
    instance: int
    name: str
    trunks: list[TrunkSpec] = field(default_factory=list)
    points: list[dict[str, Any]] = field(default_factory=list)


def _load(name: str, key: str) -> list[dict[str, Any]]:
    """Load an inventory file, tolerating both the bare-list and wrapped forms."""
    raw = json.loads((INPUT_DIR / name).read_text(encoding="utf-8"))
    rows = raw[key] if isinstance(raw, dict) and key in raw else raw
    return [r for r in rows if r.get("facility") == FACILITY]


def _controller_name(equipment_id: str, controller: str | None) -> str:
    """UC400-MAU-01 if the inventory names a controller, else a derived name."""
    return controller or f"UC400-{equipment_id}"


def build_tree() -> list[RouterSpec]:
    """Build the router/trunk/device tree from the 822 inventory.

    Equipment with no `parent` is deliberately not on the wire -- the RTAC
    chiller is local-display only (spec, "The chiller is deliberately
    off-network"). It is skipped here, which is what keeps it off BACnet.
    """
    equipment = _load("equipment.json", "equipment")
    points = _load("points.json", "points")

    points_by_equipment: dict[str, list[dict[str, Any]]] = {}
    for p in points:
        points_by_equipment.setdefault(p["equipment"], []).append(p)

    routers: dict[int, RouterSpec] = {}
    trunks: dict[str, TrunkSpec] = {}
    for trunk_name, (net, router_instance, router_name) in TRUNK_LAYOUT.items():
        router = routers.get(router_instance)
        if router is None:
            router = RouterSpec(instance=router_instance, name=router_name)
            routers[router_instance] = router
        trunk = TrunkSpec(name=trunk_name, network=net, router=router_name)
        trunks[trunk_name] = trunk
        router.trunks.append(trunk)

    # One device per CONTROLLER, not per equipment row. Equipment sharing a
    # controller (a corridor sensor on a fan coil's UC400) is one BACnet device
    # carrying the union of their points -- which is what is physically there.
    # Deterministic order: inventory order within each trunk, MACs 1..n.
    next_mac: dict[str, int] = {name: 1 for name in TRUNK_LAYOUT}
    by_controller: dict[tuple[str, str], DeviceSpec] = {}
    for item in equipment:
        parent = item.get("parent")
        if not parent:
            continue                      # off-network by design (the chiller)
        if parent not in trunks:
            raise ValueError(f"{item['id']} names unknown trunk {parent!r}")
        controller = _controller_name(item["id"], item.get("controller"))
        key = (parent, controller)
        device = by_controller.get(key)
        if device is None:
            mac = next_mac[parent]
            next_mac[parent] = mac + 1
            trunk = trunks[parent]
            device = DeviceSpec(
                instance=INSTANCE_BASE[parent] + mac - 1,
                name=controller,
                mac=mac,
                trunk=parent,
                network=trunk.network,
            )
            by_controller[key] = device
            trunk.devices.append(device)
        device.equipment.append(item["id"])
        device.points.extend(points_by_equipment.get(item["id"], []))

    # Supervisory points belong to the SC, not to any field controller: their
    # `equipment` field names a router or a trunk rather than a device id. A
    # real Tracer SC exposes exactly these -- its own health and each trunk's.
    router_by_name = {r.name: r for r in routers.values()}
    for point in points:
        owner = point["equipment"]
        if owner in router_by_name:
            router_by_name[owner].points.append(point)
        elif owner in trunks:
            router_by_name[trunks[owner].router].points.append(point)

    return [routers[i] for i in sorted(routers)]
```

- [ ] **Step 4: Run the self-test to verify it passes**

Run: `python3 open-source-stack/bacnet822.py --self-test`
Expected: `SELF-TEST PASS (bacnet822 tree: 2 routers, 4 trunks, 50 devices, 405 device + 6 supervisory objects)`

If `device_points` is not 405, the chiller's 10 points are probably still included — check that equipment with no `parent` is skipped. If `router_points` is not 6, the supervisory loop is not matching: those points name `SC-822-01` / `MSTP-01-A` style owners, not device ids.

- [ ] **Step 5: Verify nothing else changed**

Run: `scripts/run-smoke-test.sh`
Expected: `slot-3 BAS simulator smoke test passed`. This task adds a file and touches nothing else, so any failure here is unrelated and must be reported, not worked around.

- [ ] **Step 6: Checkpoint**

Do not commit. Report the self-test line and the smoke test result.

---

### Task 3: Object factory

Turn point records into BACnet objects with the right type, units, and priority array.

**Files:**
- Modify: `open-source-stack/bacnet822.py`

**Interfaces:**
- Consumes: `DeviceSpec.points` from Task 2.
- Produces, relied on by Tasks 4 and 5:
  - `class MultiStateValueObjectCmd(Commandable, MultiStateValueObject)`
  - `make_object(point: dict, instance: int) -> Object` — one BACnet object for one point record
  - `is_commandable(point: dict) -> bool`
  - `resolved_value(obj) -> float | int` and `controlling_priority(obj) -> int | None`

**Critical API notes** — verified during planning, do not rediscover:
- `AnalogOutputObject` and `BinaryOutputObject` are commandable. `AnalogValueObject` is **not** — use `AnalogValueObjectCmd` for a writable `AV`.
- bacpypes3 ships **no** commandable MultiStateValue. Declare `class MultiStateValueObjectCmd(Commandable, MultiStateValueObject): pass`. This was verified working: write `Unsigned(4)` at priority 8, relinquish with `Null(())`, falls back correctly.
- Writes need typed values: `Real(x)` for analog, `Unsigned(n)` for multi-state, and binary present values are the strings `"active"` / `"inactive"`.

- [ ] **Step 1: Write the failing self-test additions**

Add to `_self_test()` in `bacnet822.py`, before the final `print`:

```python
    # --- object factory ---------------------------------------------------
    import asyncio as _asyncio

    async def _object_checks() -> None:
        sat = next(p for d in devices for p in d.points if p["point"] == "MAU01_SAT")
        vlv = next(p for d in devices for p in d.points if p["point"] == "MAU01_CHW_VLV_CMD")
        mode = next(p for d in devices for p in d.points
                    if p["point"] == "FCU_A101_FAN_MODE")

        assert not is_commandable(sat), "MAU01_SAT is an AI and must not be commandable"
        assert is_commandable(vlv), "MAU01_CHW_VLV_CMD is a writable AO"
        assert is_commandable(mode), "FCU_A101_FAN_MODE is a writable MV"

        sat_obj = make_object(sat, 1)
        assert sat_obj.objectName == "MAU01_SAT"
        # bacpypes3's Enumerated.__str__ returns the ASN.1 name
        # ("degrees-fahrenheit"), never the camelCase alias used to construct
        # it. Compare enum identity instead -- it accepts either spelling.
        assert sat_obj.units == EngineeringUnits("degreesFahrenheit"), str(sat_obj.units)
        assert not hasattr(sat_obj, "priorityArray"), "an AI must have no priority array"

        mode_obj = make_object(mode, 1)
        assert list(mode_obj.stateText) == ["Off", "Auto", "Low", "Mid", "High"]
        assert mode_obj.numberOfStates == 5

        vlv_obj = make_object(vlv, 1)
        await _asyncio.sleep(0)

        # the control loop writes priority 16 by plain assignment
        vlv_obj.presentValue = 78.2
        assert abs(resolved_value(vlv_obj) - 78.2) < 0.01, resolved_value(vlv_obj)
        assert controlling_priority(vlv_obj) == 16

        # an operator write at 8 wins, and the loop at 16 cannot take it back
        await vlv_obj.write_property("presentValue", Real(45.0), None, 8)
        assert abs(resolved_value(vlv_obj) - 45.0) < 0.01
        assert controlling_priority(vlv_obj) == 8
        vlv_obj.presentValue = 80.0
        assert abs(resolved_value(vlv_obj) - 45.0) < 0.01, "priority 16 overrode priority 8"

        # relinquishing 8 falls back to the loop's value at 16
        await vlv_obj.write_property("presentValue", Null(()), None, 8)
        assert abs(resolved_value(vlv_obj) - 80.0) < 0.01, resolved_value(vlv_obj)
        assert controlling_priority(vlv_obj) == 16

        # relinquishing everything falls back to relinquishDefault
        await vlv_obj.write_property("presentValue", Null(()), None, 16)
        assert controlling_priority(vlv_obj) is None

        # out-of-range priorities are refused (verified against bacpypes3 0.0.102:
        # priority 0 -> writeAccessDenied, priority 17 -> invalidArrayIndex)
        from bacpypes3.errors import PropertyError
        for bad in (0, 17):
            try:
                await vlv_obj.write_property("presentValue", Real(5.0), None, bad)
            except PropertyError:
                pass
            else:
                raise AssertionError(f"priority {bad} should have been refused")

    _asyncio.run(_object_checks())
```

- [ ] **Step 2: Run it to verify it fails**

Run: `python3 open-source-stack/bacnet822.py --self-test`
Expected: `NameError: name 'is_commandable' is not defined`.

- [ ] **Step 3: Implement the factory**

Add the imports at the top of the module:

```python
from bacpypes3.basetypes import EngineeringUnits
from bacpypes3.local.analog import (
    AnalogInputObject, AnalogOutputObject, AnalogValueObject, AnalogValueObjectCmd,
)
from bacpypes3.local.binary import BinaryInputObject, BinaryOutputObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.local.multistate import MultiStateValueObject
from bacpypes3.primitivedata import Null, Real, Unsigned
```

And the factory itself:

```python
class MultiStateValueObjectCmd(Commandable, MultiStateValueObject):
    """A commandable multi-state value.

    bacpypes3 0.0.102 ships MultiStateOutputObject as commandable but no
    commandable MultiStateValue, and the 822 fan-mode points are MV.
    """


UNITS_MAP: dict[str, str] = {
    "F": "degreesFahrenheit",
    "%": "percent",
    "GPM": "usGallonsPerMinute",
    "PSI": "poundsForcePerSquareInch",
    "tons": "tons",
    "bool": "noUnits",
    "state": "noUnits",
}

FAN_MODE_STATES = ["Off", "Auto", "Low", "Mid", "High"]


def is_commandable(point: dict[str, Any]) -> bool:
    """AO and BO are always commandable; AV and MV only when writable."""
    ptype = point["type"]
    if ptype in ("AO", "BO"):
        return True
    if ptype in ("AV", "MV"):
        return bool(point.get("writable"))
    return False


def _initial(point: dict[str, Any]) -> float:
    """A plausible starting value: the midpoint of the normal range."""
    lo, hi = point.get("normal_min"), point.get("normal_max")
    if lo is None or hi is None:
        return 0.0
    return (float(lo) + float(hi)) / 2.0


def make_object(point: dict[str, Any], instance: int) -> Any:
    """Build one BACnet object for one point record."""
    name = point["point"]
    ptype = point["type"]
    units = UNITS_MAP.get(point.get("units") or "", "noUnits")
    initial = _initial(point)

    if ptype == "AI":
        return AnalogInputObject(
            objectIdentifier=("analog-input", instance), objectName=name,
            presentValue=initial, units=units, outOfService=False)
    if ptype == "AO":
        return AnalogOutputObject(
            objectIdentifier=("analog-output", instance), objectName=name,
            presentValue=initial, units=units, relinquishDefault=initial)
    if ptype == "AV":
        cls = AnalogValueObjectCmd if point.get("writable") else AnalogValueObject
        kwargs: dict[str, Any] = dict(
            objectIdentifier=("analog-value", instance), objectName=name,
            presentValue=initial, units=units)
        if point.get("writable"):
            kwargs["relinquishDefault"] = initial
        return cls(**kwargs)
    if ptype == "BI":
        return BinaryInputObject(
            objectIdentifier=("binary-input", instance), objectName=name,
            presentValue="inactive", outOfService=False)
    if ptype == "BO":
        return BinaryOutputObject(
            objectIdentifier=("binary-output", instance), objectName=name,
            presentValue="inactive", relinquishDefault="inactive")
    if ptype == "MV":
        cls = MultiStateValueObjectCmd if point.get("writable") else MultiStateValueObject
        kwargs = dict(
            objectIdentifier=("multi-state-value", instance), objectName=name,
            presentValue=2, numberOfStates=len(FAN_MODE_STATES),
            stateText=list(FAN_MODE_STATES))
        if point.get("writable"):
            kwargs["relinquishDefault"] = 2
        return cls(**kwargs)

    raise ValueError(f"unsupported point type {ptype!r} for {name}")


def resolved_value(obj: Any) -> Any:
    """The object's present value as the physics layer wants it."""
    value = obj.presentValue
    if isinstance(value, str):                 # binary objects
        return 1 if value == "active" else 0
    return float(value)


def controlling_priority(obj: Any) -> int | None:
    """Which priority slot is currently in control, or None for the default."""
    cp = getattr(obj, "currentCommandPriority", None)
    if cp is None or cp.null is not None:
        return None
    return int(cp.unsigned)
```

- [ ] **Step 4: Run the self-test to verify it passes**

Run: `python3 open-source-stack/bacnet822.py --self-test`
Expected: the tree line from Task 2 prints and the run exits 0 with no assertion error.

If a units assertion fails, check the `units` field spelling in `data/input/points.json` against `UNITS_MAP` — do not edit `points.json`, extend the map. Note that `str()` on a units value returns the ASN.1 kebab-case name (`degrees-fahrenheit`, `percent`), so compare enum identity rather than strings.

- [ ] **Step 5: Checkpoint**

Do not commit. Report the self-test output.

---

### Task 4: Server assembly

Build the 64 applications and serve them. After this task the building is discoverable but frozen — Task 5 makes it move.

**Files:**
- Modify: `open-source-stack/bacnet822.py`

**Interfaces:**
- Consumes: `build_tree()`, `make_object()`, `is_commandable()`.
- Produces, relied on by Tasks 5-7:
  - `class Server822` with attributes `routers: list[Application]`, `devices: dict[str, Application]` keyed by controller name, `objects: dict[str, Any]` keyed by **point name**, `commandables: dict[str, Any]` (the writable subset of `objects`)
  - `async def build_server(ip_cidr: str, port: int, bbmd: bool) -> Server822`
  - `def parse_args(argv)` supporting `--address`, `--port` (default 47809), `--bbmd`, `--timescale` (default 30.0), `--profile` (default `design_summer`), `--self-test`

- [ ] **Step 1: Write the builder**

```python
import argparse
import asyncio
from bacpypes3.app import Application
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.networkport import NetworkPortObject
from bacpypes3.pdu import Address
from bacpypes3.vlan import VirtualNetwork


def _virtual_port(oid: int, name: str, mac: int, trunk: str, network: int) -> NetworkPortObject:
    """A virtual MS/TP-style network port.

    Virtual ports MUST use the keyword form -- the positional form accepts
    only IPv4/IPv6 addresses.
    """
    return NetworkPortObject(
        objectIdentifier=("network-port", oid), objectName=name,
        networkType="virtual", macAddress=bytes([mac]),
        networkInterfaceName=trunk, networkNumber=network,
        networkNumberQuality="configured", protocolLevel="bacnet-application",
        statusFlags=[0, 0, 0, 0], reliability="no-fault-detected",
        outOfService=False, changesPending=False, linkSpeed=0.0)


def _ip_port(oid: int, name: str, cidr: str, port: int, bbmd: bool) -> NetworkPortObject:
    """The BACnet/IP port.

    networkNumber MUST be a non-zero integer. Without it the router raises
    `TypeError: integer network required` when building the return path for
    a routed response, and clients see an abort with no-response.
    """
    kwargs: dict[str, Any] = dict(
        objectIdentifier=("network-port", oid), objectName=name,
        networkNumber=IP_NETWORK_NUMBER, networkNumberQuality="configured")
    if bbmd:
        kwargs["bacnetIPMode"] = "bbmd"
        kwargs["bbmdAcceptFDRegistrations"] = True
        kwargs["bbmdBroadcastDistributionTable"] = []
    return NetworkPortObject(f"{cidr}:{port}", **kwargs)


class Server822:
    """The whole of Building 822 as BACnet applications."""

    def __init__(self) -> None:
        self.routers: list[Application] = []
        self.devices: dict[str, Application] = {}
        self.objects: dict[str, Any] = {}
        self.commandables: dict[str, Any] = {}

    def close(self) -> None:
        for app in list(self.devices.values()) + self.routers:
            app.close()


async def build_server(ip_cidr: str, port: int, bbmd: bool) -> Server822:
    """Construct the routers, the virtual trunks, and every field controller."""
    server = Server822()
    tree = build_tree()

    for trunk_name in TRUNK_LAYOUT:
        # VirtualNetwork registers globally by name and raises ValueError on a
        # duplicate. Guard it so a second build_server() in the same process --
        # an in-process integration test, say -- does not die confusingly.
        try:
            VirtualNetwork(trunk_name)
        except ValueError:
            pass        # already registered earlier in this process

    # Each router binds its OWN UDP port. Two BACnet/IP applications cannot
    # share one port: the second bind fails and bacpypes3 retries it silently
    # forever, so the second router would simply never appear, with no error.
    # A real job gives each SC its own IP; on one host, its own port.
    for offset, router_spec in enumerate(tree):
        objs: list[Any] = [
            DeviceObject(
                objectIdentifier=("device", router_spec.instance),
                objectName=router_spec.name, vendorIdentifier=VENDOR_IDENTIFIER,
                modelName="Synthetic Supervisory Controller", objectList=[]),
            _ip_port(1, f"{router_spec.name}-ip", ip_cidr, port + offset, bbmd),
        ]
        for i, trunk in enumerate(router_spec.trunks, start=2):
            objs.append(_virtual_port(i, trunk.name, 1, trunk.name, trunk.network))
        # the SC's own status points and its trunk status points
        for idx, point in enumerate(router_spec.points, start=1):
            obj = make_object(point, idx)
            objs.append(obj)
            server.objects[point["point"]] = obj
        server.routers.append(Application.from_object_list(objs))

    for router_spec in tree:
        for trunk in router_spec.trunks:
            for dev in trunk.devices:
                objs = [
                    DeviceObject(
                        objectIdentifier=("device", dev.instance), objectName=dev.name,
                        vendorIdentifier=VENDOR_IDENTIFIER,
                        modelName="Synthetic Field Controller",
                        description=f"{', '.join(dev.equipment)} on {dev.trunk}",
                        objectList=[]),
                    # MAC 1 belongs to the router's port on this trunk
                    _virtual_port(1, f"{dev.name}-mstp", dev.mac + 1,
                                  dev.trunk, dev.network),
                ]
                for idx, point in enumerate(dev.points, start=1):
                    obj = make_object(point, idx)
                    objs.append(obj)
                    server.objects[point["point"]] = obj
                    if is_commandable(point):
                        server.commandables[point["point"]] = obj
                server.devices[dev.name] = Application.from_object_list(objs)

    await asyncio.sleep(0.5)          # let every object's async _post_init run
    return server
```

Note the MAC arithmetic: the router's own port on each trunk takes MAC 1, so device MAC `n` from Task 2 is placed at `n + 1` on the wire. Trunk B therefore uses MACs 2-25, still inside the 1-127 MS/TP range.

- [ ] **Step 2: Add the CLI**

```python
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Building 822 BACnet/IP server")
    parser.add_argument("--address", default=None,
                        help="interface CIDR, e.g. 172.28.94.51/20 (default: autodetect)")
    parser.add_argument("--port", type=int, default=47809,
                        help="BACnet/IP UDP port for the FIRST router; the second "
                             "router binds --port + 1. Default 47809/47810 "
                             "(47808 is the hospital device)")
    parser.add_argument("--bbmd", action="store_true",
                        help="run the IP port as a BBMD accepting foreign device registration")
    parser.add_argument("--timescale", type=float, default=30.0,
                        help="model minutes per real second (default 30; 1 = real time)")
    parser.add_argument("--profile", default="design_summer",
                        help="weather profile from data/input/weather_822.json")
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args(argv)


def default_cidr() -> str:
    """This host's primary IPv4 CIDR. Never loopback -- BACnet needs broadcast."""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))       # no packet is sent
        addr = sock.getsockname()[0]
    finally:
        sock.close()
    if addr.startswith("127."):
        raise RuntimeError("refusing to bind loopback; pass --address explicitly")
    return f"{addr}/20"
```

- [ ] **Step 3: Add a temporary main and start it**

```python
async def _serve(args: argparse.Namespace) -> None:
    cidr = args.address or default_cidr()
    server = await build_server(cidr, args.port, args.bbmd)
    ports = ", ".join(str(args.port + i) for i in range(len(server.routers)))
    print(f"Building 822 on {cidr} ports {ports}  "
          f"({len(server.routers)} routers, {len(server.devices)} devices, "
          f"{len(server.objects)} objects, {len(server.commandables)} commandable)")
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        server.close()
```

and in `__main__`, when not `--self-test`, `asyncio.run(_serve(args))`.

- [ ] **Step 4: Verify it starts and reports the right shape**

Run: `python3 open-source-stack/bacnet822.py` (Ctrl-C to stop)

Expected: `Building 822 on <cidr> ports 47809, 47810  (2 routers, 50 devices, 411 objects, 162 commandable)`

411 = 405 field-controller points + 6 supervisory points. The chiller's 10 points are absent by design. If it reports fewer, a point type is falling through `make_object`. If startup exceeds the Task 1 measurement by much, stop and report.

- [ ] **Step 5: Verify the hospital device still works**

Run, in a second terminal, while the 822 server is running:

```bash
python3 open-source-stack/bacnet_device.py
```

Expected: it starts and binds 47808 without a port conflict. Stop both.

- [ ] **Step 6: Checkpoint**

Do not commit. Report the startup line, the object counts, and that 47808 is still free.

---

### Task 5: Step loop and lock guard

The building starts answering. This is the task that makes the design true.

**Files:**
- Modify: `open-source-stack/bacnet822.py`
- Modify: `simulator/bas_sim.py:288-289` (lock guard only)

**Interfaces:**
- Consumes: `Server822`, `resolved_value()`, and `model822.step_822(state, step, profile, overrides)` which returns `(new_state, points_dict)`.
- Produces: `async def run_loop(server, args)`; the lock file `data/output/.822-bacnet.lock`.

- [ ] **Step 1: Add the lock**

```python
import os

LOCK_FILE = OUTPUT_DIR / ".822-bacnet.lock"


def acquire_lock() -> None:
    """Claim 822 for this process. A stale lock (dead PID) is replaced."""
    if LOCK_FILE.exists():
        try:
            holder = json.loads(LOCK_FILE.read_text(encoding="utf-8"))
            pid = int(holder["pid"])
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pid = -1
        if pid > 0:
            # signal 0 is a liveness probe. ONLY ProcessLookupError means the
            # PID is gone. PermissionError means the process EXISTS but is
            # owned by another user -- that is alive, and treating it as stale
            # would let this process steal the lock from a live holder.
            alive = True
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                alive = False
            except PermissionError:
                alive = True
            if alive:
                raise SystemExit(
                    f"Building 822 is already served by PID {pid}. "
                    f"Stop it, or delete {LOCK_FILE} if that PID is gone.")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(json.dumps({
        "pid": os.getpid(),
        "started": datetime.now(timezone.utc).isoformat(),
    }) + "\n", encoding="utf-8")


def release_lock() -> None:
    try:
        LOCK_FILE.unlink()
    except FileNotFoundError:
        pass
```

Add `from datetime import datetime, timezone` to the imports.

- [ ] **Step 2: Add the step loop**

Import note first: `model822.py` lives in `simulator/`, which is not on the path from `open-source-stack/`. Add near the top of `bacnet822.py`, matching how `model822.py` imports `psychro`:

```python
sys.path.insert(0, str(ROOT / "simulator"))
import model822  # noqa: E402
```

Then the loop:

```python
async def run_loop(server: Server822, args: argparse.Namespace) -> None:
    """Drive the physics from the priority arrays, once per tick.

    One model minute per `timescale` real seconds. The resolved presentValue
    of every commandable object is the override input to the model; the
    model's control-loop outputs are written back at priority 16 by plain
    assignment, so an operator write at priority 8 continues to win.
    """
    state = model822.load_state()
    step = int(state.get("step", 0))
    tick = max(0.05, 60.0 / args.timescale)

    while True:
        overrides = {
            name: {"value": resolved_value(obj)}
            for name, obj in server.commandables.items()
            if controlling_priority(obj) not in (None, 16)
        }
        state, points = model822.step_822(state, step, args.profile, overrides)
        step += 1
        state["step"] = step

        for name, value in points.items():
            obj = server.objects.get(name)
            if obj is None:
                continue
            if name in server.commandables:
                # the control loop writes priority 16; an operator at 8 still wins
                obj.presentValue = value
            elif isinstance(obj, (BinaryInputObject, BinaryOutputObject)):
                # A binary present value is a BinaryPV enum, never a str and
                # never a float -- test the OBJECT's class, not the value's.
                obj.presentValue = "active" if value else "inactive"
            else:
                obj.presentValue = float(value)

        # Non-commandable 822 points are only AI, AV and BI, so the three
        # branches above are exhaustive. If a new point type appears, it lands
        # in the float branch and will fail loudly rather than silently.

        model822.save_state(state)
        _merge_latest_points(points)
        await asyncio.sleep(tick)


def _merge_latest_points(points: dict[str, float]) -> None:
    """Keep the Tracer/Metasys/Niagara front ends live against the same building."""
    path = OUTPUT_DIR / "latest_points.json"
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return                                   # front end not in use; not fatal
    if "points" not in blob:
        return
    blob["points"].update(points)
    blob["generated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(blob, indent=2, sort_keys=True) + "\n", encoding="utf-8")
```

Only points under operator command are passed as overrides — a commandable object sitting at priority 16 holds the model's *own* last output, and feeding that back as an override would freeze the loop. That is the subtlest line in this file; do not simplify it.

Wire it into `_serve`: `await run_loop(server, args)` in place of the `sleep(3600)`, with `acquire_lock()` before `build_server` and `release_lock()` in the `finally`.

- [ ] **Step 3: Verify the building responds to a command**

Run the server, then in a second terminal:

```bash
python3 - <<'EOF'
import json, time
from pathlib import Path
p = Path("data/output/state_822.json")
def step(): return json.loads(p.read_text())["step"]
a = step(); time.sleep(10); b = step()
print(f"model step {a} -> {b} (delta {b - a}; at 30x expect ~5 in 10s)")
print("LOOP TICKING" if b > a else "LOOP STALLED")
EOF
```

Expected: the step counter advances by roughly 5.

Check the **step counter**, not a temperature. A healthy building at steady
state holds supply air exactly at setpoint, so `MAU01_SAT` legitimately does
not change from one reading to the next — a static temperature proves the
control loop is working, not that the model is frozen. The step counter is
the unambiguous liveness signal. (Task 7's acceptance test is what proves the
building *responds*, by commanding a valve and watching the response.)

If the counter does not advance, the loop is not running or the lock aborted
startup.

- [ ] **Step 4: Add the bas_sim lock guard**

In `simulator/bas_sim.py`, replace line 288:

```python
    has_822 = any(p.facility == model822.FACILITY for p in points)
```

with:

```python
    has_822 = any(p.facility == model822.FACILITY for p in points)
    served_822: dict[str, float] = {}
    if has_822 and (OUTPUT_DIR / ".822-bacnet.lock").exists():
        print("bas_sim: Building 822 is served by bacnet822.py; observing its "
              "points instead of simulating them", file=sys.stderr)
        has_822 = False
        served_822 = load_served_822_points()
        # Any 822 point the server has not published yet cannot be observed
        # this run, so drop it -- the per-point loop below indexes `snapshot`
        # unconditionally and would otherwise raise KeyError.
        observable = set(served_822)
        points = [p for p in points
                  if p.facility != model822.FACILITY or p.name in observable]
        points_by_name = {p.name: p for p in points}
```

and add this helper beside the other loaders in the same module:

```python
def load_served_822_points() -> dict[str, float]:
    """Current 822 values published by bacnet822.py.

    While the BACnet server owns Building 822 we must not simulate it, but its
    points still belong in trends, alarms and latest_points.json -- so we
    observe what the server publishes instead of driving it ourselves.
    """
    try:
        blob = json.loads(
            (OUTPUT_DIR / "latest_points.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dict(blob.get("points", {}))
```

Then, inside the step loop, merge the observed values in right after the
legacy snapshot is built and before `apply_fault` is called:

```python
        if served_822:
            snapshot.update(served_822)
```

This matters because `write_outputs` rewrites `latest_points.json` wholesale
from the final snapshot. Without the merge, running `bas_sim.py` while the
server is up would blank every 822 point out of the file the front ends read.

Verify `OUTPUT_DIR`, `json` and `sys` are already in scope in that module; all
three are used elsewhere in it.

- [ ] **Step 5: Verify the guard works both ways**

With the server running:

```bash
python3 simulator/bas_sim.py --scenario normal --steps 4
```
Expected: the skip message on stderr, exit 0, hospital points still updated.

Then stop the server and re-run the same command. Expected: no skip message, and `data/output/state_822.json` updates again.

- [ ] **Step 6: Verify the hospital and office regression**

With the server stopped:

```bash
python3 simulator/bas_sim.py --scenario normal --steps 12
python3 -c "
import json
pts = json.load(open('data/output/latest_points.json'))['points']
for p in ('AHU_OR1_SAT','OR1_TEMP','ISO201_PRESSURE'):
    print(p, pts[p])
"
scripts/run-smoke-test.sh
```

Expected: smoke test passes. The hospital values must be produced by the unchanged `scenario_value()` path — if the guard accidentally skipped them, the smoke test's own assertions fail.

- [ ] **Step 7: Checkpoint**

Do not commit. Report the SAT-moves proof, both guard directions, and the smoke test result.

---

### Task 6: Audit logging

Every write gets recorded, in the schema the front ends already use.

**Files:**
- Modify: `open-source-stack/bacnet822.py`

**Interfaces:**
- Consumes: `Server822.commandables`, `controlling_priority()`.
- Produces: appends to `data/output/operator_actions.jsonl`.

The existing schema, from a real record in that file:

```json
{"action": "command", "data_boundary": "synthetic lab operator action only",
 "equipment": "MAU-01", "operator_id": "tech-01", "point": "MAU01_CHW_VLV_CMD",
 "reason": "close the valve", "role": "technician",
 "timestamp": "2026-09-14T19:35:47.608605+00:00", "units": "%", "value": 0.0}
```

- [ ] **Step 1: Add the writer**

```python
ACTIONS_FILE = OUTPUT_DIR / "operator_actions.jsonl"


def log_action(point_name: str, equipment: str, units: str, value: Any,
               priority: int | None, source: str, released: bool) -> None:
    """Append one BACnet write to the shared operator audit trail."""
    record = {
        "action": "release" if released else "command",
        "data_boundary": "synthetic lab operator action only",
        "equipment": equipment,
        "operator_id": f"bacnet:{source}",
        "point": point_name,
        "reason": "BACnet WriteProperty",
        "role": "technician",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "units": units,
        "value": None if released else value,
        "bacnet_priority": priority,
        "bacnet_source": source,
    }
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with ACTIONS_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, sort_keys=True) + "\n")
```

The three added keys (`bacnet_priority`, `bacnet_source`, and the `bacnet:` prefix on `operator_id`) are additive. `frontend/bas_api.py` reads this file with `json.loads` per line and selects known keys, so extra keys are ignored — verify that before relying on it by reading `_load_trouble_call_log` and the operator-action reader in that module.

- [ ] **Step 2: Detect writes by polling the priority array**

bacpypes3 has no write hook on local objects that is stable in 0.0.102. Detect changes in the loop instead — add to `run_loop`, before the overrides are built:

```python
        for name, obj in server.commandables.items():
            pri = controlling_priority(obj)
            previous = last_priority.get(name, "unset")
            if previous == "unset":
                last_priority[name] = pri
                continue
            if pri != previous:
                point = points_meta[name]
                log_action(name, point["equipment"], point.get("units") or "",
                           resolved_value(obj), pri, "wire",
                           released=pri in (None, 16))
                last_priority[name] = pri
```

with both maps built once, before the `while True:` line:

```python
    last_priority: dict[str, int | None | str] = {}
    points_meta: dict[str, dict[str, Any]] = {
        point["point"]: point
        for router in build_tree()
        for trunk in router.trunks
        for dev in trunk.devices
        for point in dev.points
    }
```

This records a transition of control, which is what an audit reader cares about: who took the point and when they gave it back. It does not record a re-write at the same priority; note that limitation in the module docstring rather than hiding it.

- [ ] **Step 2b: Carried fixes from the Task 5 review**

Two corrections in this same file, both authorised by the controller:

1. **`acquire_lock()` mis-reads `PermissionError` as a stale lock.** Replace the liveness probe with the corrected form now in Task 5 Step 1 — only `ProcessLookupError` means the PID is gone; `PermissionError` means the process exists under another user and is therefore alive.

2. **SIGTERM bypasses the `finally: release_lock()`**, leaving a stale lock behind after `kill`. `acquire_lock()`'s stale-PID check tolerates it, but a clean shutdown is better. Install handlers for both signals in `_serve` and wait on an event instead of sleeping forever:

```python
import signal


async def _serve(args: argparse.Namespace) -> None:
    cidr = args.address or default_cidr()
    acquire_lock()
    server = None
    try:
        server = await build_server(cidr, args.port, args.bbmd)
        ports = ", ".join(str(args.port + i) for i in range(len(server.routers)))
        print(f"Building 822 on {cidr} ports {ports}  "
              f"({len(server.routers)} routers, {len(server.devices)} devices, "
              f"{len(server.objects)} objects, {len(server.commandables)} commandable)")

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        worker = asyncio.create_task(run_loop(server, args))
        await stop.wait()
        worker.cancel()
    finally:
        if server is not None:
            server.close()
        release_lock()
```

Verify both: start the server, `kill <pid>` (plain SIGTERM), and confirm `data/output/.822-bacnet.lock` is gone afterwards.

- [ ] **Step 3: Verify a write is logged**

Start the server. Using the Task 7 client (do this step after Task 7 if the client does not exist yet), write `MAU01_CHW_VLV_CMD` at priority 8, then relinquish. Then:

```bash
tail -4 data/output/operator_actions.jsonl | python3 -c "
import sys, json
for line in sys.stdin:
    r = json.loads(line)
    print(r['action'], r['point'], r.get('bacnet_priority'), r['value'])
"
```

Expected: a `command` record at priority 8 followed by a `release` record.

- [ ] **Step 4: Checkpoint**

Do not commit. Report the two log records.

---

### Task 7: Test client and the acceptance test

The acceptance test for the whole design. Protocol correctness without a physical response is failure.

**Files:**
- Create: `scripts/bacnet822-client.py`

**Interfaces:**
- Consumes: a running `bacnet822.py`.
- Produces: CLI `read`, `write`, `release`, `whois`, and `--acceptance`.

Remember Task 1 Step 3, constraint 4: this client runs on the same host as the server, so it cannot discover by broadcast. It seeds routes and uses unicast. A real supervisor on another host does not need any of that.

- [ ] **Step 1: Write the client**

```python
#!/usr/bin/env python3
"""Test harness for the Building 822 BACnet server.

NOT an operator interface -- this exists so the write path can be asserted
automatically. The intended human clients are real BACnet supervisors.

Same-host clients cannot discover by broadcast: a BACnet/IP broadcast goes
to the subnet broadcast address at the SENDER's port, so a client on 47810
never hears a server on 47809. Routes are therefore seeded explicitly.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from bacpypes3.app import Application
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.networkport import NetworkPortObject
from bacpypes3.pdu import Address
from bacpypes3.primitivedata import Null, ObjectIdentifier, Real, Unsigned

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "open-source-stack"))
import bacnet822  # noqa: E402

CLIENT_INSTANCE = 999999


async def connect(cidr: str, server_port: int, client_port: int) -> Application:
    app = Application.from_object_list([
        DeviceObject(objectIdentifier=("device", CLIENT_INSTANCE),
                     objectName="bacnet822-client",
                     vendorIdentifier=bacnet822.VENDOR_IDENTIFIER, objectList=[]),
        NetworkPortObject(f"{cidr}:{client_port}",
                          objectIdentifier=("network-port", 1), objectName="ip"),
    ])
    await asyncio.sleep(0.3)
    host = cidr.split("/")[0]
    # Each router listens on its own port: the first at server_port, the second
    # at server_port + 1. Seed each router's own networks against its own address.
    by_router: dict[int, list[int]] = {}
    for net, router_instance, _ in bacnet822.TRUNK_LAYOUT.values():
        by_router.setdefault(router_instance, []).append(net)
    for offset, instance in enumerate(sorted(by_router)):
        await app.nsap.update_router_references(
            None, Address(f"{host}:{server_port + offset}"), by_router[instance])
    return app


def locate(point_name: str) -> tuple[Address, ObjectIdentifier, dict]:
    """Find which device carries a point, and that point's object identity."""
    for router in bacnet822.build_tree():
        for trunk in router.trunks:
            for dev in trunk.devices:
                for idx, point in enumerate(dev.points, start=1):
                    if point["point"] != point_name:
                        continue
                    obj_type = {
                        "AI": "analog-input", "AO": "analog-output",
                        "AV": "analog-value", "BI": "binary-input",
                        "BO": "binary-output", "MV": "multi-state-value",
                    }[point["type"]]
                    # device MAC n sits at n+1 on the wire (router holds MAC 1)
                    addr = Address(f"{dev.network}:{dev.mac + 1}")
                    return addr, ObjectIdentifier(f"{obj_type},{idx}"), point
    raise SystemExit(f"unknown point: {point_name}")


async def do_read(app: Application, point_name: str):
    addr, oid, _ = locate(point_name)
    return await app.read_property(addr, oid, "presentValue")


async def do_write(app: Application, point_name: str, value: float, priority: int):
    addr, oid, point = locate(point_name)
    typed = Unsigned(int(value)) if point["type"] == "MV" else Real(float(value))
    await app.write_property(addr, oid, "presentValue", typed, None, priority)


async def do_release(app: Application, point_name: str, priority: int):
    addr, oid, _ = locate(point_name)
    await app.write_property(addr, oid, "presentValue", Null(()), None, priority)
```

- [ ] **Step 2: Add the acceptance test**

```python
async def acceptance(app: Application) -> int:
    """Command -> controller resolves -> actuator moves -> process changes
    -> sensor proves the response. The design's acceptance sentence, as a test.
    """
    failures: list[str] = []

    def check(label: str, ok: bool, detail: str) -> None:
        print(f"  {'PASS' if ok else 'FAIL'}  {label}: {detail}")
        if not ok:
            failures.append(label)

    sat0 = float(await do_read(app, "MAU01_SAT"))
    vlv0 = float(await do_read(app, "MAU01_CHW_VLV_CMD"))
    check("baseline healthy", 60.0 <= sat0 <= 70.0,
          f"MAU01_SAT={sat0:.2f}F valve={vlv0:.1f}%")

    # drive the valve shut at priority 8 -- cooling should fall away
    await do_write(app, "MAU01_CHW_VLV_CMD", 0.0, 8)
    await asyncio.sleep(1.0)
    vlv1 = float(await do_read(app, "MAU01_CHW_VLV_CMD"))
    check("write @8 resolves", abs(vlv1 - 0.0) < 0.5, f"valve={vlv1:.1f}%")

    await asyncio.sleep(25.0)              # let the physics answer
    sat1 = float(await do_read(app, "MAU01_SAT"))
    check("THE BUILDING ANSWERED", sat1 > sat0 + 1.0,
          f"MAU01_SAT {sat0:.2f} -> {sat1:.2f}F with the valve shut")

    # Release and let the loop recover. While overridden, model822 echoes
    # the override value back as the valve's OWN output every tick (it is the
    # PI loop's cmd_override path, not a separate mechanism) -- so priority 16
    # is also frozen at 0.0 the instant we relinquish 8. Only the NEXT tick,
    # once step_822() sees no override, runs pi_valve() and slews the valve
    # open again. At the default 30x timescale (tick = 60/30 = 2.0s), sleeping
    # only 1.0s races that boundary and can read back before the tick fires.
    # Sleep past a full tick regardless of phase alignment.
    await do_release(app, "MAU01_CHW_VLV_CMD", 8)
    await asyncio.sleep(3.0)
    vlv2 = float(await do_read(app, "MAU01_CHW_VLV_CMD"))
    check("release returns control", vlv2 > 1.0,
          f"valve back to {vlv2:.1f}% under loop control")

    await asyncio.sleep(30.0)
    sat2 = float(await do_read(app, "MAU01_SAT"))
    check("loop recovers setpoint", sat2 < sat1,
          f"MAU01_SAT {sat1:.2f} -> {sat2:.2f}F recovering")

    print(f"\n{'ACCEPTANCE PASS' if not failures else 'ACCEPTANCE FAIL: ' + ', '.join(failures)}")
    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Building 822 BACnet test client")
    parser.add_argument("command", choices=["read", "write", "release", "acceptance"])
    parser.add_argument("point", nargs="?")
    parser.add_argument("value", nargs="?", type=float)
    parser.add_argument("--priority", type=int, default=8)
    parser.add_argument("--address", default=None)
    parser.add_argument("--port", type=int, default=47809)
    parser.add_argument("--client-port", type=int, default=47811,
                        help="47809/47810 are the two routers; the client needs a third")
    args = parser.parse_args()

    cidr = args.address or bacnet822.default_cidr()

    async def run() -> int:
        app = await connect(cidr, args.port, args.client_port)
        try:
            if args.command == "acceptance":
                return await acceptance(app)
            if args.command == "read":
                print(await do_read(app, args.point))
            elif args.command == "write":
                await do_write(app, args.point, args.value, args.priority)
                print(f"wrote {args.value} @ priority {args.priority}")
            elif args.command == "release":
                await do_release(app, args.point, args.priority)
                print(f"released priority {args.priority}")
            return 0
        finally:
            app.close()

    return asyncio.run(run())


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Run the acceptance test**

Start the server (`python3 open-source-stack/bacnet822.py`), then:

```bash
python3 scripts/bacnet822-client.py acceptance
```

Expected: five PASS lines and `ACCEPTANCE PASS`. It takes about a minute at the default 30x timescale.

If "THE BUILDING ANSWERED" fails, the write reached the object but the physics did not consume it — check the override-building line in `run_loop` (Task 5 Step 2) and confirm `controlling_priority` returns 8 for the commanded object.

- [ ] **Step 4: Checkpoint**

Do not commit. Report the full acceptance output verbatim.

---

### Task 8: Smoke test and documentation

**Files:**
- Modify: `scripts/run-smoke-test.sh`
- Create: `docs/bacnet-822.md`

- [ ] **Step 1: Extend the smoke test**

Insert before the final `echo` in `scripts/run-smoke-test.sh`:

```bash
python3 open-source-stack/bacnet822.py --self-test
```

Do **not** add the acceptance test to the smoke test — it needs a running server and takes a minute. The smoke test stays fast and offline.

- [ ] **Step 2: Run it**

Run: `scripts/run-smoke-test.sh`
Expected: the new self-test line, then `slot-3 BAS simulator smoke test passed`.

- [ ] **Step 3: Write docs/bacnet-822.md**

Include, in this order:

1. **What this is** — Building 822 as a routed BACnet internetwork; synthetic; vendor 999; generic third-party devices to any real supervisor, not Trane-native.
2. **Start it** — `python3 open-source-stack/bacnet822.py --bbmd`, the flags, and the fact that `bas_sim.py` will skip 822 while it runs.
3. **The device map** — the topology table from the spec, with the instance ranges, trunk names, network numbers, and the note that MAC `n` from the inventory sits at `n+1` on the wire because the router holds MAC 1.
4. **Connecting YABE from Windows through WSL2 NAT** — start with `--bbmd`; in YABE add a device by foreign-device registration to `<wsl-ip>:47809`; get the IP with `ip -4 addr show eth0`. Explain *why*: WSL2 NAT does not pass UDP broadcast, and `netsh portproxy` is TCP-only.
5. **The mirrored-networking switch** — add `networkingMode=mirrored` under `[wsl2]` in `C:\Users\<user>\.wslconfig`, then `wsl --shutdown` from Windows. Note that this is what a physical supervisor on the LAN needs, that it ends any running WSL session, and that it can disturb the Docker bridge the open-source stack uses.
6. **Priority array reference** — 16 slots, lowest index wins, 8 is Manual Operator, 16 is where this building's control loops write, relinquish by writing Null, and `currentCommandPriority` shows who holds it.
7. **Troubleshooting** — the four constraints from Task 1 Step 3, written as symptoms: `integer network required` / abort no-response means a missing IP `networkNumber`; `not a sequence element: address` means a keyword address on an IPv4 port; broadcast finding nothing from the same host is expected.

- [ ] **Step 4: Full end-to-end verification**

```bash
scripts/run-smoke-test.sh
python3 open-source-stack/bacnet822.py --bbmd &
sleep 5
python3 scripts/bacnet822-client.py acceptance
python3 scripts/bacnet822-client.py read MAU01_SAT
scripts/start-frontend.sh &
sleep 3
for u in / /tracer /metasys /niagara /api/chiller/822; do
  printf '%-24s %s\n' "$u" "$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:8001$u")"
done
```

Expected: smoke test passes, `ACCEPTANCE PASS`, a plausible SAT, and every URL 200. Confirm by eye that `/tracer` shows MAU-01 moving — the front end and BACnet are reading the same building.

Then stop everything and confirm `data/output/.822-bacnet.lock` is gone.

- [ ] **Step 5: Checkpoint**

Stop the server and the front end. Do not commit. This is the last task, so this checkpoint is the handoff for the whole plan. Report: smoke test output, acceptance output, the HTTP status table, what `/tracer` showed, and confirmation that the lock file was cleaned up.
