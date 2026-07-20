# Flow `vc-loctree`

```mermaid
flowchart TD
    A[Zadanie repozytoryjne] --> B{Pytanie jest już zawężone?}
    B -->|nie| C[context / repo-view]
    B -->|tak| D[focus / slice / find]
    C --> D
    D --> E{Delete, rename, duży refactor?}
    E -->|tak| F[impact plus świadek manifest/runtime/test]
    E -->|nie| G[bezpośrednie czytanie źródła]
    F --> G
    G --> H[najbliższa realna brama produktu]
```

Ścieżka literalna: `loct find Name` → `--where-symbol` → `loct body Name`.
Ścieżka discovery: `loct find --discover Terms` → literalna weryfikacja kandydatów.

Loctree mapuje reprezentowaną strukturę. Decyzje destrukcyjne wymagają osobnego
świadka dla entrypointów, manifestów, generated/dynamic wiring, testów i runtime.
