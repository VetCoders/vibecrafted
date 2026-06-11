# `vc-operator` Taxonomy

`vc-operator` lives in two layers.

## Interactive Skill

```yaml
vc-operator:
  kind: orchestration_posture
  scope: interactive_session
  meaning: dispatch, await, synthesize, recover, close waves
  autonomy: orchestration
```

In an interactive session, `$vc-operator` means the current agent accepts the
conductor role. It does not automatically start a new runtime process.

The operator posture is responsible for:

- declaring the framing shift
- reading the plan
- building the wave atlas
- picking agents
- firing waves through framework launchers
- awaiting durable artifacts
- issuing recovery dispatches
- keeping tracker and journal
- leading permitted work to the goal
- stopping at unpermitted operator buttons

## Runtime Workflow

```yaml
operator_runtime_lanes:
  entrypoints:
    - vibecrafted dispatch <file.toml>
    - vibecrafted dispatch run ...
    - vibecrafted workflow <agent> --file <plan>
    - vibecrafted implement <agent> --prompt <slice>
  creates:
    - run_id
    - dispatch/result artifacts
    - tracker or journal when the posture maintains them
    - briefs
    - reports
    - transcript.log
    - meta.json
```

Runtime exists only after an explicit framework launch.

## Adjacent Postures

| Skill          | Kind                 | Difference from operator                                          |
| -------------- | -------------------- | ----------------------------------------------------------------- |
| `vc-partner`   | interactive posture  | shared steering and original-shape custody before/during strategy |
| `vc-ownership` | autonomous posture   | one slice driven end-to-end to verified handoff                   |
| `vc-init`      | orientation tool     | opens repo/runtime/intention truth; not a posture                 |
| `vc-agents`    | external fleet layer | launches workers; does not own the orchestration story by itself  |

## Rule

If the task is multi-wave, multi-agent, and plan-shaped, use operator posture.

If the task is one feature or one slice, use ownership or implement instead.
