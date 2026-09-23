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


REQUIRED_CONFIG_KEYS: dict[str, list[str]] = {
    "Constant": ["value"],
    "ScheduleRef": ["schedule_id"],
    "PointRef": ["point"],
    "PointWriteRef": ["point"],
}

# Config keys that get used as lookup/reference identifiers elsewhere
# (referenced_point_names(), referenced_schedule_ids() put these straight
# into a set) and so must be strings. Constant's "value" is checked
# separately in validate_block_config() (number or boolean).
STRING_CONFIG_KEYS: dict[str, list[str]] = {
    "ScheduleRef": ["schedule_id"],
    "PointRef": ["point"],
    "PointWriteRef": ["point"],
}


COMPARE_OPS = (">", "<", ">=", "<=", "==")


def validate_block_config(block: dict[str, Any]) -> list[str]:
    block_type = block.get("type")
    if not isinstance(block_type, str):
        return []
    if block_type == "Compare":
        return _validate_compare_config(block)
    required = REQUIRED_CONFIG_KEYS.get(block_type, [])
    if not required:
        return []
    config = block.get("config")
    if not isinstance(config, dict):
        return [f"block {block.get('block_id')!r} config must be an object"]

    errors = [
        f"block {block.get('block_id')!r} of type {block_type!r} is missing required config key {key!r}"
        for key in required
        if key not in config
    ]
    if errors:
        return errors

    for key in STRING_CONFIG_KEYS.get(block_type, []):
        if not isinstance(config[key], str):
            errors.append(
                f"block {block.get('block_id')!r} config key {key!r} must be a string, got {config[key]!r}"
            )

    # A Constant feeds Compare/Select/Boolean inputs, so only numbers and
    # booleans make sense -- a string would compare as a TypeError, and a
    # null would read as "no value" downstream.
    if block_type == "Constant" and not isinstance(config["value"], (int, float, bool)):
        errors.append(
            f"block {block.get('block_id')!r} config key 'value' must be a number or boolean, got {config['value']!r}"
        )
    return errors


def _validate_compare_config(block: dict[str, Any]) -> list[str]:
    # op is optional (evaluation defaults to ">"), but a present op must be
    # one the evaluator knows, or the save succeeds and evaluation KeyErrors.
    config = block.get("config")
    if not isinstance(config, dict) or "op" not in config:
        return []
    if config["op"] not in COMPARE_OPS:
        return [
            f"block {block.get('block_id')!r} config key 'op' must be one of {list(COMPARE_OPS)}, got {config['op']!r}"
        ]
    return []


def validate_block_references(
    block: dict[str, Any],
    known_points: set[str] | None,
    known_schedules: set[str] | None,
) -> list[str]:
    """Reject point/schedule references the station doesn't have.

    Only called once config shape has already validated, so the reference
    keys are present and are strings. A None set means the caller didn't
    supply that inventory, and that kind of reference is not checked.
    """
    block_type = block["type"]
    if block_type in ("PointRef", "PointWriteRef") and known_points is not None:
        point = block["config"]["point"]
        if point not in known_points:
            return [f"block {block['block_id']!r} references unknown point {point!r}"]
    if block_type == "ScheduleRef" and known_schedules is not None:
        schedule_id = block["config"]["schedule_id"]
        if schedule_id not in known_schedules:
            return [f"block {block['block_id']!r} references unknown schedule {schedule_id!r}"]
    return []


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

    if not isinstance(block["block_id"], str) or not block["block_id"].strip():
        errors.append(f"block_id must be a non-blank string, got {block['block_id']!r}")
    if not isinstance(block["type"], str) or block["type"] not in BLOCK_SLOTS:
        errors.append(f"unknown block type {block['type']!r} (must be one of {sorted(BLOCK_SLOTS)})")
    if not isinstance(block["x"], (int, float)) or not isinstance(block["y"], (int, float)):
        errors.append(f"block {block['block_id']!r} has non-numeric x/y position")
    elif not (0 <= block["x"] <= CANVAS_MAX) or not (0 <= block["y"] <= CANVAS_MAX):
        errors.append(f"block {block['block_id']!r} position out of bounds (0-{CANVAS_MAX})")
    return errors


