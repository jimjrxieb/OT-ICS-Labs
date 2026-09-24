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
