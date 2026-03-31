---
name: vc-marbles
version: 2.0.0
description: >
  Counterexample-guided convergence — the loop that makes code healthier.
  Runs adaptive loops that ask one question: "what is still wrong?"
  Each fix eliminates a counterexample to health — and reveals the next one.
  The system cannot get worse, only better. Monotonic entropy reduction.
  No target needed. No plan needed. Just repeated pressure against wrongness.
  Stop when nothing is wrong. The circle is full.
  Trigger phrases: "marbles", "loop until done", "fill the gaps", "kulki",
  "iteruj aż będzie gotowe", "convergence loop", "counterexample",
  "what is still wrong", "adaptive loops", "keep going until clean",
  "wypełnij okrąg", "entropy reduction", "konwergencja".
---

# vc-marbles — Convergence Through Counterexample

> Not "is it correct?" — that cannot be proven.
> Only "what is still wrong?" — and eliminate it.
> Each loop removes entropy. Stop when the circle is full.

## The Mechanism

Traditional quality asks: _is this correct?_ and tries to prove yes.
That question has no finite answer for a living codebase.

Marbles asks a different question: **what is still wrong?**

Each loop inspects the current state and finds **counterexamples** —
concrete things that contradict health. A dead export in `utils.ts:42`.
A circular import between `auth/` and `api/`. A twin export `Button`
living in two files. These are not abstract noise. They are specific,
named, located violations of health.

Each fix is small. But each fix **changes the landscape** for the next
loop, exposing issues that were previously hidden beneath worse ones.

This is counterexample-guided convergence — CEGIS applied to code:

```
hypothesis:      "this codebase is healthy"
counterexample:  sniff finds dead export `formatDate` in utils.ts:42
correction:      remove dead export
new landscape:   utils.ts is now empty → new counterexample revealed
correction:      remove empty file
new landscape:   import in api.ts pointed to utils.ts → broken import revealed
correction:      fix import
new landscape:   cycle between api.ts and auth.ts disappeared → health score jumps

No single loop understood the whole.
Each loop only answered: "what is still wrong?"
The convergence was emergent.
```

### The Cascade Effect

Findings are not a flat list to check off. They form a **directed graph**
where fixing one reveals the next. This is the primary convergence driver:

- Dead export removed → file becomes empty → empty file is new finding
- Empty file removed → import breaks → broken import is new finding
- Import fixed → cycle disappears → health score jumps
- Health score jump → previously-masked P2 findings become visible

Each fix **irreversibly narrows** the space of possible bugs.
You cannot go backwards. Entropy drops monotonically.

This is why a drunk developer sleeping on the Return key can wake up
to a healthier repo. The agent had no plan. It had no target. It only
had the ability to find what was wrong and a key that said "again."

### Dual-Source Truth

Convergence becomes stronger with **multiple independent sources of
truth** that can counterexample each other:

```
sniff says: "exportFoo is dead"     → hypothesis
dist says:  "exportFoo is in bundle" → counterexample to sniff
agent checks: dynamic import         → hypothesis corrected
sniff learns: skip dynamic imports   → error class eliminated permanently
```

When two tools agree — confidence is high.
When they disagree — the disagreement IS the counterexample.
Cross-validation between sources is a convergence accelerator.

## When To Use

- After first implementation pass leaves known gaps
- When followup reveals findings that need iterative fixing
- When the team says "keep going until it's clean"
- When Plague Score > 20 after first hydration
- Anytime the answer to "is it done?" is "almost"
- When you need adaptive iteration count (not fixed 2 loops)

## The Loop Schedule

### No Fixed Loop Count

There is no fixed number of iterations. The loop runs until the circle
is full — nothing wrong remains. A trivial task may converge in 1 loop.
A massive architectural change may take 12. The schedule is driven by
measurement, not prediction.

```
The loop count is determined by what remains wrong, not upfront estimation.
After each loop, ask: "what is still wrong?" If something → loop again.

Factors that affect how many loops a task needs:
- LOC changed in first pass
- Number of files touched
- Cascade depth (how many layers of hidden issues exist)
- Blast radius from loctree impact()
```

### Step Size (Natural Priority)

The agent fixes what it finds. In practice, severe issues surface first
because they are the most visible. As severe issues clear, subtler ones
emerge from underneath.

```
Early loops:  Severe issues surface naturally — structural breaks, P0 blockers
Middle loops: Medium issues emerge from under the severe ones
Late loops:   Polish issues become visible — naming, edge cases, docs
```

