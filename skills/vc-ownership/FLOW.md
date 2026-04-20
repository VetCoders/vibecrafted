# `vc-ownership` Flow

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted ownership codex --prompt 'Take the wheel'] --> B[Bootstrap context and repo truth]
    B --> C[Choose the shortest path to a finished product surface]
    C --> D[Implement across code, UX, docs, and packaging]
    D --> E[Run followup and targeted gates]
    E --> F{Anything still false or unfinished?}
    F -->|yes| G[Escalate to vc-marbles, vc-dou, vc-decorate, or vc-hydrate]
    F -->|no| H[Write ownership handoff and return]
    G --> D
```

## Routes

| Entry                           | Args                         | Produces                                         | Exit            |
| ------------------------------- | ---------------------------- | ------------------------------------------------ | --------------- |
| `vibecrafted ownership <agent>` | `--prompt` or `--file`       | end-to-end delivery report, transcript, and meta | `0` on dispatch |
| `vc-ownership <agent>`          | same when the wrapper exists | same                                             | `0` on dispatch |

### Escalation edges

- Need shared steering on a risky decision -> `vibecrafted partner <agent>`
- Need more execution units -> `vc-agents`
- Remaining P0/P1 issues after implementation -> `vibecrafted marbles <agent>`

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: `reports/<timestamp>_<slug>_<agent>.md` with matching `.transcript.log` and `.meta.json`
