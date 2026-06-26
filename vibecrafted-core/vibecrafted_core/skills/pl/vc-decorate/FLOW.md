# `vc-decorate` Flow

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted decorate codex --prompt 'Polish the surface'] --> B[Map current UX and design language]
    B --> C[Inspect screenshots, docs, and runtime surface]
    C --> D[Apply coherence and finishing pass]
    D --> E[Verify the changed surface]
    E --> F{Still structurally off?}
    F -->|yes| G[Escalate to vc-partner or vc-marbles]
    F -->|no| H[Write report and return]
    G --> D
```

## Trasy

| Wejście                        | Argumenty               | Produkuje                                               | Wyjście            |
| ------------------------------ | ----------------------- | ------------------------------------------------------- | ------------------ |
| `vibecrafted decorate <agent>` | `--prompt` lub `--file` | udekorowana powierzchnia plus report, transcript i meta | `0` przy dispatchu |
| `vc-decorate <agent>`          | tak samo                | tak samo                                                | `0` przy dispatchu |

### Krawędzie eskalacji

- Strukturalny problem UX lub niejasna intencja -> `vibecrafted partner <agent> --prompt 'Co-design the better shape'`
- Zweryfikowane findingi P0/P1 po przebiegu szlifu -> `vibecrafted marbles <agent> --prompt 'Converge the remaining issues'`
- Luka w pakowaniu odkryta podczas szlifu -> `vibecrafted hydrate <agent> --prompt 'Finish the market-facing surface'`

### Artefakty sesji

- Korzeń artefaktów: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Wyjścia: `reports/<timestamp>_<slug>_<agent>.md` z pasującymi `.transcript.log` i `.meta.json`
