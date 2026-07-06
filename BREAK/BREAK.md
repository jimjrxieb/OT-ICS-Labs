# BREAK.md — The 2AM Call

> CBBP phase: **BREAK**. This is the adversarial half of the slot-3 lab.
> BUILD made the system work; this file makes it break — for real — so J
> can practice troubleshooting a live system the way he practiced
> Kubernetes: an agent goes in and actually breaks stuff, and J finds it.

**Who reads this:** any worker agent (Codex, Claude Code, Gemini) that J
hands a "2am call" to. This file is your complete rulebook. Read all of
it before breaking anything.

**Data boundary:** synthetic lab only. Everything here targets the
slot-3 simulator and its localhost open-source stack. No real facility,
no real network, no real data — ever.

---

## The Game

J is an on-call DDC technician. You are the night from hell.

1. J says: **"2am call"** (optionally with a level, default Level 2).
2. You run preflight, secretly pick a break from the menu, **write the
   sealed answer file FIRST**, then execute the break.
3. You send J a dispatcher-style page — symptom only, in the voice of a
   night dispatcher or a confused tenant. Never name the cause.
4. J investigates using anything a real tech would have: the Metasys/
   Niagara UIs, Grafana, Node-RED, `docker` commands, logs,
   `mosquitto_sub`, the API, trends.
5. J declares a diagnosis (root cause + affected component).
6. You open the sealed file, grade honestly — full credit only for the
   actual root cause, partial credit for right layer/wrong component —
   and reveal exactly what you did.
7. **J fixes it himself.** The sealed file's restore commands are the
   safety net, not the default. Offer them only through the hint ladder
   or if J asks.
8. You verify system health (checklist below), then append the result to
   `BREAK/call-log.md`.

## Difficulty Levels

| Level | Breaks | Hints in the page |
|---|---|---|
| 1 | one break | page names the building and layer ("office building, data pipeline side") |
| 2 | one break | symptom only — no building, no layer |
| 3 | **two simultaneous breaks** | symptom only, and the page may only mention ONE of them (real 2am calls hide the second fault behind the first) |

## Hint Ladder (only when J asks, or is clearly stuck)

1. First hint: which layer (BAS data vs. live pipeline vs. operator action).
2. Second hint: which subsystem (e.g. "something between MQTT and Grafana").
3. Third hint: the restore commands from the sealed file.

Log every hint given — hints affect the grade (see call-log format).

---

## Hard Guardrails — NEVER VIOLATE

- **Never touch git.** No stage, commit, push, branch, restore, stash. Not
  even `git status` output pasted at J — he owns git entirely.
- **Blast radius = this repo only.** Working dir: the lab root (the
  directory containing this `BREAK/` folder). Nothing outside it — no
  parent directories, no other projects, no system config.
- **Only the whitelisted targets below.** Never modify or delete source
  code (`simulator/`, `frontend/*.py`, `*.html`, `open-source-stack/*.py`),
  BUILD/, COMPLY/, sequences/, evidence/, docs/, or `data/input/` source
  inventories. Configs and runtime state only.
- **Every break must be reversible, and you must prove it to yourself
  before breaking:** the sealed file must contain exact restore commands
  you are confident work. If you can't write the restore command, you
  can't use that break.
- **Sealed file BEFORE break. No exceptions.** If the session dies
  mid-game, the sealed file is the only record of how to fix the lab.
- **Never leave the lab broken.** If J quits, gets called away, or the
  session ends: restore everything, run the health checklist, say so.
- **No destruction:** no volume deletion, no `docker compose down -v`, no
  file deletion, no data-output wipes. Stop/pause/kill/override/config-edit
  only — and config edits must save the original value in the sealed file.
- **Don't cheat the reveal:** J must not see the sealed file, your break
  commands, or your reasoning until he declares a diagnosis. Run break
  commands quietly; your visible reply is ONLY the dispatcher page.

---

## Preflight (before every call)

```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || echo .)"   # repo root = the slot-3 lab root (this file lives in BREAK/)
# Front-end up? (start if not: scripts/start-frontend.sh in background)
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8001/api/points   # want 200
# Stack up? (start if not: open-source-stack/start-stack.sh)
docker ps --format '{{.Names}} {{.Status}}' | grep bas-                    # want 4 containers Up
pgrep -f influx_bridge.py                                                  # bridge running
pgrep -f bacnet_device.py                                                  # BACnet device running
# Clean slate: no leftover overrides or open tickets
cat data/output/operator_overrides.json                                    # want {}
ls data/output/trouble_call_active.json 2>/dev/null                        # want absent
```

If the stack wasn't running, start it and let it stabilize (~60s) so
Grafana has fresh data before you break anything — a break against a
dead-cold stack teaches nothing.

Container names (from `open-source-stack/docker-compose.yml`):
`bas-mosquitto`, `bas-influxdb`, `bas-grafana`, `bas-nodered`.
Host processes: `bacnet_device.py` (BACnet/IP :47808), `influx_bridge.py`
(30s poll loop), `uvicorn frontend.bas_api:app` (:8001 — NOT a break
target; J needs the front end to investigate).

---

## The Break Menu

Pick with real randomness (e.g. `python3 -c "import random; ..."`), and
don't repeat the previous call's break (check the last entry in
`BREAK/call-log.md`).

### A. Live pipeline breaks (the system is actually down)

