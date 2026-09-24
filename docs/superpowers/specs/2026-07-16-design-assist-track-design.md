# DESIGN/ — The Design-Assist Track (slot-3)

**Date:** 2026-07-16
**Status:** Approved design, pre-implementation
**Target JD:** Siemens Building Automation (HVAC) Controls Engineer — design-assist,
pre-construction engineering packages, site surveys, network architecture, submittal
review. (Full JD text to be added to `COMPLY/jobdescriptionscope.md` as engineer-track
scope, alongside the existing service-technician JD.)

## Purpose

Slot-3 today trains the **service technician** job: operate the BAS, take trouble
calls, survive the 2AM game. This track adds the **design engineer** job: given a
project brief, survey existing conditions, produce a complete engineering package
(points list, SOO, valve/damper schedule, BOM, panel layout, network riser), and
carry it through submittal review to approval.

Primary goal: **practice the workflow**, repeatably — the design-work counterpart to
the trouble-call trainer. Portfolio artifacts fall out of good runs as a side effect.

## Decisions made during brainstorming

| Question | Decision |
|---|---|
| Purpose | Practice loop (not portfolio-first, not curriculum) |
| Activities | Design deliverables + network architecture + site survey/as-builts |
| Feedback mechanism | AI agent plays senior engineer / EOR against sealed rubrics (2AM-game pattern) |
| Setting | Renovations/additions to the two existing synthetic buildings |
| Approach | A (rulebook + data, no code changes to the live system), with all machine-readable deliverables shaped to `data/input/` schemas so Approach B ("your design gets built") bolts on later without rework |

## Directory structure

```
DESIGN/
  DESIGN.md                  ← agent rulebook: AI plays senior engineer / EOR
  briefs/
    P-01-riverside-floor6-fitout.md      (Level 1)
    P-02-hospital-pharmacy-reno.md       (Level 2)
    P-03-hospital-or-wing-addition.md    (Level 3)
  sealed/
    P-01-rubric.md
    P-02-rubric.md
    P-03-rubric.md
  templates/
    existing-conditions-survey.md
    proposed_equipment.json
    proposed_points.json
    proposed_alarms.json
    soo.md
    valve-damper-schedule.md
    bom.md
    panel-layout.md
    network-riser.md
  submittals/                ← J's work: submittals/P-01/rev-A/, rev-B/, ...
    .gitkeep
  review-log.md              ← accumulating record, mirrors BREAK/call-log.md
scripts/validate-submittal.py
ai-dev-prompts/6-design-project.md
```

Conventions follow `BREAK/`: `sealed/` is honor-system (J doesn't read until the
review is delivered), `review-log.md` accumulates results, `DESIGN.md` is the complete
rulebook any worker agent (Claude Code, Codex, Gemini CLI) reads before acting.

## Project briefs

Markdown with YAML frontmatter:

```yaml
---
id: P-02
title: Hospital Pharmacy Renovation
facility: hospital
level: 2
systems: [AHU, VAV, exhaust, room-pressure]
required_deliverables: [survey, equipment, points, alarms, soo, valve-damper, bom, panel-layout]
---
```

Body sections, in order:

1. **Owner project narrative** — what the owner wants, in owner language.
2. **Mechanical design summary** — the mechanical engineer's schedule of new/modified
   equipment (the thing the controls engineer designs *to*).
3. **Owner-furnished drawing set** — an as-built summary of existing conditions that
   **deliberately contradicts the live lab in 2–4 places**. These planted
   discrepancies are the site-survey game; they are enumerated only in the sealed
   rubric.
4. **Contract scope notes** — Div 23/25-style scope boundaries, and (in at least one
   brief) a planted ambiguity that should trigger an RFI.

Initial library: three briefs, one per level.

