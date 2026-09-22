"""Niagara-style Px graphic pages: bound widgets positioned on a canvas.

A Px page just lays out widgets and says which point each one is bound
to -- resolving what a widget currently shows is bas_api.py's job (it
already knows how to resolve a point's effective value and what's
driving it). This module only owns the page layout.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PX_PAGES_FILE = ROOT / "data" / "input" / "px_pages.json"


def load_px_pages() -> list[dict[str, Any]]:
    if not PX_PAGES_FILE.exists():
        return []
    return json.loads(PX_PAGES_FILE.read_text(encoding="utf-8"))


def find_px_page(px_id: str) -> dict[str, Any] | None:
    for page in load_px_pages():
        if page["px_id"] == px_id:
            return page
    return None


KNOWN_WIDGET_KINDS = {"gauge", "value", "bool"}
CANVAS_MAX = 4000


def save_px_pages(pages: list[dict[str, Any]]) -> None:
    PX_PAGES_FILE.parent.mkdir(parents=True, exist_ok=True)
    PX_PAGES_FILE.write_text(json.dumps(pages, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_widget(widget: dict[str, Any], valid_points: set[str]) -> list[str]:
    errors: list[str] = []
    for key in ("widget_id", "kind", "point", "label", "x", "y"):
        if key not in widget:
            errors.append(f"widget missing required field {key!r}")
    if errors:
        return errors

    if not isinstance(widget["widget_id"], str) or not widget["widget_id"].strip():
        errors.append(f"widget_id must be a non-blank string, got {widget['widget_id']!r}")
    if not isinstance(widget["kind"], str) or widget["kind"] not in KNOWN_WIDGET_KINDS:
        errors.append(
            f"unknown widget kind {widget['kind']!r} (must be one of {sorted(KNOWN_WIDGET_KINDS)})"
        )
    if not isinstance(widget["point"], str) or widget["point"] not in valid_points:
        errors.append(f"widget {widget['widget_id']!r} references unknown point {widget['point']!r}")
    if not isinstance(widget["x"], (int, float)) or not isinstance(widget["y"], (int, float)):
        errors.append(f"widget {widget['widget_id']!r} has non-numeric x/y position")
    elif not (0 <= widget["x"] <= CANVAS_MAX) or not (0 <= widget["y"] <= CANVAS_MAX):
        errors.append(f"widget {widget['widget_id']!r} position out of bounds (0-{CANVAS_MAX})")
    return errors


def validate_page(
    page: dict[str, Any],
    existing_pages: list[dict[str, Any]],
    valid_points: set[str],
    *,
    is_create: bool,
) -> list[str]:
    errors: list[str] = []
    for key in ("px_id", "display_name", "widgets"):
        if key not in page:
            errors.append(f"page missing required field {key!r}")
    if errors:
        return errors

    if not page["px_id"].strip():
        errors.append("px_id must not be blank")
    elif "/" in page["px_id"] or "\\" in page["px_id"] or ".." in page["px_id"]:
        errors.append(f"px_id {page['px_id']!r} contains unsafe characters")

    if is_create and any(p["px_id"] == page["px_id"] for p in existing_pages):
        errors.append(f"px_id {page['px_id']!r} already exists")

    seen_widget_ids: set[str] = set()
    for widget in page["widgets"]:
        errors.extend(validate_widget(widget, valid_points))
        wid = widget.get("widget_id")
        if isinstance(wid, str):
            if wid in seen_widget_ids:
                errors.append(f"duplicate widget_id {wid!r} on page {page['px_id']!r}")
            seen_widget_ids.add(wid)

    return errors


def self_test() -> int:
    valid_points = {"RTU1_SAT", "RTU1_SAT_SP"}
    good_widget = {"widget_id": "w1", "kind": "value", "point": "RTU1_SAT", "label": "SAT", "x": 10, "y": 10}
    assert validate_widget(good_widget, valid_points) == [], validate_widget(good_widget, valid_points)

    errs = validate_widget({**good_widget, "kind": "nonsense"}, valid_points)
    assert any("unknown widget kind" in e for e in errs), errs

    errs = validate_widget({**good_widget, "point": "NOT_A_REAL_POINT"}, valid_points)
    assert any("unknown point" in e for e in errs), errs

    errs = validate_widget({**good_widget, "x": 99999}, valid_points)
    assert any("out of bounds" in e for e in errs), errs

    errs = validate_widget({"widget_id": "w2", "kind": "value"}, valid_points)
    assert any("missing required field" in e for e in errs), errs

    existing = [{"px_id": "PAGE1", "display_name": "Page 1", "widgets": []}]
    good_page = {"px_id": "PAGE2", "display_name": "Page 2", "widgets": [good_widget]}
    assert validate_page(good_page, existing, valid_points, is_create=True) == []

    errs = validate_page({"px_id": "PAGE1", "display_name": "Dup", "widgets": []}, existing, valid_points, is_create=True)
    assert any("already exists" in e for e in errs), errs

    errs = validate_page(
        {"px_id": "PAGE3", "display_name": "P3", "widgets": [good_widget, good_widget]},
        existing, valid_points, is_create=True,
    )
    assert any("duplicate widget_id" in e for e in errs), errs

    errs = validate_widget({**good_widget, "x": "not_a_number"}, valid_points)
    assert any("non-numeric" in e for e in errs), errs

    # Fix 2b: a widget with a non-string widget_id must be rejected, not raise TypeError.
    errs = validate_widget({**good_widget, "widget_id": ["not", "a", "string"]}, valid_points)
    assert any("widget_id must be a non-blank string" in e for e in errs), errs

    errs = validate_page(
        {"px_id": "PAGE4", "display_name": "P4", "widgets": [{**good_widget, "widget_id": ["not", "a", "string"]}]},
        existing, valid_points, is_create=True,
    )
    assert any("widget_id must be a non-blank string" in e for e in errs), errs

    # Fix 3: blank px_id and widget_id must be rejected.
    errs = validate_widget({**good_widget, "widget_id": "   "}, valid_points)
    assert any("widget_id must be a non-blank string" in e for e in errs), errs

    errs = validate_page(
        {"px_id": "   ", "display_name": "Blank", "widgets": []}, existing, valid_points, is_create=True,
    )
    assert any("px_id must not be blank" in e for e in errs), errs

    errs = validate_page(
        {"px_id": "PAGE/5", "display_name": "Unsafe", "widgets": []}, existing, valid_points, is_create=True,
    )
    assert any("unsafe characters" in e for e in errs), errs

    print("px_pages self-test passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
