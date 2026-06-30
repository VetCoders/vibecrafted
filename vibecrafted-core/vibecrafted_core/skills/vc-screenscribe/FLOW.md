# `vc-screenscribe` Flow

## Flow

```mermaid
flowchart TD
    A[Video or Screenscribe repo task] --> B{Video analysis?}
    B -->|yes| C[Pick review, preprocess, transcribe, or analyze]
    C --> D[Run screenscribe CLI on absolute input paths]
    D --> E[Report artifacts and blockers]
    B -->|repo work| F[Run or consume vc-init]
    F --> G[Use Loctree map plus repo gates]
    G --> H[Implement or diagnose Screenscribe code]
```

## Routes

| Entry                     | Args              | Produces                               | Exit          |
| ------------------------- | ----------------- | -------------------------------------- | ------------- |
| `screenscribe review`     | video paths       | transcript, findings, report artifacts | review output |
| `screenscribe preprocess` | video path        | transcript-first bundle                | artifact pack |
| `vc-screenscribe`         | repo/debug prompt | repo-aware guidance                    | report        |

## Verification Rule

Observed video evidence must become actionable engineering findings. Fixes are
verified through the relevant Screenscribe runtime or report gate, not only by
editing docs.
