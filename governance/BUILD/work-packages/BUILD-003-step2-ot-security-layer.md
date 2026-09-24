# BUILD-003 - Step 2 OT Security Layer

| Field | Value |
|---|---|
| Roadmap step | `2 OT security` |
| Status | `planned` |
| Data class | `synthetic internal` |
| Human review | `yes` |

## Source Requirement

After Step 1 emits BAS operator evidence, add production-like OT security
controls as simulation artifacts: Purdue mapping, zones/conduits, remote access,
role model, audit logging, backup/restore, and incident/change workflow.

## Implementation Scope

- `docs/purdue-zone-conduit.md`
- `docs/access-role-model.md`
- `docs/remote-access-workflow.md`
- `docs/incident-change-workflow.md`
- future simulator audit/event mode

## Dev Acceptance

- Docs exist with synthetic-only values.
- Purdue levels L1, L2, L3, L3.5, and L4 are described.
- Role model includes viewer, operator, technician, vendor, admin, and security reviewer.
- Remote access workflow includes request, approval, MFA flag, session start/end, and denial cases.

## Staging Acceptance

- Step 2 artifacts reference Step 1 simulator evidence.
- No real network values are used.
- Security claims are marked implemented/planned, not validated/proven.

## BREAK Validation

BREAK should test:

- unauthorized point write blocked or documented as planned,
- remote access without approval denied or documented as planned,
- audit evidence exists for operator/vendor/admin actions,
- segmentation assumptions are documented and testable in the lab.

## PROVE Evidence

- Purdue map,
- role model,
- remote-access workflow,
- audit/event outputs,
- backup/restore evidence.

## Rollback / Abandon

Remove Step 2 claim language or mark as POA&M until the supporting simulator
evidence exists.

