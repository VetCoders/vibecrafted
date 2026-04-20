# `vc-prune` Flow

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted prune codex --prompt 'Strip dead code'] --> B[Map runtime cone and blast radius]
    B --> C[Identify deletable surfaces]
    C --> D[Cut dead or duplicate paths]
    D --> E[Run verification and impact checks]
    E --> F{Still noisy or risky?}
    F -->|yes| G[Escalate to vc-review or vc-marbles]
    F -->|no| H[Write prune report and return]
    G --> H
```

## Routes

| Entry                       | Args                   | Produces                             | Exit            |
| --------------------------- | ---------------------- | ------------------------------------ | --------------- |
| `vibecrafted prune <agent>` | `--prompt` or `--file` | pruning report, transcript, and meta | `0` on dispatch |
| `vc-prune <agent>`          | same                   | same                                 | `0` on dispatch |

### Escalation edges

- Need a findings-first audit before deleting -> `vibecrafted review <agent>`
- Deletions reveal new counterexamples -> `vibecrafted marbles <agent>`
- Wider product-surface cleanup is needed -> `vibecrafted ownership <agent>`

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: `reports/<timestamp>_<slug>_<agent>.md` with matching `.transcript.log` and `.meta.json`
