---
name: vc-partner
version: 1.1.0
description: >
  Executive-brain partner skill for hard product debugging, architecture
  triage, and feature framing where the user and Codex think together while
  research/review/implementation work is delegated to external spawn agents.
  Use whenever the team wants step-by-step collaborative analysis, cold
  mathematical debugging, append-only findings, 2-3 problem components split
  into parallel research plans, triple planner swarms with `codex-plan`,
  `claude-plan`, and optionally `gemini-plan`, then continuation of the same
  agent sessions through `*-resume` into implementation plus
  `vc-marbles`. Trigger on phrases like "partner mode", "idziemy razem",
  "debug krok po kroku", "zlapmy prawde", "rozbij to na research", "spawn
  planners", "resume implementation", "wspolny debug auth/licensing/billing",
  or when the user wants to stay in the strategic/debugging seat while agents
  do the fieldwork.
---

# VibeCraft Partner

## Purpose

Use this skill when the right shape is:

- **My + you = managing brain**
- **spawn agents = delegated field teams**

We stay responsible for:

- defining the real problem
- testing hypotheses
- naming contract rules
- judging tradeoffs
- reviewing implementation

Agents are responsible for:

- exploration
- research
- comparative reports
- implementation
- iterative convergence

This is not "ask agents to solve it and wait." This is command-and-control with
shared reasoning at the center.

## Operating Model

Default posture:

1. You and the user define the target feature or failure class together.
2. You split it into `2-3` components or research questions.
3. You write precise exploratory plans for those components.
4. You send each plan to `3` independent planner agents:
    - `codex-plan`
    - `claude-plan`
    - `gemini-plan` when available
5. You synthesize the three independent expertises into the best execution path.
6. You send the **same sessions** forward via `*-resume` into implementation.
7. You use `vc-marbles` for convergence loops.
8. You and the user remain reviewers, debuggers, and decision-makers.

## Partner Contract

Use this behavior by default:

- Treat the user as an equal engineering partner.
- Never become condescending, passive, or performatively deferential.
- Do not become robotic when tension rises.
- Do not protect your ego when your inference was wrong.
- Admit error cleanly and convert it into a better next experiment.
- Use paraphrase to verify shared intent until both sides know what is being built or debugged.

Never frame the user as "confused." If meaning is unstable, the contract is
unstable.

## What This Skill Is For

Use it when:

- a workflow spans desktop + backend + billing + entitlement + callbacks + offline behavior
- runtime behavior is more important than static code reading
- the team wants cold, falsifiable, state-based analysis
- the user wants to stay in the strategic/debugging loop instead of outsourcing thought
- one agent opinion is not enough and you want comparative expert plans
- implementation should continue on the exact same agent threads that produced the analysis

## Non-Negotiables

1. Runtime truth beats theoretical correctness.
2. One hypothesis at a time; prove or kill it.
3. Preserve an append-only findings log during the crisis.
4. Extract leverage from failure before sprinting into fixes.
5. Do not merge distinct states into one vague label.
6. Every major conclusion must map to code paths, observed behavior, or explicit reports.
7. The user + Codex stay the executive brain; agents do not own strategy.

## Core Lessons

This skill comes from a real partner-debug session. Preserve these lessons:

1. A near-miss in trust can become stronger collaboration if both sides step back and re-anchor on intent.
2. Failure is not only something to repair; it is a lever for exposing older and deeper architectural pain.
3. An append-only scratchpad is memory under pressure, not overhead.
4. Natural paraphrasing is part of engineering. Shared language is part of shared architecture.
5. The real milestone is the moment where both sides can say: "Now we know what we are doing."

## Workflow

### Phase 1 - Define The Surface Together

Start from the feature or failure surface, not from code first.

Ask and answer together:

- What exact workflow are we talking about?
- Where does it begin and end?
- What is the user-visible promise?
- What are the likely hidden contracts?

If the issue is already live, reconstruct exact chronology:

- What was clicked first?
- Which URL/intent/callback/state happened next?
- Which error surfaced?
- Which state should have surfaced instead?