| Brief | Level | Scope | New deliverable emphasis |
|---|---|---|---|
| P-01 Riverside floor-6 tenant fit-out | 1 | One system (VAV boxes on the existing RTU) | Points list + SOO only |
| P-02 Hospital pharmacy renovation | 2 | Multi-system (AHU rework, pressure relationships, exhaust) | Full package minus riser |
| P-03 Hospital OR wing addition | 3 | New wing: AHUs, VAVs, plant tie-ins, new JACE | Full package **plus** network riser with MS/TP trunks and a third-party Modbus integration (e.g., new chiller) |

## The project loop (a "run")

1. J says **"new project"** (optionally brief ID or level) to an AI CLI at repo root
   that has read `DESIGN.md`. Agent preflight: brief exists, sealed rubric exists,
   create `submittals/P-XX/`.
2. **Site survey phase.** J walks the live lab — Metasys/Niagara front ends,
   `data/input/` inventories, `docs/architecture.md` — compares against the brief's
   owner-furnished drawings, and submits an existing-conditions report (template).
   Agent grades it against the planted discrepancies and issues design go-ahead.
   Missed discrepancies are **not revealed** — they stay wrong in J's design basis
   and surface as review comments later, exactly like real life.
3. **Design phase.** J produces the required deliverables from templates into
   `submittals/P-XX/rev-A/`. J runs `scripts/validate-submittal.py` before
   submitting (self-QA is part of the job).
4. **Submittal review.** Agent reviews `rev-A/` against the sealed rubric and returns
   a numbered comment log. Each comment: number, deliverable, severity, text, and a
   disposition for the package overall — **Approved / Approved as Noted / Revise &
   Resubmit / Rejected**. Honest grading, partial credit, no reveal beyond the
   comments themselves.
5. **Revise & resubmit.** J addresses comments in `rev-B/` (copy of rev-A plus fixes,
   with a comment-response table). Agent re-reviews. Loop until Approved or Approved
   as Noted.
6. **Close-out.** Agent appends to `review-log.md`: project, date, revision count,
   survey score (discrepancies found / planted), comment counts by severity, final
   disposition, and one "lesson" line.

### RFI mechanic (replaces the 2AM hint ladder)

At any point J may submit an RFI to the agent acting as owner/EOR. RFIs are
unlimited, realistic, and never penalized — asking is the correct professional
behavior. The sealed rubric for at least one brief plants an ambiguity where the
scoring **rewards** resolving it via RFI and **dings** designing on a guess. The
agent answers RFIs in character and logs them in the submittal directory
(`rfi-log.md`).

## Deliverables and formats

| Deliverable | Format | B-compat |
|---|---|---|
| Existing-conditions survey | markdown (template) | — |
| Proposed equipment | JSON, exact `data/input/equipment.json` record schema | ✅ merge-ready |
| Proposed points list | JSON, exact `data/input/points.json` record schema | ✅ merge-ready |
| Proposed alarms | JSON, exact `data/input/alarm_rules.json` record schema | ✅ merge-ready |
| Sequence of operations | markdown, same style as existing `sequences/*.md` | — |
| Valve & damper schedule | markdown table: tag, service, line size, Cv, valve/damper type, fail position, actuator, signal | — |
| Bill of materials | markdown table: qty, part, description, where-used | — |
| DDC panel layout | markdown parts + termination table, plus Mermaid enclosure block diagram | — |
| Network riser | Mermaid diagram: supervisor, JACEs, MS/TP trunks with device counts, BACnet/IP backbone, Modbus third-party devices | — |

**The B bolt-on hook:** the three JSON deliverables use the *exact* record schemas of
their `data/input/` counterparts, so a future merge script can splice an approved
submittal into the live inventories with zero rework of this track. Engineer-only
detail (device model, signal type, wire spec) lives in the markdown deliverables —
never crammed into the JSON as extra fields.

## Sealed rubrics

One per brief, `sealed/P-XX-rubric.md`, containing:

- **Planted survey discrepancies** — the 2–4 contradictions between the
  owner-furnished drawings and the live lab, with where each is verifiable.
