# BUILD-002 - Step 1 Evidence And Templates

| Field | Value |
|---|---|
| Roadmap step | `1 BAS simulator` |
| Status | `planned` |
| Data class | `synthetic internal` |
| Human review | `yes` |

## Source Requirement

BUILD needs operator-ready evidence templates before BREAK and PROVE can use
simulator output consistently.

## Implementation Scope

- `evidence/backup-restore-checklist.md`
- `evidence/operator-checkout-template.md`
- `evidence/change-rollback-template.md`
- `evidence/scenario-evidence-index.md`
- `docs/evidence-generation.md`

## Dev Acceptance

- Templates exist.
- Each template names owner, evidence source, acceptance condition, and rollback.
- Templates do not claim live production applicability.

## Staging Acceptance

- Evidence templates map to Step 1 output files.
- Missing evidence produces a clear gap or POA&M placeholder.

## BREAK Validation

BREAK should confirm evidence templates are usable to inspect scenario outputs.

## PROVE Evidence

- generated evidence templates,
- scenario evidence index,
- source output paths.

## Rollback / Abandon

Remove or supersede templates that do not map cleanly to simulator artifacts.

