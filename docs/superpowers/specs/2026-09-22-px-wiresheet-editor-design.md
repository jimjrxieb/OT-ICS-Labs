# Px Graphics & Wire Sheet Editor — Design

- date: 2026-09-22
- status: approved — ready for Layer 1 implementation plan
- supersedes: nothing; builds on the existing read-only `px_pages.py` /
  `wiresheets.py` / `bas_api.py` surfaces
- source: brainstormed in chat this session, refined by external review
  (pasted feedback on API verb shape and the drag-mechanics cost)

## 1. Why This Exists

The learner is preparing for the Niagara N4 Technician certification,
starting from no prior Niagara experience. The domain map for that exam (Platform admin, Schedules, Alarms,
Histories, Security, Wire Sheet, Px Graphics, basic driver/device work)
already exists in this repo almost entirely — `niagara.html` has live
tabs for all of it, `schedules.py`/`wiresheets.py`/`platform_admin.py`
are real, wired, tested-in-place modules, not stubs. But J specifically
said the hands-on skill to practice is **"build a layout and connect
things"** — and today, both Px Graphics and Wire Sheet are 100%
read-only: `GET /api/px`, `GET /api/px/{id}`, `GET /api/wiresheets`,
`GET /api/wiresheets/{id}` exist; there is no `POST`/`PUT` for either
anywhere in `bas_api.py` (confirmed by grep). This spec closes that gap.

**Scope boundary:** this is an editor for this lab's synthetic Px pages
and Wire Sheets, not a general-purpose diagramming tool. It should teach
the N4 concepts (binding, linking, slots, cycles, platform discipline)
correctly, not chase drag-and-drop fidelity for its own sake.

## 2. Current State (verified this session)

| Piece | File | State |
|---|---|---|
| Px page storage | `data/input/px_pages.json` | 1 page (`RTU1_SCHEMATIC`), 8 widgets, read-only |
| Px page read API | `frontend/bas_api.py` `GET /api/px`, `GET /api/px/{id}` | Resolves each widget's point to a live value. No write path. |
| Px rendering | `frontend/static/niagara.html` `renderPxSvg()` | Renders an SVG from fixed `x`/`y` per widget. No interaction. |
| Wire Sheet storage | `data/input/wiresheets.json` | Blocks + links, read-only |
| Wire Sheet engine | `frontend/wiresheets.py` | Real DAG evaluator, dependency-ordered, **cycle detection already implemented** (`ValueError` on cycle) — reusable directly for validation |
| Wire Sheet read API | `frontend/bas_api.py` `GET /api/wiresheets`, `GET /api/wiresheets/{id}` | Resolves every block's output against live schedule/point context. No write path. |
| Action audit pattern | `frontend/bas_api.py` `_append_operator_action()`, `data/output/operator_actions.jsonl` | Established convention: every mutation logs `{action, ..., role, operator_id, timestamp}` |
| Mutation convention | `frontend/bas_api.py` | Every existing mutation is `POST` with an action-suffixed path and **Query params, not a JSON body** (`command`, `release`, `backup`, `run/{scenario}`, `trouble-calls/new`, `diagnose`) — no `PUT` anywhere in this codebase today |
| Role gating | `frontend/bas_api.py` `_require_command_role()` | Restricts writes to `technician`/`admin`, 403 otherwise |

## 3. Decisions

1. **All-`POST`, not REST-proper `PUT`.** Matches this codebase's existing
   convention exactly (see table above) rather than introducing the only
   `PUT` in the app for one feature. Routes:
   - `POST /api/px` — create a new page
   - `POST /api/px/{id}/save` — replace an existing page's widgets
   - `POST /api/px/{id}/backup` — explicit backup, kept as its own action
   - `POST /api/wiresheets` — create
   - `POST /api/wiresheets/{id}/save` — replace
   - `POST /api/wiresheets/{id}/backup` — explicit backup
