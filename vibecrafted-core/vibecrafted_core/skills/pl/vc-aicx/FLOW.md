# `vc-aicx` Flow

## Flow

```mermaid
flowchart TD
    A[Need prior intent] --> B[Identify repo or session scope]
    B --> C[Run or consume vc-init for repo work]
    C --> D[Query AICX by project, date, or run id]
    D --> E[Read selected chunks, not summaries alone]
    E --> F[Verify current truth with Loctree and repo gates]
    F --> G[Report intent, evidence, and drift]
```

## Trasy

| Wejście        | Argumenty                       | Produkuje                                 | Wyjście            |
| -------------- | ------------------------------- | ----------------------------------------- | ------------------ |
| `aicx search`  | zapytanie + filtry project/date | rankowane chunki sesji                    | lista evidence     |
| `aicx intents` | scope projektu                  | ustrukturyzowane rekordy intencji/wyników | mapa intencji      |
| `aicx extract` | surowe wyjście JSON/JSONL/task  | czytelny markdown                         | odzyskany kontekst |

## Reguła Evidence

Odzyskana intencja jest klasyfikowana względem żywego drzewa jako aktualna,
nieaktualna (stale), brakująca lub zaprzeczona. AICX potrafi wyjaśnić, dlaczego
obrano daną ścieżkę; to bieżące evidence z Loctree i bramki repo decydują, czy
nadal jest prawdziwa.
