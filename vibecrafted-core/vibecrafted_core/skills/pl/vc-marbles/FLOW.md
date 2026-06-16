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

## Trasy

| Wejście                                                             | Argumenty                                                                   | Produkuje                                                              | Wyjście                    |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------- | ---------------------------------------------------------------------- | -------------------------- |
| `vibecrafted marbles <agent>`                                       | dokładnie jeden z `--prompt`, `--file` lub `--depth`; opcjonalnie `--count` | raport ancestora plus raporty pętli, transkrypty i meta pod `marbles/` | `0` przy launchu           |
| `vc-marbles <agent>`                                                | tak samo                                                                    | tak samo                                                               | `0` przy launchu           |
| `vibecrafted marbles pause\|stop\|resume\|session\|inspect\|delete` | argumenty sterujące                                                         | akcje sterujące runtime'em marbles                                     | `0` przy udanym sterowaniu |

### Krawędzie eskalacji

- Ten sam blocker utrzymuje się po wielu pętlach -> `vibecrafted partner <agent>`
- Pozostała luka jest szersza niż zbieżność -> `vibecrafted ownership <agent>`
- Operator chce auditu zamiast kolejnych pętli -> `vibecrafted followup <agent>`

### Artefakty sesji

- Korzeń artefaktów: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/marbles/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputy: raporty ancestora, raporty pętli, raporty zbieżności, transkrypty oraz sidecary `.meta.json` pod `marbles/reports/`
