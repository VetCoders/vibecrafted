# `vc-polarize` Flow

> Front-face: `vc-polarize`. Runner bramkuje uruchomienia oparte na tasku
> przez Loctree prism score, zanim dojdzie do jakiegokolwiek dispatchu agenta.

## Flow

```mermaid
flowchart TD
    A[Operator: vc-polarize codex --task concept] --> B[Run loct prism preflight]
    B --> C{Prism score band}
    C -->|0..4 abort| D[Stop and print prism.json path]
    C -->|5..8 memo| E[Write local memo and thin context pack]
    C -->|9..12 pass| F[Dispatch full polarize pass]
    C -->|13..15 doctrine| G[Dispatch doctrine pass with regression contract]
    F --> H[Capture session UUID]
    G --> H
    H --> I[Emit context-corpus pack via aicx extract]
```

## Trasy

| Pasmo    | Wynik    | Działanie runnera                                     | Dispatch agenta |
| -------- | -------- | ----------------------------------------------------- | --------------- |
| abort    | `0..4`   | Pokaż operatorowi odrzucenie i ścieżkę prism          | nie             |
| memo     | `5..8`   | Wyemituj lokalne memo i cienki sidecar context-corpus | nie             |
| pass     | `9..12`  | Uruchom pełny prompt polarize z evidence prism        | tak             |
| doctrine | `13..15` | Uruchom przebieg doctrine z oczekiwaniem regression   | tak             |

### Context Corpus

- `pass` i `doctrine`: przechwyć `session: <uuid>` ze stdoutu agenta i opakuj
  `aicx extract --agent <agent> --session <uuid> --output <raw-path>`.
- `memo`: zapisz tylko cienki lokalny pack memo z `learning_use.allowed`
  ograniczonym do `format_examples`.
- `abort`: nie zapisuj wyjścia context-corpus.
- `--no-context-corpus`: pomiń opcjonalną emisję packu bez wywalania dispatchu.
