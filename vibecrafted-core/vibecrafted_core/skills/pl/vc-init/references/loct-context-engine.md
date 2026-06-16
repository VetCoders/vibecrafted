# Silnik `loct context` — pełna referencja

Towarzyszy Zmysłowi 2 z `SKILL.md`. Treść skilla trzyma kontrakt i
wywołanie główne; ten plik zawiera pełne tabele odnośników, mapę parametrów oraz
odruchy operacyjne.

## Anatomia atlasu — sześć kart plus receipt

| #   | Karta                      | Czytaj po                                                                              | Kiedy wymagane                                   |
| --- | -------------------------- | -------------------------------------------------------------------------------------- | ------------------------------------------------ |
| 0   | `00-core-map.md`           | tożsamość repo, bieżące ryzyko, etykiety autorytetu, bezpieczne kolejne komendy        | **zawsze**                                       |
| 1   | `01-structural-map.md`     | pliki, symbole, importy, konsumenci, entrypointy                                       | **zawsze** (puste bez zakresu — przekaż `file:`) |
| 2   | `02-runtime-map.md`        | tagi idiomów, osiągalność, podpowiedzi frameworka, kontrakty env, krawędzie dyspozycji | **zawsze** (puste bez zakresu — przekaż `file:`) |
| 3   | `03-memory-trail.md`       | ciągłość AICX: wyniki, taski, intencje operatora                                       | przy wznawianiu lub w Żywym Drzewie              |
| 4   | `04-verification-gates.md` | likely_tests, komendy weryfikacyjne, kolejne bezpieczne wywołania loct                 | przed edycjami / pre-commit                      |
| 5   | `05-risk-register.md`      | hotspots, fan-in, cache_scope, snapshot_health, dirty_worktree                         | przed release'em / chirurgią strukturalną        |
| ·   | `receipt`                  | proweniencja skanu, fingerprint snapshotu, `git_commit`, znacznik czasu skanu          | Żywe Drzewo: wykryj współbieżne reskany          |

Odpowiedź na poziomie repo jest **niekompletna**, dopóki nie odczytano kart 0, 1, 2.
Ścieżka cache'u atlasu: `~/Library/Caches/loctree/projects/<hash>/<branch>@<commit>/context-atlas/`.

## Parametry `context()` — zakres, higiena, format

| Param                | Kiedy używać                                                                                        |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| _(brak)_             | Orientacja przy bootstrapie. Karty strukturalna/runtime są celowo puste.                            |
| `file: "<path>"`     | Przed dotknięciem pliku: wypełnia strukturalną celem + deps + konsumentami + symbolami.             |
| `task: "<text>"`     | Trafność przez nakładanie się tokenów — wciąga pliki powiązane semantycznie spoza grafu zależności. |
| `changed: true`      | Filtr WIP Żywego Drzewa — ogranicza do plików zmienionych w gicie.                                  |
| `no_aicx: true`      | Sesje offline / wrażliwe; zrzuca nakładkę pamięci AICX.                                             |
| `no_scan: true`      | Tryb CI — kończy się błędem, jeśli brak snapshotu, zamiast auto-skanować.                           |
| `fail_stale: true`   | Bramka CI — kończy się błędem, jeśli snapshot zdryfował od bieżącego commita.                       |
| `fresh: true`        | Wymuś reskan (po głębokich edycjach strukturalnych lub przełączeniu gałęzi).                        |
| `format: "markdown"` | Markdown pill w stylu operatora; domyślnie `"json"` dla agentów strukturalnych.                     |
| `force_no_git: true` | Omiń strażnika wykrywania repo (rzadkie — staged checkouty, wygenerowane drzewa).                   |

## Etykiety autorytetu (zawsze sprawdź przed działaniem)

