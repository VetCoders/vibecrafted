# Przepływ `vc-followup`

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

## Trasy

| Wejście                        | Argumenty               | Produkuje                           | Wyjście            |
| ------------------------------ | ----------------------- | ----------------------------------- | ------------------ |
| `vibecrafted followup <agent>` | `--prompt` lub `--file` | raport findingów, transkrypt i meta | `0` przy dispatchu |
| `vc-followup <agent>`          | to samo                 | to samo                             | `0` przy dispatchu |

### Krawędzie eskalacji

- Pozostają problemy P0/P1 -> `vibecrafted marbles <agent>`
- Audyt pokazuje większą lukę w ownership w skali całego repo -> `vibecrafted ownership <agent>`
- Findingi wymagają wspólnej interpretacji przed działaniem -> `vibecrafted partner <agent>`

### Artefakty sesji

- Katalog artefaktów: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Wyjścia: `reports/<timestamp>_<slug>_<agent>.md` z odpowiadającymi `.transcript.log` i `.meta.json`
