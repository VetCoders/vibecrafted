---
name: vc-followup
version: 2.2.0
description: >
  AUDIT-FIRST post-implementation trajectory check. Evaluates whether
  the work is heading in the right direction, what gaps remain, what
  drift was introduced, and what the next highest-leverage move should
  be. May inspect code, runtime behavior, UX, docs, or packaging
  without requiring a single artifact like a PR or commit range as its
  frame. Sibling to `vc-review` (per-implementation diff perception)
  and `vc-audit` (per-plan spec falsification) in the AUDIT-FIRST
  perception layer of the pipeline. Trigger phrases: "follow-up check",
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

# vc-followup — AUDIT-FIRST Trajectory Check

> AUDIT-FIRST perception step. Sibling to `vc-review` (per-diff) and
> `vc-audit` (per-plan). This one asks **"is the direction healthy?"**
> across whatever surfaces the operator points at — code, UX, docs,
> packaging, integration, install path — without a bounded artifact
> requirement. Produces a report, never modifies code.

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

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "parallel", or "clean branch" are not enough. Re-read files before editing, adapt to concurrent changes, and report a substrate failure if the current tree is too poisoned to continue safely.

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

If `vc-followup <agent>` is invoked outside Zellij, the framework will attach
or create the operator session and run that workflow in a new tab.

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
- you need a post-implementation audit across code, runtime, UX, docs, or packaging

Do not use `vc-followup` when:

- you need findings on a specific PR, branch, or commit range
- you need line-level review framing
- the task is still in pre-implementation research mode

In those cases, use `vc-review` or `vc-research`.

## Audit Contract

`vc-followup` should evaluate:

- residual gaps
- drift from intended shape
- regressions or fragility
- mismatches between code and runtime truth
- missing finish around UX, docs, packaging, onboarding, or installability
- whether the current direction deserves continuation, correction, or escalation

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
- UX gap
- docs/packaging gap

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
- skip product-surface followup and look only at code
