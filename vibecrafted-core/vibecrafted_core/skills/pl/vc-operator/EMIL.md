# vc-operator — Przewodnik stylu kształtu planu

> Sygnaturowy kształt planu operatora. Każdy plan, każde ciało dispatchu, każdy tracker, każdy wpis do backlogu w trybie operatora trzyma się tego stylu.  
> Deklaracja operatora (2026-05-16): _„Let's establish my rule that plans ALWAYS go from [ ] → [x]"_.

Czytaj razem z: SKILL.md, DISPATCH.md, GUIDE.md, AUTONOMY.md.

---

## Streszczenie wykonawcze

Ten przewodnik definiuje jeden domyślny kształt dla planów i dispatchów operatora:

- Checkboxy w Markdownie w smaku GitHub wyłącznie dla pozycji pracy.
- Numerowane sekcje najwyższego poziomu ze spójną strukturą faz.
- Zdecydowany, ciepły głos operatora (klimat founder-at-9pm).
- Opcjonalna, przyjazna skanowaniu preambuła `[signals]` dla długich planów.
- Jasne framingowanie „gotowe do wklejenia" dla agentów wykonawczych.

---

## 1) Sygnatura w jednym pudełku

- [ ] Oczekująca pozycja pracy
- [x] Ukończona pozycja pracy

Checkboxy w Markdownie w smaku GitHub. Żadnego statusu prozą, żadnego numerowanego TODO, żadnych sufiksów „(done)".  
Operator skanuje za binarnym [ ] / [x]; cokolwiek innego spala czas skanowania.

---

## 2) Pięć reguł

### Reguła 1 — Checkboxy

Każdy plan, każde ciało dispatchu, każdy tracker fali, każdy handoff w punkcie stopu, każdy wpis do backlogu planu-naprzód.  
Jeśli to lista pozycji pracy, to lista checkboxów.

#### Akceptacja (przykład)

- [ ] Pisanie w canvasie aktualizuje sygnał bufora providera.
- [ ] Zmiany zaznaczenia propagują się do sygnałów selectionStart/End.
- [ ] Cmd/Ctrl+Z cofa edycje debounce'owane 150ms; Shift+Cmd/Ctrl+Z ponawia.
- [ ] Ring buffer ogranicza się do 200 kroków; wcześniejsze kroki cicho odrzucane.
- [ ] Istniejące testy pozostają zielone.
- [ ] Nowe testy pokrywają przepływ pisania, propagację zaznaczenia, podpięcie undo/redo.

#### Przykład trackera fali

Wave B (sequential, shared canvas/provider)

- [x] B-1 editor-core — 304791be on feat/textforge-editor-core
- [x] B-2 tool-rail — ba60ef66 on feat/textforge-tool-rail
- [x] B-3 stylize — ab32a848 on feat/textforge-stylize
- [ ] B-4 inspectors — firing now, await bc2zb970r

---

### Reguła 2 — Numerowane sekcje najwyższego poziomu

Plany zaczynają się od `## Executive Summary`, po którym następują numerowane nagłówki.  
Sam plan nie składa się z dowolnej prozy.

Szablon:

#### 1) Main Goal (1:1)

[Jeden akapit — co plan dowozi]

#### 2) Initial Context

[Bullety wskazujące na istotny stan repo, wcześniejsze commity, ciągłość]

#### 3) Actionable TODO (Checklist — Execute Sequentially)

[Fazowana checklista — zobacz Regułę 3]

(1:1) to pieczęć — używana, gdy plan zachowuje intencję źródłową verbatim. Usuń ją, jeśli zredagowałeś.

---

### Reguła 3 — Pod-nagłówki na fazę

Wewnątrz numerowanej sekcji TODO używaj pod-nagłówków poziomu czwartego (`####`) do oznaczania przejść między fazami. Cztery domyślne fazy:

- Examine the Code — zwiad przed edycją (Loctree, slice, impact, find)
- Implement Changes — właściwe edycje
- Verify Integrity (format, lint) — lokalne bramki
- Tests (Add If Missing) — testy + smoke

Każdy pod-nagłówek dostaje własny klaster checkboxów. Workerzy skanują pionowo przez fazy — powinni zobaczyć granicę fazy, a nie ją wywnioskować.

---

### Reguła 4 — Konwersacyjny głos operatora

Zdecydowany, ale ciepły. Jak founder piszący na czacie o 21, a nie jak korporacyjny ticket.

Przykłady:

> „Don't guess: if something is not visible in code, find and confirm in the repo first."

> „Work iteratively: implement minimally but correctly; don't lose the sense of the existing runner."

