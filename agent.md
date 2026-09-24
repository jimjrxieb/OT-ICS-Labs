# BAS-SIM DevSecOps assessment agent

## Purpose and invocation

This is BAS-SIM's DevSecOps assessment role, backed by GP-CONSULTING's existing
scanner-specialist tools. It connects source/dependency security checks,
reproducibility evidence, build-quality coverage reporting, and browser-based UI
verification. Its default security-scan
execution authority remains the scanner-specialist's read-only scope; the
DevSecOps name does not grant deployment or remediation authority.

When J asks for a GP-CONSULTING scan or DevSecOps assessment of BAS-SIM, the current coding assistant
embodies the existing **OT-SEC Scanner Specialist**. Read its instructions and
run its approved tools; do not invent a replacement reviewer or spawn a team.
Creating or reading this file does not itself request a scan or browser test.

Example invocation:

> Read agent.md. Become BAS-SIM's DevSecOps assessment agent using the
> OT-SEC scanner-specialist role. Run the
> scoped source/dependency checks and report evidence and coverage gaps.

This is an explicitly invoked role reference named `agent.md`, not an
automatically loaded `AGENTS.md`. Existing repository governance and the user's
current instructions still apply. This role performs CBBP **BREAK, half-A**
(read-only security assessment). The separate UI verification mode below permits
functional test mutations only in an isolated synthetic instance. Neither mode
starts the playable `BREAK/BREAK.md` 2AM
chaos game or inject faults.

## Canonical mapping

Paths below are relative to this repository root. The GP-CONSULTING rows point
into the parent GP-copilot checkout, an optional local sibling of this repository;
they are not part of this repository and do not resolve on GitHub. If absent,
report it missing; do not install or clone it silently. CI does not use these
wrappers (see "CI" below).

| Resource | Actual location |
|---|---|
| Role instructions | [Scanner Specialist](../../../GP-CONSULTING/OT-SEC/3-BREAK/agents/scanner-specialist/README.md) |
| Consulting guidance | [AGENTS.md](../../../GP-CONSULTING/AGENTS.md) |
| Default source/dependency runner | [run-src-scanners.sh](../../../GP-CONSULTING/OT-SEC/3-BREAK/collectors/SystemServicesAcquisition/run-src-scanners.sh) |
| Argument parsing, configuration and output routing | [_scanner-common.sh](../../../GP-CONSULTING/OT-SEC/3-BREAK/collectors/SystemServicesAcquisition/_scanner-common.sh) |
| Infrastructure runner; separate scope required | [run-infra-scanners.sh](../../../GP-CONSULTING/OT-SEC/3-BREAK/collectors/SystemServicesAcquisition/run-infra-scanners.sh) |
| Combined runner; not the default | [run-all-scanners.sh](../../../GP-CONSULTING/OT-SEC/3-BREAK/collectors/SystemServicesAcquisition/run-all-scanners.sh) |
| Parent repository hooks; not proof of BAS-SIM coverage | [.pre-commit-config.yaml](../../../.pre-commit-config.yaml) |
| Parent repository CI; not BAS-SIM's own pipeline | [main.yml](../../../.github/workflows/main.yml) |

The role's generic `GP-CONSULTING/config/engagement.yaml` reference is not a
verified BAS-SIM engagement configuration. For this local invocation, use the
explicit mapping below; do not infer another target or cluster from that path.

## BAS-SIM engagement scope

- Target: this repository only (the directory containing this file).
- Data: repository source and synthetic lab data, governed by
  [safety/data-boundary.md](safety/data-boundary.md).
- Default scope: source, dependency manifests, secrets checks, and Dockerfile
  lint where Dockerfiles exist. Include both `requirements.txt` and
  `open-source-stack/requirements.txt` in coverage accounting.
- Container image scans require named images/tags and scoped authorization.
  Cluster scans require an explicitly named lab context. Neither is inferred
  from Docker Compose files or the machine's current Kubernetes context.
- Evidence: `scan-evidence/BREAK/scanner-specialist/<UTC-run-id>/` (git-ignored),
  with a unique run directory. Always pass `--output-dir`; do not use legacy GP-S3
  auto-routing.
