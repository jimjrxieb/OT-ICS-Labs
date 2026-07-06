#!/usr/bin/env python3
"""
BACnet/IP Device — NAS JAX BAS Lab

Reads ../data/output/latest_points.json and exposes each point as a real
BACnet object on localhost:47808 (device instance 1001).

What this teaches:
  - BACnet device instance, object types (AnalogInput, BinaryInput)
  - BACnet object naming (objectName matches point_name from the simulator)
  - presentValue as the live engineering value
  - Read-Property request/response — the same exchange a JACE does to a field controller

Usage:
  pip install bacpypes3
  cd slot-3/
  python3 open-source-stack/bacnet_device.py

Enterprise equivalent:
  Metasys SNE/SNC acting as a BACnet server
  Niagara JACE acting as a BACnet server
  Any field controller with a BACnet/IP stack

Run a scenario to update values:
  python3 simulator/bas_sim.py --scenario chilled_water_degraded --steps 12
  (device refreshes from the file every 30 seconds)

Test with a BACnet read client (in another terminal):
  python3 -c "
  import asyncio, bacpypes3
  from bacpypes3.app import Application
  from bacpypes3.pdu import Address
  from bacpypes3.apdu import ReadPropertyRequest
  from bacpypes3.primitivedata import ObjectIdentifier

  async def read_point():
      app = await Application.create(Address('127.0.0.2/24'), 'test-client', 9999)
      # send Read-Property to device 1001, analogInput:1 (AHU_OR1_SAT)
      req = ReadPropertyRequest(
          objectIdentifier=ObjectIdentifier('analogInput:1'),
          propertyIdentifier='presentValue'
      )
      resp = await app.request(Address('127.0.0.1'), req)
      print('AHU_OR1_SAT presentValue:', resp.propertyValue)

  asyncio.run(read_point())
  "
"""
import asyncio
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("bacnet_device")

SLOT3_ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = SLOT3_ROOT / "data" / "output" / "latest_points.json"
REFRESH_INTERVAL = 30  # seconds between re-reads of latest_points.json

DEVICE_ADDRESS = "127.0.0.1/24"
DEVICE_INSTANCE = 1001
DEVICE_NAME = "NAS-JAX-BAS-LAB"

# Points that are binary (bool) — all others are analog (float)
BINARY_POINTS = {"AHU_OR1_FAN_CMD", "ISO201_EXH_CMD"}

# BACnet engineering units — simplified to common values for this lab
# In production: each object would have the correct unit from the point spec
UNITS_MAP = {
    "AHU_OR1_SAT": "degreesFahrenheit",
    "AHU_OR1_SAT_SP": "degreesFahrenheit",
    "OR1_TEMP": "degreesFahrenheit",
    "OR1_TEMP_SP": "degreesFahrenheit",
    "CHW_SUPPLY_TEMP": "degreesFahrenheit",
    "HW_SUPPLY_TEMP": "degreesFahrenheit",
    "OR1_RH": "percentRelativeHumidity",
    "ISO201_PRESSURE": "inchesOfWater",
    "CHW_DIFF_PRESSURE": "poundsPerSquareInch",
}


def load_points() -> dict:
    if not DATA_FILE.exists():
        log.warning("latest_points.json not found — run a scenario first:")
        log.warning("  python3 simulator/bas_sim.py --scenario normal --steps 12")
        return {}
    with DATA_FILE.open() as f:
        data = json.load(f)
    return data.get("points", {})


async def run_bacnet_device():
    try:
        from bacpypes3.app import Application
        from bacpypes3.pdu import Address
        from bacpypes3.local.analog import AnalogInputObject
        from bacpypes3.local.binary import BinaryInputObject
        from bacpypes3.basetypes import EngineeringUnits
    except ImportError as exc:
        log.error("bacpypes3 not installed: %s", exc)
        log.error("Install with: pip install bacpypes3==0.0.102")
        sys.exit(1)

    log.info("BACnet/IP device starting — device %s @ %s", DEVICE_INSTANCE, DEVICE_ADDRESS)

    app = await Application.create(
        address=Address(DEVICE_ADDRESS),
        name=DEVICE_NAME,
        instance=DEVICE_INSTANCE,
    )

    points = load_points()
    if not points:
        log.error("No points loaded. Cannot create BACnet objects. Exiting.")
        sys.exit(1)

    object_map: dict[str, object] = {}

    for idx, (name, raw_value) in enumerate(points.items(), start=1):
        is_binary = name in BINARY_POINTS
        try:
            if is_binary:
                obj = BinaryInputObject(
                    objectIdentifier=("binaryInput", idx),
                    objectName=name,
                    presentValue="active" if bool(raw_value) else "inactive",
                    outOfService=False,
                )
            else:
                obj = AnalogInputObject(
                    objectIdentifier=("analogInput", idx),
                    objectName=name,
                    presentValue=float(raw_value),
                    outOfService=False,
                    units=UNITS_MAP.get(name, "noUnits"),
                )
            app.objectIdentifier[obj.objectIdentifier] = obj
            object_map[name] = (obj, is_binary, idx)
            obj_type = "binaryInput" if is_binary else "analogInput"
            log.info("  [%2d] %-35s  %s:%d  value=%s", idx, name, obj_type, idx, raw_value)
        except Exception as exc:
            log.warning("Failed to create object for %s: %s", name, exc)

    log.info(
        "Device ready — %d BACnet objects registered. Refreshing every %ds.",
        len(object_map),
        REFRESH_INTERVAL,
    )
    log.info("Listening on %s  (BACnet/IP port 47808)", DEVICE_ADDRESS)

    while True:
        await asyncio.sleep(REFRESH_INTERVAL)
        fresh = load_points()
        updated = 0
        for name, val in fresh.items():
            if name in object_map:
                obj, is_binary, _ = object_map[name]
                if is_binary:
                    obj.presentValue = "active" if bool(val) else "inactive"
                else:
                    obj.presentValue = float(val)
                updated += 1
        log.info("Refreshed %d point values from simulator output", updated)


if __name__ == "__main__":
    try:
        asyncio.run(run_bacnet_device())
    except KeyboardInterrupt:
        log.info("BACnet device stopped")
