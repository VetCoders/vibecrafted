# `vc-marbles` Flow

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted marbles codex --prompt 'Fix what is still wrong'] --> B[Create or inherit ancestor run lock]
    B --> C[Build ancestor prompt from one source]
    C --> D[Launch L1 agent run and watcher]
    D --> E[Collect finding, fix, and new evidence]
    E --> F{Converged?}
    F -->|no| G[Spawn next loop]
    G --> E
    F -->|yes| H[Write convergence report and return]
    E -->|blocked after repeated attempts| I[Escalate to vc-partner]
    I --> H
```

## Routes

| Entry                                                               | Args                                                                  | Produces                                                                  | Exit                   |
| ------------------------------------------------------------------- | --------------------------------------------------------------------- | ------------------------------------------------------------------------- | ---------------------- |
| `vibecrafted marbles <agent>`                                       | exactly one of `--prompt`, `--file`, or `--depth`; optional `--count` | ancestor report plus loop reports, transcripts, and meta under `marbles/` | `0` on launch          |
| `vc-marbles <agent>`                                                | same                                                                  | same                                                                      | `0` on launch          |
| `vibecrafted marbles pause\|stop\|resume\|session\|inspect\|delete` | control args                                                          | marbles runtime control actions                                           | `0` on control success |

### Escalation edges

- Same blocker persists after repeated loops -> `vibecrafted partner <agent>`
- The remaining gap is broader than convergence -> `vibecrafted ownership <agent>`
- The operator wants an audit instead of more loops -> `vibecrafted followup <agent>`

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/marbles/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: ancestor reports, loop reports, convergence reports, transcripts, and `.meta.json` sidecars under `marbles/reports/`
