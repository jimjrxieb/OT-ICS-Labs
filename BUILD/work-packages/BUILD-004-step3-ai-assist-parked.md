# BUILD-004 - Step 3 AI-Assist Layer Parked

| Field | Value |
|---|---|
| Roadmap step | `3 AI` |
| Status | `parked` |
| Data class | `synthetic internal only` |
| Human review | `required before activation` |

## Source Requirement

AI assistance may be useful for troubleshooting summaries and evidence review,
but only after BAS behavior and OT security controls have evidence.

## Activation Conditions

- Step 1 simulator evidence exists.
- Step 2 security evidence exists.
- Data boundary is reviewed.
- AI output is advisory only.
- Human review blocks operational recommendations and customer-facing claims.

## Out Of Scope Until Activated

- AI-generated operational commands.
- AI-generated controller changes.
- AI-generated production recommendations.
- Real facility data in AI context.

## Future BREAK Validation

BREAK should test whether AI summaries stay inside synthetic evidence and do
not invent production claims.

## Future PROVE Evidence

- AI allowed-use policy,
- prompt/data boundary,
- audit log,
- human-review record.

