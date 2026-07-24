# `vc-loctree` Flow

```mermaid
flowchart TD
    A[Repo-specific task] --> B{Question already bounded?}
    B -->|no| C[context / repo-view]
    B -->|yes| D[focus / slice / find]
    C --> D
    D --> E{Delete, rename, major refactor?}
    E -->|yes| F[impact plus manifest/runtime/test witness]
    E -->|no| G[direct source read]
    F --> G
    G --> H[nearest real product gate]
```

Literal route: `loct find Name` → `--where-symbol` → `loct body Name`.
Discovery route: `loct find --discover Terms` → verify candidates literally.

Loctree maps represented structure. Destructive decisions require an independent
witness for entrypoints, manifests, generated/dynamic wiring, tests, and runtime.
