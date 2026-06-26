# `{{SKILL_NAME}}` Flow

> This is a scaffolding template, not an active skill. Duplicate via
> `tools/vc-skill-new.sh <name>` and replace every TODO marker before opening a
> PR. Scaffolded {{CREATED_DATE}}.

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted {{SKILL_NAME_NO_PREFIX}} claude --prompt 'TODO concrete operator example'] --> B[TODO first decisive move]
    B --> C[TODO second move or branching decision]
    C --> D{TODO branching condition?}
    D -->|primary path| E[TODO main deliverable]
    D -->|escalation| F[TODO handoff to adjacent vc-* skill]
    E --> G[Return report to operator]
    F --> G
```

## Routes

| Entry                                          | Args                   | Produces                                     | Exit            |
| ---------------------------------------------- | ---------------------- | -------------------------------------------- | --------------- |
| `vibecrafted {{SKILL_NAME_NO_PREFIX}} <agent>` | `--prompt` or `--file` | TODO terminal artifact, transcript, and meta | `0` on dispatch |
| `{{SKILL_NAME}} <agent>`                       | same                   | same                                         | `0` on dispatch |

### Escalation edges

- TODO — when this skill should hand off upstream (e.g. needs planning -> `vibecrafted scaffold <agent>`)
- TODO — when this skill should hand off downstream (e.g. ready to execute -> `vibecrafted implement <agent>`)
- TODO — when this skill should escalate to shared steering -> `vibecrafted partner <agent>`

### Session artifacts

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputs: `reports/<timestamp>_<slug>_<agent>.md` with matching `.transcript.log` and `.meta.json`

### Anti-patterns

- TODO — common failure mode #1 specific to this skill's flow
- TODO — common failure mode #2 (e.g. invoking before required prerequisite skill)
- Shipping this FLOW.md with TODO markers still in place — replace them or the
  skill has not completed its authoring contract
