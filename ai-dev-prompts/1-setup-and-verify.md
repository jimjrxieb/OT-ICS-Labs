You are an AI coding agent with shell access, working at the root of a
synthetic BAS/OT training lab repo (you should see simulator/, frontend/,
open-source-stack/, BREAK/, data/ here — confirm before proceeding).

Set up and start the full lab environment, then prove it's healthy.

Steps:
1. Read README.md for context.
2. Install dependencies:
   pip install -r requirements.txt
   pip install -r open-source-stack/requirements.txt
3. Generate baseline data:
   python3 simulator/bas_sim.py --scenario normal --steps 12
4. Start the BAS front end in the background (port 8001):
   scripts/start-frontend.sh
5. Start the docker data pipeline (Mosquitto, InfluxDB, Grafana, Node-RED,
   plus the BACnet device and Influx bridge):
   open-source-stack/start-stack.sh
   (Requires docker compose. If docker is unavailable, say so and continue
   with just the front end — the Trouble Call game works without docker.)
6. Wait ~60 seconds for data to flow, then verify and SHOW me the results:
   - curl http://127.0.0.1:8001/api/points returns 200 with point data
   - scripts/run-smoke-test.sh passes
   - docker ps shows bas-mosquitto, bas-influxdb, bas-grafana, bas-nodered up
   - pgrep finds bacnet_device.py and influx_bridge.py running
7. Print me a short "you're ready" summary with the URLs to open:
   http://localhost:8001 (BAS front end — try /metasys and /niagara),
   http://localhost:3000 (Grafana), http://localhost:1880 (Node-RED).

Rules: never run git commands. Never touch anything outside this repo.
Everything binds to localhost only. If a step fails, show me the actual
error output and your fix — don't silently work around it.
