#!/usr/bin/env python3
"""Building 822 BACnet/IP server.

Presents Building 822 as a routed BACnet internetwork: two Tracer-SC-style
routers, each with two virtual MS/TP trunks, carrying 50 field controllers.

Every write to a commandable point is audited to
data/output/operator_actions.jsonl, the same file the web front ends use.
bacpypes3 0.0.102 has no stable write hook on local objects, so writes are
detected by polling currentCommandPriority for transitions once per tick in
run_loop -- this records who took a point and when they released it, which
is what an audit reader cares about, but it does NOT record a re-write at
the same priority (no transition occurs, so nothing to detect).

Synthetic lab only. Vendor identifier 999 -- these are not Trane devices.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bacpypes3.app import Application
from bacpypes3.basetypes import EngineeringUnits
from bacpypes3.local.analog import (
    AnalogInputObject, AnalogOutputObject, AnalogValueObject, AnalogValueObjectCmd,
)
from bacpypes3.local.binary import BinaryInputObject, BinaryOutputObject
from bacpypes3.local.cmd import Commandable
from bacpypes3.local.device import DeviceObject
from bacpypes3.local.multistate import MultiStateValueObject
from bacpypes3.local.networkport import NetworkPortObject
from bacpypes3.primitivedata import Null, Real, Unsigned
from bacpypes3.vlan import VirtualNetwork

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
OUTPUT_DIR = ROOT / "data" / "output"

sys.path.insert(0, str(ROOT / "simulator"))
import model822  # noqa: E402

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
            alive = True
            try:
                os.kill(pid, 0)                      # signal 0 = liveness probe
            except ProcessLookupError:
                alive = False                        # stale, fall through
            except PermissionError:
                alive = True                          # exists, owned by another user
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


class MultiStateValueObjectCmd(Commandable, MultiStateValueObject):
    """A commandable multi-state value.

    bacpypes3 0.0.102 ships MultiStateOutputObject as commandable but no
    commandable MultiStateValue, and the 822 fan-mode points are MV.
    """


UNITS_MAP: dict[str, str] = {
    "F": "degreesFahrenheit",
    "%": "percent",
    "GPM": "usGallonsPerMinute",
    "CFM": "cubicFeetPerMinute",
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

    last_priority: dict[str, int | None | str] = {}
    points_meta: dict[str, dict[str, Any]] = {
        point["point"]: point
        for router in build_tree()
        for trunk in router.trunks
        for dev in trunk.devices
        for point in dev.points
    }

    while True:
        for name, obj in server.commandables.items():
            pri = controlling_priority(obj)
            previous = last_priority.get(name, "unset")
            if previous == "unset":
                # Every commandable starts at priority None; this tick's
                # writeback (below) is about to drive it to 16 regardless of
                # any operator action. Seed the baseline as post-writeback so
                # the NEXT tick's comparison does not see a false None -> 16
                # "release" for all 162 points on every server start.
                last_priority[name] = 16
                continue
            if pri != previous:
                point = points_meta[name]
                log_action(name, point["equipment"], point.get("units") or "",
                           resolved_value(obj), pri, "wire",
                           released=pri in (None, 16))
                last_priority[name] = pri

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
    import re
    import socket
    import subprocess

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))       # no packet is sent
        addr = sock.getsockname()[0]
    finally:
        sock.close()
    if addr.startswith("127."):
        raise RuntimeError("refusing to bind loopback; pass --address explicitly")

    # Derive the REAL prefix length from the OS rather than guessing -- the
    # BACnet/IP broadcast target (what Who-Is/I-Am reach) depends on it, and
    # a wrong guess fails silently: unicast still works, broadcast goes to
    # the wrong subnet. `ip addr` is present on any Linux/WSL host, which
    # this project already assumes.
    try:
        out = subprocess.run(
            ["ip", "-4", "-o", "addr", "show"],
            capture_output=True, text=True, timeout=2, check=True,
        ).stdout
        for line in out.splitlines():
            m = re.search(rf"\binet {re.escape(addr)}/(\d+)\b", line)
            if m:
                return f"{addr}/{m.group(1)}"
    except (OSError, subprocess.SubprocessError):
        pass

    # Fallback if `ip` is unavailable or parsing fails: assume /24, the most
    # common LAN prefix, and say so loudly rather than silently guessing.
    print(f"bacnet822: could not determine {addr}'s real prefix; assuming /24",
          file=sys.stderr)
    return f"{addr}/24"


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
    assert counts.count(10) == 1, f"expected 1 ten-point CHW entrance (adds CHW822_GPM), got {counts.count(10)}"
    assert counts.count(9) == 12, f"expected 12 fan coils sharing a controller with a corridor sensor (adds CFM), got {counts.count(9)}"
    assert counts.count(7) == 24, f"expected 24 fan coils alone (adds CFM), got {counts.count(7)}"

    # 458 rows exist for barracks822 in points.json. They split three ways:
    #   442 field-controller points   -> on the wire, under their device
    #     6 supervisory points        -> on the wire, under their router
    #    10 chiller points            -> deliberately NOT on the wire
    device_points = sum(len(d.points) for d in devices)
    router_points = sum(len(r.points) for r in routers)
    assert device_points == 442, f"expected 442 device points, got {device_points}"
    assert router_points == 6, f"expected 6 supervisory points, got {router_points}"

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

    print(f"SELF-TEST PASS (bacnet822 tree: 2 routers, 4 trunks, {len(devices)} "
          f"devices, {device_points} device + {router_points} supervisory objects)")


if __name__ == "__main__":
    args = parse_args()
    if args.self_test:
        _self_test()
    else:
        asyncio.run(_serve(args))