2. **Two layers, built in order.** Layer 1 (this plan's target) is the
   validated persistence foundation: forms, server-side validation, save/
   create/backup endpoints, audit logging, tests. Layer 2 (a later plan)
   adds pointer-drag positioning for Px and click-to-connect linking for
   Wire Sheet, over the *same* data model and endpoints — no schema
   changes in Layer 2, UI-only.
3. **Backup-before-overwrite is automatic AND the manual Platform Backup
   action stays separate.** Every `save` call snapshots the prior file
   version first (cheap insurance, always logged). The existing
   `POST /api/platform/backup` remains a distinct, deliberate action —
   real Niagara practice treats "take a backup before touching a
   station" as its own habit, and that habit is itself N4 Technician
   exam material. Automating it away would remove the thing being
   taught.
4. **Query-param POST bodies**, not JSON, matching every existing
   mutation endpoint in `bas_api.py` (`command`, `release`, etc. all use
   `Query(...)` FastAPI params). New widget/block/link payloads are
   small enough this stays consistent rather than switching to a request
   body for only the new endpoints. Exception: a full widget/block list
   replace on `save` is naturally a JSON body (an array of objects) —
   Query params don't fit an array-of-objects payload. `save` takes a
   JSON body; `create`/`backup` stay Query-param-only, matching existing
   single-value mutation endpoints.

## 4. Data Model

No new files. Existing schemas gain optional fields; nothing existing
breaks.

**`px_pages.json`** — unchanged shape. Widget kind enum, enforced at
validation time (not stored): `gauge | value | bool`. `x`/`y` remain
plain integers.

**`wiresheets.json`** — unchanged shape (`blocks`, `links`). Block type
enum is already `wiresheets.BLOCK_SLOTS` — reused directly as the
validation source of truth, not duplicated.

**New: per-file backup + audit trail.** Reuses `platform_admin.py`'s
existing `.dist`-style snapshot pattern:
- `data/output/platform-backups/px-{px_id}-{ts}.dist/px_pages.json`
- `data/output/platform-backups/wiresheet-{id}-{ts}.dist/wiresheets.json`
- Logged to the existing `data/output/platform-backup-log.jsonl`
  (same file, new `kind` field: `"platform"` vs `"px-editor"` vs
  `"wiresheet-editor"`, so the Platform Admin backup table can still
  list everything in one place).

**New operator action types**, appended to `operator_actions.jsonl` via
the existing `_append_operator_action()`:
- `px_page_created`, `px_page_saved`
- `wiresheet_created`, `wiresheet_saved`

## 5. Validation Rules (server-side, enforced on every create/save)

Applies to both Px and Wire Sheet unless noted:

1. **Unique ID.** `px_id`/`wiresheet_id` must not collide with an
   existing page on create; must match the path param on save.
2. **Point/schedule references resolve.** Every `widget.point` (Px) and
   every `PointRef`/`PointWriteRef`/`ScheduleRef` block's referenced
   name (Wire Sheet) must exist in `points.json` / `schedules.json`.
   Reject with the offending name listed, not a generic error.
3. **Known kind.** Widget `kind` ∈ `{gauge, value, bool}`; block `type` ∈
   `wiresheets.BLOCK_SLOTS`. Reject unknown kinds by name.
4. **Valid slots.** A link's `from_slot`/`to_slot` must exist in that
   block type's declared `inputs`/`outputs` (`wiresheets.slot_spec()`).
5. **No duplicate links.** No two links may share the same
   `(to, to_slot)` — an input slot accepts exactly one incoming link,
   matching real Niagara Wire Sheet semantics.
6. **No cycles.** Reuse `wiresheets.evaluate()`'s existing cycle
   detection — run it against the proposed graph before saving, not just
   at read time. A cycle is rejected at save, never silently persisted.
7. **Canvas bounds.** `x`/`y` within a sane positive range (e.g.
   0-4000) — catches obviously corrupt input, not a real design
   constraint.

All violations return `400` with a specific, field-named message (not a
generic "validation failed") — this doubles as exam-relevant feedback:
seeing exactly *why* a link was rejected teaches the slot-compatibility
rule better than a pass/fail toggle would.

## 6. API Surface (Layer 1)

```
POST /api/px                        create page       (Query: px_id, display_name, facility?)
POST /api/px/{id}/save              replace widgets   (JSON body: {"widgets": [...]})
POST /api/px/{id}/backup            explicit backup    (Query: operator_id)

POST /api/wiresheets                create sheet       (Query: wiresheet_id, display_name)
POST /api/wiresheets/{id}/save      replace blocks/links (JSON body: {"blocks": [...], "links": [...]})
POST /api/wiresheets/{id}/backup    explicit backup    (Query: operator_id)
```

All six role-gated via the existing `_require_command_role()`
(`technician`/`admin` only, 403 otherwise) — editing a station's
graphics/logic is exactly the kind of action real Niagara restricts by
role.

## 7. UI (Layer 1 — forms only, no canvas interaction)

In `niagara.html`, under the existing Px Graphics and Wire Sheet tabs:

- **Px:** "Add Widget" form (kind dropdown, point dropdown populated
  from `/api/points`, label text, x/y number inputs) below the existing
  read-only SVG render. Submitting POSTs the full updated widget array
  to `save`. A "New Page" form (px_id, display_name, facility) above the
  page selector.
- **Wire Sheet:** "Add Block" form (type dropdown, position) and "Add
  Link" form (from-block/from-slot, to-block/to-slot dropdowns, each
  populated from the currently loaded sheet's blocks and their declared
  slots). Same save-the-whole-array pattern. A "New Sheet" form
  alongside the sheet selector.
