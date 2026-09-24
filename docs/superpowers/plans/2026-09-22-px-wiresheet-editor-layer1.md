# Px Graphics & Wire Sheet Editor — Layer 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Px Graphics and Wire Sheet editable for the first time — create a page/sheet, add a widget/block, wire a link, save it, back it up — replacing today's 100%-read-only surfaces.

**Architecture:** Two new mutation-owning functions (validate + save) added to the existing `px_pages.py` and `wiresheets.py` read modules, six new role-gated `POST` endpoints in `bas_api.py` following the codebase's existing action-suffixed convention, and plain-JS forms added to the existing Px Graphics / Wire Sheet tabs in `niagara.html`. No canvas interaction, no drag, no new files for data storage — Layer 2 (a separate later plan) adds the spatial UI over this same foundation.

**Tech Stack:** Python 3.11 stdlib + FastAPI (existing), plain JS with no build step or CDN (existing `niagara.html` convention), Node.js for JS test assertions (no npm deps).

**Spec:** `docs/superpowers/specs/2026-09-22-px-wiresheet-editor-design.md`

## Global Constraints

- All six new endpoints are `POST`, action-suffixed paths, role-gated via the existing `_require_command_role()` (`technician`/`admin` only, 403 otherwise) — never `PUT` (spec §3 decision 1).
- `create`/`backup` endpoints take FastAPI `Query(...)` params; `save` endpoints take a JSON body via a `pydantic.BaseModel` — matching the one existing precedent (`DiagnosisRequest`) (spec §3 decision 4).
- Every mutation calls `_append_operator_action()` with a new action type (spec §4): `px_page_created`, `px_page_saved`, `wiresheet_created`, `wiresheet_saved`. Backup actions log their own `backup_dir`.
- Every `save` snapshots the prior file version first via `platform_admin.snapshot_single_file()`, before writing (spec §3 decision 3). The existing manual `POST /api/platform/backup` action stays separate and untouched.
- Validation failures return HTTP 400 with body `{"detail": {"errors": ["...", "..."]}}` — specific, field-named messages, never a generic "validation failed" (spec §5).
- Block/widget kind enums are read from the single existing source of truth (`wiresheets.BLOCK_SLOTS`) — never re-declared (spec §9 risk 2).
- No pytest anywhere in this repo. Python modules get a `self_test() -> int` function wired to `--self-test` (matching `simulator/model822.py`'s exact pattern). New JS gets real assertions run via Node, no DOM/browser dependency for the parts under test.
- No new third-party dependencies (Python or JS).
- Everything stays synthetic-lab-only, `127.0.0.1`-bound — no real facility/vendor data, per the parent repo's data boundary rule.

---

### Task 1: `platform_admin.py` — generalized backup snapshot

**Files:**
- Modify: `frontend/platform_admin.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `snapshot_single_file(kind: str, entity_id: str, filename: str, operator_id: str) -> dict[str, Any]` — used by Task 4 and Task 5. Returned dict shape: `{"timestamp": str, "kind": str, "entity_id": str, "operator_id": str, "backup_dir": str, "files": list[str], "data_boundary": str}`.

- [ ] **Step 1: Add `import sys` and the generalized snapshot function**

Add `import sys` to the top imports. Add this function anywhere after `load_backup_log()`:

```python
def snapshot_single_file(kind: str, entity_id: str, filename: str, operator_id: str) -> dict[str, Any]:
    """Snapshot one data/input/ file before an editor overwrites it.

    Same .dist-style pattern as take_backup(), generalized to one named
    file and a caller-supplied kind so the shared backup log can tell a
    manual Platform backup apart from an editor's automatic pre-save
    snapshot.
    """
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
```

- [ ] **Step 2: Tag the existing manual backup with `kind: "platform"`**

In `take_backup()`, find the `entry = {...}` dict and add `"kind": "platform",` as its first key, so the shared log can distinguish manual platform backups from editor auto-backups:

```python
    entry = {
        "kind": "platform",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "station_id": station_id,
        "operator_id": operator_id,
        "backup_dir": str(dist_dir.relative_to(ROOT)),
        "files": copied,
        "data_boundary": "synthetic lab platform backup only",
    }
```

- [ ] **Step 3: Add `self_test()` and the `--self-test` entry point**

Add at the end of the file:

```python
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

    print("platform_admin self-test passed")
    return 0


if __name__ == "__main__":
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
```

- [ ] **Step 4: Run it**

Run: `python3 frontend/platform_admin.py --self-test`
Expected: `platform_admin self-test passed`, exit code 0

- [ ] **Step 5: Commit**

```bash
git add frontend/platform_admin.py
git commit -m "feat(bas-sim): add generalized backup snapshot for the px/wiresheet editors"
```

---

### Task 2: `px_pages.py` — validation and write path

**Files:**
- Modify: `frontend/px_pages.py`

**Interfaces:**
- Consumes: nothing new
- Produces: `save_px_pages(pages: list[dict]) -> None`, `validate_widget(widget: dict, valid_points: set[str]) -> list[str]`, `validate_page(page: dict, existing_pages: list[dict], valid_points: set[str], *, is_create: bool) -> list[str]` — all used by Task 5. `KNOWN_WIDGET_KINDS: set[str]` and `CANVAS_MAX: int` module constants.

- [ ] **Step 1: Add constants, `save_px_pages`, and validation functions**

Append to `frontend/px_pages.py`:

```python
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

    if widget["kind"] not in KNOWN_WIDGET_KINDS:
        errors.append(
            f"unknown widget kind {widget['kind']!r} (must be one of {sorted(KNOWN_WIDGET_KINDS)})"
        )
    if widget["point"] not in valid_points:
        errors.append(f"widget {widget['widget_id']!r} references unknown point {widget['point']!r}")
    if not (0 <= widget["x"] <= CANVAS_MAX) or not (0 <= widget["y"] <= CANVAS_MAX):
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

    if is_create and any(p["px_id"] == page["px_id"] for p in existing_pages):
        errors.append(f"px_id {page['px_id']!r} already exists")

    seen_widget_ids: set[str] = set()
    for widget in page["widgets"]:
        errors.extend(validate_widget(widget, valid_points))
        wid = widget.get("widget_id")
        if wid in seen_widget_ids:
            errors.append(f"duplicate widget_id {wid!r} on page {page['px_id']!r}")
        seen_widget_ids.add(wid)

    return errors
```

- [ ] **Step 2: Add `self_test()` and the `--self-test` entry point**

```python
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

    print("px_pages self-test passed")
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(self_test() if "--self-test" in sys.argv else 0)
```

- [ ] **Step 3: Run it**

Run: `python3 frontend/px_pages.py --self-test`
Expected: `px_pages self-test passed`, exit code 0

- [ ] **Step 4: Commit**

```bash
git add frontend/px_pages.py
git commit -m "feat(bas-sim): add px_pages validation and write path"
```

---

### Task 3: `wiresheets.py` — validation and write path

**Files:**
- Modify: `frontend/wiresheets.py`

**Interfaces:**
- Consumes: existing `BLOCK_SLOTS`, `slot_spec()`, `evaluate()` (unchanged)
- Produces: `save_wiresheets(sheets: list[dict]) -> None`, `validate_block(block: dict) -> list[str]`, `validate_link(link: dict, blocks_by_id: dict) -> list[str]`, `validate_wiresheet(ws: dict, existing_sheets: list[dict], *, is_create: bool) -> list[str]` — used by Task 4. `CANVAS_MAX: int` module constant.

- [ ] **Step 1: Add `import sys`, constants, `save_wiresheets`, and validation functions**

Add `import sys` to the top imports. Append:

```python
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
```

- [ ] **Step 2: Add `self_test()` and the `--self-test` entry point**

```python
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
```

- [ ] **Step 3: Run it**

Run: `python3 frontend/wiresheets.py --self-test`
Expected: `wiresheets self-test passed`, exit code 0

- [ ] **Step 4: Commit**

```bash
git add frontend/wiresheets.py
git commit -m "feat(bas-sim): add wiresheets validation and write path, reusing evaluate() for cycle detection"
```

---

### Task 4: `bas_api.py` — Wire Sheet write endpoints + block-types endpoint

**Files:**
- Modify: `frontend/bas_api.py`

**Interfaces:**
- Consumes: `wiresheets.load_wiresheets()`, `wiresheets.validate_wiresheet()`, `wiresheets.save_wiresheets()`, `wiresheets.find_wiresheet()`, `wiresheets.BLOCK_SLOTS` (Task 3); `platform_admin.snapshot_single_file()` (Task 1); existing `_require_command_role()`, `_append_operator_action()`
- Produces: `POST /api/wiresheets`, `POST /api/wiresheets/{id}/save`, `POST /api/wiresheets/{id}/backup`, `GET /api/wiresheets/block-types` — consumed by Task 7 (frontend)

**⚠️ Route-ordering gotcha:** FastAPI matches routes in registration order. `GET /api/wiresheets/block-types` MUST be registered **before** the existing `@app.get("/api/wiresheets/{wiresheet_id}")` (currently line 454), or the literal path `block-types` will be captured as `{wiresheet_id}` and hit the wrong handler, returning a 404.

- [ ] **Step 1: Add the `WireSheetSaveRequest` model**

Near the existing `class DiagnosisRequest(BaseModel):` (around line 37), add:

```python
class WireSheetSaveRequest(BaseModel):
    blocks: list[dict[str, Any]]
    links: list[dict[str, Any]]
```

- [ ] **Step 2: Add `GET /api/wiresheets/block-types` immediately after `GET /api/wiresheets` (before the existing `GET /api/wiresheets/{wiresheet_id}`)**

Insert right after the existing `get_wiresheets()` function (ends around line 451) and before `@app.get("/api/wiresheets/{wiresheet_id}")`:

```python
@app.get("/api/wiresheets/block-types")
def get_wiresheet_block_types() -> dict[str, Any]:
    """Known Wire Sheet block types and their input/output slots, for the editor's Add Block/Add Link forms."""
    return {"block_types": wiresheets.BLOCK_SLOTS}
```

- [ ] **Step 3: Add the three write endpoints after the existing `GET /api/wiresheets/{wiresheet_id}` (after line 489, before `@app.get("/api/px")`)**

```python
@app.post("/api/wiresheets")
def create_wiresheet(
    wiresheet_id: str,
    display_name: str,
    description: str | None = None,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Create a new, empty Wire Sheet."""
    _require_command_role(role)
    sheets = wiresheets.load_wiresheets()
    new_sheet = {
        "wiresheet_id": wiresheet_id,
        "display_name": display_name,
        "ord": f"station:|slot:/WireSheet/{wiresheet_id}",
        "description": description,
        "blocks": [],
        "links": [],
    }
    errors = wiresheets.validate_wiresheet(new_sheet, sheets, is_create=True)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    sheets.append(new_sheet)
    wiresheets.save_wiresheets(sheets)
    _append_operator_action({
        "action": "wiresheet_created",
        "wiresheet_id": wiresheet_id,
        "role": role,
        "operator_id": operator_id,
    })
    return new_sheet


@app.post("/api/wiresheets/{wiresheet_id}/save")
def save_wiresheet(
    wiresheet_id: str,
    body: WireSheetSaveRequest,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Replace a Wire Sheet's blocks and links."""
    _require_command_role(role)
    sheets = wiresheets.load_wiresheets()
    existing = next((w for w in sheets if w["wiresheet_id"] == wiresheet_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Wire Sheet {wiresheet_id!r} not found")

    candidate = {**existing, "blocks": body.blocks, "links": body.links}
    errors = wiresheets.validate_wiresheet(candidate, sheets, is_create=False)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    platform_admin.snapshot_single_file("wiresheet-editor", wiresheet_id, "wiresheets.json", operator_id)
    updated = [candidate if w["wiresheet_id"] == wiresheet_id else w for w in sheets]
    wiresheets.save_wiresheets(updated)
    _append_operator_action({
        "action": "wiresheet_saved",
        "wiresheet_id": wiresheet_id,
        "role": role,
        "operator_id": operator_id,
        "block_count": len(body.blocks),
        "link_count": len(body.links),
    })
    return candidate


@app.post("/api/wiresheets/{wiresheet_id}/backup")
def backup_wiresheet(
    wiresheet_id: str,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Explicit backup of the Wire Sheet store before hand-editing."""
    _require_command_role(role)
    if wiresheets.find_wiresheet(wiresheet_id) is None:
        raise HTTPException(status_code=404, detail=f"Wire Sheet {wiresheet_id!r} not found")
    entry = platform_admin.snapshot_single_file("wiresheet-editor", wiresheet_id, "wiresheets.json", operator_id)
    _append_operator_action({
        "action": "wiresheet_backup",
        "wiresheet_id": wiresheet_id,
        "role": role,
        "operator_id": operator_id,
        "backup_dir": entry["backup_dir"],
    })
    return entry
```

- [ ] **Step 4: Start the server and exercise the new endpoints manually**

Run: `scripts/start-frontend.sh` (background it or open a second shell), then:

```bash
curl -s -X POST "http://127.0.0.1:8001/api/wiresheets/block-types" -o /dev/null -w "%{http_code}\n"   # expect 405 (GET-only)
curl -s "http://127.0.0.1:8001/api/wiresheets/block-types" | python3 -m json.tool | head -5

curl -s -X POST "http://127.0.0.1:8001/api/wiresheets?wiresheet_id=TEST_WS&display_name=Test&role=technician"
curl -s -X POST "http://127.0.0.1:8001/api/wiresheets?wiresheet_id=TEST_WS&display_name=Test&role=technician"   # expect 400, "already exists"
curl -s -X POST "http://127.0.0.1:8001/api/wiresheets/TEST_WS/save?role=technician" \
  -H "Content-Type: application/json" \
  -d '{"blocks":[{"block_id":"A","type":"Constant","x":0,"y":0,"config":{"value":1.0}}],"links":[]}'
curl -s -X POST "http://127.0.0.1:8001/api/wiresheets/TEST_WS/backup?role=technician"
curl -s "http://127.0.0.1:8001/api/wiresheets/TEST_WS"
```

Expected: block-types returns the known type map; create succeeds once then 400s on the duplicate; save returns the updated sheet with one block; backup returns a `backup_dir` under `data/output/platform-backups/`; the final read shows the saved block. Manually remove the `TEST_WS` entry from `data/input/wiresheets.json` afterward (it's a real file write) unless you want it kept for continued testing.

- [ ] **Step 5: Commit**

```bash
git add frontend/bas_api.py
git commit -m "feat(bas-sim): add Wire Sheet create/save/backup endpoints and block-types listing"
```

---

### Task 5: `bas_api.py` — Px write endpoints

**Files:**
- Modify: `frontend/bas_api.py`

**Interfaces:**
- Consumes: `px_pages.load_px_pages()`, `px_pages.validate_page()`, `px_pages.save_px_pages()`, `px_pages.find_px_page()` (Task 2); `platform_admin.snapshot_single_file()` (Task 1); existing `_require_command_role()`, `_append_operator_action()`, `_load_input_points()`
- Produces: `POST /api/px`, `POST /api/px/{id}/save`, `POST /api/px/{id}/backup` — consumed by Task 6 (frontend)

- [ ] **Step 1: Add the `PxSaveRequest` model**

Next to `WireSheetSaveRequest` from Task 4:

```python
class PxSaveRequest(BaseModel):
    widgets: list[dict[str, Any]]
```

- [ ] **Step 2: Add the three write endpoints after the existing `GET /api/px/{px_id}` (after line 536, before `@app.get("/api/roles")`)**

```python
@app.post("/api/px")
def create_px_page(
    px_id: str,
    display_name: str,
    facility: str | None = None,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Create a new, empty Px page."""
    _require_command_role(role)
    pages = px_pages.load_px_pages()
    new_page = {
        "px_id": px_id,
        "display_name": display_name,
        "ord": f"station:|slot:/Px/{px_id}",
        "facility": facility,
        "widgets": [],
    }
    valid_points = {pt["point"] for pt in _load_input_points()}
    errors = px_pages.validate_page(new_page, pages, valid_points, is_create=True)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})
    pages.append(new_page)
    px_pages.save_px_pages(pages)
    _append_operator_action({
        "action": "px_page_created",
        "px_id": px_id,
        "role": role,
        "operator_id": operator_id,
    })
    return new_page


@app.post("/api/px/{px_id}/save")
def save_px_page(
    px_id: str,
    body: PxSaveRequest,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Replace a Px page's widgets."""
    _require_command_role(role)
    pages = px_pages.load_px_pages()
    existing = next((p for p in pages if p["px_id"] == px_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Px page {px_id!r} not found")

    candidate = {**existing, "widgets": body.widgets}
    valid_points = {pt["point"] for pt in _load_input_points()}
    errors = px_pages.validate_page(candidate, pages, valid_points, is_create=False)
    if errors:
        raise HTTPException(status_code=400, detail={"errors": errors})

    platform_admin.snapshot_single_file("px-editor", px_id, "px_pages.json", operator_id)
    updated = [candidate if p["px_id"] == px_id else p for p in pages]
    px_pages.save_px_pages(updated)
    _append_operator_action({
        "action": "px_page_saved",
        "px_id": px_id,
        "role": role,
        "operator_id": operator_id,
        "widget_count": len(body.widgets),
    })
    return candidate


@app.post("/api/px/{px_id}/backup")
def backup_px_page(
    px_id: str,
    role: str = Query(...),
    operator_id: str = Query("eng-workbench"),
) -> dict[str, Any]:
    """Explicit backup of the Px page store before hand-editing."""
    _require_command_role(role)
    if px_pages.find_px_page(px_id) is None:
        raise HTTPException(status_code=404, detail=f"Px page {px_id!r} not found")
    entry = platform_admin.snapshot_single_file("px-editor", px_id, "px_pages.json", operator_id)
    _append_operator_action({
        "action": "px_page_backup",
        "px_id": px_id,
        "role": role,
        "operator_id": operator_id,
        "backup_dir": entry["backup_dir"],
    })
    return entry
```

- [ ] **Step 3: Exercise the new endpoints manually**

With the frontend still running:

```bash
curl -s -X POST "http://127.0.0.1:8001/api/px?px_id=TEST_PX&display_name=Test&role=technician"
curl -s -X POST "http://127.0.0.1:8001/api/px/TEST_PX/save?role=technician" \
  -H "Content-Type: application/json" \
  -d '{"widgets":[{"widget_id":"w1","kind":"value","point":"RTU1_SAT","label":"SAT","x":10,"y":10}]}'
curl -s -X POST "http://127.0.0.1:8001/api/px/TEST_PX/save?role=technician" \
  -H "Content-Type: application/json" \
  -d '{"widgets":[{"widget_id":"w1","kind":"value","point":"NOT_A_REAL_POINT","label":"SAT","x":10,"y":10}]}'
curl -s -X POST "http://127.0.0.1:8001/api/px/TEST_PX/backup?role=technician"
curl -s "http://127.0.0.1:8001/api/px/TEST_PX"
```

Expected: create succeeds; first save succeeds (real point); second save returns 400 with an "unknown point" message; backup returns a `backup_dir`; final read shows the widget with a resolved live value. Remove the `TEST_PX` entry from `data/input/px_pages.json` afterward if you don't want it kept.

- [ ] **Step 4: Commit**

```bash
git add frontend/bas_api.py
git commit -m "feat(bas-sim): add Px page create/save/backup endpoints"
```

---

### Task 6: `niagara.html` — Px editor forms

**Files:**
- Modify: `frontend/static/niagara.html`

**Interfaces:**
- Consumes: `POST /api/px`, `POST /api/px/{id}/save` (Task 5), existing `GET /api/points`, existing `pxLoaded`/`loadPxList()`/`loadPxPage()` globals and functions, existing `px-select`, `px-canvas` element IDs
- Produces: `pxWidgetFromForm(values) -> object` — consumed by Task 8's JS test harness

- [ ] **Step 1: Locate the Px Graphics tab markup**

Find the `<div id="px-canvas">...</div>` element (the SVG render target for the currently loaded page, referenced from JS around line 962-975). Insert the following HTML immediately after that div's closing tag:

```html
<div class="section-title" style="margin-top:16px;">Create Px Page</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
  <input id="px-new-id" placeholder="px_id (e.g. AHU3_SCHEMATIC)" style="width:220px;">
  <input id="px-new-name" placeholder="Display name" style="width:220px;">
  <input id="px-new-facility" placeholder="Facility (optional)" style="width:140px;">
  <select id="px-editor-role"><option value="technician">technician</option><option value="admin">admin</option></select>
  <button onclick="createPxPage()">Create Page</button>
</div>
<div id="px-create-status" style="font-size:0.78rem;margin-bottom:10px;"></div>

<div class="section-title">Add Widget</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
  <input id="px-widget-id" placeholder="widget_id" style="width:120px;">
  <select id="px-widget-kind">
    <option value="value">value</option>
    <option value="gauge">gauge</option>
    <option value="bool">bool</option>
  </select>
  <select id="px-widget-point"></select>
  <input id="px-widget-label" placeholder="Label" style="width:140px;">
  <input id="px-widget-x" placeholder="x" type="number" value="40" style="width:70px;">
  <input id="px-widget-y" placeholder="y" type="number" value="40" style="width:70px;">
  <button onclick="addPxWidget()">Add Widget</button>
</div>
<div id="px-save-status" style="font-size:0.78rem;"></div>
```

- [ ] **Step 2: Add the JS functions**

Inside the existing `<script>` block (anywhere after `loadPxPage` is defined), add:

```javascript
function pxWidgetFromForm(values) {
  return {
    widget_id: values.widget_id,
    kind: values.kind,
    point: values.point,
    label: values.label,
    x: parseInt(values.x, 10),
    y: parseInt(values.y, 10),
  };
}

let pxPointOptionsLoaded = false;

async function populatePxPointOptions() {
  if (pxPointOptionsLoaded) return;
  const res = await fetch('/api/points');
  const data = await res.json();
  const select = document.getElementById('px-widget-point');
  select.innerHTML = data.points.map(p => '<option value="' + p.point + '">' + p.point + '</option>').join('');
  pxPointOptionsLoaded = true;
}

async function createPxPage() {
  const status = document.getElementById('px-create-status');
  const px_id = document.getElementById('px-new-id').value.trim();
  const display_name = document.getElementById('px-new-name').value.trim();
  const facility = document.getElementById('px-new-facility').value.trim();
  const role = document.getElementById('px-editor-role').value;
  const params = new URLSearchParams({px_id, display_name, role});
  if (facility) params.set('facility', facility);
  try {
    const res = await fetch('/api/px?' + params.toString(), {method: 'POST'});
    const data = await res.json();
    if (!res.ok) {
      status.style.color = '#c62828';
      status.textContent = (data.detail && data.detail.errors) ? data.detail.errors.join('; ') : JSON.stringify(data.detail);
      return;
    }
    status.style.color = '#2e7d32';
    status.textContent = 'Created ' + data.px_id;
    pxLoaded = false;
    await loadPxList();
  } catch (e) {
    status.style.color = '#c62828';
    status.textContent = 'Error: ' + e;
  }
}

async function addPxWidget() {
  const status = document.getElementById('px-save-status');
  const px_id = document.getElementById('px-select').value;
  if (!px_id) { status.textContent = 'Select a page first.'; return; }

  const widget = pxWidgetFromForm({
    widget_id: document.getElementById('px-widget-id').value.trim(),
    kind: document.getElementById('px-widget-kind').value,
    point: document.getElementById('px-widget-point').value,
    label: document.getElementById('px-widget-label').value.trim(),
    x: document.getElementById('px-widget-x').value,
    y: document.getElementById('px-widget-y').value,
  });

  try {
    const current = await (await fetch('/api/px/' + px_id)).json();
    const widgets = current.widgets.map(w => ({widget_id: w.widget_id, kind: w.kind, point: w.point, label: w.label, x: w.x, y: w.y}));
    widgets.push(widget);

    const role = document.getElementById('px-editor-role').value;
    const res = await fetch('/api/px/' + px_id + '/save?' + new URLSearchParams({role}).toString(), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({widgets}),
    });
    const data = await res.json();
    if (!res.ok) {
      status.style.color = '#c62828';
      status.textContent = (data.detail && data.detail.errors) ? data.detail.errors.join('; ') : JSON.stringify(data.detail);
      return;
    }
    status.style.color = '#2e7d32';
    status.textContent = 'Saved. ' + data.widgets.length + ' widgets.';
    await loadPxPage(px_id);
  } catch (e) {
    status.style.color = '#c62828';
    status.textContent = 'Error: ' + e;
  }
}
```

- [ ] **Step 3: Populate the point dropdown when the Px tab is opened**

Locate `loadPxList()` (around line 951). Add one line at the top of its body:

```javascript
async function loadPxList() {
  await populatePxPointOptions();
  if (pxLoaded) return;
  // ...existing body unchanged...
```

- [ ] **Step 4: Manual browser check**

Run `scripts/start-frontend.sh`, open `http://127.0.0.1:8001/niagara`, go to the Px Graphics tab, create a page, add a widget bound to a real point, confirm it appears in the rendered SVG with a live value after `addPxWidget()` reloads the page.

- [ ] **Step 5: Commit**

```bash
git add frontend/static/niagara.html
git commit -m "feat(bas-sim): add Px page/widget creation forms to the Niagara UI"
```

---

### Task 7: `niagara.html` — Wire Sheet editor forms

**Files:**
- Modify: `frontend/static/niagara.html`

**Interfaces:**
- Consumes: `POST /api/wiresheets`, `POST /api/wiresheets/{id}/save`, `GET /api/wiresheets/block-types` (Task 4), existing `wiresheet-select`, `wiresheet-canvas` element IDs, existing `loadWireSheet()`
- Produces: `wireSheetBlockFromForm(values) -> object`, `wireSheetLinkFromForm(values) -> object` — consumed by Task 8's JS test harness

- [ ] **Step 1: Locate the Wire Sheet tab markup**

Find the `<div id="wiresheet-canvas">...</div>` element (referenced from JS around line 785-799). Insert the following HTML immediately after that div's closing tag:

```html
<div class="section-title" style="margin-top:16px;">Create Wire Sheet</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
  <input id="ws-new-id" placeholder="wiresheet_id" style="width:220px;">
  <input id="ws-new-name" placeholder="Display name" style="width:220px;">
  <select id="ws-editor-role"><option value="technician">technician</option><option value="admin">admin</option></select>
  <button onclick="createWireSheet()">Create Sheet</button>
</div>
<div id="ws-create-status" style="font-size:0.78rem;margin-bottom:10px;"></div>

<div class="section-title">Add Block</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:10px;">
  <input id="ws-block-id" placeholder="block_id" style="width:120px;">
  <select id="ws-block-type"></select>
  <input id="ws-block-x" placeholder="x" type="number" value="40" style="width:70px;">
  <input id="ws-block-y" placeholder="y" type="number" value="40" style="width:70px;">
  <button onclick="addWireSheetBlock()">Add Block</button>
</div>

<div class="section-title">Add Link</div>
<div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px;">
  <select id="ws-link-from-block" onchange="refreshWireSheetLinkSlotOptions()"></select>
  <select id="ws-link-from-slot"></select>
  <span>&#8594;</span>
  <select id="ws-link-to-block" onchange="refreshWireSheetLinkSlotOptions()"></select>
  <select id="ws-link-to-slot"></select>
  <button onclick="addWireSheetLink()">Add Link</button>
</div>
<div id="ws-save-status" style="font-size:0.78rem;"></div>
```

- [ ] **Step 2: Add the JS functions**

Inside the existing `<script>` block:

```javascript
function wireSheetBlockFromForm(values) {
  return {
    block_id: values.block_id,
    type: values.type,
    config: {},
    x: parseInt(values.x, 10),
    y: parseInt(values.y, 10),
  };
}

function wireSheetLinkFromForm(values) {
  return {
    from: values.from_block,
    from_slot: values.from_slot,
    to: values.to_block,
    to_slot: values.to_slot,
  };
}

let wsBlockTypes = {};
let wsBlockTypesLoaded = false;

async function populateWireSheetBlockTypeOptions() {
  if (wsBlockTypesLoaded) return;
  const res = await fetch('/api/wiresheets/block-types');
  const data = await res.json();
  wsBlockTypes = data.block_types;
  const select = document.getElementById('ws-block-type');
  select.innerHTML = Object.keys(wsBlockTypes).map(t => '<option value="' + t + '">' + t + '</option>').join('');
  wsBlockTypesLoaded = true;
}

async function createWireSheet() {
  const status = document.getElementById('ws-create-status');
  const wiresheet_id = document.getElementById('ws-new-id').value.trim();
  const display_name = document.getElementById('ws-new-name').value.trim();
  const role = document.getElementById('ws-editor-role').value;
  const params = new URLSearchParams({wiresheet_id, display_name, role});
  try {
    const res = await fetch('/api/wiresheets?' + params.toString(), {method: 'POST'});
    const data = await res.json();
    if (!res.ok) {
      status.style.color = '#c62828';
      status.textContent = (data.detail && data.detail.errors) ? data.detail.errors.join('; ') : JSON.stringify(data.detail);
      return;
    }
    status.style.color = '#2e7d32';
    status.textContent = 'Created ' + data.wiresheet_id;
    const listRes = await fetch('/api/wiresheets');
    const list = await listRes.json();
    const select = document.getElementById('wiresheet-select');
    select.innerHTML = list.wiresheets.map(w => '<option value="' + w.wiresheet_id + '">' + w.display_name + '</option>').join('');
    select.value = data.wiresheet_id;
    await loadWireSheet(data.wiresheet_id);
    await refreshWireSheetLinkSlotOptions();
  } catch (e) {
    status.style.color = '#c62828';
    status.textContent = 'Error: ' + e;
  }
}

async function refreshWireSheetLinkSlotOptions() {
  await populateWireSheetBlockTypeOptions();
  const id = document.getElementById('wiresheet-select').value;
  if (!id) return;
  const ws = await (await fetch('/api/wiresheets/' + id)).json();
  const blocksById = {};
  ws.blocks.forEach(b => { blocksById[b.block_id] = b; });

  const fromSelect = document.getElementById('ws-link-from-block');
  const toSelect = document.getElementById('ws-link-to-block');
  const priorFrom = fromSelect.value;
  const priorTo = toSelect.value;
  const blockOptions = ws.blocks.map(b => '<option value="' + b.block_id + '">' + b.block_id + ' (' + b.type + ')</option>').join('');
  fromSelect.innerHTML = blockOptions;
  toSelect.innerHTML = blockOptions;
  if (priorFrom) fromSelect.value = priorFrom;
  if (priorTo) toSelect.value = priorTo;

  const fromBlock = blocksById[fromSelect.value];
  const fromSlots = fromBlock ? (wsBlockTypes[fromBlock.type] || {outputs: []}).outputs : [];
  document.getElementById('ws-link-from-slot').innerHTML = fromSlots.map(s => '<option value="' + s + '">' + s + '</option>').join('');

  const toBlock = blocksById[toSelect.value];
  const toSlots = toBlock ? (wsBlockTypes[toBlock.type] || {inputs: []}).inputs : [];
  document.getElementById('ws-link-to-slot').innerHTML = toSlots.map(s => '<option value="' + s + '">' + s + '</option>').join('');
}

async function addWireSheetBlock() {
  const status = document.getElementById('ws-save-status');
  const id = document.getElementById('wiresheet-select').value;
  if (!id) { status.textContent = 'Select a Wire Sheet first.'; return; }

  const block = wireSheetBlockFromForm({
    block_id: document.getElementById('ws-block-id').value.trim(),
    type: document.getElementById('ws-block-type').value,
    x: document.getElementById('ws-block-x').value,
    y: document.getElementById('ws-block-y').value,
  });

  try {
    const current = await (await fetch('/api/wiresheets/' + id)).json();
    const blocks = current.blocks.map(b => ({block_id: b.block_id, type: b.type, config: b.config || {}, x: b.x, y: b.y}));
    blocks.push(block);
    const links = current.links;

    const role = document.getElementById('ws-editor-role').value;
    const res = await fetch('/api/wiresheets/' + id + '/save?' + new URLSearchParams({role}).toString(), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({blocks, links}),
    });
    const data = await res.json();
    if (!res.ok) {
      status.style.color = '#c62828';
      status.textContent = (data.detail && data.detail.errors) ? data.detail.errors.join('; ') : JSON.stringify(data.detail);
      return;
    }
    status.style.color = '#2e7d32';
    status.textContent = 'Saved. ' + data.blocks.length + ' blocks.';
    await loadWireSheet(id);
    await refreshWireSheetLinkSlotOptions();
  } catch (e) {
    status.style.color = '#c62828';
    status.textContent = 'Error: ' + e;
  }
}

async function addWireSheetLink() {
  const status = document.getElementById('ws-save-status');
  const id = document.getElementById('wiresheet-select').value;
  if (!id) { status.textContent = 'Select a Wire Sheet first.'; return; }

  const link = wireSheetLinkFromForm({
    from_block: document.getElementById('ws-link-from-block').value,
    from_slot: document.getElementById('ws-link-from-slot').value,
    to_block: document.getElementById('ws-link-to-block').value,
    to_slot: document.getElementById('ws-link-to-slot').value,
  });

  try {
    const current = await (await fetch('/api/wiresheets/' + id)).json();
    const blocks = current.blocks.map(b => ({block_id: b.block_id, type: b.type, config: b.config || {}, x: b.x, y: b.y}));
    const links = current.links.concat([link]);

    const role = document.getElementById('ws-editor-role').value;
    const res = await fetch('/api/wiresheets/' + id + '/save?' + new URLSearchParams({role}).toString(), {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({blocks, links}),
    });
    const data = await res.json();
    if (!res.ok) {
      status.style.color = '#c62828';
      status.textContent = (data.detail && data.detail.errors) ? data.detail.errors.join('; ') : JSON.stringify(data.detail);
      return;
    }
    status.style.color = '#2e7d32';
    status.textContent = 'Saved. ' + data.links.length + ' links.';
    await loadWireSheet(id);
  } catch (e) {
    status.style.color = '#c62828';
    status.textContent = 'Error: ' + e;
  }
}
```

- [ ] **Step 3: Wire slot-refresh into the existing sheet selector**

Locate the code that runs `loadWireSheet(...)` when `wiresheet-select` changes (search for `wiresheet-select` and its `onchange`/event listener, near line 779-799). Add a call to `refreshWireSheetLinkSlotOptions();` immediately after that handler's existing `loadWireSheet(...)` call, so the link dropdowns repopulate whenever the selected sheet changes. Do not otherwise modify that existing handler.

- [ ] **Step 4: Manual browser check**

With the frontend running, open the Wire Sheet tab, create a sheet, add two blocks (e.g. `Constant` and `Not`), add a link between them with valid slots, confirm the save succeeds and the sheet reloads showing both blocks resolved. Then attempt an invalid link (mismatched slot) and confirm the inline error message names the problem.

- [ ] **Step 5: Commit**

```bash
git add frontend/static/niagara.html
git commit -m "feat(bas-sim): add Wire Sheet create/block/link forms to the Niagara UI"
```

---

### Task 8: JS test harness + smoke test wiring

**Files:**
- Create: `scripts/test-niagara-editor-js.mjs`
- Modify: `scripts/run-smoke-test.sh`

**Interfaces:**
- Consumes: `pxWidgetFromForm`, `wireSheetBlockFromForm`, `wireSheetLinkFromForm` from `frontend/static/niagara.html` (Tasks 6-7)
- Produces: a reusable extraction-and-assert harness for future pure JS functions in this file (not just this feature)

- [ ] **Step 1: Write the extraction-and-assertion script**

Create `scripts/test-niagara-editor-js.mjs`:

```javascript
#!/usr/bin/env node
// Extracts pure editor-form functions from frontend/static/niagara.html and
// asserts their behavior against realistic form-value shapes, with no
// browser/DOM dependency -- matching this repo's "no pytest, real
// assertions" convention (see docs/superpowers/specs/
// synchrony-style-operator-ui-design.md §10).

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const HTML_PATH = path.join(__dirname, '..', 'frontend', 'static', 'niagara.html');

function extractFunction(source, name) {
  const marker = 'function ' + name + '(';
  const start = source.indexOf(marker);
  if (start === -1) {
    throw new Error('function ' + name + ' not found in ' + HTML_PATH);
  }
  let depth = 0;
  for (let i = start; i < source.length; i++) {
    if (source[i] === '{') {
      depth++;
    } else if (source[i] === '}') {
      depth--;
      if (depth === 0) {
        return source.slice(start, i + 1);
      }
    }
  }
  throw new Error('unbalanced braces extracting ' + name);
}

const html = readFileSync(HTML_PATH, 'utf-8');
const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
  throw new Error('no <script> block found in ' + HTML_PATH);
}
const scriptSource = scriptMatch[1];

const functionNames = ['pxWidgetFromForm', 'wireSheetBlockFromForm', 'wireSheetLinkFromForm'];
const extracted = functionNames.map((name) => extractFunction(scriptSource, name)).join('\n\n');

const sandbox = new Function(
  extracted + '\nreturn {pxWidgetFromForm, wireSheetBlockFromForm, wireSheetLinkFromForm};'
);
const { pxWidgetFromForm, wireSheetBlockFromForm, wireSheetLinkFromForm } = sandbox();

let failures = 0;

function check(label, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    console.error('FAIL: ' + label + '\n  got:      ' + a + '\n  expected: ' + e);
    failures++;
  } else {
    console.log('ok: ' + label);
  }
}

check(
  'pxWidgetFromForm builds a widget with parsed coordinates',
  pxWidgetFromForm({ widget_id: 'w1', kind: 'value', point: 'RTU1_SAT', label: 'SAT', x: '120', y: '45' }),
  { widget_id: 'w1', kind: 'value', point: 'RTU1_SAT', label: 'SAT', x: 120, y: 45 }
);

check(
  'wireSheetBlockFromForm builds a block with empty config and parsed coordinates',
  wireSheetBlockFromForm({ block_id: 'B1', type: 'Not', x: '10', y: '20' }),
  { block_id: 'B1', type: 'Not', config: {}, x: 10, y: 20 }
);

check(
  'wireSheetLinkFromForm builds a link with from/to/slot fields',
  wireSheetLinkFromForm({ from_block: 'A', from_slot: 'out', to_block: 'B', to_slot: 'a' }),
  { from: 'A', from_slot: 'out', to: 'B', to_slot: 'a' }
);

if (failures > 0) {
  console.error(failures + ' assertion(s) failed');
  process.exit(1);
}
console.log('niagara editor JS self-test passed');
```

- [ ] **Step 2: Run it standalone**

Run: `node scripts/test-niagara-editor-js.mjs`
Expected: three `ok:` lines and `niagara editor JS self-test passed`, exit code 0

- [ ] **Step 3: Verify it actually fails on a real break**

Temporarily change the expected value in the first `check()` call to something wrong (e.g. `x: 999`), run again, confirm it prints `FAIL:` and exits nonzero, then revert the change. This confirms the harness isn't silently passing.

- [ ] **Step 4: Wire the new checks into the smoke test**

In `scripts/run-smoke-test.sh`, after the existing line `python3 scripts/gen-822-inventory.py --self-test`, add:

```bash
python3 frontend/px_pages.py --self-test
python3 frontend/wiresheets.py --self-test
python3 frontend/platform_admin.py --self-test
node scripts/test-niagara-editor-js.mjs
```

- [ ] **Step 5: Run the full smoke test**

Run: `scripts/run-smoke-test.sh`
Expected: all existing checks still pass, plus the four new lines above, ending with `slot-3 BAS simulator smoke test passed`

- [ ] **Step 6: Manual end-to-end acceptance pass**

With the frontend running (`scripts/start-frontend.sh`), in a browser at `http://127.0.0.1:8001/niagara`:
1. Px Graphics tab: create a page, add a widget bound to a real point, save, reload the tab, confirm the widget still appears with a live value.
2. Wire Sheet tab: create a sheet, add two blocks, link them validly, save, reload the tab, confirm the link still resolves.
3. Attempt one deliberate rejection on each: an unknown point on a Px widget, and a duplicate-target link on a Wire Sheet — confirm both surface a specific inline error message, not a silent failure or a generic one.
4. Check `data/output/operator_actions.jsonl` for the four new action types and `data/output/platform-backup-log.jsonl` for `kind: "px-editor"` / `kind: "wiresheet-editor"` entries.

- [ ] **Step 7: Commit**

```bash
git add scripts/test-niagara-editor-js.mjs scripts/run-smoke-test.sh
git commit -m "test(bas-sim): add JS extraction test harness for the px/wiresheet editors, wire into smoke test"
```

---

## Self-Review

**Spec coverage:**
- §3 decision 1 (all-POST) — Tasks 4, 5 ✓
- §3 decision 2 (Layer 1/2 split) — this plan is Layer 1 only; no drag/click-to-connect anywhere in it ✓
- §3 decision 3 (auto-backup + separate manual backup) — Tasks 4, 5 call `snapshot_single_file` on save; `take_backup`/`POST /api/platform/backup` untouched except the `kind` tag (Task 1) ✓
- §3 decision 4 (query-param create/backup, JSON-body save) — Tasks 4, 5 ✓
- §4 data model (backup dirs, action types) — Task 1 (backup dirs), Tasks 4/5 (`_append_operator_action` calls) ✓
- §5 validation rules 1-7 — Task 2 (`validate_widget`/`validate_page`: rules 1, 3, unique-widget-id, bounds), Task 3 (`validate_block`/`validate_link`/`validate_wiresheet`: rules 1, 3, 4, 5, 6, bounds); point/schedule-reference rule 2 covered for Px (widget point) in Task 2, and for Wire Sheet's `PointRef`/`ScheduleRef` blocks — **gap noted below** ✓ (mostly)
- §6 API surface — all 6 endpoints + the block-types listing, Tasks 4-5 ✓
- §7 UI — Tasks 6-7 ✓
- §8 test plan — self-tests (Tasks 1-3), JS assertions (Task 8), smoke test wiring (Task 8), manual acceptance (Task 8 step 6) ✓
- §9 risk 2 (single source of truth for enums) — `validate_block` reads `BLOCK_SLOTS` directly, never redeclares it; client-side `wsBlockTypes` is fetched from `/api/wiresheets/block-types`, which also reads `BLOCK_SLOTS` directly ✓

**Gap found and accepted as out of scope:** §5 rule 2 says every `PointRef`/`PointWriteRef`/`ScheduleRef` block's referenced name must resolve. Task 3's `validate_wiresheet` does not check this — it validates slot/link/cycle correctness but not the point/schedule name embedded in a block's `config`. This is a real gap. Reasoning for leaving it in Layer 1 as-is rather than expanding scope: Layer 1's Add Block form (Task 7) doesn't yet collect `config` values from the user at all (blocks are added with empty `config`, matching `wireSheetBlockFromForm`'s output) — config population is implicitly a Layer 2/UI-completeness concern once the form supports type-specific config fields. Flagging this explicitly rather than silently dropping it: **the next plan (Layer 2, or a small Layer 1.5) must add config-field inputs to the Add Block form and extend `validate_wiresheet` to check `PointRef`/`PointWriteRef`/`ScheduleRef` config values against real points/schedules before this editor is trustworthy for those block types.** Until then, a user can create a `PointRef` block whose `config.point` doesn't exist, and it will save successfully (resolving to `None` at read time, per existing `_evaluate_block` behavior) rather than being rejected at save time.

**Placeholder scan:** no TBD/TODO, no "add appropriate handling," no unshown code — checked.

**Type consistency:** `validate_widget`/`validate_page` signatures match their Task 5 call sites exactly (`valid_points: set[str]`, `is_create` keyword-only). `validate_block`/`validate_link`/`validate_wiresheet` signatures match their Task 4 call sites. `pxWidgetFromForm`/`wireSheetBlockFromForm`/`wireSheetLinkFromForm` names and shapes match between Tasks 6-7 (definition) and Task 8 (extraction/assertion) exactly.

---

**Plan complete and saved to `docs/superpowers/plans/2026-09-22-px-wiresheet-editor-layer1.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
