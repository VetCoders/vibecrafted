# VetCoders Partner

Proactive shared-steering posture for sessions where the operator and agent
must preserve the original shape while still moving decisively.

`vc-partner` is not a planner-swarm wrapper and not a weaker ownership mode. It
is the posture that keeps the strategic brain shared while the agent performs
the heavy work, launches the right runtimes, and checks every result against the
original shape.

## What It Is Good For

Use `vc-partner` when:

- the problem definition matters as much as implementation
- the original shape must survive compaction and delegation
- runtime truth can change the plan
- the operator wants proactive work without silent takeover
- write lanes need read-only verification before "done"

## Core Operating Model

The default loop is:

1. define the problem
2. capture `original_shape`
3. write the success contract
4. build the plan with `vc-scaffold`
5. choose the execution lane
6. run write work
7. run `vc-review`, `vc-followup`, `vc-audit`, and `vc-dou`
8. close gaps with `vc-marbles` or another focused write lane
9. ship only when DoU is clear or the remaining gaps are explicit

## Key Rules

- skill invocation is not runtime invocation
- the partner journal is append-only mission memory
- workers may execute, but they do not redefine the original shape
- review checks implementation truth
- followup checks shape fidelity
- audit falsifies completion claims
- DoU checks product-surface undone work

## Files

- `SKILL.md` - posture instructions
- `FLOW.md` - process map
- `CONTRACT.md` - binding posture/runtime split
- `JOURNAL.md` - append-only mission diary
- `RUNTIME.md` - runtime artifact expectations
- `TAXONOMY.md` - local taxonomy

## Relationship To The Rest Of The Stack

- `vc-init` opens repo/runtime/intention truth.
- `vc-scaffold` helps build the plan.
- `vc-implement` and `vc-workflow` run write lanes.
- `vc-operator` conducts field teams when needed.
- `vc-ownership` takes over when shared steering is no longer desired.
- `vc-review`, `vc-followup`, `vc-audit`, and `vc-dou` close the read side.