- Both surfaces show the 400 validation message inline on rejection —
  matching the existing 403-surfacing pattern already used for
  command/release in the Technician Panel.

Layer 2 (separate, later plan) replaces the number-input positioning
with pointer-drag on the SVG canvas, and replaces the from/to dropdowns
with click-source-slot/click-target-slot canvas interaction — over these
same endpoints, same validation, no data model change.

## 8. Test Plan

Matching this repo's established convention (no pytest — `--self-test`
flags, `node --check` + assertions, `scripts/run-smoke-test.sh`):

- New validation logic gets a `--self-test` (in `px_pages.py`/
  `wiresheets.py` directly, or a new `editor_validation.py` if it grows
  large enough to warrant separating from the read-path modules) —
  covering every rule in §5 with both a passing and a rejecting case.
- New JS (form wiring, save calls) gets `node --check` + real assertions
  against realistic widget/block shapes, the same discipline used for
  `valueControlHtml`/`currentValueLabel` in the Synchrony UI spec.
- `scripts/run-smoke-test.sh` gains fast, offline checks only — schema/
  self-test style, no running-server requirement.
- Manual acceptance: create a page, add a widget bound to a real point,
  save, reload, confirm the live value resolves; create a sheet, add two
  blocks and a valid link, save, reload, confirm evaluation still works;
  attempt a cycle and a duplicate-link and confirm both are rejected
  with a specific message, not silently accepted or generically failed.

## 9. Risks

1. **Scope creep into Layer 2 mid-implementation.** The form UI will
   feel primitive next to the eventual drag/click canvas — resist adding
   partial drag support while Layer 1 is still landing. Layer 1's
   completion boundary is explicit (§8's acceptance list), not "until it
   feels good."
2. **Validation rule drift between read path and write path.** Slot/kind
   enums must be read from the same source (`wiresheets.BLOCK_SLOTS`)
   the evaluator already uses, not re-declared — a second enum that
   drifts from the first would silently accept invalid data the
   evaluator then can't resolve.
3. **Backup volume.** Automatic backup-on-every-save could accumulate
   many `.dist` directories quickly during active editing practice. Not
   solved here — acceptable for a training lab, revisit only if disk
   usage becomes a real problem.
