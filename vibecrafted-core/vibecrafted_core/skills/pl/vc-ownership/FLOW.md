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

## Trasy

| Wejście                         | Argumenty                      | Produkuje                                        | Wyjście            |
| ------------------------------- | ------------------------------ | ------------------------------------------------ | ------------------ |
| `vibecrafted ownership <agent>` | `--prompt` lub `--file`        | raport dowiezienia end-to-end, transkrypt i meta | `0` przy dispatchu |
| `vc-ownership <agent>`          | tak samo, gdy istnieje wrapper | tak samo                                         | `0` przy dispatchu |

### Krawędzie eskalacji

- Potrzebne współsterowanie przy ryzykownej decyzji -> `vibecrafted partner <agent>`
- Potrzeba więcej jednostek wykonawczych -> `vc-agents`
- Pozostałe problemy P0/P1 po implementacji -> `vibecrafted marbles <agent>`
- Entropia po marbles -> `vibecrafted polarize <agent>`
- Luki w powierzchni produktu przed wykończeniem -> `vibecrafted dou <agent>`

### Artefakty sesji

- Korzeń artefaktów: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputy: `reports/<timestamp>_<slug>_<agent>.md` z dopasowanym `.transcript.log` i `.meta.json`
