# `vc-skillaunch` Flow

## Flow

```mermaid
flowchart TD
    A[Completed workflow exists] --> B[Brainstorm with user]
    B --> C{Repo-specific?}
    C -->|yes| D[Run or consume vc-init]
    C -->|no| E[State no-repo exception]
    D --> F[Design skill contract]
    E --> F
    F --> G[Get approval]
    G --> H[Write SKILL.md, FLOW.md, scripts if needed]
    H --> I[Validate trigger and artifact shape]
```

## Trasy

| Wejście         | Argumenty                     | Produkuje                          | Wyjście                    |
| --------------- | ----------------------------- | ---------------------------------- | -------------------------- |
| `vc-skillaunch` | kontekst ukończonego workflow | wielokrotnego użytku pakiet skilla | zainstalowany draft skilla |

## Reguła walidacji

Powstały skill musi dać się wywołać i wykonać bez ukrytego kontekstu z oryginalnej
rozmowy. Jeśli przyszły agent potrzebuje niewypowiedzianego założenia, skill nie jest gotowy.
