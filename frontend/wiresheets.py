"""Niagara-style Wire Sheet: function blocks wired together with links.

A Wire Sheet program is a DAG of blocks. Each block has named input and
output slots; links carry one block's output slot into another's input
slot. Evaluating a Wire Sheet resolves every block's output slots, in
dependency order, exactly once -- the same "values flow left to right
through the wiring" model Niagara uses, just without a drag-and-drop
editor.

Blocks that reference live data (ScheduleRef, PointRef) don't reach out
for it themselves -- the caller supplies a `context` dict of already-read
values, keeping this module a pure evaluator with no file or network
access of its own.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WIRESHEETS_FILE = ROOT / "data" / "input" / "wiresheets.json"

# Declared input/output slot names per block type -- used both to evaluate
# a block and to lay it out on the canvas (a block's inputs are drawn down
# its left edge, outputs down its right edge, in this order).
BLOCK_SLOTS: dict[str, dict[str, list[str]]] = {
    "Constant": {"inputs": [], "outputs": ["out"]},
    "ScheduleRef": {"inputs": [], "outputs": ["out"]},
    "PointRef": {"inputs": [], "outputs": ["out"]},
    "Select": {"inputs": ["selector", "whenTrue", "whenFalse"], "outputs": ["out"]},
    "Compare": {"inputs": ["a", "b"], "outputs": ["out"]},
    "And": {"inputs": ["a", "b"], "outputs": ["out"]},
    "Or": {"inputs": ["a", "b"], "outputs": ["out"]},
    "Not": {"inputs": ["a"], "outputs": ["out"]},
    "PointWriteRef": {"inputs": ["in"], "outputs": ["out"]},
}


def slot_spec(block_type: str) -> dict[str, list[str]]:
    return BLOCK_SLOTS.get(block_type, {"inputs": [], "outputs": ["out"]})


def load_wiresheets() -> list[dict[str, Any]]:
    if not WIRESHEETS_FILE.exists():
        return []
    return json.loads(WIRESHEETS_FILE.read_text(encoding="utf-8"))


def find_wiresheet(wiresheet_id: str) -> dict[str, Any] | None:
    for ws in load_wiresheets():
        if ws["wiresheet_id"] == wiresheet_id:
            return ws
    return None


def referenced_schedule_ids(wiresheet: dict[str, Any]) -> set[str]:
    return {
        b["config"]["schedule_id"]
        for b in wiresheet["blocks"]
        if b["type"] == "ScheduleRef"
    }


def referenced_point_names(wiresheet: dict[str, Any]) -> set[str]:
    return {
        b["config"]["point"]
        for b in wiresheet["blocks"]
        if b["type"] in ("PointRef", "PointWriteRef")
    }


def evaluate(wiresheet: dict[str, Any], context: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Resolve every block's output slots.

    context: {"schedules": {schedule_id: bool}, "points": {point_name: value}}
    Returns {block_id: {slot_name: value}}.
    """
    blocks = {b["block_id"]: b for b in wiresheet["blocks"]}
    incoming: dict[str, list[dict[str, Any]]] = {block_id: [] for block_id in blocks}
    for link in wiresheet.get("links", []):
        incoming[link["to"]].append(link)

    resolved: dict[str, dict[str, Any]] = {}

    def resolve(block_id: str, stack: frozenset[str]) -> dict[str, Any]:
        if block_id in resolved:
            return resolved[block_id]
        if block_id in stack:
            raise ValueError(f"Wire Sheet cycle detected at block {block_id!r}")
        stack = stack | {block_id}
        inputs: dict[str, Any] = {}
        for link in incoming[block_id]:
            inputs[link["to_slot"]] = resolve(link["from"], stack).get(link["from_slot"])
        out = _evaluate_block(blocks[block_id], inputs, context)
        resolved[block_id] = out
        return out

    for block_id in blocks:
        resolve(block_id, frozenset())
    return resolved