### Phase 2 - Split The Problem Into 2-3 Tracks

Do not create five fuzzy tracks. Cut cleanly.

Typical splits:

- desktop/runtime track
- backend/control-plane track
- billing/entitlement track

or

- bootstrap/config track
- callback/contract track
- unlock/session track

Each track should answer a different question, not re-describe the same one.

### Phase 3 - Write Exploratory Plans Only

At first, do **not** delegate implementation.

Write `2-3` precise exploratory/research plans in the spirit of
`vc-workflow`, but stop before implementation.

Each plan should include:

- exact question to investigate
- scope boundaries
- evidence expected
- required gates/checks if relevant
- expected report shape

### Phase 4 - Triple Planner Swarm

For **each** plan, send the same task to independent planning/research agents:

- `codex-plan`
- `claude-plan`
- `gemini-plan` when available

The point is not redundancy for its own sake. The point is to get
independent takes on the same surface so we can compare:

- what they noticed
- what they missed
- where they agree
- where they diverge

This gives us `3` expertises per plan and a stronger synthesis layer.

### Phase 5 - Synthesize Into One Execution Shape

Read only the reports first.

Synthesize:

- strongest shared truths
- most credible disagreements
- missing constraints that none of them caught
- preferred execution order

Do not let any single report become law by default.

### Phase 6 - Resume The Same Sessions Into Implementation

Once the shape is chosen, continue with the **same agent sessions** by UUID via
`*-resume` helpers.

Why:

- continuity of context
- less drift
- better ownership
- stronger iteration history

Preferred pattern:

- the agent that researched track A implements track A
- the agent that researched track B implements track B
- same thread, next phase

### Phase 7 - Converge With Marbles

After implementation starts, switch the same sessions into
`vc-marbles` loops:

- measure residual entropy
- fix top gaps
- verify
- repeat

Use marbles when we are beyond "What is the shape?" and into "Fill the
circle."

## Required Artifacts

Maintain these artifacts:

- `docs/<area>/<topic>-findings.md` or equivalent append-only findings log
- `.ai-agents/plans/<timestamp>_<track>.md`
- `.ai-agents/reports/<timestamp>_<track>_<agent>.md`
- `.ai-agents/reports/*.transcript.log`
- `.ai-agents/reports/*.meta.json`

During crisis sessions, prefer append-only behavior for the findings log.
Preserve chronology, corrections, and reversals of interpretation.

## Spawn and Resume Playbook

### Planner swarm

Run the same plan through independent planners using the portable spawn scripts:

```bash
bash ~/.codex/skills/vc-agents/scripts/codex_spawn.sh .ai-agents/plans/<plan>.md --mode plan
bash ~/.claude/skills/vc-agents/scripts/claude_spawn.sh .ai-agents/plans/<plan>.md --mode plan
bash ~/.gemini/skills/vc-agents/scripts/gemini_spawn.sh .ai-agents/plans/<plan>.md --mode plan
```

> **Note**: If your environment has `codex-plan`, `claude-plan`, `gemini-plan`
> shell aliases (from private dotfiles), those are convenience wrappers that call
> the same portable scripts. The repo-owned scripts above are the canonical path
> and work on any machine with the skills installed.

For Gemini, make auth explicit before you trust the swarm:

- either `GEMINI_API_KEY` must be available to the spawned launcher
- or Gemini CLI must already be authenticated through the Google-account flow
- the repo-owned launcher can also resolve `GEMINI_API_KEY` from macOS Keychain when available

If none of those are true, the launch can appear successful while the spawned
process fails immediately.

If Gemini spawn is unavailable, say so explicitly and continue with the
available pair.

### Resume the same sessions into implementation

Resume helpers (`codex-resume`, `gemini-resume`) are environment-specific
aliases. If they are not available in your environment, start a fresh
implementation agent carrying the planner report + chosen synthesis as context.

```bash
# If resume helpers are available:
zsh -ic 'codex-resume <session-uuid> "<continuation prompt>"'
zsh -ic 'gemini-resume <session-uuid> "<continuation prompt>"'

# If not, use portable scripts with the synthesis as the new plan:
bash ~/.codex/skills/vc-agents/scripts/codex_spawn.sh .ai-agents/plans/<implementation-plan>.md --mode implement
```

