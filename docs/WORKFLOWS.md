# Workflows

This page documents how the command deck actually chains skills today. It is a
runtime map of `scripts/vibecrafted`, the shared helper layer, and the skill
contracts in `skills/`.

## Operator entry points

- `make vibecrafted` launches the terminal-native installer wizard.
- `make wizard` launches the browser-guided installer surface.
- `vibecrafted help` is the command-deck front door once the framework is installed.
- `vibecrafted init <agent>` is the interactive first context handoff.
- `vibecrafted research --prompt|--file` is the triple-agent swarm launcher.
- `vibecrafted <skill> <agent>` covers the agent-scoped workflow surfaces.

## Framework flow

```mermaid
flowchart TD
    A[Operator entry<br/>make vibecrafted / vibecrafted help] --> B[Choose route]
    B --> C[vibecrafted init agent]
    C --> D{What kind of move?}

    D --> E[scaffold]
    E --> F[workflow]

    D --> F[workflow]
    D --> G[implement]
    D --> H[partner]
    D --> I[intents]
    D --> J[review]
    D --> K[dou]

    H --> L[delegate]
    H --> M[agents]
    L --> F
    M --> F

    I --> J
    I --> N[ownership]
    I --> O[marbles]

    F --> P[followup]
    G --> P
    N --> P

    P --> Q{P0/P1 still open?}
    Q -->|yes| O[marbles]
    O --> P
    Q -->|no| R{Need ship surface work?}

    K --> S[hydrate]
    K --> T[decorate]
    R -->|yes| K
    T --> S
    S --> U[release]

    J --> V[Return findings]
    U --> W[Return to operator]
    R -->|no| W
```

## Route families

| Surface                      | Start here                                               | Usually chains into                                                          |
| ---------------------------- | -------------------------------------------------------- | ---------------------------------------------------------------------------- |
| New idea or vague scope      | `vibecrafted scaffold <agent>`                           | `workflow`, `partner`, `implement`                                           |
| First repo contact           | `vibecrafted init <agent>`                               | `workflow`, `implement`, `partner`, `review`, `intents`                      |
| Autonomous delivery          | `vibecrafted implement <agent>`                          | `followup`, `marbles`, optionally `dou` / `decorate` / `hydrate` / `release` |
| Shared steering              | `vibecrafted partner <agent>`                            | `delegate`, `agents`, `workflow`, `ownership`                                |
| Bounded review               | `vibecrafted review <agent>`                             | `followup`, `marbles`                                                        |
| Post-implementation audit    | `vibecrafted followup <agent>`                           | `marbles`, `dou`, `decorate`, `hydrate`, `release`                           |
| Truth audit vs original plan | `vibecrafted intents <agent>`                            | `review`, `marbles`, `ownership`                                             |
| Launch-readiness gap finding | `vibecrafted dou <agent>`                                | `hydrate`, `decorate`, `release`                                             |
| Explicit ship path           | `vibecrafted decorate <agent>` or `hydrate` or `release` | `release`                                                                    |

## Runtime contract

- Artifact root: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock path: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Generic agent-spawned runs create `plans/`, `reports/`, `tmp/`, plus `.meta.json`
  and `.transcript.log` sidecars for each report basename.
- `vc-marbles` keeps its ancestor, loop, and watcher outputs under
  `$artifact_root/marbles/`.
- `make vibecrafted` and `make wizard` are installer entry points, not skill
  execution paths; they exist to get the command deck and wrappers onto the machine.
- `vibecrafted implement` is the canonical autonomous delivery command. The
  `justdo` command and `vc-justdo` helper remain legacy aliases for installed
  agents and old prompts, not the official front face.
- `vc-review` reviews a bounded target such as PR 14, `HEAD~10..HEAD`, a branch
  diff, or a generated artifact pack. Use `vc-followup` when the question is
  broader: where the implementation is heading, what still feels unfinished,
  and what the next move should be.
- `vc-partner` is shared steering with the user. `vc-ownership` is operational
  ownership by the agent. Both can produce plans; neither silently means
  delegation unless the operator explicitly invokes a delegation path.

## Next reading

- [SKILLS](./SKILLS.md) for the per-skill route index.
- `skills/<skill>/FLOW.md` for individual flowcharts and CLI schemas.
