---
name: vc-delegate
version: 2.0.0
description: >
  Native operator-side delegation doctrine for small bounded native cuts.
  Use this when the operator agent must decide whether work should stay
  in-process through native subagents or be escalated upward into vc-agents.
  Trigger phrases: "implement with agents", "delegate to subagents", "zaimplementuj",
  "run agents", "parallel tasks", "delegate safely", "native agents",
  "Task tool agents", "implement plan", "uruchom agentów", "subagenty natywne",
  "bezpieczne agenty", "implement without externals", "no osascript".
compatibility:
  tools: []
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# vc-delegate

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

Do not launch `vc-delegate` directly. Its operator-facing replacement is:

```bash
vibecrafted <workflow> <agent> --file '/path/to/plan.md'
```

```bash
vc-<workflow> <agent> --prompt '<prompt>'
```

This skill is not the external fleet itself. It is the operator doctrine for
native delegation: when to keep a cut local, when to stop pretending a native
cut is still bounded, and when the operator should escalate into `vc-agents`.

### Concrete dispatch examples

```bash
vibecrafted partner codex --prompt 'Split this into one small native cut'
vibecrafted implement claude --file /path/to/plan.md
vibecrafted workflow agy  # gemini deprecated --prompt 'Keep this local unless it clearly wants the external fleet'
```

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Native Delegation Policy

When using native subagents, default to the same frontier as the parent agent.

Why:

- Same-named native delegation preserves the closest reasoning style to the parent.
- It maximizes context locality and cache reuse opportunities.
- On the same repo and task family, this is usually the best cost-to-quality default.

Default:

- Parent model -> the same exact native model, when available.
- If the exact model is unavailable, use the nearest native equivalent and say so explicitly.

> “Parent model" means the same concrete model identity, not merely the same vendor or family.

Exceptions:

- Codex: You may delegate to `gpt-5.3-codex-spark` with `xhigh` when the task benefits from extreme speed. Treat Spark as a fast execution tier; the parent agent remains responsible for final quality.
- Claude: For extensive long-running tasks, prefer `opus[1m]`; for easier or lighter tasks, prefer `sonnet[1m]`.
- Gemini: If `gemini-3.1-pro-preview` is unavailable or unstable during peak demand, fallback native delegation to `auto-gemini-3`.

Rule:

- Default to same-named native agents first.
- Use cross-model exceptions intentionally, never casually.
- If you trade down for speed or availability, recover quality in the parent orchestration pass.

## Escalation Direction

`vc-delegate` is a bounded native delegation tool for the operator agent.

Its role is to help the operator go deeper locally, or to admit when a task has
outgrown native delegation.

If a native delegated task becomes too extensive, too cross-cutting, or too
dependent on model-specific orchestration, it should not fake completion.

Instead, it must:

- report that the task has exceeded native delegation scope, or
- return to the parent operator, or
- escalate into `vc-agents`.

Escalation into `vc-agents`:

- by principle, `vc-agents` is not a generic recursion mechanism.
- it is a deliberate operator decision based on the `vc-why-matrix`.
- once a fleet agent has been chosen, that choice must remain stable unless the operator explicitly changes it.

## Scope Boundary

This doctrine is for the operator layer.

It is not forwarded as an execution policy to the tiny native subagents
themselves. Native subagents are execution helpers, not orchestration actors.

Read `skills/vc-agents/SKILL.md` alongside this file when the operator needs the
full external fleet and the `vc-why-matrix`.
