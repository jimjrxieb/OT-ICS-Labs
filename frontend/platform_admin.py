"""Niagara-style Platform/station administration.

Station topology (data/input/stations.json) is synthetic lab
window-dressing -- Fox ports, hosts, and licenses are fictional, nothing
listens on them. The backup action is real: it snapshots data/input/
into a timestamped .dist-style directory, the same distribution-backup
idea a real Platform's Backup tool performs before any station change
(same pattern scripts/merge-submittal.py uses for DESIGN merges).
"""

from __future__ import annotations

import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "data" / "input"
STATIONS_FILE = INPUT_DIR / "stations.json"
BACKUP_DIR = ROOT / "data" / "output" / "platform-backups"
BACKUP_LOG_FILE = ROOT / "data" / "output" / "platform-backup-log.jsonl"
BACKUP_SOURCES = ["equipment.json", "points.json", "alarm_rules.json", "schedules.json", "wiresheets.json"]


def load_stations() -> list[dict[str, Any]]:
    if not STATIONS_FILE.exists():
        return []
    return json.loads(STATIONS_FILE.read_text(encoding="utf-8"))


def find_station(station_id: str) -> dict[str, Any] | None:
    for station in load_stations():
        if station["station_id"] == station_id:
            return station
    return None


def load_backup_log() -> list[dict[str, Any]]:
    if not BACKUP_LOG_FILE.exists():
        return []
    rows = []
    for line in BACKUP_LOG_FILE.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def snapshot_single_file(kind: str, entity_id: str, filename: str, operator_id: str) -> dict[str, Any]:
    """Snapshot one data/input/ file before an editor overwrites it.

    Same .dist-style pattern as take_backup(), generalized to one named
    file and a caller-supplied kind so the shared backup log can tell a
    manual Platform backup apart from an editor's automatic pre-save
    snapshot.
    """
    # Validate inputs to prevent path traversal attacks (security-standards.md rule 7)
    for label, value in (("kind", kind), ("entity_id", entity_id), ("filename", filename)):
        if "/" in value or "\\" in value or ".." in value:
            raise ValueError(f"unsafe {label} for backup snapshot: {value!r}")

    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dist_dir = BACKUP_DIR / f"{kind}-{entity_id}-{ts}.dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    src = INPUT_DIR / filename
    copied = []
    if src.exists():
        shutil.copy2(src, dist_dir / filename)
        copied.append(filename)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "kind": kind,
        "entity_id": entity_id,
        "operator_id": operator_id,
        "backup_dir": str(dist_dir.relative_to(ROOT)),
        "files": copied,
        "data_boundary": "synthetic lab platform backup only",
    }
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with BACKUP_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def take_backup(station_id: str, operator_id: str) -> dict[str, Any]:
    """Snapshot data/input/ into a timestamped .dist-style directory."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    dist_dir = BACKUP_DIR / f"{station_id}-{ts}.dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    copied = []
    for name in BACKUP_SOURCES:
        src = INPUT_DIR / name
        if src.exists():
            shutil.copy2(src, dist_dir / name)
            copied.append(name)

    entry = {
        "kind": "platform",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "station_id": station_id,
        "operator_id": operator_id,
        "backup_dir": str(dist_dir.relative_to(ROOT)),
        "files": copied,
        "data_boundary": "synthetic lab platform backup only",
    }
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with BACKUP_LOG_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True) + "\n")
    return entry


def self_test() -> int:
    """Backup snapshot mechanics: real file copy, real log entry, correct shape."""
    probe = INPUT_DIR / "schedules.json"
    assert probe.exists(), "self-test requires data/input/schedules.json to exist"

    entry = snapshot_single_file("platform-selftest", "SELFTEST", "schedules.json", "self-test")
    assert entry["kind"] == "platform-selftest", entry
    assert entry["entity_id"] == "SELFTEST", entry
    assert entry["files"] == ["schedules.json"], entry

    dist_dir = ROOT / entry["backup_dir"]
    assert dist_dir.is_dir(), f"backup dir missing: {dist_dir}"
    assert (dist_dir / "schedules.json").exists(), "backed-up file missing"

    log_entries = load_backup_log()
    assert any(e["backup_dir"] == entry["backup_dir"] for e in log_entries), "backup not logged"

    # Validate path-traversal rejection on entity_id with ".."
    try:
        snapshot_single_file("platform-selftest", "../escape", "schedules.json", "self-test")
        assert False, "expected ValueError for path-traversal entity_id"
    except ValueError:
        pass

    # Validate path-traversal rejection on entity_id with "/"
    try:
        snapshot_single_file("platform-selftest", "a/b", "schedules.json", "self-test")
        assert False, "expected ValueError for entity_id containing a slash"
    except ValueError:
        pass

    print("platform_admin self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
