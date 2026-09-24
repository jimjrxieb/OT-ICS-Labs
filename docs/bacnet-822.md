# Building 822 — BACnet/IP Server

## 1. What this is

`open-source-stack/bacnet822.py` presents Building 822 as a routed BACnet
internetwork: two supervisory-controller-style routers, each fanning out
to two virtual MS/TP trunks, carrying 50 field controllers — 448 objects
total, 162 of them commandable. It is driven by the real physics in
`simulator/model822.py`: a write to a commandable object is the override
input to the control loop, and the sensor objects report what the model
actually computes in response. This is the same building `/tracer`,
`/metasys`, and `/niagara` already show; the BACnet server and the web
front end read and write the same underlying state.

**This building is entirely synthetic**, and its devices identify with
BACnet vendor ID **999** — a placeholder for lab equipment, not a
registered vendor. A real supervisor (YABE, Niagara, an actual Tracer
SC+) will **not** recognize these as Trane devices. It will see 52
generic third-party BACnet devices (2 routers + 50 controllers) and will
need every point bound to a template by hand, exactly as it would for
any unknown vendor's equipment on a real job. That is deliberate, not a
gap to apologize for: reproducing Trane's registered vendor identity or
proprietary device profiles was explicitly rejected during design as an
IP problem that would buy presentation, not the skill this lab exists
to teach. What you get instead is the actual first-day-on-a-real-job
experience — point binding, trunk discovery, and reading a priority
array on equipment nobody pre-labeled for you.

## 2. Start it

```bash
cd <repo-root>
python3 open-source-stack/bacnet822.py --bbmd
```

Flags:

| Flag | Default | Meaning |
|---|---|---|
| `--address` | autodetect | Interface CIDR to bind, e.g. `172.28.94.51/20`. Never loopback — BACnet needs broadcast. |
| `--port` | `47809` | UDP port for the **first** router. The second router binds `--port + 1` (`47810` by default). Chosen to sit next to, not on top of, the existing hospital device on `47808`. |
| `--bbmd` | off | Run the IP port as a BBMD (Broadcast Distribution Table) that accepts Foreign Device Registration. See section 4 — this is what makes a Windows client work through WSL2 NAT. |
| `--timescale` | `30` | Model minutes per real second. Default gives a valve write visible movement in roughly 30 seconds. `--timescale 1` runs real-time. |
| `--profile` | `design_summer` | Weather profile from `data/input/weather_822.json`. |
| `--self-test` | — | Offline structural check (topology, object counts, priority-array behavior). No socket is bound. This is what `scripts/run-smoke-test.sh` runs. |

The server prints a one-line summary once every router, trunk, and
device is built, e.g.:

```
Building 822 on 172.28.94.51/20 ports 47809, 47810  (2 routers, 50 devices, 448 objects, 162 commandable)
```

It holds `data/output/.822-bacnet.lock` for as long as it runs.
**`simulator/bas_sim.py` detects that lock and skips stepping Building
822 while the BACnet server owns it** — it keeps driving the hospital
and office buildings normally and just prints a message that 822 is
served elsewhere. Stop the server with Ctrl-C (`SIGINT`) or `SIGTERM`;
it releases the lock on the way out. If it dies uncleanly, the lock is
keyed to its PID and a stale one is detected and replaced automatically
on the next start — you do not need to delete it by hand.

## 3. The device map

```
BACnet/IP  <host>:47809 (router 1) and <host>:47810 (router 2), IP network 822
|
+- SC-822-01   device 822001   port 47809   [router]
|   +- network 1  "MSTP-01-A"   7 devices   822011-822017
|   +- network 2  "MSTP-01-B"  18 devices   822101-822118
|
+- SC-822-02   device 822002   port 47810   [router]
|   +- network 3  "MSTP-02-A"   7 devices   822021-822027
|   +- network 4  "MSTP-02-B"  18 devices   822201-822218
|
+- CHILLER-RTAC-822 -- absent by design. Not a BACnet device.
```

