#!/usr/bin/env python3
"""Merge an APPROVED DESIGN/ submittal into the live lab inventories.

This is the "construction" step of the design-assist track: an approved
engineering package gets built into data/input/, so the simulator
generates data for it and the front ends show it.

Usage:
    python3 scripts/merge-submittal.py DESIGN/submittals/P-01/rev-B            # dry run
    python3 scripts/merge-submittal.py DESIGN/submittals/P-01/rev-B --apply    # build it
    python3 scripts/merge-submittal.py --self-test

Gates (both must pass, dry run or not):
  1. Schema-clean per scripts/validate-submittal.py (also blocks
     double-merges: once built, IDs collide with the live inventory).
  2. The submittal dir contains review-<rev>.md for THIS rev with
     disposition APPROVED or APPROVED_AS_NOTED. No approval, no build.

--apply backs up the three inventories to DESIGN/merged-backups/<ts>/,
appends the proposed records (text-append — existing lines untouched),
logs the merge to DESIGN/merge-log.md, and prints restore commands.

Synthetic training lab tooling. Standard library only. Never runs git.
"""

import datetime
import importlib.util
import json
import re
import shutil
import sys
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent

INVENTORIES = {
    "proposed_equipment.json": "data/input/equipment.json",
    "proposed_points.json": "data/input/points.json",
    "proposed_alarms.json": "data/input/alarm_rules.json",
}
APPROVED = {"APPROVED", "APPROVED_AS_NOTED"}


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_submittal", Path(__file__).with_name("validate-submittal.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def check_approval(rev_dir):
    """Return (disposition, review_path) or (None, reason)."""
    review = rev_dir.parent / f"review-{rev_dir.name}.md"
    if not review.exists():
        return None, f"no review found for this rev (expected {review})"
    m = re.search(r"disposition:\s*([A-Z_]+)", review.read_text())
    if not m:
        return None, f"{review.name} has no 'disposition:' line"
    return m.group(1), review


def load_proposals(rev_dir):
    """Return {deliverable filename: list of records} for files present."""
    proposals = {}
    for fname in INVENTORIES:
        fpath = rev_dir / fname
        if fpath.exists():
            proposals[fname] = json.loads(fpath.read_text())
    return proposals


def append_to_list_file(path, records):
    """Append records to a flat JSON list file, preserving existing text."""
    text = path.read_text()
    stripped = text.rstrip()
    if not stripped.endswith("]"):
        raise ValueError(f"{path}: expected file to end with ']'")
    body = stripped[:-1].rstrip()
    lines = ",\n".join(
        "  " + json.dumps(r, separators=(", ", ": ")) for r in records)
    sep = "" if body.endswith("[") else ","
    new_text = body + sep + "\n" + lines + "\n]\n"
    json.loads(new_text)  # round-trip guard before touching disk
    path.write_text(new_text)


def append_to_equipment_file(path, records):
    """Append records inside the 'equipment' list of equipment.json."""
    text = path.read_text()
    idx = text.rindex("\n  ]")  # closing bracket of the equipment list
    lines = ",\n".join(
        "    " + json.dumps(r, separators=(", ", ": ")) for r in records)
    new_text = text[:idx] + ",\n" + lines + text[idx:]
    doc = json.loads(new_text)  # round-trip guard
    if len(doc["equipment"]) != len(json.loads(text)["equipment"]) + len(records):
        raise ValueError(f"{path}: post-merge equipment count mismatch")
    path.write_text(new_text)


