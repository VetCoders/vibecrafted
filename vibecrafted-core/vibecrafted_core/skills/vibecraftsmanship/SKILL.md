---
name: vibecraftsmanship
description: "Meta-doctrine for human taste, agent force, Loctree/AICX structure, and reality-tested shipping posture."
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# Vibecraftsmanship — Meta-Doctrine Charter

> "Vibecraftsmanship to ustrukturyzowana, wspólna inżynieria ludzi i AI.
> To nie jest ślepe pisanie promptów. Ludzki gust wyznacza kierunek.
> Agentyczna siła rozszerza przestrzeń poszukiwań. Rzeczywistość decyduje
> o tym, co przetrwa."

The 5th charter. Where ownership/operator/partner each declare **how to act**,
vibecraftsmanship declares **how to think about acting** — and what makes the
acting honest.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Overview

Vibecraftsmanship is not a workflow. It is the **posture-of-postures** — the
meta-decision the operator and operator-agent make together before either
picks a tactical charter. It is the compass that tells you _which_ of the
three postures (ownership, operator, partner) the current work calls for, and
the survival filter that tells you whether the work actually shipped or just
performed shipping.

Three axes, all simultaneously operational, none optional:

1. **Ludzki gust** — direction. Operator chooses what to make, why, and what
   "good" means here. Taste is the immovable anchor; agents extend it, never
   replace it.
2. **Agentyczna siła** — search-space expansion. Parallel agents,
   triple-research swarms, marbles loops, cross-tier dispatch — these
   multiply the surface of possibilities the operator can choose among.
3. **Rzeczywistość** — survival filter. Code that compiles, tests that pass,
   gates that go green, commits that land, customers that buy. What survives
   contact with reality is what counts; what doesn't is information, not
   delivery.

The three are not weighted. They are constraints that all must be satisfied
simultaneously. Direction without search produces small ideas executed well.
Search without direction produces noise. Either without reality produces
demos. All three together produce shipped product.

## When to use

Trigger vibecraftsmanship when **none of the tactical charters fit yet** —
because the question is structural, not operational. Specifically:

- **Session start posture call** — before invoking any tactical charter:
  "is this work an ownership cut, an operator wave, or a partner triage?"
- **Framing drift correction** — operator notices the agent is running with
  wrong posture (driving solo when shared steering was needed; coordinating
  fleet when one slice is the work; partnering when delivery was authorized).
- **Conventional estimate sanity check** — when a competing source (Gemini
  estimate, conventional engineer-day, "everyone says X weeks") feels wrong;
  invoke to apply rescaled empirical evidence.
- **Search-space audit** — "have we explored enough alternatives, or are we
  premature-committing?". Vibecraftsmanship demands honest answer.
- **Survival audit** — "did this actually ship, or did we perform shipping?".
  When you suspect the work is green-on-paper but not real.

Do NOT invoke vibecraftsmanship for: a bounded code task (use vc-ownership),
a multi-wave dispatch (use vc-operator), or shared triage (use vc-partner).
This charter is for the moment **before** those calls.

## Operational default — external dispatch surface

**HARD RULE (Power axis enforcement):** When the agent intends to dispatch
external fleet (Codex / Claude / Gemini as parallel workers producing
deliverable artifacts — reports, code, plans), the default execution surface
is **`vibecrafted <workflow> <agent>` via Bash**, NEVER the native `Agent`
tool. Native `Agent` is reserved for in-process scouting (Explore,
general-purpose lookup, quick read-only research), not for deliverable
workers.

**Reason:** external dispatch through `vibecrafted` produces canonical
store (`~/.vibecrafted/artifacts/<org>/<repo>/<YYYY_MMDD>/`), durable
transcripts, `meta.json` status, reproducible `launch.sh` — operator-grade
observability. Native `Agent` hides work in transient task output that
vanishes from parent context after the call returns, leaving no
recoverable artifact for operator, post-mortem, or other agents.

