# `{{SKILL_NAME}}` Flow

> To szablon scaffoldingu, nie aktywny skill. Zduplikuj przez
> `tools/vc-skill-new.sh <name>` i zastąp każdy marker TODO przed otwarciem
> PR-a. Wyscaffoldowano {{CREATED_DATE}}.

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

## Trasy

| Wejście                                        | Argumenty               | Produkuje                                   | Wyjście            |
| ---------------------------------------------- | ----------------------- | ------------------------------------------- | ------------------ |
| `vibecrafted {{SKILL_NAME_NO_PREFIX}} <agent>` | `--prompt` lub `--file` | TODO terminalny artefakt, transkrypt i meta | `0` przy dispatchu |
| `{{SKILL_NAME}} <agent>`                       | tak samo                | tak samo                                    | `0` przy dispatchu |

### Krawędzie eskalacji

- TODO — kiedy ten skill powinien przekazać pracę upstream (np. potrzeba planowania -> `vibecrafted scaffold <agent>`)
- TODO — kiedy ten skill powinien przekazać pracę downstream (np. gotowe do wykonania -> `vibecrafted implement <agent>`)
- TODO — kiedy ten skill powinien eskalować do współdzielonego sterowania -> `vibecrafted partner <agent>`

### Artefakty sesji

- Korzeń artefaktów: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Wyjścia: `reports/<timestamp>_<slug>_<agent>.md` z pasującymi `.transcript.log` i `.meta.json`

### Antywzorce

- TODO — typowy tryb porażki #1 specyficzny dla przebiegu tego skilla
- TODO — typowy tryb porażki #2 (np. wywołanie przed wymaganym skillem-prerekwizytem)
- Dowiezienie tego FLOW.md z wciąż obecnymi markerami TODO — zastąp je, inaczej
  skill nie dopełnił swojego kontraktu autorskiego
