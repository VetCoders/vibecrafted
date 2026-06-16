# `vc-loctree` Flow

## Flow

```mermaid
flowchart TD
    A[Repo-specific task] --> B[repo-view]
    B --> C[focus target dirs]
    C --> D[slice files before edits]
    D --> E{Delete or major refactor?}
    E -->|yes| F[impact]
    E -->|no| G[find before new symbols]
    F --> G
    G --> H[follow dead/cycles/twins/hotspots when needed]
    H --> I[Run nearest gate]
```

## Trasy

| Wejście          | Argumenty       | Produkuje               | Wyjście         |
| ---------------- | --------------- | ----------------------- | --------------- |
| `loct repo-view` | korzeń projektu | przegląd repo           | mapa            |
| `loct focus`     | katalog         | przegląd modułu         | mapa celu       |
| `loct slice`     | plik            | zależności i konsumenci | kontekst edycji |

## Reguła fallbacku

Grep lub surowe przeszukiwanie plików to evidence fallbacku tylko wtedy, gdy Loctree nie potrafi
odpowiedzieć na pytanie strukturalne. Odnotuj tę lukę strukturalną, aby powierzchnia Loctree mogła
się poprawić.