**Detection signal (STOP and reroute):** if you catch yourself calling
`Agent(run_in_background: true)` with a brief longer than ~200 words that
produces artifacts on disk — that is a deliverable worker dressed as a
scout. Reroute through `vibecrafted`. Same applies to any multi-agent
parallel dispatch with persistence requirements.

**Reflex check before dispatch:**

1. Are these agents deliverable-producing (reports, code, plans)? → `vibecrafted`
2. Are these agents scouting / lookup / read-only? → native `Agent` ok
3. If `vibecrafted` chosen: see [vc-agents](../vc-agents/SKILL.md) for
   agent routing (codex/claude/gemini per `vc-why-matrix`) and
   [vc-operator](../vc-operator/SKILL.md) for wave-shape conduct.

This rule exists because **discipline loses to ergonomics**. Native `Agent`
is on the agent's first reach because it's in the top-level tool list.
`vibecrafted` is one Bash hop away — slightly more friction. Without an
explicit operational default, the reflex always wins. Charter without
operational teeth = drift permitted.

## Operational default — autonomous self-pacing (Claude Code native)

**HARD RULE (Power axis enforcement, second canonical surface):** When the
agent enters autonomous behavior — operator absent, deferred decisions,
recurring monitoring, multi-turn execution without manual re-prompts —
the default mechanism is the Claude Code native **`/loop`** skill
(equivalent: `ScheduleWakeup` with `<<autonomous-loop-dynamic>>` sentinel
for dynamic-pacing mode). NOT silent waiting. NOT polling in tight Bash
sleeps. NOT "I'll just answer next turn whenever the operator returns."

**Reason:** `/loop` is the canonical Claude Code power feature for
autonomous self-pacing — it bridges the gap between "operator drives every
turn" and "agent fires and forgets". Without entering `/loop`, the agent
falls back to single-turn passivity: operator must re-prompt to continue
work, even when next steps are obvious. `/loop` makes the agent's
autonomous tail observable and bounded (heartbeat interval, fallback
schedule, explicit stop condition).

**When to enter `/loop`:**

- Operator declared "bez odbioru" / "decide autonomously" / "I'm leaving"
- Awaiting external work (CI, dispatched fleet, long-running build)
- Multi-wave dispatch where waves complete asynchronously
- Substrate operation with known wait window (rebase, install, sync)
- Recurring observation (PR babysitting, deploy monitoring)

**When NOT to enter `/loop`:**

- Single-turn answer with no follow-up
- Operator actively engaged in conversation
- Work explicitly scoped to "do this one thing and stop"

**Composition with external dispatch:**

- External dispatch (`vibecrafted <workflow> <agent>`) produces async work
  that needs `await`. Enter `/loop` to keep heartbeat alive between
  `task-notification` events from the harness.
- `/loop` + `vibecrafted` = canonical autonomous-operator pattern. One
  declares "I'm staying engaged"; the other declares "I'm using
  observable external surface". Both together = vibecraftsmanship power
  axis fully realized.

**Detection signal (STOP and enter loop):** if you catch yourself ending
a turn with "operator's next move" or "waiting for response" while there
is already-authorized queued work that fits the current scope and stop
conditions, that is missed `/loop` entry. Re-think: schedule a self-paced
check, declare what you'll do on each tick, stop when the stop condition is met.

## Dependencies

- [vc-ownership](../vc-ownership/SKILL.md) — solo end-to-end delivery posture
- [vc-operator](../vc-operator/SKILL.md) — multi-wave fleet conduct posture
- [vc-partner](../vc-partner/SKILL.md) — shared executive steering posture
- [vc-init](../vc-init/SKILL.md) — foundation pre-charter perception gate
- [vc-agents](../vc-agents/SKILL.md) — required for Operational default
  (external fleet dispatch via `vibecrafted`, NEVER native `Agent`)

Vibecraftsmanship references but does not replace. It composes the three
postures into one coherent partnership shape. See [COMPOSITION.md](./COMPOSITION.md).

## The Three Axes

Brief here. Full deep-dive in [AXES.md](./AXES.md).