def _evaluate_block(block: dict[str, Any], inputs: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    block_type = block["type"]
    config = block.get("config", {})

    if block_type == "Constant":
        return {"out": config["value"]}
    if block_type == "ScheduleRef":
        return {"out": context.get("schedules", {}).get(config["schedule_id"])}
    if block_type == "PointRef":
        return {"out": context.get("points", {}).get(config["point"])}
    if block_type == "Select":
        selector = inputs.get("selector")
        return {"out": inputs.get("whenTrue") if selector else inputs.get("whenFalse")}
    if block_type == "Compare":
        a, b = inputs.get("a"), inputs.get("b")
        if a is None or b is None:
            return {"out": None}
        ops = {
            ">": a > b, "<": a < b, ">=": a >= b, "<=": a <= b, "==": a == b,
        }
        return {"out": bool(ops[config.get("op", ">")])}
    if block_type == "And":
        return {"out": bool(inputs.get("a")) and bool(inputs.get("b"))}
    if block_type == "Or":
        return {"out": bool(inputs.get("a")) or bool(inputs.get("b"))}
    if block_type == "Not":
        val = inputs.get("a")
        return {"out": None if val is None else not bool(val)}
    if block_type == "PointWriteRef":
        return {"out": inputs.get("in")}
    raise ValueError(f"Unknown Wire Sheet block type {block_type!r}")


CANVAS_MAX = 4000


def save_wiresheets(sheets: list[dict[str, Any]]) -> None:
    WIRESHEETS_FILE.parent.mkdir(parents=True, exist_ok=True)
    WIRESHEETS_FILE.write_text(json.dumps(sheets, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_block(block: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key in ("block_id", "type", "x", "y"):
        if key not in block:
            errors.append(f"block missing required field {key!r}")
    if errors:
        return errors

    if block["type"] not in BLOCK_SLOTS:
        errors.append(f"unknown block type {block['type']!r} (must be one of {sorted(BLOCK_SLOTS)})")
    if not (0 <= block["x"] <= CANVAS_MAX) or not (0 <= block["y"] <= CANVAS_MAX):
        errors.append(f"block {block['block_id']!r} position out of bounds (0-{CANVAS_MAX})")
    return errors


def validate_link(link: dict[str, Any], blocks_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for key in ("from", "from_slot", "to", "to_slot"):
        if key not in link:
            errors.append(f"link missing required field {key!r}")
    if errors:
        return errors

    from_block = blocks_by_id.get(link["from"])
    to_block = blocks_by_id.get(link["to"])
    if from_block is None:
        errors.append(f"link references unknown source block {link['from']!r}")
    if to_block is None:
        errors.append(f"link references unknown target block {link['to']!r}")
    if from_block is not None and link["from_slot"] not in slot_spec(from_block["type"])["outputs"]:
        errors.append(f"block {link['from']!r} has no output slot {link['from_slot']!r}")
    if to_block is not None and link["to_slot"] not in slot_spec(to_block["type"])["inputs"]:
        errors.append(f"block {link['to']!r} has no input slot {link['to_slot']!r}")
    return errors


def validate_wiresheet(
    ws: dict[str, Any],
    existing_sheets: list[dict[str, Any]],
    *,
    is_create: bool,
) -> list[str]:
    errors: list[str] = []
    for key in ("wiresheet_id", "display_name", "blocks", "links"):
        if key not in ws:
            errors.append(f"wiresheet missing required field {key!r}")
    if errors:
        return errors

    if is_create and any(w["wiresheet_id"] == ws["wiresheet_id"] for w in existing_sheets):
        errors.append(f"wiresheet_id {ws['wiresheet_id']!r} already exists")

    seen_block_ids: set[str] = set()
    for block in ws["blocks"]:
        errors.extend(validate_block(block))
        bid = block.get("block_id")
        if bid in seen_block_ids:
            errors.append(f"duplicate block_id {bid!r} on wiresheet {ws['wiresheet_id']!r}")
        seen_block_ids.add(bid)

    if errors:
        return errors

    blocks_by_id = {b["block_id"]: b for b in ws["blocks"]}
    seen_targets: set[tuple[str, str]] = set()
    for link in ws["links"]:
        errors.extend(validate_link(link, blocks_by_id))
        target = (link.get("to"), link.get("to_slot"))
        if target in seen_targets:
            errors.append(
                f"input slot {link.get('to_slot')!r} on block {link.get('to')!r} already has an incoming link"
            )
        seen_targets.add(target)

    if errors:
        return errors

    try:
        evaluate(ws, {"schedules": {}, "points": {}})
    except ValueError as exc:
        errors.append(str(exc))
    except KeyError as exc:
        errors.append(f"block config missing required key {exc}")

    return errors


def self_test() -> int:
    good_blocks = [
        {"block_id": "A", "type": "Constant", "x": 0, "y": 0, "config": {"value": 1.0}},
        {"block_id": "B", "type": "Not", "x": 100, "y": 0},
    ]
    good_links = [{"from": "A", "from_slot": "out", "to": "B", "to_slot": "a"}]
    good_ws = {"wiresheet_id": "WS1", "display_name": "WS1", "blocks": good_blocks, "links": good_links}
    assert validate_wiresheet(good_ws, [], is_create=True) == [], validate_wiresheet(good_ws, [], is_create=True)

    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": "NoSuchType", "x": 0, "y": 0}]}, [], is_create=True
    )
    assert any("unknown block type" in e for e in errs), errs

    errs = validate_wiresheet(
        {**good_ws, "links": [{"from": "A", "from_slot": "nope", "to": "B", "to_slot": "a"}]}, [], is_create=True
    )
    assert any("no output slot" in e for e in errs), errs

    errs = validate_wiresheet(
        {**good_ws, "links": good_links + [{"from": "A", "from_slot": "out", "to": "B", "to_slot": "a"}]},
        [], is_create=True,
    )
    assert any("already has an incoming link" in e for e in errs), errs

    cyclic_blocks = [
        {"block_id": "X", "type": "Not", "x": 0, "y": 0},
        {"block_id": "Y", "type": "Not", "x": 100, "y": 0},
    ]
    cyclic_links = [
        {"from": "X", "from_slot": "out", "to": "Y", "to_slot": "a"},
        {"from": "Y", "from_slot": "out", "to": "X", "to_slot": "a"},
    ]
    errs = validate_wiresheet(
        {"wiresheet_id": "WS2", "display_name": "WS2", "blocks": cyclic_blocks, "links": cyclic_links},
        [], is_create=True,
    )
    assert any("cycle" in e.lower() for e in errs), errs

    errs = validate_wiresheet(good_ws, [good_ws], is_create=True)
    assert any("already exists" in e for e in errs), errs

    print("wiresheets self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