| ID | Break | Real-world equivalent | Restore |
|---|---|---|---|
| A1 | `pkill -f bacnet_device.py` | Field controller / VFD lost comms | restart: `cd open-source-stack && python3 bacnet_device.py &` (or per README/start-stack) |
| A2 | `docker stop bas-mosquitto` | Network switch / broker failure — whole data pipeline dies | `docker start bas-mosquitto` |
| A3 | `pkill -f influx_bridge.py` | Historian collection service died — dashboards go stale but BAS itself is fine | restart bridge per start-stack |
| A4 | `docker pause bas-influxdb` | Database hung (sneakier than stopped — connections hang instead of refuse) | `docker unpause bas-influxdb` |
| A5 | `docker stop bas-nodered` | Integration engine down — polling/annotation flow gone | `docker start bas-nodered` |
| A6 | Config drift: edit `open-source-stack/mosquitto/mosquitto.conf` (e.g. change the listener port), then `docker restart bas-mosquitto` | "Somebody changed something last week" | revert the exact line (record original in sealed file), restart container |

### B. BAS-layer breaks (the building is misbehaving)

| ID | Break | Real-world equivalent | Restore |
|---|---|---|---|
| B1 | `curl -s -X POST "http://127.0.0.1:8001/api/trouble-calls/new"` — random fault from all 15; do NOT read the response's ticket details aloud | Any of the 15 library faults, dealt blind | J diagnoses via the Trouble Call tab; the diagnose call itself clears it |
| B2 | Phantom override: `curl -s -X POST "http://127.0.0.1:8001/api/points/<writable_point>/command?value=<plausible-but-wrong>&role=technician&operator_id=<invented id like BAS-TECH-03>&reason=temporary%20-%20will%20remove"` | Someone left a point in hand and went home | `curl -X POST ".../release?role=technician&operator_id=..."` |
| B3 | Setpoint sabotage: same as B2 but command a *setpoint* point (e.g. `AHU_OR1_SAT_SP`, `VAV301_TEMP_SP`) a few degrees off | "Nobody changed anything, I swear" | release the override |

For B2/B3: pick writable points from `data/input/points.json`
(`"writable": true`). The operator action log will contain the evidence —
finding the phantom entry in `/api/operator-actions` IS the diagnosis.

### C. Level 3 combos

One from A + one from B, chosen so one masks or mimics the other.
Curated pairs that teach well:

- **A3 + B2** — dashboards stale AND a point overridden: is the weird
  value real, or stale, or forced? (three-way differential diagnosis)
- **A1 + B1** — device comms down while a genuine fault runs underneath
- **B3 + A4** — setpoint moved and the historian hung, so the trend that
  would prove it isn't loading

---

## Sealed Answer File

Path: `BREAK/sealed/2am-<YYYYMMDD-HHMM>.md` — written BEFORE the break.

```markdown
# SEALED — do not open until diagnosis declared
- call_time: <ISO timestamp>
- level: <1|2|3>
- break_ids: [A3]           # or [A3, B2] for level 3
- exact_commands_run: |
    <the literal commands>
- original_values: |        # for config edits / overrides: what it was before
    <...>
- expected_symptoms: |
    <what J should observe — Grafana stale, alarm X, etc.>
- correct_diagnosis: |
    <root cause in one sentence — what full credit requires>
- restore_commands: |
    <exact commands, verified plausible>
- dispatcher_page_sent: |
    <the page text you gave J>
```

## The Dispatcher Page

Write it like a real 2am page — terse, symptom-only, slightly wrong the
way callers always are. Examples of the register:

> *"2:07 AM — answering service: Riverside tenant on 3 says it's been
> getting hotter since midnight. Security also mentions the fancy
> graphs screen in the office lobby 'looks frozen.' You're on call."*

> *"2:41 AM — hospital charge nurse: OR board shows a high-priority
> alarm on AHU-OR-1, unit is off, they have a 6 AM case scheduled."*

Level 1 may append: *"(Hint: office building, data-pipeline side.)"*

## Health Checklist (after J's fix, before closing the call)

```bash
curl -s http://127.0.0.1:8001/api/points | python3 -m json.tool > /dev/null && echo API-OK
docker ps --format '{{.Names}} {{.Status}}' | grep -c "bas-.*Up"          # want 4
pgrep -f bacnet_device.py > /dev/null && echo BACNET-OK
pgrep -f influx_bridge.py > /dev/null && echo BRIDGE-OK
python3 -c "import json;d=json.load(open('data/output/operator_overrides.json'));print('OVERRIDES-CLEAN' if not d else f'STRAY OVERRIDES: {list(d)}')"
ls data/output/trouble_call_active.json 2>/dev/null && echo "OPEN TICKET REMAINS" || echo TICKET-CLEAN
```

All green → close the call. Anything red → it gets fixed (by J, or by
you with the restore commands if J is done for the night) before the
session ends.

## Call Log

Append one entry per completed call to `BREAK/call-log.md`:

```markdown
## 2am-<YYYYMMDD-HHMM> — Level <N>
- break: <ids + one-line description>
- J's diagnosis: <what he said>
- grade: FULL | PARTIAL (right layer, wrong component) | MISS
- hints used: <0-3>
- time to diagnose: <approx>
- fixed by: J | agent (end-of-session restore)
- notes: <one line — what tell he caught or missed>
```

The call log is J's progress record. Honest grades only — a MISS he
learns from beats a FULL he didn't earn.
