---
name: vc-followup
version: 2.2.0
description: >
  AUDIT-FIRST post-implementation trajectory check. Evaluates whether
  the work is heading in the right direction, what gaps remain, what
  drift was introduced, and what the next highest-leverage move should
  be. Reads the work in motion — code, runtime behavior, architecture,
  integration — without requiring a single artifact like a PR or commit
  range as its frame. Product-surface completeness (packaging, install,
  discoverability) belongs to `vc-dou`, not here. Sibling to `vc-review`
  (per-implementation diff perception) and `vc-audit` (per-plan spec
  falsification) in the AUDIT-FIRST perception layer of the pipeline.
  Trigger phrases: "follow-up check",
  "followup audit", "czy sa jeszcze luki", "readiness before hands-on",
  "audit this implementation", "po implementacji", "gaps after agents",
  "co zostało do zrobienia", "post-implementation review",
  "czy to idzie dobrze", "czy ten kierunek ma sens", "what still feels off".
compatibility:
  tools: []
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v3 -->

> **Invocation for `vc-followup` (launcher `followup`)**
>
> Same three-path _shape_ as the fleet, with **this** skill's literals — see the
> canonical [Delegation Matrix](../DELEGATION_MATRIX.md):
>
> - [Shared three paths](../DELEGATION_MATRIX.md#shared-three-paths)
> - [Launcher catalogue](../DELEGATION_MATRIX.md#launcher-catalogue-core-runtime)
> - [Per-launcher rule](../DELEGATION_MATRIX.md#per-launcher-rule-the-semantic-delta)
> - [Native vs external](../DELEGATION_MATRIX.md#native-subagents-vs-external-workers)
>
> | Path                    | Literal for this skill                                                                                                                    |
> | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
> | 1. User-launched worker | `vibecrafted followup <agent>`                                                                                                            |
> | 2. Interactive          | `/vc-followup` — execute **in this session**; use native subagents when required; do **not** externalize merely because a launcher exists |
> | 3. Agent-operator       | may dispatch the worker form above via `vc-dispatch` / operator lines while preserving this skill's identity                              |

> Freer native on some runs ≠ abandon external fleet. `vc-dispatch` and `vc-ship` keep their own identities.

<!-- /fleet-imperative -->

# vc-followup — AUDIT-FIRST Trajectory Check

> AUDIT-FIRST perception step. This one asks **"is the direction
> healthy?"** about the work in motion — code, runtime, architecture,
> integration — without a bounded artifact requirement. Produces a
> report, never modifies code.

## Frame — what makes this one distinct

The four AUDIT-FIRST READ skills differ by **frame**, not by depth. Pick
by what the question is bounded to:

- `vc-review` → a bounded **diff** (PR / branch / commit range): _is this
  change clean and safe to merge?_
- `vc-audit` → a bounded **plan** (a written spec claiming completion):
  _did the claimed work actually land in code?_
- `vc-followup` → an unbounded **trajectory** (no artifact required):
  _is the work heading the right way — continue, correct, or escalate?_
- `vc-dou` → the whole **product surface** from the buyer's frame: _can
  someone find, trust, try, and buy this?_

Followup judges direction. It does **not** audit shippability — packaging,
install paths, SEO, and representation are `vc-dou`'s frame. When you smell
a product-surface gap, name it and hand it to `vc-dou`; do not grade it here.

## Pipeline Position

`vc-followup` lives in the **trajectory perception** slot:

```
... → implement (WRITE) → [FOLLOWUP: AUDIT-FIRST] → review (READ) → marbles (WRITE) → ...
```

Followup answers **"is the trajectory healthy?"**. Review answers
**"is this diff clean?"**. Audit answers **"did the written spec
land?"**. All three are AUDIT-FIRST; none of them modify code. Fixes
belong downstream in `vc-marbles`.

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "parallel", or "clean branch" are not enough. The one sanctioned second mode is a Fleet Worktree dispatch (written plan, pre-committed verifiers, disjoint domains, single-thread integrator — see Living Tree Rule, Mode B); outside that formation, stay in the shared tree. Re-read files before editing, adapt to concurrent changes, and report a substrate failure if the current tree is too poisoned to continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate

Before this workflow performs repo-specific analysis, planning, implementation, review, release, or delegation, it MUST run or consume the `vc-init` procedure for the assigned repo. If fresh `vc-init` evidence is absent, perform the init pass first and treat workflow-specific work as blocked until repo truth exists.

`Loctree:loctree` is the default structural perception skill for that pass. Use Loctree before grep or docs-driven claims to produce or refresh the Code-Derived Application Map: repo-view, focus, slice, impact, find, and follow as relevant. Search for existing symbols and contracts before creating new ones; run impact before delete or major refactor; run slice before editing.

The point is to find the hooks: load-bearing hubs, twins, dead code, drift, runtime entrypoints, and blast-radius traps. If the task is explicitly non-repo or no-code, state the no-repo exception in the report. Otherwise, missing `vc-init`/Loctree evidence is a process failure.

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start operator
```

Then launch this workflow through the command deck:

```bash
vibecrafted followup <agent> --file '/path/to/context.md'
```

```bash
vc-followup <agent> --prompt '<prompt>'
```

`vc-followup <agent>` defaults to a detached headless worker both inside and
outside vc-frame. Observe it through its receipt, transcript, and awaitable run
state.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## What It Is

`vc-followup` is a post-implementation direction audit.

It asks questions like:

- is this going in the right direction
- what still feels unfinished or unstable
- what gaps remain after the last implementation push
- what drift appeared between the intended shape and the current one
- what is the next highest-leverage move

It is intentionally broader than `vc-review`.

`vc-review` evaluates a bounded object inside clear review frames:

- a PR
- a branch
- a commit range
- a review artifact pack

`vc-followup` evaluates the post-implementation state of the work, even when
there is no single canonical artifact to review.

## When To Use

Use `vc-followup` when:

- code was just implemented and you want to assess the direction, not only the diff
- a task is "working" but still feels off
- agents finished a pass and you want to see what remains open
- you want a next-move recommendation after implementation
- you need a post-implementation read of the work's direction across code,
  runtime, and architecture

Do not use `vc-followup` when:

- you need findings on a specific PR, branch, or commit range — that's `vc-review`
- you need line-level review framing — that's `vc-review`
- the target is a written plan claiming completion — that's `vc-audit`
- the question is shippability / product-surface completeness — that's `vc-dou`
- the task is still in pre-implementation research mode — that's `vc-research`

## Audit Contract

`vc-followup` should evaluate:

- residual gaps in the implementation arc
- drift from intended shape
- regressions or fragility
- mismatches between code and runtime truth
- whether the architecture is converging or fragmenting
- whether the current direction deserves continuation, correction, or escalation

A product-surface gap (packaging, install, discoverability) gets **named and
handed to `vc-dou`** — followup flags it, it does not audit it.

The result should not read like a code review.
It should read like a post-implementation trajectory check.

## Output Shape

Default output structure:

1. **Current state** — what exists now and what changed since the last implementation push
2. **What still feels off** — gaps, drift, fragility, unfinished surfaces
3. **Direction verdict** — is the work heading in the right direction or not
4. **Next move** — the highest-leverage continuation

If relevant, explicitly separate:

- code gap
- runtime gap
- architecture / integration gap
- (product-surface gap → tagged for `vc-dou`, not graded here)

## Relationship To Other Skills

- Use `vc-review` for bounded, artifact-framed evaluation
- Use `vc-followup` for postimplementation direction audit
- Use `vc-marbles` when followup finds unresolved `P0` / `P1` entropy that needs convergence loops
- Use `vc-dou` when the code may be fine but the whole product surface is still incomplete

## Anti-Patterns

Do not:

- collapse `vc-followup` into a synonym for `vc-review`
- force it to depend on a PR or commit range when the real question is directional
- return only findings without saying whether the current trajectory is healthy
- confuse "there are still gaps" with "the direction is wrong"
- drift into product-surface auditing (packaging, install, SEO, presence) —
  that is `vc-dou`'s frame; followup judges the work's direction, not its shippability
