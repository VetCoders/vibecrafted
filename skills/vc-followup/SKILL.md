---
name: vc-followup
version: 2.1.0
description: >
  Post-implementation follow-up audit skill. Use this when implementation
  exists and the team needs to evaluate whether the work is heading in the
  right direction, what gaps remain, what drift was introduced, and what the
  next highest-leverage move should be. This is not the same as bounded
  `vc-review`: followup is trajectory-aware, postimplementational, and may
  inspect code, runtime behavior, UX, docs, or packaging without requiring a
  single artifact like a PR or commit range as its frame. Trigger phrases:
  "follow-up check", "followup audit", "czy sa jeszcze luki",
  "readiness before hands-on", "audit this implementation", "po implementacji",
  "gaps after agents", "co zostało do zrobienia", "post-implementation review",
  "czy to idzie dobrze", "czy ten kierunek ma sens", "what still feels off".
compatibility:
  tools: []
---

# vc-followup

## Operator Entry

Operator enters the framework session through:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start vibecrafted
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

`vc-followup` evaluates the postimplementation state of the work, even when
there is no single canonical artifact to review.

## When To Use

Use `vc-followup` when:

- code was just implemented and you want to assess the direction, not only the diff
- a task is "working" but still feels off
- agents finished a pass and you want to see what remains open
- you want a next-move recommendation after implementation
- you need a postimplementation audit across code, runtime, UX, docs, or packaging

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
It should read like a postimplementation trajectory check.

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
