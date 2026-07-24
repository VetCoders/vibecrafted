# Przepływ `vc-implement` — faza WRITE ship

> Skill id `implement`. Faza WRITE VC-ship. Nie alias `vc-justdo`.
> Prefiks run-id: `impl-` (osobny od `just-` justdo).

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted implement codex --prompt 'Ship the feature'] --> B[Bootstrap repo context]
    B --> C{Greenfield or still vague?}
    C -->|yes| D[Escalate to vc-scaffold first]
    C -->|no| E[Implement directly]
    D --> E
    E --> F[Run tests and integration checks]
    F --> G[Mandatory vc-followup audit]
    G --> H{P0 or P1 findings remain?}
    H -->|yes| I[Mandatory vc-marbles loop]
    I --> G
    H -->|no| J[Write report and return]
    E -->|need shared steering| K[Escalate to vc-partner or vc-agents]
    K --> E
```

## Trasy

| Wejście                         | Argumenty               | Produkuje                               | Wyjście            |
| ------------------------------- | ----------------------- | --------------------------------------- | ------------------ |
| `vibecrafted implement <agent>` | `--prompt` lub `--file` | raport implementacji, transkrypt i meta | `0` przy dispatchu |
| `vc-implement <agent>`          | to samo                 | to samo                                 | `0` przy dispatchu |

Nie trasy tego skilla: `vibecrafted justdo …` / `vc-justdo` (`vc-justdo`).

### Krawędzie eskalacji

- Scope jest wciąż architektoniczny → `vibecrafted scaffold <agent>`
- Potrzebne wspólne sterowanie → `vibecrafted partner <agent>`
- Pozostają problemy P0/P1 → `vibecrafted marbles <agent>`

### Tożsamość runtime

| Powierzchnia    | Wartość                           |
| --------------- | --------------------------------- |
| Skill id        | `implement`                       |
| Komórka matrycy | Cykl ship — faza WRITE            |
| Prefiks run-id  | `impl-`                           |
| Faza ship?      | Tak — w `SHIP_STAGES` po scaffold |