def merge(rev_dir, apply=False, lab_root=LAB_ROOT, out=print):
    """Run gates, then (if apply) build the submittal into the inventories.

    Returns process exit code.
    """
    rev_dir = Path(rev_dir).resolve()
    lab_root = Path(lab_root).resolve()
    try:
        rel = rev_dir.relative_to(lab_root / "DESIGN" / "submittals")
    except ValueError:
        out(f"BLOCKED: {rev_dir} is not inside DESIGN/submittals/")
        return 1
    if len(rel.parts) != 2:
        out("BLOCKED: point me at a rev dir, e.g. DESIGN/submittals/P-01/rev-B")
        return 1
    project, rev = rel.parts

    validator = _load_validator()
    errors = validator.validate(rev_dir, lab_root)
    if errors:
        out(f"BLOCKED: submittal is not schema-clean ({len(errors)} finding(s)):")
        for e in errors:
            out(f"  {e}")
        out("If this rev was already merged, the ID collisions above are "
            "the double-merge guard doing its job.")
        return 1
    out("GATE 1 PASS: schema-clean vs live inventories")

    disposition, detail = check_approval(rev_dir)
    if disposition is None:
        out(f"BLOCKED: {detail}")
        return 1
    if disposition not in APPROVED:
        out(f"BLOCKED: {detail.name} disposition is {disposition} — "
            "only APPROVED / APPROVED_AS_NOTED packages get built")
        return 1
    out(f"GATE 2 PASS: {detail.name} disposition {disposition}")

    proposals = load_proposals(rev_dir)
    if not proposals:
        out("BLOCKED: no proposed_*.json deliverables in this rev")
        return 1
    out("")
    for fname, records in proposals.items():
        target = INVENTORIES[fname]
        ids = [r.get("id") or r.get("point") for r in records]
        out(f"  {fname} -> {target}: {len(records)} record(s)")
        out(f"    {', '.join(str(i) for i in ids)}")

    if not apply:
        out("\nDRY RUN — nothing written. Re-run with --apply to build it.")
        return 0

    ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = lab_root / "DESIGN" / "merged-backups" / ts
    backup_dir.mkdir(parents=True)
    for target in set(INVENTORIES.values()):
        shutil.copy2(lab_root / target, backup_dir)
    out(f"\nBacked up inventories to {backup_dir.relative_to(lab_root)}/")

    for fname, records in proposals.items():
        target = lab_root / INVENTORIES[fname]
        if fname == "proposed_equipment.json":
            append_to_equipment_file(target, records)
        else:
            append_to_list_file(target, records)
        out(f"MERGED {fname} -> {INVENTORIES[fname]}")

    log = lab_root / "DESIGN" / "merge-log.md"
    counts = "; ".join(f"{len(v)} from {k}" for k, v in proposals.items())
    entry = (f"\n## {project} {rev} — merged {ts}\n"
             f"- disposition: {disposition} ({detail.name})\n"
             f"- records: {counts}\n"
             f"- backup: DESIGN/merged-backups/{ts}/\n"
             f"- restore: cp DESIGN/merged-backups/{ts}/*.json data/input/\n")
    if not log.exists():
        log.write_text("# Merge Log\n\nOne entry per approved submittal "
                       "built into the live lab.\n")
    log.write_text(log.read_text() + entry)

    out(f"\nDone. {project} {rev} is built into the lab. Next:")
    out("  python3 simulator/bas_sim.py --scenario normal --steps 12")
    out("  scripts/start-frontend.sh   # then check your points in the tree")
    out(f"To un-build: cp DESIGN/merged-backups/{ts}/*.json data/input/")
    return 0


# ---------------------------------------------------------------- self-test

def _fixture_lab(root):
    (root / "data/input").mkdir(parents=True)
    (root / "data/input/equipment.json").write_text(
        '{\n  "facilities": [\n    {"id": "office", "name": "Fixture Tower"}'
        '\n  ],\n  "equipment": [\n'
        '    {"id": "RTU-9", "type": "AHU", "serves": "Fixture", '
        '"vendor": "JCI", "controller": "X", "purdue_level": 1, '
        '"facility": "office"}\n  ]\n}\n')
    (root / "data/input/points.json").write_text(
        '[\n  {"point": "RTU9_SAT", "equipment": "RTU-9", "type": "AI", '
        '"units": "F", "normal_min": 50, "normal_max": 60, "writable": false, '
        '"critical": false, "trend_interval_sec": 60, "facility": "office"}\n]\n')
    (root / "data/input/alarm_rules.json").write_text(
        '[\n  {"point": "RTU9_SAT", "condition": "outside_normal", '
        '"priority": "medium", "message": "fixture"}\n]\n')
    sub = root / "DESIGN/submittals/P-99/rev-A"
    sub.mkdir(parents=True)
    (sub / "proposed_equipment.json").write_text(json.dumps([{
        "id": "VAV-901", "type": "VAV", "serves": "Fixture Zone",
        "vendor": "JCI", "controller": "X9", "purdue_level": 1,
        "facility": "office"}]))
    (sub / "proposed_points.json").write_text(json.dumps([{
        "point": "VAV901_TEMP", "equipment": "VAV-901", "type": "AI",
        "units": "F", "normal_min": 70, "normal_max": 76, "writable": False,
        "critical": False, "trend_interval_sec": 300, "facility": "office"}]))
    (sub / "proposed_alarms.json").write_text(json.dumps([{
        "point": "VAV901_TEMP", "condition": "outside_normal",
        "priority": "medium", "message": "fixture zone temp"}]))
    return sub


