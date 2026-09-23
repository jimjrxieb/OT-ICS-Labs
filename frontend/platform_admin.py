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
BACKUP_SOURCES = [
    "equipment.json", "points.json", "alarm_rules.json", "schedules.json", "wiresheets.json", "px_pages.json",
]


class BackupError(ValueError):
    """A backup that can't be trusted as a restore source."""


def _new_dist_dir(prefix: str) -> Path:
    """Create a fresh .dist directory; never reuse one.

    Names are second-resolution timestamps, so two snapshots in the same
    second would otherwise share (and overwrite) one directory while the
    log recorded two backups. A collision gets a -2, -3, ... suffix.
    """
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        suffix = "" if n == 1 else f"-{n}"
        dist_dir = BACKUP_DIR / f"{prefix}-{ts}{suffix}.dist"
        try:
            dist_dir.mkdir()
            return dist_dir
        except FileExistsError:
            n += 1


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

    dist_dir = _new_dist_dir(f"{kind}-{entity_id}")
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
    dist_dir = _new_dist_dir(station_id)
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


def read_backup_file(backup_dir: str, filename: str) -> list[Any]:
    """Load one JSON store from a recorded backup, or raise BackupError.

    Only directories the backup log recorded are readable, and they must
    resolve inside BACKUP_DIR -- a restore request can't be pointed at an
    arbitrary path. Nothing is written here; callers validate the content
    before changing any state.
    """
    if not filename or "/" in filename or "\\" in filename or ".." in filename:
        raise BackupError(f"unsafe backup filename {filename!r}")
    if backup_dir not in {e["backup_dir"] for e in load_backup_log()}:
        raise BackupError(f"{backup_dir!r} is not a recorded backup")
    dist_dir = (ROOT / backup_dir).resolve()
    if dist_dir.parent != BACKUP_DIR.resolve():
        raise BackupError(f"{backup_dir!r} is not a recorded backup")
    path = dist_dir / filename
    if not path.is_file():
        raise BackupError(f"backup {backup_dir!r} does not contain {filename}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise BackupError(f"{filename} in backup {backup_dir!r} is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise BackupError(f"{filename} in backup {backup_dir!r} must contain a JSON list")
    return data


def backups_containing(filename: str) -> list[dict[str, Any]]:
    """Recorded backups that still hold `filename` on disk, newest first.

    One row per directory (older log rows may share a directory from before
    _new_dist_dir(); the latest entry wins).
    """
    by_dir: dict[str, dict[str, Any]] = {}
    for entry in load_backup_log():
        if filename in entry.get("files", []) and (ROOT / entry["backup_dir"] / filename).is_file():
            by_dir[entry["backup_dir"]] = entry
    return sorted(by_dir.values(), key=lambda e: e["timestamp"], reverse=True)


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

    # Regression: snapshots taken within the same second used to share one
    # .dist directory, so later copies overwrote earlier ones while the log
    # still listed each as a separate backup.
    first = snapshot_single_file("platform-selftest", "SAMESEC", "schedules.json", "self-test")
    second = snapshot_single_file("platform-selftest", "SAMESEC", "schedules.json", "self-test")
    assert first["backup_dir"] != second["backup_dir"], (first, second)
    assert (ROOT / first["backup_dir"] / "schedules.json").exists()

    # Px pages are station configuration too; a Platform backup must cover them.
    assert "px_pages.json" in BACKUP_SOURCES, BACKUP_SOURCES

    # read_backup_file: the one gate every restore goes through.
    data = read_backup_file(first["backup_dir"], "schedules.json")
    assert isinstance(data, list), data

    def expect_backup_error(backup_dir: str, filename: str, needle: str) -> None:
        try:
            read_backup_file(backup_dir, filename)
        except BackupError as exc:
            assert needle in str(exc), (needle, str(exc))
            return
        raise AssertionError(f"expected BackupError containing {needle!r}")

    expect_backup_error("data/output/platform-backups/never-logged.dist", "schedules.json", "not a recorded backup")
    expect_backup_error("data/input", "schedules.json", "not a recorded backup")
    expect_backup_error(first["backup_dir"], "wiresheets.json", "does not contain wiresheets.json")
    expect_backup_error(first["backup_dir"], "../../input/schedules.json", "unsafe backup filename")

    corrupt = snapshot_single_file("platform-selftest", "CORRUPT", "schedules.json", "self-test")
    (ROOT / corrupt["backup_dir"] / "schedules.json").write_text("{not json", encoding="utf-8")
    expect_backup_error(corrupt["backup_dir"], "schedules.json", "is not valid JSON")
    (ROOT / corrupt["backup_dir"] / "schedules.json").write_text('{"a": 1}', encoding="utf-8")
    expect_backup_error(corrupt["backup_dir"], "schedules.json", "must contain a JSON list")

    listed = backups_containing("schedules.json")
    dirs = [b["backup_dir"] for b in listed]
    assert len(dirs) == len(set(dirs)), "backups_containing must list each directory once"
    assert dirs[0] == corrupt["backup_dir"], "backups_containing must list newest first"

    print("platform_admin self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
