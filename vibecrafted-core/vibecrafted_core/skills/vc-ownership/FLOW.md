# `vc-ownership` Flow

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted ownership codex --prompt 'Take the wheel'] --> B[Bootstrap context and repo truth]
    B --> C[Choose the shortest path to a finished product surface]
    C --> D[Implement across code, UX, docs, and packaging]
    D --> E[Run gates and real-path smoke]
    E --> F[Run vc-review, vc-followup, vc-audit, vc-dou]
    F --> G{Anything still false or unfinished?}
    G -->|yes| H[Escalate to vc-marbles, vc-polarize, vc-decorate, or vc-hydrate]
    H --> D
    G -->|no| I[Write ownership handoff and return]
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
- Entropy after marbles -> `vibecrafted polarize <agent>`
- Product-surface gaps before finish -> `vibecrafted dou <agent>`

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: `reports/<timestamp>_<slug>_<agent>.md` with matching `.transcript.log` and `.meta.json`
