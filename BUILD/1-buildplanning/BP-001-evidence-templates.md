# BUILD Plan BP-001 — Step 1 Evidence Templates

**Status:** DRAFT
**Approved by:** — (awaiting J review)
**Approval scope:** Local synthetic lab only — `slot-3/evidence/` and `slot-3/docs/` only
**Source finding:** `COMPLY/scope-statement.md` backup/restore gap; `BUILD/work-packages/BUILD-002-step1-evidence-and-templates.md`
**Target:** `slot-3/evidence/`, `slot-3/docs/`
**Owner:** ot-build-agent

---

## Why This Build Exists

COMPLY identified that backup/restore has not been tested and that operator
checkout and change-rollback procedures are undocumented. Before BREAK can
validate simulator scenarios, it needs operator-ready evidence templates that
name the owner, evidence source, acceptance condition, and rollback path for
each type of BAS operation.

These templates also create the evidence skeleton that PROVE will fill in after
BREAK runs. Without them, BREAK output has no home and cannot be cited in a
deliverable.

---

## Approved Context

Worker may use:

- `slot-3/data/output/` — simulator output files as the evidence source anchor
- `slot-3/data/input/` — equipment and point inventory for naming
- `slot-3/sequences/` — SOO docs for checkout procedure context
- `slot-3/COMPLY/` — scope statement and questionnaire for owner/role names
- `slot-3/BUILD/evidence-plan/break-prove-evidence-plan.md` — named evidence expectations

Worker must not use:

- Real hospital data, real facility names, PHI, real credentials
- Real vendor portal information, screenshots, or point lists
- External network access
- git operations (no stage, commit, push, or branch)

---

## Proposed Change

1. Create `slot-3/evidence/backup-restore-checklist.md` — synthetic backup
   target list, restore check steps, evidence path, owner, and acceptance
   condition.

2. Create `slot-3/evidence/operator-checkout-template.md` — pre-change
   checks, physical/logical response verification, trend review step, and
   closeout note fields. Mirrors the SOO checkout concept from
   `sequences/AHU-OR-1-SOO.md`.

3. Create `slot-3/evidence/change-rollback-template.md` — rollback trigger,
   rollback steps, rollback validation, and residual-risk note fields.

4. Create `slot-3/evidence/scenario-evidence-index.md` — one row per
   simulator scenario, naming the output file path, alarm count expectation,
   trend row expectation, and BREAK validation status.

5. Create `slot-3/docs/evidence-generation.md` — explains how to run the
   simulator to regenerate evidence, what each output file means, and how
   the templates map to simulator output.

---

## Files In Scope

- `slot-3/evidence/backup-restore-checklist.md` (new)
- `slot-3/evidence/operator-checkout-template.md` (new)
- `slot-3/evidence/change-rollback-template.md` (new)
- `slot-3/evidence/scenario-evidence-index.md` (new)
- `slot-3/docs/evidence-generation.md` (new)

---

## Out Of Scope

- `slot-3/simulator/bas_sim.py` — no changes to the simulator engine
- `slot-3/data/input/` — no changes to input files
- `slot-3/scripts/` — no changes to smoke test
- Step 2 OT security layer
- Step 3 AI-assist layer
- Any production BAS system

---

## Acceptance Checks

- All five files exist at the paths listed above.
- Each template names: owner role, evidence source file path, acceptance
  condition, and rollback or gap note.
- No template claims live production applicability.
- `scenario-evidence-index.md` has one row for each of the four simulator
  scenarios: `normal`, `chilled_water_degraded`, `isolation_pressure_loss`,
  `or_humidity_excursion`.
- `docs/evidence-generation.md` names the exact `python3 simulator/bas_sim.py`
  commands needed to regenerate each output file.
- Smoke test still passes after build: `bash scripts/run-smoke-test.sh`

---

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Template usability check | Manual review of each template against `data/output/` file contents | Every template field has a matching simulator output or a named gap |
| Scenario evidence index accuracy | Run all four scenarios, compare output file counts to index | Row counts and alarm expectations match actual output |

---

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Operator evidence templates exist and map to simulator | `BUILD/4-completedbuilds/BP-001-evidence-templates.md` | `evidence/scenario-evidence-index.md`, `docs/evidence-generation.md` |
| Backup/restore evidence path is named | `BUILD/4-completedbuilds/BP-001-evidence-templates.md` | `evidence/backup-restore-checklist.md` |

---

## Residual Risk

- Restore has not been executed — the checklist names the procedure but does
  not prove it works. This remains a COMPLY gap until a restore-test run is
  added in Step 2.
- Operator checkout template is synthetic — it reflects the SOO structure but
  has not been validated against a real Metasys or Niagara session.

---

## Worker Instructions

Before editing, confirm:

1. `slot-3/data/output/` contains `latest_points.json`, `alarms.jsonl`,
   `trends.csv`, and `scenario-summary.md` from a recent simulator run.
2. `slot-3/evidence/README.md` exists (it does — do not overwrite it).
3. `slot-3/docs/` exists (it does — `architecture.md` is already there).
4. None of the five target files exist yet (if any do, report before writing).

If any required field in this plan is missing, stop and report it.
