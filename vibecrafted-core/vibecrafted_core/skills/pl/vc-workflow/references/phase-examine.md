# Faza 1: EXAMINE — głęboka analiza Loctree

## Cel

Zbuduj kompletne zrozumienie strukturalne, zanim zmienisz cokolwiek w kodzie.
Wyjście zasila bezpośrednio pytania researchu i plany implementacji.

## Workflow analizy

### Krok 1: Globalna mapa

Uruchom `repo-view(project)`, aby uchwycić:

- Łączną liczbę plików i LOC
- Rozbicie na języki
- Wskaźniki zdrowia (martwe eksporty, cykle, twins, hotspoty)
- Najważniejsze pliki-huby (najwyższa liczba importerów)

Odnotuj sygnały zdrowia — staną się później celami `follow()`.

### Krok 2: Ograniczenie zakresu

Dla każdego docelowego modułu (max 3 katalogi):

- Uruchom `focus(directory)`, aby zobaczyć strukturę wewnętrzną
- Odnotuj: liczbę plików, LOC na plik, krawędzie wewnętrzne, zależności zewnętrzne
- Zidentyfikuj, które pliki to entrypointy, a które wewnętrzne helpery

Heurystyka decyzyjna:

- Jeśli moduł ma <10 plików → przeanalizuj wszystkie
- Jeśli moduł ma 10-30 plików → skup się na hubach + plikach pasujących do słów kluczowych taska
- Jeśli moduł ma >30 plików → skup się tylko na hubach, rozszerzaj wedle potrzeby

### Krok 3: Kontekst na poziomie pliku

Dla każdego pliku, który prawdopodobnie się zmieni:

- Uruchom `slice(file, consumers=true)`, aby dostać:
  - Bezpośrednie zależności (co ten plik importuje)
  - Bezpośrednich konsumentów (co importuje ten plik)
  - Tranzytywną ocenę ryzyka
- Odnotuj zależności i konsumentów w CONTEXT.md

### Krok 4: Ocena ryzyka

Dla plików o wysokim stopniu huba (>5 konsumentów) i kandydatów do usunięcia:

- Uruchom `impact(file)`, aby dostać pełny zasięg zmiany
- Bezpośredni konsumenci: pliki, które popsują się natychmiast
- Tranzytywni konsumenci: pliki dotknięte przez łańcuch zależności
- Jeśli impact jest wysoki → zaplanuj strategię izolacji (adapter, nowy wariant, moduł o ograniczonym zakresie)

### Krok 5: Weryfikacja symboli

Zanim zaproponujesz jakiekolwiek nowe typy, funkcje lub stałe:

- Uruchom `find(name)` ze wsparciem regex: `find("NewType|new_function")`
- Sprawdź istniejące wzorce do ponownego użycia
- Sprawdź konflikty nazw

### Krok 6: Pogoń za sygnałem

Jeśli repo-view oznaczył problemy (martwe eksporty, cykle, twins, hotspoty):

- Uruchom `follow(scope)` dla odpowiednich zakresów
- Martwe eksporty → kandydaci do sprzątnięcia podczas refaktoru
- Cykle → ograniczenia kolejności zależności
- Twins → potencjalne okazje do deduplikacji
- Hotspoty → pliki, które zmieniają się często (potrzebują wyższego pokrycia testami)

## Format wyjścia CONTEXT.md

```markdown
# Examination: <slug>

Date: <YYYY-MM-DD>
Pipeline: .vibecrafted/pipeline/<slug>/

## Repo Health

- Files: N | LOC: N | Languages: Rust, Swift, ...
- Dead exports: N flagged
- Cycles: N detected
- Health score: good/warning/critical

## Task Understanding

- User request: <original request>
- Interpreted scope: <what needs to change>

## Target Modules

### <module-1>

- Path: <dir>
- Files: N | LOC: N
- Entry points: <files>
- External consumers: <count>

## Critical Files (slice results)

| File            | LOC | Dependencies | Consumers | Risk |
| --------------- | --- | ------------ | --------- | ---- |
| path/to/file.rs | 450 | 3            | 12        | HIGH |

## Existing Symbols

- `TypeA` — defined in path/file.rs:42 (14 consumers)
- `fn helper_b` — defined in path/other.rs:100 (used by 3 files)

## Risk Map

| File         | Blast Radius  | Mitigation            |
| ------------ | ------------- | --------------------- |
| contracts.rs | 24 transitive | Additive changes only |

## Open Questions (for Research phase)

1. <question about unknown API/pattern>
2. <question about best approach>

## Phase Decision

- [ ] Research needed — unknown: <what>
- [ ] Skip to Implement — well-understood domain
```

## Typowe wzorce analizy

### Nowa funkcja

Skup się na: gdzie funkcja się integruje, istniejące wzorce do naśladowania, dotknięte pliki-huby.
Kluczowe narzędzia: `repo-view` → `focus` (docelowy moduł) → `slice` (punkty integracji) → `find` (podobne funkcje).

### Naprawa buga

Skup się na: ścieżka reprodukcji, dotknięta ścieżka kodu, pokrycie testami.
Kluczowe narzędzia: `slice` (buggy plik) → `impact` (zakres fixa) → `find` (powiązane symbole).

### Refaktor

Skup się na: pełny zasięg zmiany, kolejność zależności, ścieżka migracji.
Kluczowe narzędzia: `repo-view` → `focus` → `impact` (każdy plik do dotknięcia) → `follow(cycles)`.

### Integracja

Skup się na: pliki graniczne, wzorce adapterów, konfiguracja.
Kluczowe narzędzia: `repo-view` → `focus` (moduł graniczny) → `slice` (pliki adapterów) → `find` (istniejące adaptery).

## Fallback (loctree niedostępne)

Jeśli loctree MCP nie jest dostępne:

1. `rg --files | head -50` dla przeglądu plików
2. `rg -l "pattern"` dla odkrycia konsumentów
3. `rg "use |mod |pub " file.rs` dla śledzenia zależności
4. Ręczna ocena impactu przez grep

Raportuj: „Loctree unavailable — using grep fallback. Structural coverage: reduced."
