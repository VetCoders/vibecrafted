# Szablon SCAFFOLD.md

Użyj tego szablonu jako wyjścia planowania. W swoim faktycznym wyjściu wytnij komentarze.

```markdown
---
run_id: <generated-unique-id>
agent: <claude|codex|gemini>
skill: <vc-scaffold|vc-workflow|vc-implement>
project: <repo-name>
status: pending
vector: <stabilize|implement|recon|e2e> # selects the gate profile = what counts as delivery
created: <ISO-8601 timestamp>
---

# Architecture Plan: [Project Name]

## Problem Statement

[1-2 zdania. Jaki problem rozwiązujemy? Czemu to ma znaczenie?]

Przykład: „Monolit staje się nieutrzymywalny. Musimy wyciągnąć serwis płatności do osobnego serwisu, żeby zespoły mogły dowozić niezależnie, bez koordynowania deployów."

## Key Architectural Decisions

### Decision 1: [Name]

**Choice:** [Co robimy]
**Trade-off:** [Z czego rezygnujemy]
**Why:** [Czemu to lepsze niż alternatywa]

### Decision 2: [Name]

**Choice:** [Co robimy]
**Trade-off:** [Z czego rezygnujemy]
**Why:** [Czemu to lepsze niż alternatywa]

(Trzymaj się 3-5 decyzji. Nie każdego technicznego szczegółu.)

## Scope Boundaries

### Phase 1: MVP (This Sprint/Cycle)

**In scope:**

- Ficzer/komponent A
- Ficzer/komponent B
- Infrastruktura testowa

**Out of scope:**

- Ficzer X (nice to have, dowozi się w fazie 2)
- Optymalizacja Y (nie blokuje MVP)

**Explicitly out of scope:**

- Przepisanie starego systemu (nie wydarza się)
- Migracja do języka Z (poza granicami)

## Architecture Overview

[Diagram ASCII lub krótki opis]

Przykład:
```

User → API Gateway → Auth Service → Payment Service → Stripe
↓
Cache Layer
↓
Database

```

## Task Breakdown

Każdy task jest agent-ready. Agenci wykonują równolegle, gdy pozwalają na to zależności. Każdy task niesie
marker `state` `[ ] [~] [?] [!] [x]` (zobacz references/measure-core.md); tylko delivery-verifier przerzuca
`[~]→[x]`. vc-operator czyta kolumnę `state`, żeby trigger/stop.

### Task 1: [Imperative title]   `state: [ ]`
**Vector:** [stabilize|implement|recon|e2e]
**Produces:** [Jaki kod/config/testy powstają]
**Depends on:** [Task X, gotowa infrastruktura]
**Owner:** [Skill agenta lub rola człowieka]
**Delivery-verifier:** [niefałszowalny test, który przerzuca [~]→[x]; bez niego task dowozi się jako [?]]
**Acceptance:** [intent vs baseline — co dowodzi, że delivery ≈ claim, nie tylko „agent tak powiedział"]

Przykład:
```

Task: Build authentication middleware state: [ ]
Vector: implement
Produces: /middleware/auth.ts, /tests/auth.test.ts
Depends on: Infrastructure up, database schema
Owner: Core backend agent
Delivery-verifier: `pnpm test auth` green — rejects invalid tokens, passes valid; flips [~]→[x]
Acceptance: intent (auth enforced on all routes) vs baseline (routes open); delivery proven by the verifier, not "agent said so"

```

## Test Gates (per Vector profile)

Każda faza ma bramkę dostarczania wybraną przez jej `Vector` (zobacz references/measure-core.md) — bramka
definiuje, co liczy się jako delivery, więc różni się wg Vectora. Nie przesuwaj fazy, dopóki jej bramka nie przerzuci
każdego cięcia `[~]→[x]`.

- **implement** → ficzer działa + testy zielone na ścieżkach core
- **stabilize** → krwawienie ustaje + bramka regresji/canary zielona (busy ≠ dead)
- **recon** → mapa/odpowiedź dostarczona z referencjami do evidence
- **e2e** → pełna ścieżka przebiega end-to-end
- **always** → żadnych odsłoniętych sekretów; bramka bezpieczeństwa nie pominięta (`--no-verify` zabronione)

## Living Tree Note

Ten plan żyje. Zmienia się, gdy się uczymy. Gdy zmieniasz plan:

1. **Opatrz datą** zmianę
2. **Wyjaśnij dlaczego** (nowe ograniczenie, odkryta zależność, zmiana rynku)
3. **Przejdź task breakdown na nowo**, jeśli scope się zmienił
4. **Zaktualizuj kryteria akceptacji**, jeśli definicje się przesunęły

Udokumentuj rozumowanie. Przyszli inżynierowie ci podziękują.

---

## Running This Plan

1. Przeczytaj ten dokument od góry do dołu
2. Dla każdego taska odpal agenta lub przypisz człowieka
3. Każdy task produkuje artefakty (kod, testy, docy)
4. Zwaliduj wobec kryteriów akceptacji
5. Gdy wszystkie taski fazy 1 przechodzą bramki, przejdź do fazy 2

Żadnego machania rękami. Jasna praca. Jasne kryteria. Tak dowożą founderzy.
```