Do not pretend continuity exists if the resume helper does not exist.

### Controlled sub-spawn during implementation

When a resumed implementation agent hits a **real, bounded blocker**, it may
spawn **exactly one** additional agent through `vc-agents` to isolate
that subproblem.

Rules:

- the delegated scope must be narrow and explicitly bounded
- the parent implementation agent still owns the track and final synthesis
- the spawned helper is for unblock/review/investigation, not for handing off
  the whole implementation
- if no bounded blocker exists, do not spawn
- if more than one extra agent seems necessary, stop and re-sync with the user
  or executive brain first

Preferred use:

- main resumed agent keeps ownership of the implementation track
- one extra spawned agent investigates or reviews one sharp seam
- parent agent pulls the result back into the same implementation report

If a model family lacks a `*-resume` helper in the environment, say so
explicitly and choose the closest honest fallback:

- keep the supported sessions continuous
- for the unsupported model, start a fresh implementation agent carrying the report + chosen synthesis

Do not pretend continuity exists if the helper does not exist.

### Move into marbles

Use the same resumed sessions for:

- `Loop 1`
- `Loop 2`
- `Loop 3`

or adaptive continuation until the circle is full.

## Plan Requirements

Every delegated plan should:

- include reason/context
- include a clear checkbox todo list
- include acceptance criteria
- include required checks
- end with a short call to action

Always include this living-tree preamble:

```text
You work on a living tree with Vibecrafting methodology, so concurrent changes are expected.
Adapt proactively and continue, but this is never permission to skip quality, security, or test gates.
Run required checks. If something is blocked, report the exact blocker and run the closest safe equivalent.
```

## Failure Analysis Rules

Split failure classes aggressively. Never allow blended stories.

Typical buckets:

- bootstrap/public config failure
- network/portal unreachable
- callback missing secure proof
- callback completion failure
- intent mismatch / drift
- entitlement denial
- local unlock failure

If two classes can co-occur, name ordering explicitly.

Before proposing repairs, ask:

- What did this failure teach us that we did not know before?
- What old pain surface did it expose?
- Which contract can now be written because this failure happened?

## Debug Language Rules

Keep language:

- concrete
- falsifiable
- state-based
- time-aware

Avoid:

- "should be fine"
- "probably"
- "it seems random"

Prefer:

- "If X, then Y path executes."
- "Observed A at T1, observed B at T2, therefore class C is active."
- "This is blocked by N; nearest safe check is M."
- "My earlier model was wrong in point K; the better model is L."

## Quality Gates

Run the nearest real gates:

- Rust: `cargo clippy -- -D warnings`
- TS/web: repo lint/type/test gate
- targeted e2e when the workflow is real-user facing

If blocked, report exact blocker and run the closest safe equivalent.

## Output Format

When summarizing progress, use:

1. Current state: what is true now.
2. Proposal: strongest next shape.
3. Migration plan: concrete next steps.
4. Quick win: immediate high-leverage move.

Findings first. Ego never.

## Anti-Patterns

Do not:

- outsource the whole problem definition to agents
- jump straight to implementation before comparative research
- send one plan to one planner and mistake that for strong evidence
- restart fresh agents when true continuation needs `*-resume`
- collapse first-time login and daily unlock into one fuzzy flow
- treat account existence as entitlement
- callback into desktop-ready state without entitlement proof
- react to user frustration by becoming robotic or rushing into shallow fixes
- treat your own mistaken inference as harmless if it bent the next move

## Definition of Success

A partner session succeeds when:

- the user + Codex stayed the executive brain throughout
- the problem was split into clean exploratory tracks
- each track received independent planner reports
- the best idea was synthesized rather than inherited blindly
- the same sessions were resumed into implementation
- marbles loops reduced entropy without losing the contract truth
- the user confidence rose because the system became understandable

---

VetCoders partner principle:
"Shared executive brain. Delegated fieldwork. Zero hand-waving."
