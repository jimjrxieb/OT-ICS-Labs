You are an AI coding agent with shell access, working at the root of a
synthetic BAS/OT training lab repo. Shut the lab down cleanly.

Steps:
1. First check BREAK/sealed/ for any sealed answer file newer than the
   last entry in BREAK/call-log.md — an unfinished 2AM Call game means a
   break may still be in place. If found, apply its restore_commands
   FIRST so the lab isn't stored broken, and note it in BREAK/call-log.md
   as "fixed by: agent (end-of-session restore)".
2. Release any stray overrides:
   check data/output/operator_overrides.json; release via
   POST /api/points/{name}/release?role=technician while the API is
   still up.
3. Stop the docker stack: open-source-stack/stop-stack.sh
4. Stop host processes: the uvicorn front end (port 8001),
   bacnet_device.py, and influx_bridge.py if running.
5. Confirm: docker ps shows no bas-* containers; nothing listening on
   8001; no bacnet_device/influx_bridge processes. Show me the checks.

Rules: never run git commands. Never delete volumes, data files, or
anything else — stop and shut down only (docker compose down -v is
FORBIDDEN; stop-stack.sh does it right). Never touch anything outside
this repo.
