# GitHub repository security settings

Files in this repository (`.github/workflows/`, `.github/dependabot.yml`,
`SECURITY.md`) cannot turn on GitHub's own protections. Apply these once in the
repository settings, then re-check after any settings change. Paths are the
GitHub web UI as of 2026; names occasionally move.

## Settings → Advanced Security (Code security)

- [ ] **Dependency graph**: on (required by Dependency Review and Dependabot).
- [ ] **Dependabot alerts**: on.
- [ ] **Dependabot security updates**: on (security fixes open PRs
      automatically; version updates come from `.github/dependabot.yml`).
- [ ] **Secret Protection → Secret scanning**: on.
- [ ] **Secret Protection → Push protection**: on. Blocks a push that contains
      a recognized secret before it reaches GitHub; Gitleaks in CI is the
      second line.
- [ ] **Private vulnerability reporting**: on. `SECURITY.md` points reporters
      to it.
- [ ] **Code scanning**: leave **default setup off**. CodeQL runs from
      `.github/workflows/codeql.yml` (advanced setup); enabling both conflicts.

## Settings → Actions → General

- [ ] **Workflow permissions**: *Read repository contents and packages
      permissions*. Every workflow here also sets `permissions:` explicitly.
- [ ] **Allow GitHub Actions to create and approve pull requests**: off.
- [ ] **Actions permissions**: *Allow OWNER, and select non-OWNER, actions and
      reusable workflows*, then allow actions created by GitHub plus
      `ossf/scorecard-action@*` (the only third-party action used).
- [ ] **Require actions to be pinned to a full-length commit SHA**: on, if
      offered. Every `uses:` here is already SHA-pinned.
- [ ] **Fork pull request workflows from outside collaborators**: *Require
      approval for all external contributors*.

## Settings → Rules → Rulesets (branch `main`)

Create a ruleset targeting the default branch:

- [ ] **Restrict deletions** and **Block force pushes**.
- [ ] **Require a pull request before merging** (for a solo repo, 0 required
      approvals still forces changes through the checks below).
- [ ] **Require status checks to pass**, adding the check names after their
      first run: `Smoke test (clean checkout)`, each job in `security`
      (Gitleaks, Bandit, Semgrep, Trivy, Grype, Hadolint, zizmor,
      Dependency review), and `Analyze (python)` /
      `Analyze (javascript-typescript)`.
- [ ] **Require code scanning results**: CodeQL, blocking on *High or higher*
      security alerts, if offered.
- [ ] Optional: **Require signed commits** (set up SSH or GPG commit signing
      locally first).

## Account

- [ ] Two-factor authentication on the owning GitHub account, preferably a
      passkey or security key.
- [ ] Review **Settings → Developer settings → Personal access tokens**:
      remove unused tokens; prefer fine-grained tokens scoped to one
      repository with an expiry.

## After enabling

1. Push to `main` (or open a pull request) and confirm every workflow runs.
2. Check **Security → Code scanning** for results from Gitleaks, Bandit,
   Semgrep, Trivy, Grype, Hadolint, zizmor, CodeQL and Scorecard.
3. Add the status-check names to the ruleset (they appear only after a run).
