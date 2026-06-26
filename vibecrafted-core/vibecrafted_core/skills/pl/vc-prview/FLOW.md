# `vc-prview` Flow

## Flow

```mermaid
flowchart TD
    A[Review branch, PR, or artifact pack] --> B[Run or consume vc-init]
    B --> C[Generate prview artifacts]
    C --> D[Read report.json and merge gate]
    D --> E[Read quality logs and changed-file context]
    E --> F[Extract findings with evidence]
    F --> G[Write before-merge TODO]
```

## Trasy

| Wejście                           | Argumenty    | Produkuje         | Wyjście            |
| --------------------------------- | ------------ | ----------------- | ------------------ |
| `prview --pr <n>`                 | numer PR     | artifact pack     | evidence do review |
| `prview --with-tests --with-lint` | scope gałęzi | artefakty jakości | bramka merge       |
| `vc-prview <agent>`               | prompt/plik  | raport findingów  | ograniczony audyt  |

## Reguła wyjścia

Najpierw produkuj findingi, uporządkowane wg severity i ugruntowane w evidence
na poziomie pliku. Trzymaj podsumowania jako drugorzędne wobec wykonalnego
wyjścia przed mergem.
