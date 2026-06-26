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

## Routes

| Entry                             | Args         | Produces          | Exit            |
| --------------------------------- | ------------ | ----------------- | --------------- |
| `prview --pr <n>`                 | PR number    | artifact pack     | review evidence |
| `prview --with-tests --with-lint` | branch scope | quality artifacts | merge gate      |
| `vc-prview <agent>`               | prompt/file  | findings report   | bounded audit   |

## Output Rule

Produce findings first, ordered by severity and grounded in file-level evidence.
Keep summaries secondary to actionable before-merge output.