50 field controllers, not 62 equipment records — 12 corridor sensors are
wired into an adjacent fan coil's controller instead of getting a
controller of their own, which is how it is actually done in the field
(a corridor sensor lands on a spare input of a nearby unit controller,
it does not get its own UC400). A device's `objectName` on the wire
(e.g. `UC400-MAU-01`) is the controller, and its `description` lists
every equipment ID it serves.

**MAC addressing:** within the inventory, controllers on a trunk are
numbered MAC 1, 2, 3... in inventory order. On the wire, that same
device sits at **MAC n + 1**, because the router's own port on that
trunk occupies MAC 1. So the first controller on `MSTP-01-A` (MAC 1 in
the inventory) answers at address `1:2` on the wire, not `1:1`.
`scripts/bacnet822-client.py locate()` does this translation for you;
if you are addressing a device by hand in YABE or another client, add 1
to the inventory MAC.

**Two routers, two ports — this is not a typo.** Two BACnet/IP
applications cannot share one UDP port: the second bind fails and
bacpypes3 retries it silently, forever, with no error surfaced. So
`SC-822-01` binds `--port` (47809) and `SC-822-02` binds `--port + 1`
(47810). **If you only search one port, you will only find one SC.**
Point a client at both 47809 and 47810 (or register both as foreign
devices) to see the whole building.

**The chiller (`CHILLER-RTAC-822`) is not on BACnet, by design.** It is
local-display only — visible at `/api/chiller/822` on the web front
end — and is not integrated to the supervisory network. This mirrors a
real job where chiller data that was never brought onto the BAS trunk
has to be read at the unit control panel, not assumed to be a BACnet
point just because everything else in the plant is. It is a design
choice recorded in the build's spec, not something left unfinished.

## 4. Connecting YABE from Windows through WSL2 NAT

The development host runs WSL2 in its default NAT mode. In that mode,
UDP broadcast does not cross the boundary between Windows and the Linux
VM, and `netsh portproxy` — the usual way to forward a port into
WSL2 — only forwards TCP, not UDP. A plain BACnet/IP discovery (which
is UDP broadcast) from a Windows client will simply see nothing, with
no error.

The fix built into the server is BBMD plus Foreign Device Registration,
which needs no environment change at all:

1. Start the server with `--bbmd` (see section 2). This makes its IP
   port a BBMD — it will accept a foreign device registration and then
   forward broadcasts to that registrant as if it were local.
2. Get the WSL2 IP address (run this **inside WSL**, not Windows):
   ```bash
   ip -4 addr show eth0
   ```
   Look for the `inet` line, e.g. `172.28.94.51/20` — the address
   before the `/` is what you register against.
3. In YABE, add a device by **Foreign Device Registration** to
   `<wsl-ip>:47809` (and, separately, `<wsl-ip>:47810` for the second
   router — see section 3). YABE then discovers both SCs and every
   device behind them normally.

This gets a Windows client working with zero changes to WSL2 network
mode. It also happens to be a real BACnet/IP skill in its own right —
BBMD and Foreign Device Registration are exactly how a supervisor
crosses a subnet boundary on a real job, not a lab-only workaround.

## 5. The mirrored-networking switch (physical supervisor on the LAN)

BBMD/FDR (section 4) solves a Windows client reaching into WSL2. It does
**not** help a **physical** device elsewhere on the LAN — a real Tracer
SC+, if shadowing gives you access to one — discover the WSL2 host,
because that traffic never touches the Windows BBMD client at all.
That case needs WSL2 itself switched to mirrored networking, where the
Linux VM shares the host's network interface directly instead of
sitting behind NAT.

1. On the **Windows** side, edit (or create)
   `C:\Users\<user>\.wslconfig` and add:
   ```ini
   [wsl2]
   networkingMode=mirrored
   ```
2. From a **Windows** terminal (PowerShell or cmd — not a shell inside
   WSL):
   ```
   wsl --shutdown
   ```

