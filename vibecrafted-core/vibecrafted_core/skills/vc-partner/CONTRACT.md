# `vc-partner` Contract

This document is the binding contract behind the readable flow.

## Layer Contract

```yaml
interactive_skill:
  name: vc-partner
  kind: interactive_posture
  activates_when:
    - user names "$vc-partner"
    - user asks to think/define/shape together
    - user wants proactive shared steering without full takeover
  does_not_automatically:
    - launch "vibecrafted partner"
    - create a run_id
    - create transcript/meta artifacts
    - spawn workers

runtime_workflow:
  name: vibecrafted partner
  kind: runtime_workflow
  activates_when:
    - operator launches "vibecrafted partner <agent>"
    - framework dispatches a partner run explicitly
  creates:
    - run_id
    - partner/journal.md
    - reports
    - transcript.log
    - meta.json
```

## Posture Contract

```yaml
vc-partner:
  owns:
    - original_shape
    - success_contract
    - partner_journal
    - decision_log
    - shape_review
  may_launch_runtime:
    - vc-implement
    - vc-workflow
    - vc-operator
    - vc-marbles
    - vc-polarize
    - vc-review
    - vc-followup
    - vc-audit
    - vc-dou
    - vc-release
  must_not:
    - silently become vc-ownership
    - outsource problem definition to workers
    - allow delegated workers to redefine original_shape
    - treat mermaid as a binding runtime trigger
    - claim_done_before_vc_dou
    - ship_before_read_cadence_or_fresh_evidence
```

## Binding Artifacts

For non-trivial work, `vc-partner` must preserve these fields either in
runtime metadata or in the append-only journal:

```yaml
problem:
  statement: ""
  scope: []
  non_goals: []
original_shape:
  promise: ""
  target_user_or_operator: ""
  invariants: []
  accepted_drift_policy: ""
success_contract:
  acceptance: []
  gates: []
  runtime_proof: []
execution:
  selected_lane: ""
  reason: ""
  delegated_runs: []
shape_review:
  faithful: null
  mismatches: []
  drift_decisions: []
audit:
  review_report: ""
  followup_report: ""
  audit_report: ""
  dou_report: ""
ship:
  commit: ""
  release_or_next_move: ""
```

## Read-Write Cadence

```yaml
write_lanes:
  - vc-implement
  - vc-workflow
  - vc-marbles
  - vc-polarize
read_lanes:
  - vc-review
  - vc-followup
  - vc-audit
  - vc-dou
completion_rule: "Do not claim finished until DoU passes or records explicit remaining gaps."
```

## Drift Policy

Shape drift is not forbidden. Silent shape drift is forbidden.

Allowed drift requires one of:

- runtime evidence disproves the original assumption
- operator explicitly chooses a new shape
- audit/followup finds that the original shape cannot satisfy the promise

Every drift decision must be appended to the partner journal.

## Compaction Policy

After compaction or resume, the partner must restate:

1. original shape
2. current state
3. known drift decisions
4. next bounded move

If these cannot be reconstructed, the session is blocked until the journal,
report, or operator restores them.
