You are an AI coding agent with shell access, working at the root of a
synthetic BAS/OT training lab repo. I'm a working HVAC/DDC technician
and I want to add ONE new fault to the trouble-call training library —
based on a real failure I've seen in the field. You'll interview me,
encode it, and prove it works.

Steps:
1. Read these first, in order:
   - data/input/fault_library.json — the 15 existing faults; this is the
     exact schema to follow (fault_id, equipment, category, symptom_text,
     affected_points, injection directives, correct_equipment,
     correct_category, explanation)
   - data/input/points.json — the available points and their normal
     ranges (fault injection can only perturb points that exist)
   - governance/BUILD/2-approvedbuilds/BP-006-trouble-call-diagnosis-mode.md
     sections on the injection schema — supported modes are: drift
     (rate_per_step from start_step), stuck/step/noise_flatline (pin at a
     value — noise_flatline reads as a dead/flatlined sensor), and
     forces (side effects like forcing another point or raise_alarm).
     Oscillation is NOT supported.
2. Interview me, ONE question at a time:
   - What happened, in my own words? (the war story)
   - What did the front end show first vs. what was actually wrong?
   - Which building/equipment here is the closest match? (If the fault
     needs a point that doesn't exist — e.g. a status or safety input —
     tell me, and add it to data/input/points.json following the existing
     schema, with a realistic normal range.)
   - What should the symptom_text say? (symptom only — never the cause;
     write it like a dispatcher or confused caller would)
3. Draft the fault entry and show it to me for approval BEFORE writing.
   The explanation field matters most: it must teach the "tell" — what
   in the trends/alarms points to this root cause and not its lookalikes.
4. After I approve: append it to data/input/fault_library.json (never
   modify existing entries), then verify:
   - python3 simulator/bas_sim.py --fault <new_id> --steps 12 runs clean
   - show me the actual trend values from data/output/trends.csv proving
     the signature looks like the real thing
   - scripts/run-smoke-test.sh still passes
   - if the front end is running, deal it to me once:
     POST /api/trouble-calls/new?fault_id=<new_id> and let me play it
5. Summarize what was added and where.

Rules: never run git commands. Never touch anything outside this repo.
Synthetic values only — no real facility names, addresses, hostnames, or
identifying details from my story; genericize them. Only touch
data/input/fault_library.json (and points.json only if a new point is
genuinely required).
