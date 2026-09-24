# BUILD Plan NNN — Short Title

**Status:** DRAFT | APPROVED | IMPLEMENTED | COMPLETE
**Approved by:** Name / role / date
**Approval scope:** Local synthetic lab only — no production BAS, no real facility, no live controllers
**Source finding:** COMPLY gap ID, work-package ID, scope-statement recommendation, or BUILD ticket
**Target:** Exact files or folders this build may touch
**Owner:** Build engineer or worker role

## Why This Build Exists

State the COMPLY gap, scope-statement recommendation, or learning objective that
created this work. If the work cannot trace back to COMPLY or a human-approved
build item, it is not ready.

## Approved Context

Worker may use:

- approved repository files under `slot-3/`
- synthetic facility data from `data/input/` and `data/output/`
- generated fake/synthetic BAS point names, equipment names, alarm records
- sequences and architecture docs already in `slot-3/`

Worker must not use:

- real hospital data, real facility names, or real patient records
- real credentials, hostnames, IP addresses, serial numbers, or vendor remote-access details
- real vendor screenshots or point lists
- fire alarm, nurse call, medical device, elevator, or life-safety system data
- external network access during implementation

## Proposed Change

Describe the exact implementation or documentation change.

1. First concrete step.
2. Second concrete step.
3. Final concrete step.

## Files In Scope

- `slot-3/path/to/file-or-folder`

## Out Of Scope

- Any file not listed above
- Real facility or production BAS systems
- Step 2 OT security layer (unless this plan explicitly covers it)
- Step 3 AI-assist layer (parked)
- git operations — worker never stages, commits, or pushes

## Acceptance Checks

- Check 1
- Check 2
- Check 3

## BREAK Handoff

| Scenario | Runner or evidence | Expected result |
|---|---|---|
| Scenario name | `path/to/runner-or-evidence` | PASS condition |

## PROVE Handoff

| Claim | PROVE artifact | Evidence to cite |
|---|---|---|
| Claim to close | `path/to/prove-file.md` | `path/to/evidence-file` |

## Residual Risk

State what remains after this build. If it is accepted for lab use, say so. If
it needs new work, route it to a future BUILD item.

## Worker Instructions

Before editing, the worker must confirm:

- what is already implemented in `slot-3/`
- what exact files are in scope per this plan
- what is out of scope
- what acceptance checks will close this task
- what BREAK/PROVE evidence path will follow

If any required field above is missing from this plan, stop and report the
missing fields instead of implementing.

## Pipeline

```text
1-buildplanning/ (draft) -> human review -> 2-approvedbuilds/ (approved)
  -> worker implementation
  -> 3-buildscodereview/human-review/ (if needed)
  -> acceptance checks pass
  -> 4-completedbuilds/
  or -> 4R-remediationRebuilds/ (if checks fail)
```