def validate_link(link: dict[str, Any], blocks_by_id: dict[str, dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for key in ("from", "from_slot", "to", "to_slot"):
        if key not in link:
            errors.append(f"link missing required field {key!r}")
    if errors:
        return errors

    if not all(isinstance(link[key], str) for key in ("from", "from_slot", "to", "to_slot")):
        errors.append("link 'from'/'from_slot'/'to'/'to_slot' must all be strings")
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
    known_points: set[str] | None = None,
    known_schedules: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    for key in ("wiresheet_id", "display_name", "blocks", "links"):
        if key not in ws:
            errors.append(f"wiresheet missing required field {key!r}")
    if errors:
        return errors

    # Shape first: restore passes whole records from backup files, which
    # never went through request-body typing.
    for key in ("wiresheet_id", "display_name"):
        if not isinstance(ws[key], str):
            errors.append(f"{key} must be a string")
    for key in ("blocks", "links"):
        if not isinstance(ws[key], list) or not all(isinstance(item, dict) for item in ws[key]):
            errors.append(f"{key} must be a list of objects")
    if errors:
        return errors

    if not ws["wiresheet_id"].strip():
        errors.append("wiresheet_id must not be blank")
    elif "/" in ws["wiresheet_id"] or "\\" in ws["wiresheet_id"] or ".." in ws["wiresheet_id"]:
        errors.append(f"wiresheet_id {ws['wiresheet_id']!r} contains unsafe characters")

    if is_create and any(w["wiresheet_id"] == ws["wiresheet_id"] for w in existing_sheets):
        errors.append(f"wiresheet_id {ws['wiresheet_id']!r} already exists")

    seen_block_ids: set[str] = set()
    for block in ws["blocks"]:
        errors.extend(validate_block(block))
        errors.extend(validate_block_config(block))
        bid = block.get("block_id")
        if isinstance(bid, str):
            if bid in seen_block_ids:
                errors.append(f"duplicate block_id {bid!r} on wiresheet {ws['wiresheet_id']!r}")
            seen_block_ids.add(bid)

    if errors:
        return errors

    for block in ws["blocks"]:
        errors.extend(validate_block_references(block, known_points, known_schedules))

    blocks_by_id = {b["block_id"]: b for b in ws["blocks"] if isinstance(b.get("block_id"), str)}
    seen_targets: set[tuple[str, str]] = set()
    for link in ws["links"]:
        errors.extend(validate_link(link, blocks_by_id))
        to_val, to_slot_val = link.get("to"), link.get("to_slot")
        if isinstance(to_val, str) and isinstance(to_slot_val, str):
            target = (to_val, to_slot_val)
            if target in seen_targets:
                errors.append(f"input slot {to_slot_val!r} on block {to_val!r} already has an incoming link")
            seen_targets.add(target)

    if errors:
        return errors

    try:
        evaluate(ws, {"schedules": {}, "points": {}})
    except ValueError as exc:
        errors.append(str(exc))
    except KeyError as exc:
        errors.append(f"block config missing required key {exc}")
    except TypeError as exc:
        errors.append(f"block evaluation type error: {exc}")

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

    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": ["not", "a", "string"], "x": 0, "y": 0}]},
        [], is_create=True,
    )
    assert any("unknown block type" in e for e in errs), errs

    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": "Constant", "x": "bad", "y": 0, "config": {"value": 1.0}}]},
        [], is_create=True,
    )
    assert any("non-numeric" in e for e in errs), errs

    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": ["not", "a", "string"], "type": "Constant", "x": 0, "y": 0, "config": {"value": 1.0}}]},
        [], is_create=True,
    )
    assert any("block_id must be a non-blank string" in e for e in errs), errs

    # Fix 1: PointWriteRef with empty config must be rejected at validate_wiresheet,
    # not silently pass and blow up the read path later.
    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": "PointWriteRef", "x": 0, "y": 0, "config": {}}]},
        [], is_create=True,
    )
    assert any("missing required config key 'point'" in e for e in errs), errs

    # Fix 2a: a link with a non-string from/to must be rejected, not raise TypeError.
    errs = validate_wiresheet(
        {**good_ws, "links": [{"from": ["A"], "from_slot": "out", "to": "B", "to_slot": "a"}]},
        [], is_create=True,
    )
    assert any("must all be strings" in e for e in errs), errs

    # Fix 2c: a string Constant feeding a Compare must be rejected, not raise
    # TypeError. Since Layer 1.5 it is caught earlier, by the Constant value check.
    mismatched_blocks = [
        {"block_id": "C1", "type": "Constant", "x": 0, "y": 0, "config": {"value": "not_a_number"}},
        {"block_id": "C2", "type": "Constant", "x": 0, "y": 50, "config": {"value": 5}},
        {"block_id": "CMP", "type": "Compare", "x": 100, "y": 0, "config": {"op": ">"}},
    ]
    mismatched_links = [
        {"from": "C1", "from_slot": "out", "to": "CMP", "to_slot": "a"},
        {"from": "C2", "from_slot": "out", "to": "CMP", "to_slot": "b"},
    ]
    errs = validate_wiresheet(
        {"wiresheet_id": "WS3", "display_name": "WS3", "blocks": mismatched_blocks, "links": mismatched_links},
        [], is_create=True,
    )
    assert any("config key 'value' must be a number or boolean" in e for e in errs), errs

    # Layer 1.5: Constant values must be numbers or booleans -- no strings,
    # nulls, or containers.
    for bad_value in ("72", None, [1], {"v": 1}):
        errs = validate_wiresheet(
            {**good_ws, "blocks": [{"block_id": "A", "type": "Constant", "x": 0, "y": 0,
                                      "config": {"value": bad_value}}], "links": []},
            [], is_create=True,
        )
        assert any("config key 'value' must be a number or boolean" in e for e in errs), (bad_value, errs)

    # Layer 1.5: Compare's op is optional, but when present must be a real operator.
    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": "Compare", "x": 0, "y": 0,
                                  "config": {"op": "=>"}}], "links": []},
        [], is_create=True,
    )
    assert any("config key 'op' must be one of" in e for e in errs), errs
    for good_op in (">", "<", ">=", "<=", "=="):
        errs = validate_wiresheet(
            {**good_ws, "blocks": [{"block_id": "A", "type": "Compare", "x": 0, "y": 0,
                                      "config": {"op": good_op}}], "links": []},
            [], is_create=True,
        )
        assert errs == [], (good_op, errs)

    # Layer 1.5: when the caller supplies the known points/schedules, a
    # reference to anything else is rejected instead of silently resolving
    # to null at runtime.
    ref_ws = {**good_ws, "links": [], "blocks": [
        {"block_id": "P", "type": "PointRef", "x": 0, "y": 0, "config": {"point": "RTU1_SATT"}},
        {"block_id": "W", "type": "PointWriteRef", "x": 0, "y": 50, "config": {"point": "NOPE_SP"}},
        {"block_id": "S", "type": "ScheduleRef", "x": 0, "y": 100, "config": {"schedule_id": "NO_SUCH_SCHED"}},
    ]}
    errs = validate_wiresheet(ref_ws, [], is_create=True,
                              known_points={"RTU1_SAT"}, known_schedules={"OFFICE_OCCUPANCY"})
    assert any("references unknown point 'RTU1_SATT'" in e for e in errs), errs
    assert any("references unknown point 'NOPE_SP'" in e for e in errs), errs
    assert any("references unknown schedule 'NO_SUCH_SCHED'" in e for e in errs), errs

    ok_ref_ws = {**good_ws, "links": [], "blocks": [
        {"block_id": "P", "type": "PointRef", "x": 0, "y": 0, "config": {"point": "RTU1_SAT"}},
        {"block_id": "S", "type": "ScheduleRef", "x": 0, "y": 100, "config": {"schedule_id": "OFFICE_OCCUPANCY"}},
    ]}
    errs = validate_wiresheet(ok_ref_ws, [], is_create=True,
                              known_points={"RTU1_SAT"}, known_schedules={"OFFICE_OCCUPANCY"})
    assert errs == [], errs

    # Regression: PointWriteRef/PointRef/ScheduleRef config values that are
    # present but not strings (e.g. a list) must be rejected, not silently
    # pass validation and later crash referenced_point_names()/
    # referenced_schedule_ids() with an unhashable-type TypeError.
    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": "PointWriteRef", "x": 0, "y": 0,
                                  "config": {"point": ["RTU1_SAT"]}}]},
        [], is_create=True,
    )
    assert any("config key 'point' must be a string" in e for e in errs), errs

    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": "PointRef", "x": 0, "y": 0,
                                  "config": {"point": 42}}]},
        [], is_create=True,
    )
    assert any("config key 'point' must be a string" in e for e in errs), errs

    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "A", "type": "ScheduleRef", "x": 0, "y": 0,
                                  "config": {"schedule_id": {"nested": "dict"}}}]},
        [], is_create=True,
    )
    assert any("config key 'schedule_id' must be a string" in e for e in errs), errs

    # Numeric and boolean Constant values are legitimate and must still pass.
    for good_value in (5, 55.0, -0.01, True, False):
        errs = validate_wiresheet(
            {**good_ws, "blocks": [{"block_id": "A", "type": "Constant", "x": 0, "y": 0,
                                      "config": {"value": good_value}}], "links": []},
            [], is_create=True,
        )
        assert errs == [], (good_value, errs)

    # Fix 3: blank wiresheet_id and block_id must be rejected.
    errs = validate_wiresheet({**good_ws, "wiresheet_id": "   "}, [], is_create=True)
    assert any("wiresheet_id must not be blank" in e for e in errs), errs

    errs = validate_wiresheet(
        {**good_ws, "blocks": [{"block_id": "  ", "type": "Not", "x": 0, "y": 0}]},
        [], is_create=True,
    )
    assert any("block_id must be a non-blank string" in e for e in errs), errs

    # Restore feeds whole records from backup files straight into this
    # validator (no request-body typing), so malformed shapes must come back
    # as errors, not AttributeError/TypeError.
    for label, bad_ws, needle in [
        ("blocks not a list", {**good_ws, "blocks": "oops"}, "blocks must be a list of objects"),
        ("block not an object", {**good_ws, "blocks": [42]}, "blocks must be a list of objects"),
        ("links not a list", {**good_ws, "links": {"a": 1}}, "links must be a list of objects"),
        ("id not a string", {**good_ws, "wiresheet_id": 7}, "wiresheet_id must be a string"),
        ("name not a string", {**good_ws, "display_name": None}, "display_name must be a string"),
    ]:
        errs = validate_wiresheet(bad_ws, [], is_create=True)
        assert any(needle in e for e in errs), (label, errs)

    print("wiresheets self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