This ordering is **emergent**, not prescribed. The agent does not need
to categorize findings into P0/P1/P2 before fixing them. It fixes what
it finds. The cascade handles priority naturally — severe issues block
visibility of subtle ones, so they get fixed first by construction.

P0/P1/P2 labels remain useful for **reporting** convergence trajectory,
not for steering which findings to fix.

## Convergence Protocol

### Each Loop Iteration

```
┌─────────────────────────────────────────────────────────┐
│  LOOP N                                                  │
│                                                          │
│  1. ASK: "what is still wrong?"                          │
│     └─ Read previous loop's findings                     │
│     └─ Run quality gates (multiple independent sources)  │
│     └─ List concrete counterexamples to health           │
│                                                          │
│  2. TARGET the most prominent counterexamples            │
│     └─ Write focused fix plan for TOP findings only      │
│     └─ Max 3-5 items per loop (don't boil the ocean)     │
│     └─ Expect cascades: fixing these will reveal more    │
│                                                          │
│  3. ELIMINATE counterexamples                             │
│     └─ vc-agents (first choice) or vc-delegate (small)   │
│     └─ Each fix narrows the space of possible bugs       │
│                                                          │
│  4. OBSERVE the new landscape                            │
│     └─ Run gates on the changed codebase                 │
│     └─ Note: NEW findings may appear (cascade effect)    │
│     └─ This is expected and good — hidden issues exposed │
│                                                          │
│  5. SCORE                                                │
│     └─ Calculate convergence metrics                     │
│     └─ Distinguish cascade from divergence               │
│     └─ Decide: continue or converged?                    │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

### Convergence Metrics

After each loop, calculate:

```markdown
## Loop N Convergence Report

What is still wrong:

- P0 count: X (must be 0 to converge)
- P1 count: X (must be 0 to converge)
- P2 count: X (must be 0 to converge — full circle fill)
- Cascade findings: X (new issues revealed by fixes — expected)

Quality gates:

- Build: pass/fail
- Lint: pass/fail
- Tests: X/Y passing
- Security: pass/fail

Counterexample trajectory:

- Findings from previous loop resolved: N
- New findings revealed by fixes (cascade): N
- Net counterexamples remaining: N
- Files touched this loop: N
- Net LOC delta: +X / -Y

Convergence score: X/100

- 0-30: deep issues, large cascade potential
- 30-60: converging, cascades settling
- 60-85: nearly converged, only shallow issues remain
- 85-99: close — remaining items are isolated, no cascades
- 100: nothing wrong remains — circle is full
```

### Stopping Criteria

**STOP iterating when ANY of these are true:**

1. **Nothing is wrong** — no counterexamples remain at any priority
2. **Convergence score = 100** — all findings resolved
3. **Two consecutive loops with zero delta** — plateaued (reassess)
4. **User says stop** — always respected

**DO NOT STOP when:**

- Counterexamples remain (unless user explicitly accepts risk)
- Quality gates failing
- Divergence detected (stop iterating, but investigate — don't ship)

### Cascade vs Divergence

When loop N has MORE findings than loop N-1, distinguish:

**Cascade (healthy):** Previous findings are RESOLVED, but new ones
appeared because fixes revealed hidden issues.

```
Loop N-1: 3 findings (A, B, C)
Loop N:   4 findings (D, E, F, G) — A, B, C are gone

This is cascade. Entropy decreased even though count increased.
The new findings are shallower than the old ones.
Continue iterating — the cascade will settle.
```

**Divergence (unhealthy):** Previous findings are STILL PRESENT,
and new ones appeared on top.

```
Loop N-1: 3 findings (A, B, C)
Loop N:   5 findings (A, B, C, D, E) — originals still there!

This is divergence. Fixes are introducing new problems without
solving old ones. Entropy increased.

Possible causes:
1. Scope too broad — narrow the fix scope
2. Wrong abstraction — step back and re-examine
3. Living tree conflict — other changes interfered
4. Agent hallucination — verify the "fix" actually fixed anything

