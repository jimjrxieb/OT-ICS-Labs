You are an AI coding agent with shell access, working at the root of a
synthetic BAS/OT training lab repo (you should see simulator/, frontend/,
open-source-stack/, BREAK/, data/ here — confirm before proceeding).

Set up and start the full lab environment, then prove it's healthy.

Steps:
1. Read README.md for context.
2. Install dependencies:
   pip install -r requirements.txt
   pip install -r open-source-stack/requirements.txt
   (Under pyenv, pip may exit nonzero with a shim-rehash permission error
   even though every package installed fine. If the output says
   "requirement already satisfied" or shows successful installs, verify
   with a runtime import instead of re-running pip — that exit code is
   benign.)
3. Generate baseline data:
   python3 simulator/bas_sim.py --scenario normal --steps 12
4. Start the BAS front end in the background (port 8001):
   scripts/start-frontend.sh
5. Start the docker containers (Mosquitto, InfluxDB, Grafana, Node-RED):
   open-source-stack/start-stack.sh
   (Requires docker compose. If docker is unavailable, say so and continue
   with just the front end — the Trouble Call game works without docker.)
6. Start the two pipeline processes yourself, in the background, from the
   repo root — start-stack.sh does NOT start these, it only prints
   instructions:
   python3 open-source-stack/bacnet_device.py   (background, capture output)
   python3 open-source-stack/influx_bridge.py   (background, capture output)
7. Wait ~60 seconds for data to flow, then verify and SHOW me the results:
   - curl http://127.0.0.1:8001/api/points returns 200 with point data
   - scripts/run-smoke-test.sh passes
   - docker ps shows bas-mosquitto, bas-influxdb, bas-grafana, bas-nodered up
   - pgrep finds bacnet_device.py and influx_bridge.py running
   - the influx_bridge output shows points flowing end-to-end, e.g. a line
     like "MQTT 24/24 → InfluxDB 24/24" — processes existing is not the
     same as data flowing
8. Print me a short "you're ready" summary with the URLs to open:
   http://localhost:8001 (BAS front end — try /metasys and /niagara),
   http://localhost:3000 (Grafana), http://localhost:1880 (Node-RED).

Rules: never run git commands. Never touch anything outside this repo.
Everything binds to localhost only. If a step fails, show me the actual
error output and your fix — don't silently work around it.
