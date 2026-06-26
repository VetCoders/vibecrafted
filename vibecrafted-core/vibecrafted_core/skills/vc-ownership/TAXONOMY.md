# `vc-ownership` Taxonomy

`vc-ownership` lives in two layers.

## Interactive or Headless Skill

```yaml
vc-ownership:
  kind: autonomous_posture
  scope: interactive_or_headless_session
  meaning: take responsibility end-to-end, minimize questions, drive to green
  autonomy: full
```

In an interactive session, `$vc-ownership` means the current agent accepts
autonomous delivery responsibility. In a headless session, the same posture
means fewer questions, stronger assumptions, and full end-to-end verification
inside the assigned mandate.

It does not automatically launch a separate runtime process.

## Runtime Workflow

```yaml
vibecrafted_ownership_runtime:
  entrypoints:
    - vibecrafted ownership <agent> --file <task>
    - vibecrafted ownership <agent> --prompt <mandate>
    - vc-ownership <agent> --prompt <mandate>
  creates:
    - run_id
    - reports
    - transcript.log
    - meta.json
```

Runtime exists only after an explicit framework launch.

## Adjacent Postures

| Skill         | Kind                  | Difference from ownership                         |
| ------------- | --------------------- | ------------------------------------------------- |
| `vc-partner`  | interactive posture   | keeps strategic steering shared                   |
| `vc-operator` | orchestration posture | conducts waves instead of owning one slice        |
| `vc-init`     | orientation tool      | opens repo/runtime/intention truth; not a posture |

## Rule

Ownership drives the slice, but it still ends with read-only perception:
`vc-review`, `vc-followup`, `vc-audit`, and `vc-dou`.
