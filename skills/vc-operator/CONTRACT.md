# `vc-operator` Contract

This document is the binding contract behind the readable operator flow.

## Layer Contract

```yaml
interactive_skill:
  name: vc-operator
  kind: orchestration_posture
  activates_when:
    - user names "$vc-operator"
    - user asks to conduct a plan or fleet
    - user asks for multi-wave dispatch
  does_not_automatically:
    - launch "vibecrafted dispatch"
    - create a run_id
    - create transcript/meta artifacts
    - fire workers

runtime_supervisor:
  name: vibecrafted dispatch
  kind: runtime_supervisor
  activates_when:
    - operator launches "vibecrafted dispatch <file.toml>"
    - operator launches "vibecrafted dispatch run ..."
    - framework dispatches a supervisor run explicitly
  creates:
    - run_id
    - dispatch tracker/result artifacts
    - reports
    - briefs
    - transcript.log
    - meta.json
```

## Posture Contract

```yaml
vc-operator:
  owns:
    - plan_intake
    - wave_atlas
    - agent_selection
    - dispatch_briefs
    - await_and_recovery
    - tracker
    - journal
    - wave_close_outs
    - stop_point_handoff
  may_launch_runtime:
    - vc-scaffold
    - vc-implement
    - vc-workflow
    - vc-marbles
    - vc-audit
    - vc-review
    - vc-followup
    - vc-release
    - vc-ownership
    - vc-partner
  must_not:
    - silently become a worker
    - dispatch without vc-init evidence
    - dispatch without a wave atlas
    - use native subagents as substitutes for fleet dispatch
    - blind-restart stalled workers
    - push_merge_deploy_or_publish_without_plan_or_session_permission
```

## Binding Artifacts

```yaml
operator_run:
  plan_name: ""
  artifact_root: ""
  framing_shift: ""
  init_evidence: ""
wave_atlas:
  waves: []
  dependencies: []
  parallel_groups: []
dispatches:
  briefs: []
  run_ids: []
  agents: []
verification:
  reports: []
  gates: []
  branches: []
  shas: []
recovery:
  stalls: []
  recovery_dispatches: []
plan_mutations:
  skipped: []
  added: []
  reordered: []
  cherry_picks: []
security_guardrails:
  prompt_scans: []
  commit_scans: []
close_out:
  tracker: ""
  journal: ""
  stop_point_handoff: ""
```

## Stop Button Policy

Operator mode stops before any unpermitted:

- push
- force-push
- merge
- deploy
- public message
- paid action
- irreversible state change
- trust-boundary action

An action is permitted only when it is explicitly allowed in the written plan or
stated and documented in the current session. If the permission is ambiguous,
stop and hand off the button.

The final handoff should make the remaining button obvious.

## Plan Mutation Policy

The operator may change dispatch shape without a new button when the final goal
does not change:

- regroup waves
- skip, add, or reorder prompts
- cherry-pick between active wave branches

Each mutation must be appended to `journal.md` with what changed, why, and what
goal invariant remains unchanged.

## Security Guardrail Policy

Before each wave, scan worker briefs for insecure commands and hard-stop
triggers. After each worker commit, scan committed changes for secrets,
personal data, local-only paths, local network topology, IP addresses, and
internal documents. If detected, revert the offending commit, sanitize the
surface, commit again, and record the incident in `journal.md`.

## Recovery Policy

Stall does not mean restart.

Allowed recovery requires:

1. read the stalled worker's report/transcript/meta if present
2. classify the failure
3. issue a focused recovery dispatch or escalate to marbles/ownership
4. append the recovery decision to `journal.md`

Blind re-fire is a process failure.
