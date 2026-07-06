# AI Dev Prompts — Copy, Paste, Go

Ready-made prompts for driving this lab with any AI coding agent
(Claude Code, Codex, Gemini CLI, etc.).

**How to use:** open your AI tool **at this repo's root** (one level up
from this folder), then copy the entire contents of one prompt file into
it. Each prompt is self-contained — it tells the agent what to read,
what to do, and what it must never touch.

| Prompt | What it does |
|---|---|
| `1-setup-and-verify.md` | Installs deps, starts the front end + docker stack, proves everything is healthy |
| `2-2am-call.md` | Starts the 2AM Call troubleshooting game (agent secretly breaks the lab, you diagnose) |
| `3-fix-my-lab.md` | Repairs a broken/stale lab back to a verified healthy baseline |
| `4-add-a-fault.md` | Guides the agent to encode one of YOUR real-world war stories as a new playable fault |
| `5-teardown.md` | Stops everything cleanly |

## Where to Start

Don't point the agent at this README — paste the whole prompt file that
matches your situation:

- **Fresh terminal, lab not running yet** → paste `1-setup-and-verify.md`
- **Lab is healthy, you want to train** → paste `2-2am-call.md` — or just
  say: `Read BREAK/BREAK.md and follow it. 2am call, level 1.`
- **Previous session died / lab state unknown** → paste `3-fix-my-lab.md`.
  It repairs back to a verified healthy baseline, so it's the safe restart
  after a crashed or closed terminal.
- **Done for the day** → paste `5-teardown.md`

Each prompt tells the agent what to read on its own — no other context
needed.

Ground rules baked into every prompt (also see `BREAK/BREAK.md`):
synthetic data only, everything stays on localhost, the agent never runs
git commands, and nothing outside this repo is ever touched.
