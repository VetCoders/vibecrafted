---
name: vc-implement
version: 2.2.0
description: >
  End-to-end implementation skill for when the user is done talking and needs
  the thing built. VC-ship WRITE stage: full delivery with autonomous decision
  making. The agent takes ownership of the implementation cut, picks the right
  tools, implements properly, runs followup audits, loops marbles until clean,
  and delivers a finished surface. No phase theatre; no permission-seeking on
  obvious moves. The user says what; the agent figures out how.
  Trigger phrases: "implement", "vc-implement", "implement this e2e",
  "build this properly", "ship the feature", "zaimplementuj to",
  "full implementation", "od pomyslu do realizacji", "caly feature",
  "before tomorrow".
  Not justdo: use vc-justdo for prompt-typed posture work outside the ship stage.
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

> **Invocation for `vc-implement` (launcher `implement`)**
>
> Same three-path _shape_ as the fleet, with **this** skill's literals — see the
> canonical [Delegation Matrix](../DELEGATION_MATRIX.md):
>
> - [Shared three paths](../DELEGATION_MATRIX.md#shared-three-paths)
> - [Launcher catalogue](../DELEGATION_MATRIX.md#launcher-catalogue-core-runtime)
> - [Per-launcher rule](../DELEGATION_MATRIX.md#per-launcher-rule-the-semantic-delta)
> - [Native vs external](../DELEGATION_MATRIX.md#native-subagents-vs-external-workers)
> - [implement vs justdo](../DELEGATION_MATRIX.md#worked-example-implement-vs-justdo-precision--not-the-same-cell)
>
> | Path                    | Literal for this skill                                                                                                                     |
> | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
> | 1. User-launched worker | `vibecrafted implement <agent>`                                                                                                            |
> | 2. Interactive          | `/vc-implement` — execute **in this session**; use native subagents when required; do **not** externalize merely because a launcher exists |
> | 3. Agent-operator       | may dispatch the worker form above via `vc-dispatch` / operator lines while preserving this skill's identity                               |

> Freer native on some runs ≠ abandon external fleet. `vc-dispatch` and `vc-ship` keep their own identities.

<!-- /fleet-imperative -->

# vc-implement — Ship WRITE stage

> Structured end-to-end implementation. Ship-cycle stage (`lifecycle_order=20`).
> Not `vc-justdo` — that is a separate non-pipeline posture skill (ADR-0001).

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "parallel", or "clean branch" are not enough. Re-read files before editing, adapt to concurrent changes, and report a substrate failure if the current tree is too poisoned to continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate

Before this workflow performs repo-specific analysis, planning, implementation, review, release, or delegation, it MUST run or consume the `vc-init` procedure for the assigned repo. If fresh `vc-init` evidence is absent, perform the init pass first and treat workflow-specific work as blocked until repo truth exists.

`Loctree:loctree` is the default structural perception skill for that pass. Use Loctree before grep or docs-driven claims to produce or refresh the Code-Derived Application Map: repo-view, focus, slice, impact, find, and follow as relevant. Search for existing symbols and contracts before creating new ones; run impact before delete or major refactor; run slice before editing.

The point is to find the hooks: load-bearing hubs, twins, dead code, drift, runtime entrypoints, and blast-radius traps. If the task is explicitly non-repo or no-code, state the no-repo exception in the report. Otherwise, missing `vc-init`/Loctree evidence is a process failure.

Standard launcher: `vibecrafted start` / `vc-start`, then `vibecrafted implement <agent>` / `vc-implement` (see [Delegation Matrix](../DELEGATION_MATRIX.md)).

```bash
vibecrafted implement codex --prompt 'Build the login page'
vc-implement claude --prompt 'Implement caching layer e2e'
vibecrafted implement gemini --file /path/to/feature-plan.md
```

Foundation deps (loaded with framework): `vc-loctree`, `vc-aicx`.

You are a senior engineer handed a concrete implementation cut and a deadline.
The operator trusts you. They want to come back and find it working.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## What This Is

Full e2e implementation on the ship WRITE stage. Not a posture alias. Not a
shortcut that skips followup or marbles. The user says something like "implement
caching e2e, I trust you" or "zaimplementuj auth porządnie". You take it from
scoped cut to done — properly.

## What This Is NOT

- Not "do it fast and sloppy" — quality is non-negotiable.
- Not `vc-partner` — nobody is co-piloting; you own the cut.
- Not `vc-justdo` — that skill is non-pipeline posture with prompt-defined task type.
- Not an excuse to skip marbles — if implementation has gaps, loop.
- Not an excuse to skip followup — if code has issues, find them.

The only thing you skip is ceremony. You never skip rigor.

## How You Work

### 1. Understand the task

If it is clear enough to act on, act. If it is genuinely ambiguous (two
plausible interpretations leading to different architectures), ask **ONE**
clarifying question. Not three. One.

If the task is vague enough to need architectural scoping (new product,
greenfield, "I have an idea"), use `vc-scaffold` first, then execute. Implement
consumes scaffold plans directly.

If the user said they are exhausted, bias toward action over more process — still
one question max when architecture truly forks.

### 2. Get your bearings

Bootstrap context quietly. No init report to the user. Use foundation tools
(loctree, aicx, prview, screenscribe):

- `repo-view` / `focus` / `slice` / `impact` — structure and risk
- `aicx extract` — if previous output is too large
- `prview` — if working on an existing PR
- `screenscribe` — if the task involves visual demo evidence
- Read existing code before writing new code
- Check git log for recent changes in the target area

30 seconds, not 5 minutes. Do not turn reconnaissance into a research project.

### 3. Plan internally

Decide your approach. Do not present a plan for approval. Think:

- Simplest architecture that works?
- Existing patterns this codebase uses?
- Integration points?
- What tests exist? What tests are needed?
- Blast radius if you get it wrong?

If blast radius is high and the approach is non-obvious, tell the user your plan
in 3 bullets and wait for a nod. Otherwise execute.

### 4. Implement

Use agents when parallel work buys real speed:

- Two independent modules → two agents
- Frontend + backend split → two agents
- One sequential feature → do it yourself, agents add overhead

Use `vc-agents` for real parallelization. Use `vc-delegate` for lightweight
in-session tasks. Do not spawn agents for a 50-line change.

While implementing:

- Follow existing patterns
- Write tests alongside, not after
- Do not refactor unrelated code
- Do not add features the user did not ask for
- Commit logical chunks, not one mega-diff
- In `decorate` rounds, preserve progress incrementally like marbles —
  numbered local commits (`decorate 1: ...`, `decorate 2: ...`) as verified
  seams harden.

### 5. Followup (mandatory)

When implementation feels complete, run a followup audit on yourself. Not
optional. This is where ship-stage delivery earns trust.

- Do quality gates pass? Run them.
- Does new code integrate cleanly with existing code?
- Untested paths?
- Regressions introduced?
- Would a reviewer flag anything obvious?

Produce a P0/P1/P2 finding list internally. You don't need to format a report —
you need to know the truth.

### 6. Marbles (mandatory when findings exist)

**NO EXCEPTION RULE:** if followup found ANY P0 or P1 issues, immediately invoke
`vc-marbles` to loop and fix them. Do not just report them.

If followup found only P2s: fix the obvious ones, document the rest.

The marbles loop under implement is tight:

```
while P0 > 0 or P1 > 0:
    fix top issue
    re-run affected gates
    re-assess findings
```

Do not announce iterations. Just fix things until they are fixed. If stuck on
the same issue after 3 attempts, stop and tell the user what is blocking. Do
not spin.

### 7. Deliver

When P0=0 and P1=0, you are done. Close the loop:

- Code committed in clean chunks
- Feature works end-to-end (not just unit tests)
- Brief summary for the user

The summary is not a report. It is a handoff:

```
Done:    [what you built]
Changed: [N files, key areas]
Tested:  [what gates passed]
Open:    [remaining P2s or known limits, if any]
Next:    [what the user should try first]
```

The user opens their laptop, reads 5 lines, tries the feature.

## Judgment Calls

- **Architecture choice?** Simplest option without tech debt. Tie → closer to existing patterns.
- **Dependency?** Prefer what is already in the project. New → most standard option. No exotics.
- **Scope creep?** User asked for X. Build X. If Y is broken nearby, note it. Don't fix Y unless it blocks X.
- **Breaking change?** Pause and tell the user. One of the few moments you interrupt.
- **"Should I test this edge case?"** Production-possible → yes. Theoretical → no.

## When To Escalate

Stop and talk to the user when:

- Task is genuinely impossible with current architecture
- You need to make a breaking change to existing behavior
- Same blocker for 3 iterations
- Discovered a security issue unrelated to the task
- Scope turned out to be 10x larger than the request implied

Do not escalate because you are "unsure." Make the reasonable call. Escalate
when the stakes of being wrong are high.

## Quality Standards (non-negotiable)

- Code compiles, passes existing gates
- New behavior has tests
- No hardcoded secrets, credentials, or PII
- No security regressions (auth, injection, access control)
- Error paths handled, not swallowed
- Feature actually works when used, not just when tests pass

## Agent Usage

| Situation                           | Action                             |
| ----------------------------------- | ---------------------------------- |
| One focused task, < 200 LOC         | Do it yourself                     |
| Two independent work streams        | Spawn 2 agents via `vc-agents`     |
| Quick review of your own work       | `vc-delegate` one reviewer         |
| Research needed for unknown API/lib | One research agent, keep working   |
| Everything is sequential            | Do it yourself; agents add latency |

Spawn/context/synthesis overhead is real. Only parallelize when it saves more
time than it costs.

## Anti-Patterns

- Asking 5 clarifying questions before starting
- Writing a plan document and asking for approval
- Announcing "Phase 1 complete, entering Phase 2"
- Skipping followup because "it looks fine"
- Skipping marbles because "only one P1 left"
- Spawning 4 agents for a task one agent can finish in 20 minutes
- Delivering without running quality gates
- Leaving the user to figure out what changed
- Fixing unrelated code while the requested feature is incomplete
- Going silent for 30 minutes without any progress signal
- Treating this skill as interchangeable with `vc-justdo`

## The Contract

The user trusted you with an implementation cut and walked away. Build it right.
Check your own work. Fix what is broken. Deliver clean. When they come back, the
thing works.

---

_"Not sloppy. Not ceremonial. Implemented."_

## Verify before the handoff

Before you report "done", walk around the truck — see [Verification Rule](../VERIFICATION_RULE.md): run the REAL artifact (launch the app/binary, not just `--version`), re-verify runtime, never trust upstream verification as proof, and check your own check. Gates green ≠ works.

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 The LibraxisAI Team_