| Etykieta           | Zaufanie                                                                    |
| ------------------ | --------------------------------------------------------------------------- |
| `repo_verified`    | Twardy fakt ze snapshotu. Najwyższe zaufanie.                               |
| `loctree_derived`  | Wywnioskowane przez analizator (liczby importerów, dead/cycle itp.). Mocne. |
| `aicx_operator`    | Z intencji operatora w poprzednich sesjach. Traktuj jak trwałą preferencję. |
| `aicx_agent`       | Z wyników poprzednich agentów (inni agenci, to repo, niedawne).             |
| `aicx_failure`     | Poprzednia nieudana próba — czytaj uważnie, nie powtarzaj ścieżki.          |
| `semantic_guess`   | Heurystyka. Zweryfikuj przed działaniem.                                    |
| `stale_or_unknown` | Sprawdź ponownie stan repo; nie ufaj jako-jest.                             |

## Pod-narzędzia atlasu (drill-down bez ponownego pobierania całego świata)

- `context_manifest(project, with_aicx)` — wylistuj dostępne sekcje (w tym
  `receipt`) z rozmiarami + kursorem.
- `context_section(project, section)` — bezpośrednie pobranie `core` / `structural` /
  `runtime` / `memory` / `receipt`.
- `context_next(cursor)` — stronicowane pobieranie chunków po wywołaniu początkowym.

## Narzędzia drill-down (po atlasie, gdy zakres jest znany)

| Narzędzie             | Warunek wyzwolenia                                                |
| --------------------- | ----------------------------------------------------------------- |
| `slice(file)`         | Zaraz zmodyfikujesz ten konkretny plik.                           |
| `impact(file)`        | Zaraz usuniesz lub zmienisz nazwę tego pliku.                     |
| `find(pattern)`       | Trzeba zlokalizować symbol — **nigdy najpierw grep**.             |
| `follow(scope)`       | Podążanie za `dead` / `cycles` / `twins` / `hotspots` / `trace`.  |
| `focus(directory)`    | Pogłębiona analiza na poziomie modułu po orientacji.              |
| `query(kind, target)` | Zapytania grafowe: `who-imports`, `where-symbol`, `component-of`. |

## Narzędzia analizy (sygnał, nie orientacja)

| Narzędzie     | Kiedy używać                                                       |
| ------------- | ------------------------------------------------------------------ |
| `health()`    | Szybki sweep poprawności (cycles + dead + twins) na starcie sesji. |
| `findings()`  | Pełny JSON issues do triage'u / przed release'em.                  |
| `audit()`     | Kompleksowy przebieg audytu (bramka CI, konwergencja vc-marbles).  |
| `doctor()`    | Tożsamość cache'u + fingerprint snapshotu + status dryfu.          |
| `coverage()`  | Luki w pokryciu testami (strukturalne).                            |
| `manifests()` | Podsumowania `package.json` / `Cargo.toml`.                        |
| `dist()`      | Weryfikacja tree-shakingu z source mapów.                          |
| `insights()`  | Podsumowanie wglądów AI.                                           |

## Odruch przed edycją w Żywym Drzewie

Przed każdym oknem edycji dłuższym niż kilka minut wywołaj `doctor()` (lub odczytaj
`fingerprint` z `repo-view`), aby wykryć współbieżny reskan od innego
agenta. Jeśli fingerprint przesunął się od twojego ostatniego wywołania, ponów
`context(fresh: true)` przed kontynuacją. Pomijanie tego we współdzielonych
katalogach to sposób, w jaki koordynacja wieloagentowa cicho się sypie.

## CLI jako powierzchnia operatora (nie fallback agenta)

`loct context`, `loct slice`, `loct find`, `loct doctor` itp. istnieją dla
bezpośredniej inspekcji operatora — markdown pill (`--markdown`), interaktywny
debugging, shell pipes (`loct findings | jq ...`). Obie powierzchnie współdzielą
ten sam silnik i ten sam cache atlasu; różnią się ergonomią, nie
możliwościami. Agenci **nie** używają CLI jako fallbacku z parytetem dla MCP. Jedyny
wyjątek: gdy operator poda ci literalną komendę CLI w
prompcie („run `loct doctor` and report"), wykonaj zgodnie z instrukcją —
operator celowo korzysta z powierzchni interaktywnej.
