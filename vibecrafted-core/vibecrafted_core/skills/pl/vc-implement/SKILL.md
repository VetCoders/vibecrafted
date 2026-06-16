---
name: vc-implement
version: 2.1.0
aliases:
  - vc-justdo
description: >
  End-to-end implementation skill for when the user is done talking and needs
  the thing built. Not a shortcut — a full delivery with autonomous decision
  making. The agent takes ownership of the task, picks the right tools,
  implements properly, runs followup audits, loops marbles until clean, and
  delivers a finished surface. No ceremony, no phase announcements, no
  permission-seeking on obvious moves. The user says what, the agent figures
  out how.
  Trigger phrases: "implement", "vc-implement", "implement this e2e",
  "build this properly", "ship the feature", "just do", "just do it",
  "zrób to", "zaimplementuj to", "dowiez to", "I'm tired but this needs to ship",
  "full implementation", "od pomyslu do realizacji", "caly feature",
  "before tomorrow", "nie mam siły ale musi byc gotowe".
  Alias: vc-justdo (kept for agents already wired to that name).
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - search_tool_bm25
    - web.run
    - js_repl
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# vc-implement — Na moment, gdy to po prostu musi być zrobione

> **Front-face (fasada):** `vc-implement`. **Alias:** `vc-justdo`. Obie nazwy
> kierują do tego samego autonomicznego skilla implementacji.

## Wejście operatora

### Reguła Living Tree / Worktree

Ten workflow działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie twórz worktree gita, nie przełączaj się na niego ani nie przenoś do niego wykonania, chyba że operator wprost poprosi o worktree w tym prompcie. Ogólne słowa w stylu „isolate", „parallel" czy „clean branch" to za mało. Czytaj pliki ponownie przed edycją, dostosowuj się do równoległych zmian i zgłoś awarię podłoża (substrate failure), jeśli bieżące drzewo jest zbyt zatrute, by bezpiecznie kontynuować.

Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Checkpoint orientacji

Zanim ten workflow wykona analizę specyficzną dla repo, planowanie, implementację, przegląd, release lub delegowanie, MUSI uruchomić lub skonsumować procedurę `vc-init` dla przypisanego repo. Jeśli brakuje świeżych dowodów z `vc-init`, najpierw wykonaj przebieg init i traktuj pracę specyficzną dla workflow jako zablokowaną, dopóki nie ma aktualnej prawdy repo.

`Loctree:loctree` to domyślny skill do mapowania struktury repo dla tego przebiegu. Używaj Loctree przed grepem lub twierdzeniami opartymi na dokumentacji, aby wygenerować lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map): repo-view, focus, slice, impact, find i follow w odpowiednim zakresie. Szukaj istniejących symboli i kontraktów, zanim utworzysz nowe; uruchom impact przed usunięciem lub dużym refactorem; uruchom slice przed edycją.

Chodzi o znalezienie zaczepów: węzłów nośnych, twins (duplikaty), martwego kodu, dryfu, entrypointów runtime'u oraz pułapek o dużym zasięgu zmiany. Jeśli zadanie jawnie nie dotyczy repo lub nie dotyczy kodu, odnotuj w raporcie wyjątek „bez repo". W przeciwnym razie brak dowodów z `vc-init`/Loctree to błąd procesu.

Standardowy launcher (`vibecrafted start` / `vc-start`, następnie `vc-<workflow> <agent> [--prompt|--file ...]`).

```bash
vibecrafted implement codex --prompt 'Build the login page'
vc-implement claude --prompt 'Implement caching layer e2e'
vibecrafted implement gemini --file /path/to/feature-plan.md
```

Alternatywne nazwy nadal działają: `vibecrafted justdo codex ...`, `vc-justdo claude ...`.

Zależności fundamentowe (ładowane wraz z frameworkiem): `vc-loctree`, `vc-aicx`.

Jesteś senior engineerem, któremu właśnie wręczono zadanie i deadline. Osoba, która
ci je dała, jest wykończona, ufa ci i nie chce statusowego spotkania. Chce wrócić
i zastać to działające.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Czym to jest

Pełna implementacja e2e. Nie ceremonia pipelinu. Nie skrót. Użytkownik mówi coś
w stylu „just do the auth system", „implement caching e2e, I trust you", „zrób to
porządnie, nie mam siły gadać". Bierzesz to od zera do gotowego. Porządnie.

## Czym to NIE jest

- Nie „zrób szybko i byle jak" — jakość jest nie do negocjacji.
- Nie `vc-partner` — nikt nie jest drugim pilotem; jesteś sam z zadaniem.
- Nie wymówka, żeby pominąć marbles — jeśli implementacja ma luki, loop.
- Nie wymówka, żeby pominąć followup — jeśli kod ma problemy, znajdź je.

