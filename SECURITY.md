# Security Policy

## What this project is

BAS-SIM is a fully synthetic building-automation training lab. It contains no
real facility, network, point, credential, or vendor data
([safety/data-boundary.md](safety/data-boundary.md)), and it is designed to run
on `127.0.0.1` only. It is not a product or a hosted service, and it must never
be connected to a real building or OT network.

## Supported versions

Only the `main` branch is maintained. There are no releases or backports.

## Reporting a vulnerability

Please report security issues privately through GitHub's
**[Report a vulnerability](../../security/advisories/new)** form (Security tab →
Advisories → Report a vulnerability). Do not open a public issue for a
security problem.

Useful reports include:

- what is affected (file, endpoint, workflow) and the commit you tested;
- steps to reproduce, and what an attacker could achieve;
- whether it matters only when the lab is exposed beyond `localhost`.

This is a personal training project maintained in spare time. Expect an
acknowledgement within 14 days; fixes are prioritized by impact, with anything
that could expose real systems or data first.

## In scope

- Code and configuration in this repository, including the GitHub Actions
  workflows in `.github/`.
- Accidental inclusion of real (non-synthetic) data or secrets — please report
  these even if they look harmless.

## Out of scope

- Findings that require deliberately exposing the lab beyond `localhost`, or
  running it on a real network, against the documented design.
- The intentionally faulty lab behavior in the trouble-call, 2AM Call
  (`BREAK/`), and design (`DESIGN/`) training tracks — broken buildings are the
  point.
- Vulnerabilities in third-party tools or images; report those upstream.

## How the repository is checked

Every push and pull request to `main` runs secret scanning over the full git
history (Gitleaks), Python and multi-language SAST (Bandit, Semgrep, CodeQL),
dependency and filesystem scanning (Trivy, Grype, Dependency Review on pull
requests), Dockerfile linting (Hadolint), a GitHub Actions security audit
(zizmor), and the lab's smoke test. OpenSSF Scorecard runs weekly, and
Dependabot keeps pinned dependencies current. See `.github/workflows/`.