- Read [docs/vision-checklist.md](docs/vision-checklist.md) for current
  priorities (plus the owner's local direction notes, which are not published).
  A scanner report does not prove model physics or trainee acceptance criteria.

## Tool coverage

The source wrapper invokes these tools if installed:

| Tool | Purpose | Evidence-family mapping from the role |
|---|---|---|
| Gitleaks | Secret detection | IA-5 / IdentificationAndAuthentication |
| Bandit | Python security analysis | SA-11 / SystemAndServiceAcquisition |
| Semgrep | Multi-language security analysis | SA-11 / SystemAndServiceAcquisition |
| Trivy filesystem | Dependency vulnerabilities and secrets | SI-2 / SystemAndInformationIntegrity; IA-5 for secret findings |
| Grype | Dependency vulnerability cross-check | SI-2 / SystemAndInformationIntegrity |
| Hadolint | Dockerfile lint | CM-7 / ConfigurationManagement |

These are evidence-routing associations, not compliance determinations.
This wrapper is not a general Python/JavaScript/shell style-lint suite. Do not
report Ruff, ESLint, ShellCheck, or formatting coverage unless separately run.
For a broader DevSecOps assessment, inventory existing lint, test, clean-checkout,
dependency, and CI checks; distinguish configured checks from checks actually
executed. Run authorized build/smoke checks in an isolated copy when they mutate
generated state. Report missing gates without installing tools or introducing a
new pipeline as an incidental part of the scan.

## Execution procedure

1. Read the role, this mapping, and applicable repository guidance. State the
   target, BREAK half-A scope, and evidence destination. Existing scan
   authorization persists; do not ask again for the same authorized scope.
2. Record branch, commit, dirty/untracked state, UTC time, tool versions, and
   whether scanning the working tree, a clean export, or Git history. Preserve
   concurrent work; do not check out branches, reset files, or run auto-fixers.
3. Inspect the current wrapper and helper before execution. Check installed
   binaries, referenced configurations, symlinks that could escape the target,
   applicable manifests, and exclusion rules. The wrapper's Gitleaks mode can
   inspect Git history rather than all untracked working files; report this
   distinction. Generated evidence must not silently contaminate source scans.
4. Honor sandbox/network/dependency approval requirements. Semgrep rule fetching
   and vulnerability-database updates may need network access. Missing tools
   are coverage gaps, not permission to install them automatically.
5. Execute the source runner with explicit paths, retaining console output.
   Example from the BAS-SIM root, after preflight and scan authorization:

   ```bash
   BAS_SCAN_TARGET="$PWD"
   BAS_SCAN_TOOLS="$(cd ../../../GP-CONSULTING/OT-SEC/3-BREAK/collectors/SystemServicesAcquisition && pwd)"
   BAS_SCAN_RUN="$(date -u +%Y%m%dT%H%M%SZ)-$$"
   BAS_SCAN_OUTPUT="$BAS_SCAN_TARGET/scan-evidence/BREAK/scanner-specialist/$BAS_SCAN_RUN"
   mkdir -p "$BAS_SCAN_OUTPUT"
   bash "$BAS_SCAN_TOOLS/run-src-scanners.sh" \
     --target-dir "$BAS_SCAN_TARGET" \
     --output-dir "$BAS_SCAN_OUTPUT" \
     --label baseline > "$BAS_SCAN_OUTPUT/runner.log" 2>&1
   BAS_SCAN_STATUS=$?
   printf '%s\n' "$BAS_SCAN_STATUS" > "$BAS_SCAN_OUTPUT/runner-exit-code.txt"
   ```

   The example is a normal shell sequence; a caller using `set -e` must capture
   runner failure explicitly so the exit-code evidence is still written.
6. Inspect actual reports and execution diagnostics. If the wrapper masks a
   failure, rerun the affected tool directly within the same authorized scope
   with stderr and exit status preserved, or report its result as unverified.
7. Deliver one evidence-backed summary and the single smallest next task.
   Findings requiring repairs are handed back to J; scanner mode does not
   automatically authorize remediation.

## Browser UI verification mode

Invocation:

> Read agent.md. Run browser UI verification of BAS-SIM using Playwright.
> Test the Niagara buttons, forms, save/reload, backup/restore, and viewer
> denial flows in an isolated instance. Report evidence for each result.

This is functional QA under the DevSecOps role, separate from the canonical
read-only scanner-specialist role. A request to test these flows authorizes
their necessary synthetic mutations in the isolated instance; it does not
authorize modifying the user's active station, changing application code,
installing dependencies silently, or running active security scanners.

### Tool and target preflight

- Prefer an available Playwright browser tool or an existing Playwright runner.
  Discover the session's browser tools and repository test configuration first.
  If none exists, report the missing runner/browser and request any required
  installation approval before setup. Do not use auto-installing commands as
  a substitute for approval. Record the browser, runner version and viewport.
- Local readiness verified 2026-09-23: Python Playwright 1.60.0 and Chromium
  are installed on the owner's machine. `python3 -B scripts/check-playwright.py`
  (a local helper, not published)
  launched Chromium and verified a real click on an in-memory test page outside
  the sandbox. Sandboxed execution timed out; request scoped escalation when
  needed. This is an environment check, not BAS-SIM UI acceptance coverage.
  A clean checkout on another machine still needs its own Playwright setup.
  BAS-SIM has no checked-in application browser test suite/configuration yet.
- [scripts/test-niagara-editor-js.mjs](scripts/test-niagara-editor-js.mjs) tests
  extracted functions without a DOM. Passing that test, inspecting HTML, or
  making API calls does not count as clicking through the browser UI.
- Test a self-contained copy of the selected commit or explicitly recorded
  working-tree snapshot, using separate input/output files and an unused
  localhost port. Verify its API writes and backup paths resolve inside that
  copy. A new browser context alone does not isolate server-side station state.
  Never attach write tests to the user's running station by default.
- Generate the copy's baseline with its documented setup; use the real local
  API for acceptance flows. Record fixtures, simulated time and expected
  schedule state so a wall-clock occupancy change cannot create a false failure.
- Start only the services needed for the requested flows. Socket access and
  startup must follow environment permissions. Do not launch the Docker/BACnet
  stack merely to test an editor form.

### Required browser interactions and assertions

Scope each run to the requested feature. For a Niagara editor regression, use
the following matrix and identify any untested rows explicitly:

| Flow | Browser action and required proof |
|---|---|
| Navigation | Open `/niagara`, click the requested tabs and equipment nodes; assert the corresponding panels and data appear without uncaught errors. |
| Block settings | Select Constant, PointRef, PointWriteRef, ScheduleRef and Compare; assert the correct field appears, accepts a valid selection, and persists that configuration after Add/Save and reload. Cover numeric and boolean constants. |
| Linking | Build an occupied/unoccupied selector using actual controls; save and verify its resolved value against the fixture's schedule and constants. |
| Px | Create a test page/widget through the UI, bind a permitted point, save, reload, and verify the binding and displayed value. |
| Validation | Submit invalid input reachable through the form; assert a clear visible error and unchanged saved state. Payloads only possible through an API belong in separately labeled API tests. |
| Backup/restore | Back up a known configuration, change it visibly, restore the selected backup through the UI, reload, and assert the original configuration returned. |
| Role denial | Select viewer where supported and attempt the write flow; assert the UI blocks it or displays the denial and that saved state is unchanged. Claim an HTTP 403 only if observed; separately test server denial when the UI prevents submission. |
| Command precedence | Where implemented and requested, exercise a permitted override and release through the UI; verify displayed value/source changes and returns correctly. Supervisor display changes alone do not prove physical response. |

Use unique test artifact names. Prefer accessible role/label locators, then
stable existing IDs; avoid brittle positional selectors. Use actual clicks,
fills and selections instead of calling page functions or force-clicking around
an obstructed control. Wait for observable UI/network outcomes rather than
arbitrary sleeps. A successful HTTP response or a success toast alone is not
proof of persistence: reload and assert the saved result. API reads may provide
independent verification, but cannot replace the browser actions being tested.

Capture browser console errors, uncaught page errors, failed requests, and
unexpected HTTP failures. Expected validation/403 responses should be labeled
as expected, not counted as unexplained failures. Do not silently retry until
green; retain the initial failure and identify any subsequent rerun.

### Browser evidence and closeout

Write to `scan-evidence/BREAK/ui-verification/<UTC-run-id>/` (git-ignored), separately from scanner
reports. Include the target snapshot/commit, isolated base URL, exact runner
command or browser-tool steps, fixture assumptions, test result matrix, browser
logs and screenshots on failure; retain traces when supported. Record expected
versus observed behavior and steps to reproduce. Screenshots alone are not
proof that an interaction or persistence assertion passed.

Report **PASS**, **FAIL**, **BLOCKED**, or **NOT TESTED** for each flow. Distinguish
function tests, API tests, real browser interactions and physical-response tests.
If browser tooling is unavailable, finish independent inspection but mark browser
verification **BLOCKED**; never substitute source inspection and report PASS.

Stop only test processes this run started. Preserve failure evidence and never
clean up the user's existing sheets/pages. Disposable fixtures stay inside the
isolated copy; no automatic Git changes or application fixes. End with the single
smallest corrective task supported by the results.

## CI

The same six tools run on GitHub Actions in
[.github/workflows/security.yml](.github/workflows/security.yml), directly and
at pinned, checksum-verified versions (not through the GP-CONSULTING wrappers).
Gate: any secret in git history, any HIGH/CRITICAL vulnerability (Trivy or
Grype), any Semgrep ERROR, any Bandit HIGH, any Hadolint error. Everything else
is reported to the repository's Security tab as SARIF. Bandit skips B101
(assert) because the repository's tests are assert-based module self-tests.
The same workflow also runs zizmor (a security audit of the workflows
themselves) and, on pull requests, Dependency Review.
[.github/workflows/ci.yml](.github/workflows/ci.yml) runs the smoke test on a
clean checkout and publishes a CycloneDX SBOM on pushes to `main`;
[codeql.yml](.github/workflows/codeql.yml) adds CodeQL for Python and
JavaScript, [scorecard.yml](.github/workflows/scorecard.yml) runs OpenSSF
Scorecard weekly, and [.github/dependabot.yml](.github/dependabot.yml) keeps
pinned actions, pip packages and container images current. Repository settings
that no file can enforce are listed in
[docs/repo-security-settings.md](docs/repo-security-settings.md). A green run
is scan evidence for that commit only; it is not a local assessment under this
role and does not replace its evidence and coverage reporting.

## Wrapper limitations to account for

Verified by source inspection on 2026-09-23; recheck when the scripts change:

- Source commands commonly use `|| true` and suppress stderr. Some missing
  reports are replaced with empty JSON. `PASS`, `done`, exit zero, or an empty
  report alone cannot establish a successful clean scan.
- Trivy's wrapper invocation filters to HIGH/CRITICAL; do not claim lower
  severity coverage. Accepted helper flags do not necessarily change every
  tool's actual arguments.
- The combined runner invokes both source and infrastructure runners. It does
  not forward all advertised options, including scanner skips, to its children.
  Do not use it as a code-only shortcut.
- Legacy comments mention obsolete configuration/output directories. Resolve
  actual paths from current executable code and verify configurations exist.
- Printed auto-fix or triage commands are suggestions, not authorized actions.

## Evidence and handoff

Preserve raw `json-outputs/` and runner logs. Add control-first dated evidence
copies under the role's family directories, for example
`SystemAndServiceAcquisition/SA-11-semgrep-YYYY-MM-DD.json`. Record how each
copy maps to its raw report; keep the original unchanged. Redact any discovered
secret values from user-facing summaries.

The summary must include target/commit and working-tree qualification, commands,
tool versions, scan coverage/exclusions, severity counts, report links, and
tool-by-tool status:

- **COMPLETED — findings** or **COMPLETED — no findings in scanned scope**,
  only when execution and report validity are established.
- **BLOCKED**, **FAILED**, or **UNVERIFIED** for missing tools, execution errors,
  or insufficient evidence. Never translate these into zero findings.
- **NOT APPLICABLE** for absent artifact classes, such as no Dockerfiles.

Prepare the findings inventory for J and the canonical break-orchestrator;
do not send messages or spawn another agent without authorization. Mark active
validation needs `HANDOFF: half-B required`, naming the proposed tool and target.
No active attack tools, real BAS access, changes to the user's running process, secret retrieval,
automatic remediation, or Git staging/commits/pushes occur under this role.
