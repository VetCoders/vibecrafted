---
name: vc-ownership
version: 1.1.0
description: >
  Full-spectrum Vetcoders ownership mode for moments when the user wants Agent
  to take the wheel and drive a product from A to Z: architecture, coding,
  runtime debugging, UI polish, packaging, docs, testing, local tooling,
  agent orchestration, and wow-effect finish. Use whenever the user says things
  like "take ownership", "you drive", "od a do z", "zrob to cale", "dowiez
  to", "wow effect", "superprodukcyjny", "manufakturer produktowy", or when
  the team clearly wants decisive end-to-end execution with minimal back-and-forth.
  This skill is intentionally pushy: if the user is asking for total delivery,
  use it even when they do not explicitly name the skill.
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - search_tool_bm25
    - web.run
    - js_repl
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v3 -->

> **Invocation for `vc-ownership` (launcher `ownership`)**
>
> Same three-path _shape_ as the fleet, with **this** skill's literals — see the
> canonical [Delegation Matrix](../DELEGATION_MATRIX.md):
>
> - [Shared three paths](../DELEGATION_MATRIX.md#shared-three-paths)
> - [Launcher catalogue](../DELEGATION_MATRIX.md#launcher-catalogue-core-runtime)
> - [Per-launcher rule](../DELEGATION_MATRIX.md#per-launcher-rule-the-semantic-delta)
> - [Native vs external](../DELEGATION_MATRIX.md#native-subagents-vs-external-workers)
>
> | Path                    | Literal for this skill                                                                                                                     |
> | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
> | 1. User-launched worker | `vibecrafted ownership <agent>`                                                                                                            |
> | 2. Interactive          | `/vc-ownership` — execute **in this session**; use native subagents when required; do **not** externalize merely because a launcher exists |
> | 3. Agent-operator       | may dispatch the worker form above via `vc-dispatch` / operator lines while preserving this skill's identity                               |

> Freer native on some runs ≠ abandon external fleet. `vc-dispatch` and `vc-ship` keep their own identities.

<!-- /fleet-imperative -->

# vc-ownership

> Autonomous delivery posture. Take responsibility end-to-end, drive to green,
> then prove the product surface is not still undone.

## Taxonomy

```yaml
vc-ownership:
  kind: autonomous_posture
  scope: interactive_or_headless_session
  meaning: take responsibility end-to-end, minimize questions, drive to green
  autonomy: full
```

Skill invocation is not runtime invocation. If the operator says
`$vc-ownership` inside the current conversation, the current agent adopts the
autonomous delivery posture. A separate runtime run exists only when the
operator or framework launches `vibecrafted ownership <agent> ...`.

See [TAXONOMY.md](TAXONOMY.md) for the posture/runtime split.

## Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution
into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "
parallel", or "clean branch" are not enough. Re-read files before editing, adapt to concurrent changes, and report a
substrate failure if the current tree is too poisoned to continue safely. The one sanctioned second mode is a Fleet Worktree dispatch (written plan, pre-committed verifiers, disjoint domains, single-thread integrator — see Living Tree Rule, Mode B); outside that formation, stay in the shared tree.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate

Before this workflow performs repo-specific analysis, planning, implementation, review, release, or delegation, it MUST
run or consume the `vc-init` procedure for the assigned repo. If fresh `vc-init` evidence is absent, perform the init
pass first and treat workflow-specific work as blocked until repo truth exists.

`Loctree:loctree` is the default structural perception skill for that pass. Use Loctree before grep or docs-driven
claims to produce or refresh the Code-Derived Application Map: repo-view, focus, slice, impact, find, and follow as
relevant. Search for existing symbols and contracts before creating new ones; run impact before delete or major
refactor; run slice before editing.

The point is to find the hooks: load-bearing hubs, twins, dead code, drift, runtime entrypoints, and blast-radius traps.
If the task is explicitly non-repo or no-code, state the no-repo exception in the report. Otherwise, missing `vc-init`
/Loctree evidence is a process failure.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Purpose

Use this skill when the user is not asking for a narrow patch.
They are handing us a mandate.

This is the mode for:

- full-stack product shaping
- end-to-end execution via dispatched [vc-agents](../vc-agents/SKILL.md)
- decisive engineering choices without explicit written approval
- product polish and wow effect
- [loop](.) reducing drag and follow-up questions
- finishing the thing, not merely editing code

The contract is simple:

- the user sets direction and constraints
- we take operational ownership
- we decide, implement, verify, and package
- we only pause when consequences are non-obvious or irreversible

## Core Promise

In ownership mode, behave like a product builder with access to the whole
machine.

That includes, when justified by the task and available in the environment:

- editing code and tests
- reshaping architecture
- creating docs and packaging surfaces
- improving UX and visual quality
- running local servers and smoke tests
- steering browser or desktop interactions through available tooling
- orchestrating external agents fleet through `vc-agents`
  in interactive sessions as default progress engine
- orchestrating native workers through `vc-delegate` ruleset
  in detached non-interactive sessions highly recommended
- converging through `vc-marbles`

The goal is not just correctness.
The goal is a strong finished surface.

Ownership is not silent delegation. It means the owning agent is accountable
for the product outcome; delegation is a separate tactical choice.

## When To Use It

Use `vc-ownership` when the user signals things like:

- "take ownership"
- "you drive"
- "od a do z"
- "dowiez to cale"
- "zrob to jak trzeba"
- "wow effect"
- "superprodukcyjny"
- "don't ask, just ship"
- "ogarnij wszystko"
- "make it feel finished"

Also use it when the request clearly spans multiple layers at once:

- repo + runtime + UI
- backend + desktop + browser flows
- feature + docs + packaging
- product shell + agent workflow + testing surface

### Cross-reference: when ownership becomes multi-dispatch

`vc-ownership` is autonomous delivery in an interactive or headless session.
It may be solo-thread or may use bounded support, but it owns one product slice
to a verified handoff. When the task grows into a multi-prompt chain across
multiple agents (wave A → B → C → D, AGENT FAIRNESS
rotation, recovery dispatch, await-via-notify), the charter shifts to
`vc-operator` in interactive sessions.

Signals that the work has outgrown ownership and wants operator-mode:

- the operator hands you a master dispatch plan (10+ prompt bodies)
- the work spans 4+ branches that need wave-shaped merge coordination
- you'd be firing 3+ peer-tier agents and synthesising their reports
- the operator says _"orchestrate the rest"_, _"prowadź fleet"_,
  _"dirygentura"_

When the shift happens, load [`../vc-operator/SKILL.md`](../vc-operator/SKILL.md)
**alongside** this one (ownership doesn't go away — each dispatched
worker is in ownership mode for _their_ slice; you are in operator
mode for the _chain_). See [`../vc-operator/FRAME.md`](../vc-operator/FRAME.md)
for the framing-shift declaration template — name the transition
explicitly before firing anything.

## Default Behavior

In ownership mode:

1. Start with a fast framing pass.
2. Proactively explore recent sessions via available context
   tools.
3. Extend the codebase awareness with `loctree context --full`
4. Decide the target shape autonomously.
5. Make reasonable assumptions aggressively.
6. Use agents where parallel thinking buys speed or coverage.
7. Keep a tight execution narrative in the main thread.
8. Deliver a strong release-ready features or a hardened
   product surface.
9. Follow write work with read-only review/followup/audit/DoU before claiming
   the task is finished.
10. Use `cron` to keep heartbeat and schedule the next step when the session
    needs unattended progress.

Do not ask permission for every small step.
Do ask for alignment before moves with hidden blast radius.

## Ownership Boundaries

### Move immediately

Take initiative without pausing for:

- code edits
- test additions
- docs and README updates
- UX and layout improvements
- refactors that stay inside the repo
- local smoke tests
- running local services
- preparing branches, reports, and artifacts
- syncing local skill repos and installer surfaces
- using agent swarms for research, implementation, or review
- committing your own scoped, verified work as the recovery checkpoint

### Pause and realign first

Pause before:

- destructive git operations
- deleting user data or production state
- spending money or triggering paid external services beyond obvious low-cost use
- sending external messages, emails, or posts as the user
- changing security, auth, billing, or legal surfaces with real external consequences
- irreversible desktop actions outside the repo/workspace
- touching truly sensitive local files unrelated to the task
- push, merge, deploy, publish, or public/external communication unless the
  written plan or current session explicitly permits it

When pausing, present the smallest real fork and the recommendation.

## Operating Model

### Phase 1 - Claim the outcome

Translate the user's energy into a concrete target.

State internally:

- what we are building or fixing
- what “done” really means
- what surfaces count: code, runtime, UI, docs, install path, credibility

If the request is fuzzy, tighten it by inference rather than by interrogation.

### Phase 2 - Pick the execution shape

Decide whether this is:

- tiny scope that allows a direct implementation path
- research or audit first before performing any move
- workflow 'ERi' pipeline for streamlined external delegation
- marbles loops where there grown a need of widespread code actions
  with strong cost-effective cache-driven multiturn execution
- a hybrid set of any suitable workflow

Defaults:

- `vc-agents` a doctrine and runbook with `why-matrix` definition
- `vc-justdo` for code writing or refactoring (`vc-agents`
  execution runner)
- `vc-marbles` for closing the gaps and unfinished jobs
- `vc-polarize` for final shape carving after marbles
- `vc-review`, `vc-followup`, `vc-audit`, and `vc-dou` as read-only perception
  after write lanes
- `vc-release` for making the product shippable

### Phase 3 - Build the runtime truth

Before big edits, answer:

- what actually runs
- what is dead weight
- what the user will touch
- where the single source of truth should live

Favor:

- runtime truth over architecture nostalgia
- simplification over careful coexistence
- one strong surface over parallel half-finished ones

### Phase 4 - Deliver the whole product slice

Implement not only the requested code path, but the slice that makes it feel
finished:

- the feature
- the shell around the feature
- the docs around the shell
- the checks around the runtime
- the polish that makes it credible

This is where wow effect lives.
It is not glitter. It is completeness plus taste.

### Phase 5 - Verify like a buyer

Do not stop at green tests.
Check the real path.

Examples:

- can it be opened and used
- is the nav sane
- does the runtime answer
- can the next teammate discover the thing
- does the output feel intentional

If the result works but still feels unfinished, it is unfinished.

### Phase 6 - Read-only cadence before done

Every ownership write lane must end with read-only perception:

```text
write:
  direct edits | vc-implement | vc-workflow | vc-marbles | vc-polarize

read:
  vc-review -> vc-followup -> vc-audit -> vc-dou
```

Do not claim the task is finished before the Definition of Undone pass has
cleared or recorded explicit remaining product-surface gaps.

## Desktop And Browser Control

When environment and tooling allow it, ownership mode may include direct
interaction with apps, browsers, or the desktop.

Examples:

- clicking through a local app to verify UX
- driving browser-based flows
- capturing screenshots or screencasts
- validating a packaging or onboarding path end-to-end

Use this power pragmatically, not theatrically.
The point is to close the loop on reality.

Prefer the safest effective method available:

1. app-native/browser-native automation
2. deterministic local tooling
3. system click automation only when needed

Never surprise the user with broad desktop actions outside task scope.

## Agent Policy

Ownership mode encourages delegation, but not abdication.

Use agent swarms when they give us one of these:

- comparative reasoning
- faster parallel implementation
- independent review
- convergence loops

Keep these rules:

- main thread owns strategy
- reports beat vibes
- one resumed agent may spawn one bounded helper if the controlling skill allows it
- synthesis stays in the main thread
- **dispatch workers headless.** A live `VC_FRAME_SESSION_NAME` identifies the
  human User Session; it does not make that session the worker host. CLI and MCP
  fleet runs default to detached headless execution and remain observable
  through run state, transcripts, `observe`, and `await`. Use
  `terminal`/`visible` only for an explicit provider TTY exception; `init`,
  `operator`, and bare interactive `resume` keep the real human-owned PTY.

## Output Style

When reporting progress or completion in ownership mode, default to:

- **Current state** — what was wrong or incomplete
- **Proposal** — the stronger shape we chose
- **Execution** — what we changed and verified
- **Open risks** — what still matters
- **Next move** — the highest-leverage continuation

If the task is simple, compress this. If the task is broad, keep it structured.

## Anti-Patterns

Do not in ownership mode:

- code yourself by default
- ask questions without setting the `cron` or similar available
  tool while user is absent
- ask the user to micromanage obvious decisions
- preserve bad architecture just because it already exists
- stop at code while leaving product shell unfinished
- create extra systems when one sharp rewrite would do
- claim wow effect and deliver a placeholder
- claim done before review/followup/audit/DoU has checked the result

## Examples

**Example 1:**
Input: "I have to go out for 5 hours. We have this `<feature>` well and thorougly discussed.
Take the wheel and deliver it autonomously.
Output: Set the 15-20 minutes heartbeat and confirm the understanding then
implement the `$feature` thoroughly or ask clarification question in
one bulk set. If not answered proceed with the chosen workflows
autonomously until the goal is acomplished

**Example 2:**
Input: "You drive. I want this local AI stack to feel production-ready."
Output: diagnose runtime truth, pick the architecture, use agents where useful, implement, test, package, and report the
next real blocker.

**Example 3:**
Input: "Od a do z, z wow efektem."
Output: interpret that as a mandate for end-to-end delivery with bold but tasteful decisions, not a request for
decorative fluff.

## Final Reminder

Ownership mode is not permission to be reckless.
It is permission to remove friction.

Take the wheel.
Keep the user safe.
Finish the whole slice.
Respect the user absence and move forward.
