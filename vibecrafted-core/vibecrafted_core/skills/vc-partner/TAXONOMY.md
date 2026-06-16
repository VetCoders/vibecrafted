# `vc-partner` Taxonomy

`vc-partner` lives in two layers.

## Interactive Skill

```yaml
vc-partner:
  kind: interactive_posture
  scope: current_interactive_session
  meaning: proactive shared steering, original shape custody, partner journal, read/write cadence
  autonomy: collaborative
```

In an interactive session, `$vc-partner` means the current agent accepts the
shared-steering posture. It does not automatically start a new runtime process.

The partner posture is responsible for:

- defining the problem with the operator
- preserving `original_shape`
- building the plan with `vc-scaffold`
- choosing the right execution lane
- enforcing write -> read cadence
- judging shape fidelity after implementation
- keeping the partner journal current

## Runtime Workflow

```yaml
vibecrafted_partner_runtime:
  entrypoints:
    - vibecrafted partner <agent> --file <shape-or-plan>
    - vibecrafted partner <agent> --prompt <intent>
    - vc-partner <agent> --prompt <intent>
  creates:
    - run_id
    - partner/journal.md
    - reports
    - transcript.log
    - meta.json
```

Runtime exists only after an explicit framework launch.

## Adjacent Postures

| Skill          | Kind                  | Difference from partner                            |
| -------------- | --------------------- | -------------------------------------------------- |
| `vc-ownership` | autonomous posture    | takes the wheel and drives end-to-end              |
| `vc-operator`  | orchestration posture | conducts waves and field teams after a plan exists |
| `vc-init`      | orientation tool      | opens repo/runtime/intention truth; not a posture  |

## Rule

Partner may launch write lanes, but it cannot call the work done until the
read-only cadence has checked implementation truth, shape fidelity, completion
claims, and Definition of Undone.
