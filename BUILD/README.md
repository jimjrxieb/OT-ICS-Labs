# Slot-3 BUILD

This directory is the implementation work queue for the synthetic hospital
BAS/OT simulator.

The consulting source-of-truth package lives in:

```text
/home/jimmie/linkops-industries/GP-copilot/GP-CONSULTING/OT-SEC/2-BUILD
```

---

## Pipeline

BUILD work moves through these stages:

```text
1-buildplanning/   ← draft plans, human reviews here
      ↓  (human approves → moves file)
2-approvedbuilds/  ← worker picks up from here
      ↓  (worker implements)
3-buildscodereview/human-review/  ← optional human review notes
      ↓  (acceptance checks pass)
4-completedbuilds/ ← done and verified
      or
4R-remediationRebuilds/  ← failed checks, needs rework
```

**BUILD-PIPELINE-STATUS.md** is the kanban board — check it first.

---

## Folder Map

| Path | Purpose |
|---|---|
| `BUILD-PIPELINE-STATUS.md` | Kanban board — what is approved, in progress, done. |
| `1-buildplanning/` | Draft build plans awaiting human approval. |
| `2-approvedbuilds/` | Approved plans ready for worker execution. |
| `3-buildscodereview/human-review/` | Human reviewer notes. |
| `4-completedbuilds/` | Completed and acceptance-checked builds. |
| `4R-remediationRebuilds/` | Builds that failed review, returned for rework. |
| `templates/approved-build-template.md` | Required fields for every build plan. |
| `BUILD-PLAN.md` | Slot-specific build plan and step roadmap. |
| `work-packages/` | Legacy work packages (BUILD-001–004) — reference only. |
| `guardrails/` | Slot-local guardrails. |
| `evidence-plan/` | Named BREAK and PROVE evidence expectations. |

---

## Build Order

1. Step 1: BAS simulator behavior + operator evidence.
2. Step 2: OT security layer (zone/conduit, remote access, backup/restore).
3. Step 3: AI-assist layer (parked until Step 2 evidence exists).

Do not implement Step 2 claims before Step 1 emits operator evidence.
Do not implement Step 3 before Step 2 evidence exists.

---

## How To Approve A Build

1. Review the draft plan in `1-buildplanning/`.
2. If approved: move the file to `2-approvedbuilds/`, set **Status** to
   `APPROVED`, add your name and date.
3. Update `BUILD-PIPELINE-STATUS.md`.
4. Hand the path to the worker terminal.

---

## Data Boundary

Synthetic data only. No real hospital details, credentials, PHI, IPs, hostnames,
vendor portal information, screenshots, logs, or diagrams.
