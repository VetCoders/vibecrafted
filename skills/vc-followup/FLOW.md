# `vc-followup` Flow

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted followup codex --file context.md] --> B[Read current implementation and prior intent]
    B --> C[Run audit and verification passes]
    C --> D[Classify P0, P1, and P2 findings]
    D --> E{Any P0 or P1?}
    E -->|yes| F[Escalate to vc-marbles or vc-ownership]
    E -->|no| G[Return findings and next move]
    F --> G
```

## Routes

| Entry                          | Args                   | Produces                              | Exit            |
| ------------------------------ | ---------------------- | ------------------------------------- | --------------- |
| `vibecrafted followup <agent>` | `--prompt` or `--file` | findings report, transcript, and meta | `0` on dispatch |
| `vc-followup <agent>`          | same                   | same                                  | `0` on dispatch |

### Escalation edges

- P0/P1 issues remain -> `vibecrafted marbles <agent>`
- The audit shows a bigger repo-wide ownership gap -> `vibecrafted ownership <agent>`
- Findings need shared interpretation before action -> `vibecrafted partner <agent>`

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: `reports/<timestamp>_<slug>_<agent>.md` with matching `.transcript.log` and `.meta.json`
