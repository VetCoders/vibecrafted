# `vc-screenscribe` Flow

## Flow

```mermaid
flowchart TD
    A[Video or ScreenScribe repo task] --> B{Video analysis?}
    B -->|yes| C[Pick review, preprocess, transcribe, or analyze]
    C --> D[Run screenscribe CLI on absolute input paths]
    D --> E[Report artifacts and blockers]
    B -->|repo work| F[Run or consume vc-init]
    F --> G[Use Loctree map plus repo gates]
    G --> H[Implement or diagnose ScreenScribe code]
```

## Trasy

| Wejście                   | Argumenty         | Produkuje                               | Wyjście           |
| ------------------------- | ----------------- | --------------------------------------- | ----------------- |
| `screenscribe review`     | ścieżki wideo     | transcript, findingi, artefakty raportu | wyjście review    |
| `screenscribe preprocess` | ścieżka wideo     | bundle transcript-first                 | paczka artefaktów |
| `vc-screenscribe`         | prompt repo/debug | wskazówki świadome repo                 | raport            |

## Reguła weryfikacji

Zaobserwowane evidence z wideo musi stać się wykonalnymi findingami inżynierskimi. Poprawki
weryfikuje się przez właściwy runtime ScreenScribe lub bramkę raportu, a nie tylko przez
edytowanie dokumentów.
