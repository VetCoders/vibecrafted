# `vc-canary` Flow

```mermaid
flowchart TD
  A[$PWD] --> B[loct auto + canary_cli atlas]
  B --> C{coverage pass?}
  C -->|no| D[STOP + loctree-fail hak]
  C -->|yes| E[SENSE: planes_hint + hubs → scopes.json]
  E --> F[Fleet: 1 agent per scope]
  F --> G[merge-catalog + diff-audit]
  G --> H{suspicious deletions?}
  H -->|yes| I[examine why + AskUser — no revert]
  H -->|no| J[gates + one commit]
  I --> J
  J --> K[findings cross-check]
  K --> L[report → discuss → decide]
```

## Phase contract

| Phase    | Question                            | Output                      |
| -------- | ----------------------------------- | --------------------------- |
| Atlas    | Is inventory complete with receipt? | `.loctree/atlas/*`          |
| Sense    | Which planes?                       | `scopes.json` + briefs      |
| Fleet    | Did each scope deliver catalog?     | `catalogs/<id>.json`        |
| Settle   | Safe to commit?                     | one commit or operator hold |
| Findings | What is confirmed signal?           | `findings.json` + report    |