- **Required-content checklists** per deliverable (e.g., SOO must cover occupied /
  unoccupied / failure modes / safeties / alarm actions; points list must cover every
  sequence reference; riser must respect MS/TP device limits and segment life-safety
  air handlers sensibly).
- **Planted gotchas** — e.g., the mechanical schedule omits a code-required point;
  a naive trunk layout exceeds device limits; the RFI-worthy ambiguity.
- **Scoring guidance** — what earns Approved vs. Revise & Resubmit; partial credit
  rules; how missed survey discrepancies convert into review comments.

### Generate-a-new-brief mode

`DESIGN.md` includes instructions for the agent to author a **new** brief + sealed
rubric on demand (same pattern as the 2AM game writing sealed answers before
breaking): pick a facility and scope, plant discrepancies against the *current*
live inventories, write `sealed/P-XX-rubric.md` first, then publish the brief. This
is how the library grows past the initial three.

## QA tooling

`scripts/validate-submittal.py` — Python 3.11+, standard library only, consistent
with `bas_sim.py`'s dependency-free approach. Usage:

```bash
python3 scripts/validate-submittal.py DESIGN/submittals/P-02/rev-A
```

Checks (JSON deliverables only):

1. Files parse and are lists of records.
2. Required fields present with correct types, per the `data/input/` schemas.
3. Equipment IDs unique — within the submittal *and* against existing
   `data/input/equipment.json`.
4. Point names unique within submittal and against existing `data/input/points.json`.
5. Every proposed point references an equipment ID that exists in the proposed
   equipment file or the existing inventory.
6. Every proposed alarm references a point that exists (proposed or existing).
7. `facility` values match known facility IDs.

Exit 0 clean / exit 1 with a findings list. J runs it before submitting; the agent
runs it as review step zero; later it becomes Approach B's merge pre-check.

## Documentation updates

- `README.md` — add "4. Design projects" under *What You Can Do*, and add `DESIGN/`
  to the repo map.
- `COMPLY/jobdescriptionscope.md` — add the Siemens BAS Controls Engineer JD as the
  engineer-track scope (keep the existing service-tech JD; the lab now targets both).
- `ai-dev-prompts/6-design-project.md` — copy-paste starter prompt mirroring
  `2-2am-call.md` ("Read DESIGN/DESIGN.md and follow it. New project, level 1.").

## Safety and data boundary (unchanged)

- Everything stays synthetic; the existing `safety/data-boundary.md` rules apply to
  briefs, rubrics, and submittals. No real facility data, sequences, vendor exports,
  or drawings may be pasted into any deliverable.
- Approach A makes **no changes to the live system**: the agent writes only inside
  `DESIGN/`, and reads the rest of the repo. No docker required for this track
  (front ends suffice for surveys; the docker stack is optional enrichment).
- Nothing produced here is a real design or code/life-safety approval — same
  disclaimer as the README.

## Out of scope (deliberate)

- AutoCAD / drafting — the lab practices engineering *content*, not CAD.
- Commissioning against the docker stack (Approach C).
- The actual merge script and simulator integration (Approach B) — this design only
  shapes the data for it.
- Any changes to `bas_sim.py`, `frontend/`, or `open-source-stack/`.

## Testing / verification of the implementation itself

- `validate-submittal.py` gets a self-test mode (`--self-test`) with inline
  known-good and known-bad fixtures, so the validator is provable without a real
  submittal.
- Each shipped brief's planted discrepancies are verified against the live
  inventories at build time (a discrepancy that accidentally matches reality is a
  broken brief).
- Smoke: `run-smoke-test.sh` untouched; this track adds no runtime surface.

## Implementation order

1. Templates + `validate-submittal.py` (+ self-test).
2. `DESIGN.md` rulebook (including generate-a-new-brief mode and RFI rules).
3. P-01 brief + sealed rubric (Level 1, smallest).
4. P-02, P-03 briefs + rubrics.
5. README / COMPLY / ai-dev-prompts updates.
6. Dry run: play P-01 end-to-end, fix friction, log the run in `review-log.md`.