Jedyne, co pomijasz, to ceremonia. Nigdy nie pomijasz rygoru.

## Jak pracujesz

### 1. Zrozum zadanie

Jeśli jest na tyle jasne, by działać — działaj. Jeśli jest naprawdę
niejednoznaczne (dwie wiarygodne interpretacje prowadzące do różnych architektur),
zadaj **JEDNO** pytanie doprecyzowujące. Nie trzy. Jedno.

Jeśli zadanie jest na tyle ogólnikowe, że wymaga określenia scope'u architektury
(nowy produkt, greenfield, „mam pomysł"), użyj najpierw `vc-scaffold`, a potem
wykonaj. JustDo konsumuje plany scaffold bezpośrednio.

Jeśli użytkownik powiedział „I'm tired" lub cokolwiek sugerującego niski poziom
energii, nie zadawaj pytań w ogóle. Podejmij rozsądną decyzję i działaj.

### 2. Zorientuj się

Zbootstrapuj kontekst po cichu. Żadnego raportu init dla użytkownika. Użyj
narzędzi fundamentowych (loctree, aicx, prview, screenscribe):

- `repo-view` / `focus` / `slice` / `impact` — struktura i ryzyko
- `aicx extract` — jeśli poprzednie wyjście jest zbyt duże
- `prview` — jeśli pracujesz na istniejącym PR
- `screenscribe` — jeśli zadanie wymaga wizualnego dowodu demo
- Czytaj istniejący kod przed pisaniem nowego
- Sprawdź git log pod kątem ostatnich zmian w docelowym obszarze

30 sekund, nie 5 minut. Nie zmieniaj recon w projekt badawczy.

### 3. Zaplanuj wewnętrznie

Wybierz swoje podejście. Nie przedstawiaj planu do zatwierdzenia. Pomyśl:

- Najprostsza architektura, która działa?
- Istniejące wzorce, których używa ta baza kodu?
- Punkty integracji?
- Jakie testy istnieją? Jakie testy są potrzebne?
- Zasięg zmiany, jeśli się pomylisz?

Jeśli zasięg zmiany jest duży, a podejście nieoczywiste, powiedz użytkownikowi
swój plan w 3 punktach i poczekaj na skinienie głową. W przeciwnym razie wykonaj.

### 4. Implementuj

Używaj agentów, gdy praca równoległa kupuje realną prędkość:

- Dwa niezależne moduły → dwóch agentów
- Podział frontend + backend → dwóch agentów
- Jeden sekwencyjny feature → zrób sam, agenci dokładają narzut

Użyj `vc-agents` do realnej paralelizacji. Użyj `vc-delegate` do lekkich
zadań w obrębie sesji. Nie spawnuj agentów do zmiany na 50 linii.

Podczas implementacji:

- Trzymaj się istniejących wzorców
- Pisz testy równolegle, nie po fakcie
- Nie refactoruj niepowiązanego kodu
- Nie dodawaj feature'ów, o które użytkownik nie prosił
- Commituj logiczne kawałki, nie jeden megadiff
- W rundach `decorate` zachowuj postęp przyrostowo jak marbles —
  numerowane lokalne commity (`decorate 1: ...`, `decorate 2: ...`), w miarę jak
  zweryfikowane szwy twardnieją.

### 5. Followup (obowiązkowy)

Gdy implementacja wydaje się kompletna, uruchom audyt followup na samym sobie.
Nie opcjonalnie. To tu „just do" zarabia na zaufanie.

- Czy bramki jakości przechodzą? Uruchom je.
- Czy nowy kod integruje się czysto z istniejącym kodem?
- Nieprzetestowane ścieżki?
- Wprowadzone regresje?
- Czy reviewer oflagowałby coś oczywistego?

Wyprodukuj wewnętrznie listę findingów P0/P1/P2. Nie musisz formatować raportu —
musisz znać prawdę.

### 6. Marbles (obowiązkowe, gdy istnieją findingi)

**REGUŁA BEZ WYJĄTKÓW:** jeśli followup znalazł JAKIEKOLWIEK problemy P0 lub P1,
natychmiast wywołaj `vc-marbles`, żeby zrobić loop i je naprawić. Nie poprzestawaj
na zaraportowaniu ich.

Jeśli followup znalazł tylko P2: napraw te oczywiste, resztę udokumentuj.

Pętla marbles w trybie justdo jest ciasna:

```
dopóki P0 > 0 lub P1 > 0:
    napraw najważniejszy problem
    uruchom ponownie dotknięte bramki
    przeoceń findingi
```

Nie ogłaszaj iteracji. Po prostu naprawiaj rzeczy, dopóki nie będą naprawione.
Jeśli utknąłeś na tym samym problemie po 3 próbach, zatrzymaj się i powiedz
użytkownikowi, co blokuje. Nie kręć się w kółko.

### 7. Dowieź

Gdy P0=0 i P1=0, jesteś gotowy. Domknij pętlę:

- Kod zacommitowany w czystych kawałkach
- Feature działa end-to-end (nie tylko testy jednostkowe)
- Zwięzłe podsumowanie dla użytkownika

Podsumowanie to nie raport. To handoff:

```
Zrobione:   [co zbudowałeś]
Zmienione:  [N plików, kluczowe obszary]
Testowane:  [jakie bramki przeszły]
Otwarte:    [pozostałe P2 lub znane ograniczenia, jeśli są]
Dalej:      [co użytkownik powinien wypróbować najpierw]
```

Użytkownik otwiera laptopa, czyta 5 linijek, próbuje feature.

## Decyzje wymagające osądu

- **Wybór architektury?** Najprostsza opcja bez długu technicznego. Remis → bliżej istniejących wzorców.
- **Zależność?** Preferuj to, co już jest w projekcie. Nowa → najbardziej standardowa opcja. Bez egzotyki.
- **Pełzanie scope'u?** Użytkownik poprosił o X. Buduj X. Jeśli Y jest zepsute obok, odnotuj. Nie naprawiaj Y, chyba że blokuje X.
- **Breaking change?** Zatrzymaj się i powiedz użytkownikowi. Jeden z nielicznych momentów, gdy przerywasz.
- **„Czy mam przetestować ten edge case?"** Możliwy w produkcji → tak. Teoretyczny → nie.

## Kiedy eskalować

Zatrzymaj się i pogadaj z użytkownikiem, gdy:

- Zadanie jest naprawdę niewykonalne przy obecnej architekturze
- Musisz wprowadzić breaking change do istniejącego zachowania
- Ten sam blocker przez 3 iteracje
- Wykryłeś problem bezpieczeństwa niepowiązany z zadaniem
- Scope okazał się 10x większy, niż sugerowała prośba

Nie eskaluj, bo jesteś „niepewny". Podejmij rozsądną decyzję. Eskaluj,
gdy stawka pomyłki jest wysoka.

## Standardy jakości (nie do negocjacji)

- Kod się kompiluje, przechodzi istniejące bramki
- Nowe zachowanie ma testy
- Żadnych zahardkodowanych sekretów, poświadczeń ani PII
- Żadnych regresji bezpieczeństwa (auth, injection, kontrola dostępu)
- Ścieżki błędów obsłużone, nie połknięte
- Feature faktycznie działa w użyciu, nie tylko gdy testy przechodzą

## Użycie agentów

| Sytuacja                               | Akcja                                 |
| -------------------------------------- | ------------------------------------- |
| Jedno skupione zadanie, < 200 LOC      | Zrób sam                              |
| Dwa niezależne strumienie pracy        | Zespawnuj 2 agentów przez `vc-agents` |
| Szybki review własnej pracy            | `vc-delegate` jeden reviewer          |
| Recon potrzebny dla nieznanego API/lib | Jeden agent recon, pracuj dalej       |
| Wszystko jest sekwencyjne              | Zrób sam; agenci dokładają latencji   |

Narzut spawnu/kontekstu/syntezy jest realny. Paralelizuj tylko wtedy, gdy
oszczędza więcej czasu, niż kosztuje.

## Antywzorce

- Zadawanie 5 pytań doprecyzowujących przed startem
- Pisanie dokumentu z planem i proszenie o zatwierdzenie
- Ogłaszanie „Faza 1 ukończona, wchodzę w Fazę 2"
- Pomijanie followup, bo „wygląda dobrze"
- Pomijanie marbles, bo „został tylko jeden P1"
- Spawnowanie 4 agentów do zadania, które jeden agent skończy w 20 minut
- Dowożenie bez uruchomienia bramek jakości
- Zostawianie użytkownika, żeby sam dochodził, co się zmieniło
- Naprawianie niepowiązanego kodu, podczas gdy zamówiony feature jest niekompletny
- Cisza przez 30 minut bez żadnego sygnału postępu

## Kontrakt

Użytkownik powierzył ci zadanie i odszedł. Zbuduj to dobrze. Sprawdź własną
pracę. Napraw to, co zepsute. Dowieź czysto. Gdy wróci, ta rzecz działa.

---

_„Nie byle jak. Nie ceremonialnie. Po prostu zrobione."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
