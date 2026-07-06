You are an AI coding agent with shell access, working at the root of a
synthetic BAS/OT training lab repo. Something in the lab is broken,
stale, or in an unknown state — maybe a 2AM Call game ended badly, maybe
a container died, maybe an override got left behind. Bring it back to a
verified healthy baseline.

Steps:
1. Diagnose current state (show me what you find):
   - Front end: curl http://127.0.0.1:8001/api/points (want 200)
   - Containers: docker ps — want bas-mosquitto, bas-influxdb,
     bas-grafana, bas-nodered all Up (not paused, not exited)
   - Host processes: pgrep -f bacnet_device.py and pgrep -f influx_bridge.py
   - Stray overrides: data/output/operator_overrides.json should be {}
   - Open trouble-call ticket: data/output/trouble_call_active.json
     should not exist
   - Check BREAK/sealed/ for any sealed answer file NEWER than the last
     entry in BREAK/call-log.md — that means an unfinished game left a
     break in place. Read the sealed file and use its restore_commands.
   - Config drift: git diff --stat is FORBIDDEN (no git commands) —
     instead check open-source-stack/mosquitto/mosquitto.conf and
     docker-compose.yml against what the running services expect if
     symptoms point there.
2. Fix everything you found: unpause/start containers, restart dead
   processes, release stray overrides via the API
   (POST /api/points/{name}/release?role=technician), clear abandoned
   tickets per the sealed file, apply recorded restore commands.
3. Regenerate a clean baseline: python3 simulator/bas_sim.py --scenario normal --steps 12
4. Run the full health checklist from BREAK/BREAK.md and show me every
   result. Run scripts/run-smoke-test.sh.
5. Summarize: what was broken, what you did, current state.

Rules: never run git commands. Never touch anything outside this repo.
Fix by restarting/restoring — never by deleting data or source files.