Action: STOP. Re-run vc-workflow (Examine phase) on affected area.
Do not continue blind iteration on a diverging trajectory.
```

## Implementation Pattern

### Supervisor / Watchdog Mode

When `marbles` acts as a supervisor rather than the primary implementer,
run a standing watchdog loop that periodically checks the branch, reads fresh
agent artifacts, and writes a rolling status snapshot.

Use this mode when:

- external agents are already implementing in parallel
- the main thread should stay available for synthesis and decisive cuts
- the team wants a recurring pulse without manually babysitting every run

Canonical cadence:

- every `600` seconds by default
- shorter only for short fire drills
- longer only when gates are expensive and progress is slow

The watchdog loop is not a substitute for thinking. It is a heartbeat:

```bash
while true; do
  sleep 600
  # inspect branch status
  # inspect fresh agent reports/meta/transcripts
  # write/update a supervisor snapshot artifact
  # decide whether to intervene, continue, or stop
done
```

Preferred outputs:

- `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/supervisor-latest.md`
- `~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/supervisor-watch.log`

If the platform supports a native recurring prompt primitive such as `/loop`,
prefer combining it with `marbles` rather than replacing `marbles` with it:

```text
/loop 10m <marbles supervisor prompt>
```

The timer provides cadence.
`marbles` provides convergence logic, counterexample tracking, and stop conditions.

Supervisor mode must still:

- track counterexample trajectory
- distinguish cascade from divergence
- escalate when agents plateau
- stop when nothing is wrong

### Using vc-delegate (native, small-task fallback)

```
For each loop:
  1. Read previous findings
  2. Select top 3-5 actionable counterexamples
  3. Launch parallel Task agents:

     Task("Fix: <finding-1>", prompt=<focused fix plan>)
     Task("Fix: <finding-2>", prompt=<focused fix plan>)
     Task("Verify: run gates", prompt="cd $ROOT && <gate commands>")

  4. Collect results
  5. Write loop report to ~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_<slug>_loop_N.md
  6. Calculate convergence score
  7. If not converged → loop N+1
```

### Using vc-agents (Terminal, first choice)

```
For each loop:
  1. Write loop plan to ~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/plans/<ts>_<slug>_loop_N_fixes.md
  2. Spawn agent with plan
  3. Read report from ~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<ts>_<slug>_loop_N.md
  4. Run gates locally
  5. Calculate convergence score
  6. If not converged → loop N+1
```

## Output Format

### Per-Loop Report

```markdown
# Marbles Loop N: <slug>

Date: <YYYY-MM-DD>
Duration: <time>

## What Was Wrong (before)

- P0: X | P1: X | P2: X
- Convergence score: X/100

## Counterexamples Eliminated

1. [P1] <finding> → <fix applied> → <result>
2. [P2] <finding> → <fix applied> → <result>
3. [P1] <finding> → <fix applied> → <result>

## What Is Still Wrong (after)

- P0: X | P1: X | P2: X
- Cascade findings revealed: X
- Convergence score: X/100

## Gate Results

- Build: pass/fail
- Lint: pass/fail
- Tests: X/Y
- Security: pass/fail

## Delta

- Counterexamples eliminated: N
- Cascade findings revealed: N
- Net change: -N (negative = converging)

## Decision

- [ ] Continue → Loop N+1 (reason: <what remains wrong>)
- [ ] Converged → nothing wrong, proceed to DoU
- [ ] Diverging → stop and re-examine
```

### Final Convergence Report

```markdown
# Marbles Convergence: <slug>

Date: <YYYY-MM-DD>
Total loops: N
Total duration: <time>

## Trajectory

| Loop | P0  | P1  | P2  | Cascade | Score | Delta |
| ---- | --- | --- | --- | ------- | ----- | ----- |
| 1    | 2   | 5   | 8   | —       | 15    | —     |
| 2    | 0   | 3   | 6   | +2      | 40    | +25   |
| 3    | 0   | 1   | 4   | +1      | 65    | +25   |
| 4    | 0   | 0   | 2   | 0       | 85    | +20   |
| 5    | 0   | 0   | 0   | 0       | 100   | +15   |

## Convergence Curve

Score: 15 → 40 → 65 → 85 → 100
████████████████████████████████████████████████

## Final State

- Nothing wrong remains
- Quality gates: all passing
- Cascade: settled (no new findings in final loop)
- Circle: full

## Verdict

DoU → DoD transition: COMPLETE
Plague Score before: XX → after: XX
Ready for: Phase 3 (dou → decorate → hydrate → release)
```

## The DoU → DoD Transition

This is the moment the circle is full:

```
DoU (Definition of Undone) = measuring what is still wrong
DoD (Definition of Done)   = nothing is wrong, circle is full