**Do this deliberately, not automatically.** `wsl --shutdown` ends
every running WSL session immediately, including this one and whatever
else you have open — there is no graceful per-window shutdown. It also
changes how WSL2's virtual network behaves, which can disturb the
Docker bridge that `open-source-stack`'s own stack (InfluxDB, Grafana,
Mosquitto — see `open-source-stack/docker-compose.yml`) depends on.
Only make this switch when you actually need a physical device on the
LAN to see the host; for a Windows-side software client (YABE, Niagara
running on Windows), the BBMD path in section 4 is simpler and does not
touch WSL2's network mode at all.

## 6. Priority array reference

This is the core mechanism to understand before touching a commandable
point, on this lab or on a real job — it is exactly how a real Tracer
SC resolves conflicting commands.

- Every commandable object (`AnalogOutput`, writable `AnalogValue`,
  `BinaryOutput`, writable `MultiStateValue`) carries a **16-slot
  priority array**. `presentValue` resolves to the value in the
  **lowest-numbered occupied slot** — priority 1 beats priority 8 beats
  priority 16.
- **Priority 8 is "Manual Operator"** — the slot a technician's
  override write lands in. This lab's test client
  (`scripts/bacnet822-client.py`) writes here by default.
- **Priority 16 is where this building's own control loop writes its
  output, every tick.** In bacpypes3, a plain attribute assignment
  (`obj.presentValue = value`) writes priority 16 — this is the
  library's documented behavior for a `Commandable` object, not a
  workaround the server has to implement.
- Because 8 is numerically lower than 16, an operator override at 8
  wins over the loop's output at 16 for as long as it is held — command
  a valve at priority 8 and the control loop cannot fight it back, even
  though it keeps trying every tick.
- **Relinquishing a priority means writing BACnet `Null` to that
  slot**, never a Python `None` — see the troubleshooting section
  below for what happens if you get this wrong. Once priority 8 is
  relinquished, `presentValue` falls through to the next occupied slot
  (usually 16, the loop). If **every** slot is `Null`, `presentValue`
  falls back to the object's `relinquishDefault`.
- `currentCommandPriority` reads back which slot currently controls the
  point — check it after a write to confirm you actually took control,
  and after a release to confirm you gave it back.

## 7. Troubleshooting

Written as symptom → cause, since that is how you will actually run
into these — three of the four are bacpypes3 0.0.102 API edges hit
while building this server, and are worth recognizing on sight.

**Reads hang, then abort with `no-response` (or a raised
`TypeError: integer network required`).**
The IP network port is missing an explicit, non-zero `networkNumber`,
or two routers are trying to bind the same UDP port (see section 3 —
each router needs its own port). Without a network number, the router
has nowhere to build the return path for a routed response and the
request times out rather than failing immediately.

**`AttributeError: not a sequence element: address`.**
An IPv4 `NetworkPortObject` was constructed with `address=` passed as a
keyword. `address` on an IPv4 port is a derived, read-only property —
the address has to be given positionally, as part of the object
identifier string (`NetworkPortObject("172.28.94.51/20:47809", ...)`).
This only applies to IPv4/IPv6 ports; the virtual MS/TP-style ports in
this server use the opposite convention — `macAddress=` and
`networkInterfaceName=` as keywords — and reject the positional form.

**A relinquish/release seems to do nothing, or crashes the point.**
The caller sent a Python `None` instead of a BACnet `Null`. `None`
produces a priority-array entry with no branch set, and the object's
internal recalculation then crashes rather than falling through to the
next priority. Always release with an explicit
`Null(())` (see `scripts/bacnet822-client.py do_release`), never bare
`None`.

**YABE (or another client) discovers nothing broadcasting from the
same WSL host the server runs on.** Expected, and not a bug in this
server: a BACnet/IP broadcast goes to the subnet broadcast address at
the *sender's own port*, so a client bound to a different port than the
server never hears it, even on the same machine — this is why
`scripts/bacnet822-client.py` seeds its routes explicitly instead of
relying on discovery. **This limitation is same-host only.** A real
client on a different host — a Windows box through BBMD (section 4), or
a physical supervisor on the LAN (section 5) — discovers normally.
