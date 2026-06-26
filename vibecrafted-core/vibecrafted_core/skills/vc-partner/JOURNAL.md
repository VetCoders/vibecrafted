# `vc-partner` Journal

The partner journal is an append-only mission diary.

It exists because `vc-partner` is responsible for preserving the original shape
across compaction, delegation, review, audit, and shipping.

## Path

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/partner/journal.md
```

If no runtime artifact root exists yet, keep the same structure inside the
interactive report or create the artifact root before the first delegated run.

## Rules

- Append only.
- First entry captures `original_shape`.
- Never rewrite earlier entries to make the narrative cleaner.
- Corrections are new entries.
- Every delegated run, compaction, finding, gap closure, and shape drift gets an
  entry.
- The final report summarizes the journal; it does not replace it.

## First Entry

````md
## <timestamp> - original shape

```yaml
original_shape:
  problem: ""
  promise: ""
  target_user_or_operator: ""
  invariants: []
  non_goals: []
  success_contract: []
  accepted_drift_policy: "only with explicit journal entry"
```

- Evidence: source prompt, operator clarification, repo/runtime context
- Next: first bounded move
````

## Normal Entry

```md
## <timestamp> - <phase>

- State: what is true now
- Shape check: faithful | drifting | intentionally changed
- Evidence: commands, reports, runtime observations, links
- Decision: what changed in the plan or contract
- Next: the next bounded move
```

## Drift Entry

```md
## <timestamp> - shape drift decision

- Previous model:
- New model:
- Why this is not a mylik:
- Evidence:
- Operator approval: yes | no | not needed because runtime proof is decisive
- Updated invariants:
- Next:
```

## Handoff Entry

```md
## <timestamp> - handoff to <runtime>

- Runtime:
- Reason:
- Original shape excerpt:
- Worker must preserve:
- Worker must not:
- Expected artifact:
- Await/recovery path:
```

## Resume Entry

```md
## <timestamp> - resume after compaction

- Original shape:
- Last known state:
- Open gaps:
- Drift decisions so far:
- Next bounded move:
```