> „Paste the following prompt into the execution agent. This is a ready prompt."

Czym to nie jest:

- Nie korporacyjne („The following deliverables are required:")
- Nie tylko-bulletowe (niektóre linie to pełne zdania — pozwól głosowi wybrzmieć)
- Nie akademickie („It would be beneficial to consider...")
- Nie przesycone wykrzyknikami (bez hype'u)

Głos jest własnym głosem operatora.

---

### Reguła 5 — Minimalne markery ekspresyjne

Lekkie markery ekspresyjne (kaomoji lub podobne) mogą być używane oszczędnie w wyjściach statusowych, ale nigdy w ciałach promptów dispatchu.  
Używane wyłącznie do zaakcentowania tonu emocjonalnego. Unikaj ciężkiego lub niewłaściwego użycia.

---

## 3) Blok [signals] (opcjonalny, ale rekomendowany)

Długie plany (>20 pozycji checklisty) otwierają się blokiem `[signals]`, który auto-streszcza stan skanowania.

Przykład:

    [signals]
    RED LIGHT: checklist detected (open: 17, done: 0)
    - [ ] (first 4 unchecked items pulled forward)
    - [ ] ...
    Results (when partial done):
    - [x] (first 2 checked items pulled forward — proof of progress)
    [/signals]

Dla planów poniżej 20 pozycji pomiń `[signals]` — dodaje szum.

---

## 4) Framing „READY TO COPY-PASTE"

Każde ciało promptu dispatchu otwiera się framingiem sygnalizującym: gotowe do wklejenia verbatim do CLI innego agenta:

    Paste the following prompt into the execution agent. This is a ready prompt. Do not ask the user for missing details — take initiative, examine the repo, and propose specific changes. Preserve the 1:1 intent from the brief above.

PROMPT FOR AGENT (For Copy-Paste)

1. Task Description  
   [...]

---

## 5) Pieczęć (1:1)

Gdy plan jest wyprowadzony z głosu źródłowego lub notatek bez redagowania, oznacz sekcje pieczęcią (1:1).

Przykład:

#### 1) Main Goal (1:1)

Unify the storage location for all artifacts into a single folder: .aiContext/. Implement it consistent with the current logic in runner.sh. Separate "models" from "agents".

Zrzuć pieczęć, gdy dodałeś wnioskowanie, zawężenie lub rozszerzenie.

---

## 6) Antywzorce

- Status prozą zamiast checkboxów
- Numerowane TODO zamiast checkboxów
- Mieszanie checkboxów z numerowaną prozą
- Ciężkie lub niewłaściwe markery ekspresyjne
- Korporacyjny głos
- Pieczęć (1:1) na zsyntetyzowanej treści
- Pomijanie [signals] w planie na 30 pozycji

---

## 7) Przykładowy szkielet (gotowy do wklejenia)

    [signals]
    RED LIGHT: checklist detected (open: 12, done: 0)
    - [ ] [first 3–4 most important pending items pulled forward]
    [/signals]

    ## Executive Summary
    [1–3 sentences: what this plan does and why now.]

    ## 1) Main Goal (1:1)
    [Source intent in one paragraph.]

    ## 2) Initial Context
    - Repo state: [current branch, SHA, last known landings]
    - Continuity: [which prior session authored this plan; which agent]
    - Reusable surfaces: [files / contracts to plug into]

    ## 3) Actionable TODO (Checklist — Execute Sequentially)

    #### Examine the Code
    - [ ] [loctree slice / find / impact directive 1]
    - [ ] [recon directive 2]

    #### Implement Changes
    - [ ] [edit / create directive 1]
    - [ ] [edit / create directive 2]

    #### Verify Integrity (format, lint)
    - [ ] Run [project-specific gate command]
    - [ ] [format / lint commands]

    #### Tests (Add If Missing)
    - [ ] [test directive 1]
    - [ ] [test directive 2]

    ## 4) Acceptance
    - [ ] [observable outcome 1]
    - [ ] [observable outcome 2]
    - [ ] All existing tests stay green.

    ## 5) Out of Scope
    - [things explicitly NOT touched in this prompt]

    ## 6) Branch + Commit + Report
    - Branch: feat/<slug> off <parent-sha>
    - Commit title: [<agent>/<workflow>] <imperative description>
    - Report: ~/artifacts/<...>/reports/<prompt-id>_<ts>_<agent>.md

    Paste the above prompt into the execution agent. This is a ready prompt. Do not ask — take initiative, examine the repo, and propose specific changes.

---

Plan [ ] → [x], numerowany, z głosem, opieczętowany (1:1).

Vibecrafted. with AI Agents (c)2024–2026
