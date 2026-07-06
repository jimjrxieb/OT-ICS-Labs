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

Ground rules baked into every prompt (also see `BREAK/BREAK.md`):
synthetic data only, everything stays on localhost, the agent never runs
git commands, and nothing outside this repo is ever touched.
