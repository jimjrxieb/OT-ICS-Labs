#!/usr/bin/env python3
"""Synthetic hospital BAS terminal console.

Simulates logging in to either the Metasys ADS or Niagara Supervisor
and navigating points, alarms, and trends from the command line.

Usage:
    python3 bas_console.py
    python3 bas_console.py --host localhost --port 8001
"""

from __future__ import annotations

import argparse
import cmd
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


# ---------------------------------------------------------------------------
# Platform language maps
# ---------------------------------------------------------------------------

PLATFORMS = {
    "metasys": {
        "name": "Metasys ADS",
        "vendor": "Johnson Controls",
        "server": "MET-ADS-01",
        "banner": (
            "\n╔══════════════════════════════════════════════════════════╗\n"
            "║  METASYS Advanced Diagnostic Script (ADS)                ║\n"
            "║  Server: MET-ADS-01 — NAS JAX Regional Medical Center    ║\n"
            "║  Operator: BAS-OPR-01  [SYNTHETIC LAB]                   ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        ),
        "equip_label": "Field Device",
        "point_label": "Object Name",
        "value_label": "Present Value",
        "alarm_label": "Alarm Summary",
        "trend_label": "Sampled Value Trend",
        "status_ok": "Normal",
        "status_alarm": "*** ALARM ***",
        "tree_header": "Site Navigator — NAS JAX Hospital > BAS Network (MET-SNE-01)",
        "point_fmt": lambda pt, val, units, status: (
            f"  {pt:<28} PV: {str(val):<10} {units:<10} [{status}]"
        ),
        "ack_word": "Acknowledge",
        "run_word": "Scenario run",
    },
    "niagara": {
        "name": "Niagara 4 Supervisor",
        "vendor": "Tridium",
        "server": "N4-SUP-01",
        "banner": (
            "\n╔══════════════════════════════════════════════════════════╗\n"
            "║  Niagara Workbench — Engineering Access                  ║\n"
            "║  Station: N4-SUP-01 — NAS JAX Regional Medical Center    ║\n"
            "║  User: eng-workbench  [SYNTHETIC LAB]                    ║\n"
            "╚══════════════════════════════════════════════════════════╝\n"
        ),
        "equip_label": "Controller",
        "point_label": "Ord (Slot)",
        "value_label": "Out",
        "alarm_label": "AlarmService Console",
        "trend_label": "History Extension Records",
        "status_ok": "ok",
        "status_alarm": "unackedAlarm",
        "tree_header": "Nav Container — station:|slot:/ > Drivers > BACnetNetwork / JACENetwork",
        "point_fmt": lambda pt, val, units, status: (
            f"  station:|slot:/Drivers/.../{pt:<22} Out: {str(val):<10} {units:<8} [{status}]"
        ),
        "ack_word": "AckState → acked",
        "run_word": "BajaScript module executed",
    },
}

SCENARIO_NAMES = [
    "normal",
    "chilled_water_degraded",
    "isolation_pressure_loss",
    "or_humidity_excursion",
]


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _checked_url(url: str) -> str:
    """Only http(s): urlopen also accepts file:// and other schemes."""
    scheme = urllib.parse.urlsplit(url).scheme
    if scheme not in ("http", "https"):
        raise ValueError(f"refusing non-HTTP URL scheme {scheme!r}: {url}")
    return url


def _get(url: str) -> dict[str, Any]:
    try:
        # Bandit B310: the URL scheme is limited to http/https by _checked_url().
        with urllib.request.urlopen(_checked_url(url), timeout=5) as resp:  # nosec B310
            return json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Cannot reach server at {url} — is it running? ({exc})") from exc


def _post(url: str) -> dict[str, Any]:
    req = urllib.request.Request(_checked_url(url), method="POST", data=b"")
    try:
        # Bandit B310: the URL scheme is limited to http/https by _checked_url().
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
            return json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise ConnectionError(f"Cannot reach server at {url} ({exc})") from exc


# ---------------------------------------------------------------------------
# Console shell
# ---------------------------------------------------------------------------

class BASConsole(cmd.Cmd):
    intro = (
        "\nSynthetic Hospital BAS Console\n"
        "Data boundary: synthetic lab only — no real hospital or PHI\n"
        "Type 'login metasys' or 'login niagara' to start.\n"
        "Type 'help' for commands.\n"
    )

    def __init__(self, base_url: str) -> None:
        super().__init__()
        self.base = base_url.rstrip("/")
        self.platform: str | None = None
        self.lang: dict[str, Any] | None = None
        self.prompt = "bas> "

    # ------------------------------------------------------------------
    # login
    # ------------------------------------------------------------------

    def do_login(self, arg: str) -> None:
        """login metasys | login niagara — connect to a BAS front-end platform."""
        plat = arg.strip().lower()
        if plat not in PLATFORMS:
            print(f"Unknown platform {plat!r}. Use: login metasys  or  login niagara")
            return
        self.platform = plat
        self.lang = PLATFORMS[plat]
        print(self.lang["banner"])
        self.prompt = f"{plat}> "
        print(f"Connected to {self.lang['name']} — {self.lang['server']}")
        print(f"Type 'ls' to list equipment, 'help' for all commands.\n")

    # ------------------------------------------------------------------
    # ls
    # ------------------------------------------------------------------

    def do_ls(self, arg: str) -> None:
        """ls [equipment] — list equipment (no arg) or points under an equipment."""
        if not self._require_login():
            return
        try:
            data = _get(f"{self.base}/api/points")
        except ConnectionError as e:
            print(f"Error: {e}")
            return

        equip_map = data.get("equipment", {})
        target = arg.strip() if arg.strip() else None

        if not target:
            print(f"\n{self.lang['tree_header']}")
            print(f"  Scenario: {data.get('scenario', '—')}  |  {data.get('data_boundary', '')}\n")
            for eq, pts in equip_map.items():
                alarm_pts = [p for p in pts if p["status"] == "alarm"]
                flag = "  *** ALARM" if alarm_pts else ""
                print(f"  {eq:<30} ({len(pts)} points){flag}")
            print()
        else:
            pts = equip_map.get(target)
            if pts is None:
                print(f"Equipment {target!r} not found. Run 'ls' to see all equipment.")
                return
            print(f"\n{self.lang['equip_label']}: {target}\n")
            for pt in pts:
                val = pt["value"]
                if pt["units"] == "bool":
                    val = "ON" if val == 1 else "OFF"
                elif val is not None:
                    val = f"{float(val):.3f}"
                status = self.lang["status_alarm"] if pt["status"] == "alarm" else self.lang["status_ok"]
                print(self.lang["point_fmt"](pt["point"], val, pt["units"], status))
            print()

    # ------------------------------------------------------------------
    # get
    # ------------------------------------------------------------------

    def do_get(self, arg: str) -> None:
        """get <point_name> — read current value and metadata for a single point."""
        if not self._require_login():
            return
        point = arg.strip()
        if not point:
            print("Usage: get <point_name>  (e.g. get AHU_OR1_SAT)")
            return
        try:
            data = _get(f"{self.base}/api/points/{point}")
        except ConnectionError as e:
            print(f"Error: {e}")
            return
        except urllib.error.HTTPError as e:
            print(f"Point not found: {point} ({e})")
            return

        lang = self.lang
        print(f"\n{lang['point_label']}: {data['point']}")
        print(f"  {lang['equip_label']}: {data['equipment']}")
        print(f"  Type:         {data['type']}")
        print(f"  {lang['value_label']}:  {data['value']} {data['units']}")
        print(f"  Normal range: {data['normal_min']} – {data['normal_max']} {data['units']}")
        print(f"  Writable:     {data['writable']}")
        print(f"  Critical:     {data['critical']}")
        status = lang["status_alarm"] if data["status"] == "alarm" else lang["status_ok"]
        print(f"  Status:       {status}")
        if "alarm" in data:
            a = data["alarm"]
            print(f"  Alarm msg:    {a.get('message')}  [priority: {a.get('priority')}]")
        print()

    # ------------------------------------------------------------------
    # alarms
    # ------------------------------------------------------------------

    def do_alarms(self, _: str) -> None:
        """alarms — list active alarms from the most recent simulator run."""
        if not self._require_login():
            return
        try:
            data = _get(f"{self.base}/api/alarms")
        except ConnectionError as e:
            print(f"Error: {e}")
            return

        lang = self.lang
        print(f"\n{lang['alarm_label']} — {data['count']} active record(s)\n")
        if data["count"] == 0:
            print(f"  No active alarms — {lang['status_ok']}\n")
            return

        bp = data.get("by_priority", {})
        if bp.get("critical"): print(f"  CRITICAL : {bp['critical']}")
        if bp.get("high"):     print(f"  HIGH     : {bp['high']}")
        if bp.get("medium"):   print(f"  MEDIUM   : {bp['medium']}")
        print()

        for i, a in enumerate(data["alarms"], 1):
            ts = a.get("timestamp", "").replace("T", " ").replace("+00:00", "Z")
            print(f"  [{i}] {a['priority'].upper():<10} {a['point']:<28} {a['equipment']}")
            print(f"       {ts}  value={a['value']} {a['units']}  range={a['normal_min']}–{a['normal_max']}")
            print(f"       {a['message']}")
            print()
        print(f"  To acknowledge: ack <number>  (e.g. ack 1)\n")

    # ------------------------------------------------------------------
    # ack
    # ------------------------------------------------------------------

    def do_ack(self, arg: str) -> None:
        """ack <alarm_number> — acknowledge an alarm (synthetic session only)."""
        if not self._require_login():
            return
        lang = self.lang
        try:
            n = int(arg.strip())
            print(f"  {lang['ack_word']} — alarm #{n} acknowledged (session only — resets on refresh)\n")
        except ValueError:
            print("Usage: ack <number>  (e.g. ack 1)")

    # ------------------------------------------------------------------
    # trends
    # ------------------------------------------------------------------

    def do_trends(self, arg: str) -> None:
        """trends <point_name> — show last trend records for a point."""
        if not self._require_login():
            return
        point = arg.strip()
        if not point:
            print("Usage: trends <point_name>  (e.g. trends CHW_SUPPLY_TEMP)")
            return
        try:
            data = _get(f"{self.base}/api/trends/{point}")
        except ConnectionError as e:
            print(f"Error: {e}")
            return
        except Exception:
            print(f"No trend data for {point!r}. Run a scenario first.")
            return

        lang = self.lang
        print(f"\n{lang['trend_label']} — {data['point']} ({data['count']} records)\n")
        print(f"  {'Timestamp':<32} {'Value':<12} Units")
        print(f"  {'-'*32} {'-'*12} -----")
        for r in data["rows"]:
            ts = r.get("timestamp", "").replace("T", " ").replace("+00:00", "Z")
            print(f"  {ts:<32} {float(r['value']):<12.4f} {r['units']}")
        print()

    # ------------------------------------------------------------------
    # run
    # ------------------------------------------------------------------

    def do_run(self, arg: str) -> None:
        """run <scenario> — trigger the simulator. Scenarios: normal, chilled_water_degraded, isolation_pressure_loss, or_humidity_excursion"""
        if not self._require_login():
            return
        scenario = arg.strip()
        if not scenario:
            print("Usage: run <scenario>")
            print("Scenarios: " + ", ".join(SCENARIO_NAMES))
            return
        if scenario not in SCENARIO_NAMES:
            print(f"Unknown scenario {scenario!r}. Valid: {', '.join(SCENARIO_NAMES)}")
            return
        print(f"  Running scenario: {scenario} ...")
        try:
            data = _post(f"{self.base}/api/run/{scenario}")
        except ConnectionError as e:
            print(f"Error: {e}")
            return

        lang = self.lang
        print(f"  {lang['run_word']} complete.")
        print(f"  Scenario:    {data['scenario']}")
        print(f"  Steps:       {data['steps']}")
        print(f"  Alarms:      {data['alarm_count']}")
        print(f"  Generated:   {data.get('generated_at', '—')}")
        print(f"  Boundary:    {data.get('data_boundary', 'synthetic lab data only')}")
        print(f"\n  Use 'ls', 'alarms', or 'trends <point>' to inspect results.\n")

    # ------------------------------------------------------------------
    # scenarios
    # ------------------------------------------------------------------

    def do_scenarios(self, _: str) -> None:
        """scenarios — list available simulator scenarios."""
        print("\nAvailable scenarios:")
        descs = {
            "normal": "All points within normal range. Baseline.",
            "chilled_water_degraded": "CHW supply temp rising, diff pressure falling, OR temp drifting up.",
            "isolation_pressure_loss": "ISO-201 room pressure drifting toward zero. Critical life-safety alarm.",
            "or_humidity_excursion": "OR-1 relative humidity rising above 60% surgical limit.",
        }
        for sc in SCENARIO_NAMES:
            print(f"  {sc:<35} {descs[sc]}")
        print()

    # ------------------------------------------------------------------
    # exit / quit
    # ------------------------------------------------------------------

    def do_exit(self, _: str) -> bool:
        """exit — disconnect and quit."""
        plat = self.lang["name"] if self.lang else "BAS Console"
        print(f"\nDisconnected from {plat}. Goodbye.\n")
        return True

    def do_quit(self, arg: str) -> bool:
        """quit — alias for exit."""
        return self.do_exit(arg)

    def do_EOF(self, _: str) -> bool:
        print()
        return self.do_exit("")

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    def _require_login(self) -> bool:
        if not self.platform:
            print("Not logged in. Use: login metasys  or  login niagara")
            return False
        return True

    def default(self, line: str) -> None:
        print(f"Unknown command: {line!r}. Type 'help' for available commands.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic hospital BAS terminal console")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=8001)
    args = parser.parse_args()
    base = f"http://{args.host}:{args.port}"
    console = BASConsole(base)
    try:
        console.cmdloop()
    except KeyboardInterrupt:
        print("\nInterrupted.")
        sys.exit(0)


if __name__ == "__main__":
    main()
