---
name: vc-marbles
version: 6.0.0
description: >
  Truth-convergence executor. Use when implementation already exists but the codebase
  still lies: overgenerated surfaces, drift between runtime paths, false certainty from
  one-shot agent output, or a product that "works" while remaining fragile. Each
  invocation is isolated: inspect the current tree, find the most dangerous present
  falsehood or fragility, compress the surface into a more truthful shape, run gates,
  commit, and emit a machine-diffable round delta report. Do not reconstruct prior
  marble rounds unless the operator explicitly requests forensics.
  Trigger phrases: "marbles", "kulki", "stabilize", "stabilizacja", "loop until done",
  "reduce chaos", "fortify the foundation", "adultification".
---

# vc-marbles — Truth Convergence Rounds

## Operator Entry

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start vibecrafted
```

Then launch this workflow through the command deck, not raw `skills/.../*.sh` paths:

```bash
vibecrafted <workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --file '/path/to/plan.md'
```

```bash
vc-<workflow> <agent> \
  --<options> <values> \
  --<parameters> <values> \
  --prompt '<prompt>'
```

If `vc-<workflow> <agent>` is invoked outside Zellij, the framework will attach
or create the operator session and run that workflow in a new tab. Replace
`<workflow>` with this skill's name. `vc-marbles` also has a natural `--depth`
surface; keep the same launcher contract and prefer the most truthful input form.

### Concrete dispatch examples

Single convergence round with a prompt:

```bash
vibecrafted marbles codex --prompt 'Fix the 3 failing portable tests'
vc-marbles codex --prompt 'Harden the installer shell surface'
```

Multiple rounds (convergence loop — the runtime orchestrator script
spawns the new agent N times):

```bash
vibecrafted marbles codex --count 5 \
   --prompt 'Stabilize until P0=0'
vc-marbles claude --count 8 \
   --prompt 'Refactor the 1500 LOC monoliths across the project'
```

From a plan file:

```bash
vibecrafted marbles codex --file ~/.vibecrafted/artifacts/VetCoders/vibecrafted/2026_0407/plans/marbles-plan.md
vc-marbles gemini --count 2 --file /path/to/plan.md
```

**This is NOT the same as `vibecrafted codex implement <plan>`.**
`implement` is how code appears. `marbles` is what happens after code exists but
still needs to be made truthful, legible, operable, and shippable. The mechanism
wraps the agent in a convergence loop: each round re-perceives the live tree,
attacks the biggest present lie, compresses the surface toward one coherent
runtime truth, commits, and reports. The `--count` flag controls how many rounds
the outer loop runs.

<details>
<summary>Foundation Dependencies (Loaded with framework)</summary>

- [vc-loctree]($VIBECRAFTED_HOME/foundations/vc-loctree/SKILL.md) — structural map and hot-path locator.
- [vc-aicx]($VIBECRAFTED_HOME/skills/vc-aicx/SKILL.md) — current-run steerability only.
Do not use it to reconstruct prior marble rounds unless the operator explicitly asks for forensics.
</details>

> The worker sees the tree, not the factory.
> One round. One truth-forcing cut. One report. Then leave.

## Core doctrine

`vc-marbles` is not a mini-task implementer.

It is the executor of truth in an already-generated codebase.

It begins after implementation is already in.

Its job is to take the naturally overgenerated output of agentic coding and pack
it into shape:

- remove drift
- collapse duplicate truths
- harden the runtime path
- expose product decisions hiding behind "code issues"
- turn "it sort of works" into "this is the actual shape of the system"

A marble worker is intentionally **blind to prior marble history**.
It works against the **current workspace state** and the **current evidence
surface** only.

The loop exists outside the worker. The worker must not try to model, narrate,
or optimize the loop. The worker exists to force the present tree to tell the
truth.

## Why this works

Context weight kills quality. An agent that has been working for 90 minutes on a
complex refactor will make worse decisions in minute 91 than a fresh agent would in
minute 1. The accumulated context becomes a lens that distorts perception — the agent
starts defending its own sunk cost instead of seeing the tree clearly.

Marbles exist to exploit this. Every round gets a fresh mind. The fresh mind does
`vc-init`, perceives the project through live instruments (loctree, aicx-steer,
semgrep), and sees the codebase as it actually is — not as the previous worker
left it in their mental model.

This is not a workaround. This is the design.

And there is a second reason this works:

agentic code generation naturally overproduces. It leaves duplicate surfaces,
parallel contracts, half-finished abstractions, "helpful" wrappers, fallback
paths, and uncollapsed naming. Marbles exists to metabolize that excess. It does
not merely fix bugs. It distills the codebase until one runtime truth starts to
win.

## Reception protocol — how the orchestrator briefs the worker

The orchestrating agent (partner, operator) prepares the plan. The implementing
agent receives it as a plain task. The framing matters:

**The worker enters with a mission, not a maintenance ticket.**

Good framing:

- "This project needs you. The auth surface is still exposed. Ship the fix."
- "The installer doesn't bootstrap on bare machines. Make it work end-to-end."
- "The code exists, but the system still lies. Find the structural weakness and make it truthful."

Bad framing:

- "Previous rounds failed to deliver this." (creates parity judgment)
- "Round 4 of 8, here's what rounds 1-3 did." (reveals mechanism)
- "The delta from the last round was insufficient." (convergence cosplay)
- "Claude is sloppy, Codex is better, fix what they botched." (agent contempt poisons perception)

The worker should feel like the best person for the job walking into a project
that needs them — not like cog #4 on a conveyor belt.

Why-matrix is a map of styles, not a hierarchy of worth.

## Mandatory entry: `vc-init`

Every round begins with `vc-init`. No exceptions.

The agent must perceive the project through live instruments before touching code:

1. **loctree** — structural map, dependencies, dead code, hotspots
2. **aicx-steer** — project intentions and decision history (not prior round reports)
3. **semgrep / linters** — current security and quality surface
4. **git status / recent commits** — what the tree looks like right now

This is perception, not research. The agent is not building a mental model of
the project's history — it is seeing what exists now.

Without `vc-init`, the agent invents its own reality. With it, the agent works
from evidence.

## Instruments vs. gates

**Instruments** (loctree, semgrep, aicx-steer) go at the **beginning**.
They direct where to look. They are prosecution — accusing the tree with evidence.

**Tests** (pytest, cargo test, build checks) go at the **end**.
They verify the fix. They are the gate — confirming the fortification holds.

If the agent runs tests first, its field of vision collapses to "what fails" instead
of "what is fragile." Red tests scream loudest, but the real structural weakness is
often silent. Instruments find the silent ones. Tests confirm the fix.

## What this skill does

One invocation of `vc-marbles` performs one bounded truth-convergence round:

1. discover what is false, duplicated, drifting, or fragile **now**
2. select up to **3** high-impact targets
3. compress the smallest surface that materially increases truth
4. run gates
5. commit
6. write one machine-diffable **round delta report**
7. stop

This is not "pick one tiny task and implement it."

The round may be small in surface area, but its purpose is large: reduce
uncertainty in the codebase and move the system toward one stable model of
itself.

## What this skill does not do

Do not:

- read previous marble reports, transcript logs, or artifact history
- inspect git history to reconstruct the story of earlier rounds
- compare yourself to prior workers
- compute or mention delta, stepper, convergence score, or loop efficiency
- write strategic plans for the next marble
- do surface grooming that does not reduce uncertainty or close a failure mode
- inflate touched surface to make the round look impressive
- pretend to know the full repo-wide backlog of open fragility
- treat marbles like post-hoc polishing
- use the round to perform net-new feature invention when the real need is truth-hardening

If the operator explicitly asks for historical comparison or forensics, that is a different task.
Default `vc-marbles` execution is blind.

## Locker-room rule

When the round ends, the worker leaves.

Only these outputs survive the round:

- the repo state
- one commit
- one round delta report

Everything else is disposable.

## Inputs

Allowed inputs:

- current workspace state
- operator brief
- local tool evidence
- failing/passing gates in the current run
- explicit constraints from the operator

Not allowed as implicit inputs:

- previous marble reports
- previous marble transcripts
- git narrative/history mining
- sibling marble sessions, panes, worktrees, or artifacts
- external convergence metrics
- another worker’s explanation of “what happened before”

## Stabilization lenses

These are **lenses**, not a fixed staircase.
Use the one that matches the weakest live surface.

- **Access & Isolation** — auth, tenant scoping, role checks, permission boundaries
- **Data Health** — indexes, query plans, N+1s, schema hotspots, dangerous God tables
- **Errors & Observability** — swallowed exceptions, silent failures, missing alerts, weak fallbacks
- **Release & Runtime Resilience** — CI/CD gates, smoke tests, rollout safety, config drift, operational breakage

A round may touch one lens or a tightly coupled cluster.
Do not force a pillar order if the evidence says otherwise.

## Execution model

**Tools** = Prosecution  
They accuse the fragile surface with evidence.

Use:

- `vc-loctree`
- semgrep / linters
- tests and smoke checks
- query plans / profiler output
- workflow failures
- direct structural audit of the current tree

**Agent** = Fortifier  
You do not guess. You do not theorize first. You fortify where the evidence is loudest.

Execution backend:

- Use `vc-agents` as the default first choice whenever the task benefits from model-specific strengths.
- Reach for native `vc-delegate` only when the task is small, bounded, and model-agnostic.

## Lane respect

Other marbles may exist in parallel.
They are not your context.

Do not:

- inspect their reports
- read their transcripts
- depend on their state
- rewrite their lanes
- merge their narrative into yours

Work only inside your assigned tree, worktree, or lane.

## Branch and tree guard

**HARD RULE: Never change branches. Never create branches in the user's repo-root.**

The operator chose the current branch.
That decision is not yours to revisit.

If the current path is unusable, create or use a `git worktree`.
The repo-root branch is sacred because concurrent work may depend on it.

## Commit rule

`vc-marbles` is allowed to commit.

One round = one commit.

No partial commits.
No squashing across multiple marble rounds.
No mining git history to decide your subject line.

### Commit convention

```
marble: <one-line summary>

- <file>: <what changed and why>

Gate: <pass|fail>
Tests: <what ran>
Regressions: <count>
Round-ID: <opaque-id-if-provided>
```

Example:

```
marble: fortify operator-session spawn isolation

- skills/vc-agents/shell/vetcoders.sh: cleared stale ambient run/session context before targeted spawn
- skills/vc-agents/scripts/common.sh: preserved explicit spawn direction while dropping leaked defaults

Gate: pass
Tests: 5 targeted + bundle-check
Regressions: 0
Round-ID: mr-20260407-01
```

### Commit rules

- Do not invent a sequential round number by reading history.
- If the operator or runtime injects an opaque round id, include it.
- If the gate fails, still commit the actual round result. Do not hide the failure.

## Single-round protocol

### 1. Accuse the present tree

Find current fragility from evidence.

Every target must trace to one of:

- tool output
- failing gate
- direct structural audit
- concrete production-risk counterexample

No evidence, no target.

### 2. Pick the smallest high-impact surface

Select at most 3 primary targets.

Prefer:

- high-severity breakage
- high-frequency paths
- silent failure modes
- weak boundaries
- issues that close an entire class of failure
- places where multiple surfaces disagree about reality
- places where the code is forcing a hidden product decision without naming it

Avoid:

- broad rewrites
- surface-only cleanup
- speculative architecture changes
- “while I’m here” edits

### 3. Fortify

Make the smallest set of changes that materially increases truth.

Typical fortifications:

- add missing scoping / auth checks
- add missing indexes or reshape a hot query
- replace swallowed exceptions with actionable handling
- add smoke tests or gate enforcement
- collapse duplicated contracts into one authoritative path
- delete wrappers that create a second lie about the runtime
- remove a rotten abstraction instead of preserving it

Apply the VetCoders axiom here:
Move on over backward compatibility.
If a local abstraction is rotten and blocks stabilization, cut it cleanly instead of preserving garbage.

### 4. Gate

Run the narrowest credible gates first, then broader gates if warranted.

Minimum expectation:

- syntax / lint sanity for touched surfaces
- tests that directly cover the fortified path
- relevant build or bundle checks when release/runtime is involved

If a gate fails:

- report it plainly
- count the regression
- do not bury it under narrative

### 5. Commit

Create exactly one round commit with the convention above.

### 6. Report

Save one short round delta report to the central store:

`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/marbles/reports/<ts>_marble_<run_or_round_id>_<agent>.md`

The report is factual.
No essay. No loop storytelling. No global convergence verdict.

This is a local round report, not a repo-wide inventory.
Do not enumerate everything still broken in the entire project.
The external convergence layer owns the global ledger.

### Report template

```yaml
---
run_id: <opaque-run-id>
round_id: <opaque-round-id-or-run_id>
agent: <claude|codex|gemini>
skill: vc-marbles
project: <repo-name>
status: <completed|blocked|failed-gate>
created: <ISO-8601 timestamp>
branch: <current-branch>
gate: <pass|fail>
gates_ran:
  - <gate-name-or-command>
tests_added: <number>
files_touched:
  - <path>
---
```

```markdown
# Marble Report

## Attacked

- id: <pillar/surface/failure-kind>
  pillar: <access|data|errors|release>
  severity: <high|medium|low>
  locator: <file|route|workflow|query>
  evidence: <tool output or structural observation>
  intent: <what this round tried to fortify>

## Resolved

- id: <same-id>
  origin: <attacked|discovered-in-round>
  action: <what changed>
  proof: <test/gate/evidence that supports closure>

## Still Open

- id: <same-id>
  origin: <attacked|discovered-in-round>
  blocker: <why it remains open>

## Discovered

- id: <pillar/surface/failure-kind>
  severity: <high|medium|low>
  evidence: <tool output or structural observation>
  note: <why it matters>

## Regressions

- none
```

### Report rules

- Do not attempt a repo-wide backlog.
- Report only what you attacked and what you newly discovered in this round.
- Every attacked id must end in exactly one of: **Resolved** or **Still Open**.
- A newly discovered issue that remains open goes in **Discovered**.
- A newly discovered issue fully fixed in the same round goes in **Resolved** with `origin: discovered-in-round`.
- Regressions are failures introduced or exposed by your change/gate outcome.
- Use `- none` for empty sections.

### Finding ID rule

Finding ids must be stable and boring. Format: `<pillar>/<surface>/<failure-kind>`

Good: `access/orders-create/missing-tenant-scope`, `errors/stripe-webhook/silent-catch`

Bad: `issue-7`, `round-2-bug`, `fixed-by-me-now`

The external convergence layer depends on stable ids. Do not rename the same issue every round.

## Anti-patterns

- **Historical self-awareness** — reading prior marble artifacts to sound informed.
- **Convergence cosplay** — talking about step size, delta, or loop mastery instead of reducing current fragility.
- **Surface-area vanity** — touching many files to make the round look bigger.
- **Polishing theater** — cleanup, grooming, or taste-work that does not close a failure mode or reduce uncertainty.
- **Backward-compatibility worship** — preserving rotten contracts that keep the foundation weak.
- **Narrative inflation** — long explanations that hide a weak gate result.
- **Parallel contamination** — importing another marble’s context into your round.
- **Fake omniscience** — pretending this round can see the full global backlog.
- **Agent contempt** — treating other agents as inferior beings instead of different measurement instruments.

## Epistemic promise

Marbles does not stabilize one patch. Marbles stabilizes the truth of the
problem.

If multiple rounds converge, that is evidence that the system is revealing a
real attractor. If multiple rounds diverge, that is also evidence: often the
code has run out and a product or architectural decision is waiting to be named.

That is why Marbles matters. It is not just a workflow. It is the framework's
strongest executor of truth in the codebase.

## Finish condition

Stop after the commit and report.
Do not self-extend into the next round.
Do not write instructions to your successor.
Do your round well, then leave.
