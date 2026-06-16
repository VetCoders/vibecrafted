# Faza 2: RESEARCH — odkrywanie twardych faktów (ground truth)

## Cel

Zbadaj niewiadome wyniesione przez fazę Examine.
Przekształć otwarte pytania z CONTEXT.md w konkretne wskazówki implementacyjne.
Nigdy nie zgaduj — znajdź autorytatywne źródła.

## Hierarchia źródeł researchu

### Tier 1: Context7 (dokumentacja bibliotek)

Dla każdego pytania o bibliotekę/framework:

```
1. resolve-library-id(libraryName, query)
2. query-docs(libraryId, query)
```

Najlepsze do: użycia API, konfiguracji, przewodników migracji, oficjalnych przykładów.
Limit: 3 wywołania na pytanie. Po 3 próbach użyj najlepszego wyniku.

### Tier 2: Brave Search (research webowy)

Dla szerszych pytań, aktualnych praktyk, porównań:

```bash
python3 $VIBECRAFTED_ROOT/skills/vc-research/engines/brave_search.py "query" [-c count] [-l lang]
```

Wskazówki do formułowania zapytań:

- Dopisz bieżący rok: `"Rust async patterns 2026"`
- Bądź konkretny: `"objc2 NSEvent addLocalMonitor Rust"`, nie `"event handling"`
- Użyj filtra języka dla wyników zależnych od locale: `-l pl` dla wyników polskich
- Max 20 wyników na zapytanie: `-c 20`

### Tier 3: WebFetch (konkretne strony)

Dla konkretnych URL-i znalezionych przez wyszukiwanie:

```
WebFetch(url, prompt)
```

Najlepsze do: czytania konkretnych stron dokumentacji, issue na GitHubie, blog postów.
Zawsze wyciągaj: przykłady kodu, wymagania wersji, znane ograniczenia.

### Tier 4: Wnętrze bazy kodu

Przeszukaj istniejący kod pod kątem wcześniejszego dorobku (tylko PO mapowaniu loctree):

- `Grep(pattern)` dla wzorców implementacyjnych
- `find(name)` dla istniejących symboli
- `Read(file)` dla konkretnych implementacji

## Strategia zapytań

### Z otwartych pytań CONTEXT.md

Każde otwarte pytanie z Examine mapuje się na zapytania researchowe:

| Typ pytania                           | Podejście researchowe                                        |
| ------------------------------------- | ------------------------------------------------------------ |
| „Jak działa API X?"                   | Context7 → Brave → WebFetch                                  |
| „Najlepszy wzorzec dla Y?"            | Brave ("Y best practices <lang> <year>") → grep bazy kodu    |
| „Czy biblioteka Z jest kompatybilna?" | Context7 (docs biblioteki) → Brave (raporty kompatybilności) |
| „Wydajność podejścia A vs B?"         | Brave (benchmarki) → WebFetch (szczegółowe porównanie)       |
| „API macOS dla funkcji F?"            | Brave ("macOS <API> Swift/Rust") → Apple docs przez WebFetch |

### Doprecyzowanie zapytania

Jeśli początkowe zapytanie zwraca słabe wyniki:

1. Poszerz: usuń konkretne terminy
2. Przeformułuj: inna terminologia
3. Przełącz język: spróbuj po angielsku, jeśli szukasz po polsku (lub odwrotnie)
4. Przełącz źródło: przejdź do kolejnego tieru

### Kontrola głębokości

- **Quick research** (1-2 pytania): 5-10 minut, 3-5 zapytań
- **Standard research** (3-5 pytań): 15-20 minut, 8-15 zapytań
- **Deep research** (złożone niewiadome): 30+ minut, 15-25 zapytań

Raportuj poziom głębokości w nagłówku RESEARCH.md.

## Format wyjścia RESEARCH.md

````markdown
# Research: <slug>

Date: <YYYY-MM-DD>
Depth: quick | standard | deep
Artifact root: $VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/

## Open Questions (from CONTEXT.md)

1. <Q1>
2. <Q2>

## Findings

### Q1: <question>

**Sources consulted:**

- Context7: <libraryId> — <result summary>
- Brave: "<query>" — <N results>
- WebFetch: <URL> — <key finding>

**Answer:**
<concise, factual answer>

**Code example:**

```<lang>
// relevant example from authoritative source
```
````

**Confidence:** high | medium | low
**Caveat:** <any limitations or version-specific notes>

---

### Q2: <question>

...

## Architectural Decision Record

### Decision: <what was decided>

- **Context**: <from CONTEXT.md>
- **Options considered**:
  1. {option A} — {pros/cons}
  2. {option B} — {pros/cons}
- **Chosen**: <option> because <reasoning based on findings>
- **Consequences**: <what this means for implementation>

## Implementation Guidance (for agents)

### Must-know for implementers:

- <concrete guidance derived from research>
- <API patterns to use>
- {pitfalls to avoid}

### Dependencies to add:

- <crate/package name> = "<version>"

### Configuration required:

- <env vars, feature flags, etc.>

```

## Typowe wzorce researchu

### Integracja nowego API
1. Context7: znajdź dokumentację biblioteki
2. Brave: "<library> + <target language> integration <year>"
3. WebFetch: przeczytaj przewodnik getting-started
4. Baza kodu: sprawdź istniejące wzorce adapterów

### Decyzja architektoniczna
1. Brave: "<pattern A> vs <pattern B> <language>"
2. WebFetch: przeczytaj artykuły porównawcze
3. Context7: sprawdź dokumentację obu bibliotek
4. Decyzja: macierz za/przeciw

### Specyficzne dla macOS
1. Brave: "macOS <API> <framework> <year>"
2. WebFetch: dokumentacja deweloperska Apple
3. Brave: "<API> Rust objc2 binding"
4. Baza kodu: istniejące wzorce użycia API macOS

### Pytanie o wydajność
1. Brave: "<technology> benchmarks <year>"
2. WebFetch: wyniki/metodologia benchmarków
3. Context7: przewodniki optymalizacji
4. Decyzja: z twardymi liczbami

## Antywzorce

- Research bez konkretnych pytań (nieukierunkowane przeglądanie)
- Ufanie pojedynczemu źródłu w krytycznych decyzjach
- Nieodnotowywanie źródeł (findingi stają się nieweryfikowalne)
- Spędzanie >30 min na jednym pytaniu (eskaluj albo zaakceptuj niepewność)
- Research bez kontekstu z Examine (zadawanie złych pytań)
```