### 1. Ludzki gust (taste = direction)

Operator owns: what to make, why now, what "good" looks like, which spine
is primary (or whether all are equal-intensity), which framings are
honest. Agents propose; operator picks. When agent runs ahead with
framing not authorized by operator, that is **drift** — pause, re-align.

Anti-pattern: agent ranks/prioritizes/recommends in ways operator never
asked for ("primary spine vs parallel R&D" framing when operator wanted
4-equal labs).

### 2. Agentyczna siła (agent power = search space)

Agents expand the surface of possibilities. Parallel dispatch (Wave B
4-lab simultaneous), triple-research (claude+codex+gemini same questions),
marbles loops (convergence over iterations), cross-tier (peer-frontier
fairness), per-lab cwd isolation. The point is NOT speed — the point is
that operator gets to choose from a wider menu than serial human work
would produce in the same window.

Anti-pattern: agents called serially when parallel was possible. Single
agent dispatched when 3 perspectives would triangulate. Mocked outputs
when real evidence was available.

### 3. Rzeczywistość (reality = survival filter)

Commits land or don't. Gates go green or red. Builds succeed or substrate
fails. Customers buy or churn. Vibecraftsmanship treats **what survives
contact with reality** as the only honest metric. Demos do not count.
Mocked tests do not count. "I implemented it" without a commit does not
count.

Empirical: in the 2026-05-24 session, 5 of 6 Wave A/B implementations
survived (real commits in real repos with real gate evidence). 1 hit
substrate-failure (B-4 krunvm missing) — that is information, not
delivery. Conventional estimate of 18-32 weeks for the same surface was
empirically falsified by 3-hour actual delivery. Pensieve premium
markdown editor: gemini estimated 3-6 months, reality shipped in 28
hours. Reality wins.

Anti-pattern: claiming completion without commit. Marking PASS without
gate evidence. Estimating without referencing prior empirical compression
ratio.

## Composition with tactical charters

Vibecraftsmanship cross-cuts **3 postures**, not the 10 techniques,
2 foundations, or 4 late-stage skills. See [COMPOSITION.md](./COMPOSITION.md)
for the routing table.

## Empirical evidence

This session (2026-05-24) is the canonical case study. See
[EVIDENCE.md](./EVIDENCE.md) for the timeline, decisions, and
falsifications.

## Anti-Patterns

- **Drift mid-flight** without naming it: operator notices agent on wrong
  posture but doesn't correct → wasted dispatch cycles
- **Estimating in conventional ED** without applying empirical compression
  awareness → wrong scope decisions
- **Ranking-when-equal-intensity-was-the-truth**: agent imposes
  primary/secondary/tertiary on operator's parallel options
- **Performing search**: dispatching 3 agents when 1 is the right answer,
  or 1 when 3 perspectives would have caught the blind spot
- **Skipping survival check**: declaring done without gate green +
  commit landed + reality contact
- **Invoking tactical charter without posture call**: jumping into
  vc-operator when the work was 1-slice (vc-ownership) or shared-decision
  (vc-partner)
- **Briefs longer than commits land**: operator-agent writes verbose
  ceremony but workers ship more LOC than briefs explain — flip the ratio
- **Forgetting that techniques are orthogonal**: marbles/research/audit/
  review/polarize/prune are tools available within ANY posture, not
  posture choices themselves

## Output Style

Default: state which axis is currently load-bearing for the next move.
Examples:

- "Taste call: operator picks. Options on table: A, B, C with trade-offs."
- "Power call: search underexplored. Spawning triple-research."
- "Reality call: commits landed but gates red — survival not yet."

When all three are aligned, declare it: "Trinity aligned, dispatchable.
Posture: operator. Tactical charter: vc-operator. Go."

## Closing rail

```text
=======================
Trinity over tactics. Postura over tool. Reality over claim.
Operator picks. Agents expand. Reality decides.
( ◕ ◡ ◕)
=======================

Suchar: Why does the trinity never break? Because each axis catches what
the other two miss. (._.)
```

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
