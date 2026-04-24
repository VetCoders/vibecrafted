# `vc-research` Flow

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted research --prompt 'Research the topic'] --> B[Parse one question or plan file]
    B --> C[Create or inherit swarm run context]
    C --> D[Prepare Claude, Codex, and Gemini launchers]
    D --> E{Runtime?}
    E -->|terminal or visible| F[Open shared zellij research tab]
    E -->|headless| G[Print launcher paths and await command]
    F --> H[Each agent writes report, transcript, and meta]
    G --> H
    H --> I[Await and synthesize next]
```

## Routes

| Entry                                      | Args         | Produces                      | Exit            |
| ------------------------------------------ | ------------ | ----------------------------- | --------------- |
| `vibecrafted research --prompt <text>`     | question     | swarm launch plus run context | `0` on dispatch |
| `vibecrafted research --file <plan.md>`    | plan file    | same                          | `0` on dispatch |
| `vibecrafted research await --run-id <id>` | run selector | await/summary output          | `0` on read     |
| `vc-research --prompt\|--file`             | same         | same                          | `0` on dispatch |

### Escalation edges

- Research is complete and the team wants a plan -> `vibecrafted scaffold <agent>`
- Research is complete and execution should start -> `vibecrafted workflow <agent>` or `implement` (legacy alias: `justdo`)
- Research needs one strong owner instead of a swarm -> `vibecrafted <agent> research <plan.md>`

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: per-agent reports, transcripts, and `.meta.json` sidecars under `reports/`