The transition happens when:
- No counterexamples remain at any priority
- Quality gates pass
- Cascade has settled (last loop revealed nothing new)
- Stranger test passes (someone unfamiliar can use it)

At this point, DoU transforms into DoD:
  "What is still wrong?" → "Nothing."
  ~~DoU~~ → **DoD**
```

## Integration with VibeCrafted Pipeline

```
scaffold → init → workflow → followup → [MARBLES] ↻ → dou → decorate → hydrate → release
                                         ^^^^^^^^^^^^^
```

Marbles is the gate between building and shipping.
It does not loop back to workflow. It loops itself.
implement/spawn are internal execution tools used by workflow and marbles.

## In-Session Execution (Plugin Infrastructure)

Marbles has a plugin infrastructure in `references/` that enables in-session
self-referential loops through Claude Code's Stop hook API:

- **`/marbles` command** (`references/commands/marbles-loop.md`) — slash command
  that starts a loop in the current session
- **`/cancel-marbles` command** (`references/commands/cancel-marbles.md`) — cancels
  the active loop
- **Stop hook** (`references/hooks/stop-hook.sh`) — intercepts session exit,
  reads the last assistant message, checks for completion promise or iteration
  limit, and feeds the same prompt back if the loop should continue
- **Setup script** (`references/scripts/setup-marbles-loop.sh`) — creates the
  `.claude/marbles.local.md` state file with frontmatter (iteration count,
  max iterations, completion promise, session ID)

### How It Works

1. User runs `/marbles <prompt> --completion-promise 'DONE' --max-iterations 20`
2. Setup script writes `.claude/marbles.local.md` with the prompt and settings
3. Agent works on the task and tries to exit
4. Stop hook fires, reads the state file and transcript
5. If completion promise found in output OR max iterations reached → allow exit
6. Otherwise → block exit and inject the same prompt as new input
7. Agent sees its previous work in files/git, iterates on the same task

This is the in-session counterpart to the Supervisor / Watchdog mode described
above. Supervisor mode uses external observation; the plugin infrastructure
uses Claude Code's own hook API for zero-overhead self-referential iteration.

### Background Marbles (Ghost Mode)

The plugin infrastructure enables a pattern where marbles runs as a background
process. The Stop hook keeps the session alive while the agent iterates. This
is useful when:

- the user wants to walk away and let the agent converge
- external agents are not needed (single-session task)
- the task fits in one context window

Ghost mode is not a separate feature — it is the natural consequence of running
`/marbles` with `--max-iterations` or `--completion-promise` and letting the
hook do its job.

## Anti-Patterns

- Fixed loop count ("always run 4 loops") — defeats adaptive convergence
- Looping without asking "what is still wrong?" — blind iteration
- Rigid P0→P1→P2 ordering as steering — cascades don't respect categories
- Continuing past convergence (overfit — introduces new problems)
- Looping without writing reports (no trajectory = no learning)
- Confusing cascade with divergence (new findings after fixes can be healthy)
- Ignoring actual divergence (old findings still present + new ones = stop)
- Single counterexample per loop (too slow — target 3-5 per loop)
- Entire codebase per loop (too broad — scope to affected area)
- Treating P0/P1/P2 as steering mechanism instead of reporting labels

## Why This Works

1. **Agents generate approximations** — next-token prediction always introduces gaps
2. **Gaps are findable** — quality gates, structural analysis, and runtime checks can locate specific counterexamples
3. **Counterexamples are eliminable** — each one is a concrete, actionable thing to fix
4. **Fixes change the landscape** — removing one issue reveals the next (cascade effect)
5. **Entropy drops monotonically** — the system cannot get worse through counterexample elimination
6. **No target needed** — the agent doesn't need to know what "healthy" looks like, only what "wrong" looks like
7. **Convergence is emergent** — the destination reveals itself only after you arrive
8. **Multiple truth sources accelerate** — when `sniff` and `dist` disagree, the disagreement IS the counterexample
9. **Divergence is detectable** — if old problems persist while new ones appear, stop

The circle fills. Not "enough." All the way.
Nothing wrong remains. Quality gates pass. The circle is full.

That's DoD. Not "good enough." Done.

---

_"Not 'is it correct?' — that cannot be proven._
_Only 'what is still wrong?' — and eliminate it._
_Stop when the circle is full."_

_Vibecrafted with AI Agents by VetCoders (c)2026 VetCoders_