def self_test():
    import tempfile
    failures = []
    quiet = lambda *a: None  # noqa: E731

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        rev = _fixture_lab(root)

        # 1. No review -> blocked, even as dry run.
        if merge(rev, apply=False, lab_root=root, out=quiet) == 0:
            failures.append("merge allowed with no review file")

        # 2. Unapproved disposition -> blocked.
        review = rev.parent / "review-rev-A.md"
        review.write_text("- disposition: REVISE_AND_RESUBMIT\n")
        if merge(rev, apply=False, lab_root=root, out=quiet) == 0:
            failures.append("merge allowed with REVISE_AND_RESUBMIT")

        # 3. Approved dry run -> exit 0, nothing written.
        review.write_text("- disposition: APPROVED\n")
        before = (root / "data/input/points.json").read_text()
        if merge(rev, apply=False, lab_root=root, out=quiet) != 0:
            failures.append("approved dry run should pass")
        if (root / "data/input/points.json").read_text() != before:
            failures.append("dry run wrote to inventories")

        # 4. Apply -> records land, files parse, style preserved.
        if merge(rev, apply=True, lab_root=root, out=quiet) != 0:
            failures.append("approved apply should succeed")
        eq = json.loads((root / "data/input/equipment.json").read_text())
        pts = json.loads((root / "data/input/points.json").read_text())
        alarms = json.loads((root / "data/input/alarm_rules.json").read_text())
        if [e["id"] for e in eq["equipment"]] != ["RTU-9", "VAV-901"]:
            failures.append(f"equipment not merged: {eq['equipment']}")
        if [p["point"] for p in pts] != ["RTU9_SAT", "VAV901_TEMP"]:
            failures.append(f"points not merged: {pts}")
        if len(alarms) != 2:
            failures.append(f"alarms not merged: {alarms}")
        pts_text = (root / "data/input/points.json").read_text()
        if '\n  {"point": "VAV901_TEMP"' not in pts_text:
            failures.append("merged point not in compact per-line style")
        if not list((root / "DESIGN/merged-backups").iterdir()):
            failures.append("no backup dir created")
        if "P-99 rev-A" not in (root / "DESIGN/merge-log.md").read_text():
            failures.append("merge-log.md missing entry")

        # 5. Double merge -> blocked by ID collision.
        if merge(rev, apply=True, lab_root=root, out=quiet) == 0:
            failures.append("double merge was not blocked")

        # 6. Backup actually restores.
        backup = next((root / "DESIGN/merged-backups").iterdir())
        for f in backup.glob("*.json"):
            shutil.copy2(f, root / "data/input" / f.name)
        pts = json.loads((root / "data/input/points.json").read_text())
        if [p["point"] for p in pts] != ["RTU9_SAT"]:
            failures.append("backup restore did not roll back points")

        # 7. Path outside DESIGN/submittals -> blocked.
        if merge(root / "data/input", apply=False, lab_root=root,
                 out=quiet) == 0:
            failures.append("merge allowed outside DESIGN/submittals")

    if failures:
        for f in failures:
            print(f"SELF-TEST FAIL: {f}")
        return 1
    print("SELF-TEST PASS")
    return 0


def main(argv):
    args = [a for a in argv[1:] if a != "--apply"]
    apply = "--apply" in argv
    if len(args) != 1 or args[0] in ("-h", "--help"):
        print(__doc__)
        return 2
    if args[0] == "--self-test":
        return self_test()
    return merge(args[0], apply=apply)


if __name__ == "__main__":
    sys.exit(main(sys.argv))
