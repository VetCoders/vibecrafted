---
name: vc-marbles
version: 7.0.0
description: >
  WRITE step that floods every crack with deliberate over-correction.
  Single workers see one round, one truth-forcing cut, one commit;
  the skill at swarm level produces an intentional excess of fixes —
  marbles in every hole — which `vc-polarize` then strips back to one
  axis. Use when implementation already exists but the codebase still
  lies: overgenerated surfaces, drift between runtime paths, false
  certainty from one-shot agent output, or a product that "works"
  while remaining fragile. Each worker invocation is isolated and
  blind to prior marble history. Trigger phrases: "marbles", "kulki",
  "stabilize", "stabilizacja", "loop until done", "reduce chaos",
  "fortify the foundation", "adultification", "rzuć kulki",
  "wypełnij pęknięcia".
default: vc-marbles
aliases:
  - vc-fortify
compatibility:
  tools:
    - Skill
    - TaskCreate
    - TaskUpdate
    - Bash
    - Read
    - Write
    - Edit
requires:
  - vc-init
  - loctree
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v3 -->

> **Wywołanie dla `vc-marbles` (launcher `marbles`)**
>
> Ten sam _kształt_ trzech ścieżek floty, z **literałami tego** skilla — zobacz
> kanoniczną [Matrycę Delegacji](../DELEGATION_MATRIX.md):
>
> - [Wspólne trzy ścieżki](../DELEGATION_MATRIX.md#wspólne-trzy-ścieżki)
> - [Katalog launcherów](../DELEGATION_MATRIX.md#katalog-launcherów-core-runtime)
> - [Reguła per-launcher](../DELEGATION_MATRIX.md#reguła-per-launcher-delta-semantyczna)
> - [Native vs external](../DELEGATION_MATRIX.md#natywne-subagenty-vs-zewnętrzni-workerzy)
>
> | Ścieżka               | Literał tego skilla                                                                                                            |
> | --------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
> | 1. Worker użytkownika | `vibecrafted marbles <agent>`                                                                                                  |
> | 2. Interactive        | `/vc-marbles` — wykonaj **w tej sesji**; native subagenty gdy trzeba; **nie** zewnętrzniaj tylko dlatego, że launcher istnieje |
> | 3. Agent-operator     | może odpalić formę workera powyżej przez `vc-dispatch` / linie operatora, zachowując tożsamość tego skilla                     |

> Swobodniejszy native na niektórych biegach ≠ porzucenie floty external. `vc-dispatch` i `vc-ship` zachowują własne tożsamości.

<!-- /fleet-imperative -->

# vc-marbles — Deliberate Excess (Worker-Blind, Swarm-Wide)

> Krok `WRITE` w samym centrum pipeline'u. Tam gdzie `vc-followup` mówi
> **„falsyfikuj twierdzenie ze speca, nigdy nie dotykaj kodu"**, a `vc-polarize`
> mówi **„tnij z powrotem do jednej prawdy"**, ten mówi **„worker widzi
> drzewo, nie fabrykę — jedna runda, jedno cięcie wymuszające prawdę, jeden
> raport; swarm produkuje nadmiar, który polarize potem zdziera."**

---

## Wejście operatora

### Reguła Living Tree / Worktree

Działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie przenoś się
do worktree, chyba że wprost o to poproszono. Jedyny usankcjonowany drugi tryb to dispatch Fleet Worktrees (pisany plan, zacommitowane wcześniej verifiery, rozłączne domeny plików, jednowątkowy integrator — patrz Reguła Living Tree, Tryb B); poza tą formacją zostań we wspólnym drzewie. Czytaj pliki ponownie przed
edycją, dostosowuj się do równoległych zmian (inni workerzy mogli zapisać
między twoimi dispatchami). Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Checkpoint orientacji

Każda runda zaczyna się od `vc-init`. Bez wyjątków. Zanim dotkniesz kodu, zbierz aktualny obraz repo
przez dostępne narzędzia: `Loctree:loctree` buduje
Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map — mapa
strukturalna, zależności, martwy kod, hotspoty); **aicx-steer** (intencje
projektu, nie raporty z poprzedniej rundy); **semgrep / lintery** (bieżąca
powierzchnia jakości); **git status / ostatnie commity**. Bez `vc-init` agent
wymyśla własną rzeczywistość.

Standardowy launcher:

```bash
# Single round (3 runs by default):
vibecrafted marbles codex --prompt 'Fix the 3 failing portable tests'
vc-marbles codex --prompt 'Harden the installer shell surface'

# Multiple rounds (convergence loop — runtime spawns fresh agent 3..n times)
vibecrafted marbles codex --count 5 --prompt 'Stabilize until P0=0'
vc-marbles claude --count 8 --prompt 'Refactor the 1500 LOC monoliths'

# From a plan file:
vibecrafted marbles codex --file ~/.vibecrafted/artifacts/vetcoders/vibecrafted/2026_0407/plans/marbles-plan.md
vc-marbles gemini --count 5 --file /path/to/plan.md

# Crawl back into the canonical store then read 'n' recently
# implemented plans then fill the all the gaps:
vibecrafted marbles codex --count 10 --depth n
vc-marbles claude --depth 12 --prompt 'Focus on "vc-followup assumptions from the last 12 plans'
```

**To nie to samo co `vibecrafted implement codex <plan>`.** `implement`
to sposób, w jaki kod powstaje. `marbles` to to, co dzieje się po tym, jak kod
już istnieje, ale wciąż trzeba uczynić go prawdziwym i gotowym do dowiezienia.
Każda runda owija świeżego agenta w gorącą pętlę zbieżności. `--count` steruje
liczbą iteracji pętli zewnętrznej.

---

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Cel

`vc-marbles` to krok COMPLETION, który zamienia naturalnie przegenerowany
output kodowania agentycznego w utwardzony, testowalny fundament. Każdy
pojedynczy worker jest zdyscyplinowany: jedna runda, jeden bounded target,
jeden commit. Ale **swarm** (rój agentów) workerów/rund w obrębie
inicjatywy celowo przesadza z fixami — marbles w każdej rysie, nawet w tych,
których być może nie powinno się wypełniać. Nadmiar jest sednem.
`vc-polarize` później zdziera z powrotem do jednej prawdy.

Marbles **nie** próbuje rozwiązać konceptualnego rozmazu na poziomie
produktu (sprzeczne dokumenty, rozjeżdżające się kierunki produktu).
Eksponuje te decyzje produktowe chowające się za „problemami kodu" i
zostawia je `vc-polarize` do rozstrzygnięcia oraz wyboru finalnego kształtu
o jednej prawdzie.

## Świadomość kosztu: zimny start, gorąca pętla

`vc-marbles` wygląda na drogi tylko wtedy, gdy każdy run agenta liczy się jako
świeże zdarzenie. To zły model rozliczania.

Drogi jest zimny start: czytanie repo, rekonstrukcja intencji, znalezienie
prawdziwej powierzchni awarii i nauczenie się, gdzie system kłamie. Gdy ten
kontekst jest już gorący, powtarzane runy marbles po tej samej bounded
powierzchni to nie marnotrawstwo. To kompresja.

Marbles wykorzystuje rozgrzany cache.

Dobra pętla marbles trzyma podłoże stabilne:

- to samo repozytorium
- ten sam obszar zadania
- te same padające bramki
- ta sama intencja architektoniczna
- ten sam lub porównywalny prompt
- mały dystans czasowy między runami

Dzięki temu każdy nowy worker płaci mniej za archeologię i wydaje więcej
swojego budżetu na delty: przeoczone rysy, fałszywe fixy, kruche założenia
oraz spory między agentami.

Celem nie są tanie runy. Celem są gęstsze runy.

Jedno izolowane wywołanie agenta daje ci jedną interpretację. Gorąca pętla
marbles daje ci nacisk zbieżności. Gdy kilku workerów wciąż napiera na tę
samą powierzchnię, pozostałe spory stają się sygnałem: albo kod wciąż kłamie,
albo prawda produktu jest rozmazana.

I tu przejmuje pałeczkę `vc-polarize`.

Zasada kosztu:

- jeden zimny run odkrywa kształt
- powtarzane gorące runy eksponują zbieżność
- stale pętle generują szum
- rozproszone pętle niszczą rozgrzany cache
- `vc-polarize` decyduje, co przetrwa

Nie rozpraszaj runów marbles po niepowiązanych inicjatywach. Nie przepisuj
bez przerwy powierzchni docelowej, chyba że operator celowo resetuje
eksperyment. Marbles działa, bo swarm wciąż napiera na te same rysy, aż
fałszywe naprawy, przepełnione luki i prawdziwe decyzje strukturalne staną
się widoczne.

Krótko: marbles nie zaczyna od zera przy każdym runie. Trzyma ten sam
kontekst pracy, tę samą powierzchnię problemu i te same bramki, dzięki czemu
kolejne workery mniej czasu tracą na archeologię repo, a więcej na brakujące
luki, fałszywe fixy i kruche założenia. To daje gęstsze, łatwiejsze do
porównania runy.

Nadmiar jest celowy. Marbles wypełnia za dużo, żeby `vc-polarize` mógł
ciąć z powrotem do jednej prawdy na podstawie evidence, nie gustu.

## Kiedy używać

Użyj `vc-marbles`, gdy:

- implementacja istnieje, ale baza kodu wciąż kłamie (dryf, kruche
  ścieżki, połknięte błędy, przegenerowane wrappery)
- padające bramki trzeba dopchnąć do P0/P1=0
- operator chce gorącą pętlę zbieżności z `--count` iteracjami pętli zewnętrznej
- trzeba puścić swarm agentów na kruchej powierzchni

**Nie** używaj tego skilla, gdy:

- implementacja jeszcze nie istnieje — to `vc-workflow` lub
  `vc-implement`
- pytanie brzmi „czy plan faktycznie wylądował?" — to `vc-audit`
  (READ-ONLY)
- pytanie brzmi „która konkurująca prawda wygrywa?" — to `vc-polarize`
- diff potrzebuje tylko review bez modyfikacji — to `vc-review`

---

## Pozycja w pipelinie

`vc-marbles` to jeden z kroków WRITE w cyklu jakości (przykład):

```
... → implement (W) → review (R) → workflow (W) → followup (R) → marbles (W) → audit (R) → polarize (W) → ...
```

Celowy nadmiar swarmu produkuje powierzchnię, którą trzeba sfalsyfikować
(`vc-audit`), a potem przyciąć do jednej prawdy (`vc-polarize`).
Marbles to **zalew**; polarize to **decydujące cięcie**. Audit
siedzi pomiędzy jako READ-ONLY warstwa falsyfikacji.

---

## Doktryna workera (ślepy z premedytacją)

Worker jest celowo **ślepy na wcześniejszą historię marbles**, pracując
wyłącznie przeciw **bieżącemu stanowi workspace'u**. Ciężar kontekstu zabija
jakość — agent pracujący 90 minut podejmuje gorsze decyzje w 91. minucie niż
świeży agent w 1. minucie, broniąc kosztu utopionego zamiast widzieć drzewo.
Każda runda dostaje świeży umysł. To nie obejście — to projekt.

**Warstwa odbioru wyników (reception)** (operator / orchestrator) trzyma rejestr otwartych
findingów, porównuje kandydatów między równoległymi rundami i decyduje, czy
uznać zbieżność, czy odpalić kolejną falę. Zobacz
[`RECEPTION.md`](RECEPTION.md). Nie ładuj warstwy odbioru do kontekstu workera.

---

## Instrumenty vs bramki

**Instrumenty** (loctree, semgrep, aicx-steer) idą na **początek**
— kierują, gdzie patrzeć (oskarżasz drzewo dowodami, nie przeczuciem).

**Testy** (pytest, cargo test, build) idą na **koniec** — weryfikują
fix (bramka).

Start od testów zawęża pole widzenia do „co pada", zamiast pokazać „co jest kruche".
Czerwone testy krzyczą najgłośniej, ale prawdziwa strukturalna słabość
często jest cicha.

---

## Model operacyjny (pojedyncza runda)

Jedno wywołanie = jedna bounded round.

1. **Oskarż obecne drzewo.** Każdy cel śledzi się do: outputu narzędzia,
   padającej bramki, audytu strukturalnego lub kontrprzykładu z ryzyka
   produkcyjnego. **Bez evidence nie ma celu.**
2. **Wybierz najmniejszą powierzchnię o dużym wpływie.** Najwyżej **3 cele**
   na rundę. Preferuj awarie o wysokim severity, ścieżki o wysokiej
   częstotliwości, ciche tryby awarii, słabe granice, problemy zamykające
   klasę awarii. Gdy wiele powierzchni nie zgadza się co do rzeczywistości
   albo kod wymusza ukrytą decyzję produktową, **wyeksponuj ją, ale jej nie
   rozstrzygaj** — to zadanie `vc-polarize`.
3. **Utwardź.** Najmniejszy zbiór zmian, który materialnie zwiększa
   prawdę. Dodaj brakujący scope/auth, brakujące indeksy, zamień
   połknięte wyjątki na obsługę, po której da się działać, dodaj smoke testy,
   scal zduplikowane kontrakty, usuń zgniłe wrappery. Aksjomat
   Vetcoders: **idź dalej ponad wsteczną kompatybilność** — tnij czysto, jeśli
   lokalna abstrakcja jest zgniła i blokuje stabilizację.
4. **Bramkuj.** Najwęższe wiarygodne bramki najpierw; szersze, jeśli zasadne.
   Minimum: składnia / lint dla dotkniętych powierzchni, testy pokrywające
   utwardzoną ścieżkę, odpowiednie sprawdzenia build/bundle. Jeśli bramka
   pada: raportuj wprost, podaj liczbę regresji, nie zagrzebuj jej pod narracją.
5. **Commit.** Dokładnie jeden commit rundy z konwencją poniżej.
6. **Raport.** Zapisz do
   `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/marbles/reports/<ts>_marble_<run_or_round_id>_<agent>.md`.

**Worker zatrzymuje się tutaj.** Nie rozszerzaj się samodzielnie na następną
rundę. Nie pisz instrukcji dla swojego następcy. Warstwa odbioru wyników
decyduje, co odpala następne.

Pełny detal pojedynczej rundy (instrumenty, soczewki, zasada z szatni)
mieszka w [`FLOW.md`](FLOW.md). Routing odbioru wyników / zbieżności mieszka w
[`RECEPTION.md`](RECEPTION.md).

---

## Soczewki stabilizacji (Stabilization Lenses)

Jeśli nie ma dokładnego opisu taska, wybierz tę pasującą do najsłabszej żywej powierzchni:

- **Access & Isolation** — auth, scope per tenant, sprawdzenia ról, granice uprawnień
- **Data Health** — indeksy, plany zapytań, N+1, hotspoty schematu, God Tables
- **Errors & Observability** — połknięte wyjątki, ciche awarie, brakujące alerty
- **Release & Runtime Resilience** — bramki CI/CD, smoke testy, bezpieczeństwo rolloutu, dryf konfiguracji

Runda może dotknąć jednej soczewki lub ściśle sprzężonego klastra. Nie wymuszaj
kolejności filarów, jeśli evidence mówi inaczej.

---

## Reguła commita

**Jedna runda = jeden commit.** Bez częściowych commitów. Bez squashowania
między rundami. Bez kopania w historii gita, żeby ustalić subject line.

Format:

```
marble: <one-line summary>

- <file>: <what changed and why>

Gate: <pass|fail>
Tests: <what ran>
Regressions: <count>
Round-ID: <opaque-id-if-provided>
```

---

## Strażnik gałęzi i drzewa

**TWARDA ZASADA: Nigdy nie zmieniaj gałęzi. Nigdy nie twórz gałęzi w
repo-root użytkownika. Nigdy nie twórz worktree ani nie przenoś się do niego
podczas runu marbles.** Operator wybrał bieżącą gałąź — to nie twoja decyzja
do rewizji. Jeśli ścieżka jest zbyt zatruta, by bezpiecznie kontynuować,
zwróć kontrolę operatorowi / runtime'owi i nazwij awarię podłoża (substrate
failure) w raporcie.

---

## Złożenie ze skillami sąsiednimi

- **`vc-init`** — wymagana bramka. Każda runda zaczyna się tutaj.
- **`vc-audit`** — downstreamowa READ-ONLY falsyfikacja. Audit sprawdza,
  czy deklarowane fixy swarmu faktycznie wylądowały względem spisanego
  planu.
- **`vc-polarize`** — downstreamowy krok WRITE. Po zalewie marbles +
  verdykcie auditu polarize zdziera z powrotem do jednej prawdy.
- **`vc-review`** — sąsiednie READ-ONLY review na bounded diffach.
  Commit rundy marbles można przejrzeć indywidualnie przed kontynuacją
  swarmu.
- **`vc-followup`** — sąsiedni READ-ONLY check trajektorii. Użyj po
  fali marbles, by ocenić zdrowie ogólnego kierunku.

---

## Antywzorce

- **Historyczna samoświadomość** — czytanie wcześniejszych artefaktów marbles, by zabrzmieć kompetentnie
- **Cosplay zbieżności** — gadanie o rozmiarze kroku / delcie / mistrzostwie pętli
- **Próżność powierzchni** — dotykanie wielu plików, żeby runda wyglądała na większą
- **Teatr polerowania** — sprzątanie, które nie zamyka żadnego trybu awarii
- **Kult wstecznej kompatybilności** — zachowywanie zgniłych kontraktów
- **Inflacja narracyjna** — długie wyjaśnienia ukrywające słabą bramkę
- **Kontaminacja równoległa** — importowanie kontekstu innego marble'a
- **Fałszywa wszechwiedza** — udawanie, że widzi się cały globalny backlog
- **Pogarda wobec agentów** — traktowanie innych agentów jako gorszych; why-matrix to
  mapa stylów, nie hierarchia wartości
- **Rozwiązywanie rozmazu produktu w workerze** — eksponuj, nie rozstrzygaj;
  zostaw to dla polarize
- **Samorozszerzanie** — pisanie planu następnej rundy z wnętrza tej
  rundy

---

## Warunek zakończenia

Zatrzymaj się po commicie i raporcie. Potem **nie** rozszerzaj się samodzielnie.
Jeśli implementacja jest kompletna, ale ma wysoki konceptualny rozmaz (konkurujące
prawdy, pofragmentowana powierzchnia produktu), zostanie przekazana do
`vc-audit` po falsyfikację i `vc-polarize`, by uzyskać klarowność na poziomie release
candidate i kształt o jednej prawdzie.

---

## Wezwanie do działania

Przeczytaj [`FLOW.md`](FLOW.md) przed pierwszą rundą — zawiera szczegóły
protokołu pojedynczej rundy i semantykę gorącej pętli zbieżności. Przeczytaj
[`RECEPTION.md`](RECEPTION.md) przed uruchomieniem jako operator /
orchestrator — opisuje dyscyplinę na poziomie swarmu i routing
równoległych rund. Potem oskarż obecne drzewo.

---

## Klamra końcowa

```text
=======================
Pamiętaj: tryb marbles to pozwolenie na napisanie małego albo szerzej zakrojonego,
ale prawdziwego fixa, nie pozwolenie na refactor, chyba że wynika to wprost
z opisu taska. Nie musisz przejmować się przerośniętym kodem wokół pewnych
części bazy kodu, ale masz twardy obowiązek opisać go
w raporcie, jeśli na niego natrafisz.
Worker widzi drzewo, nigdy fabrykę. Jedna runda, jeden commit, jeden raport.
Potem wychodzi. Swarm produkuje nadmiar; polarize go zdziera.
(•̀⌄•́)و ̑̑
=======================

Suchar: Dlaczego worker marbles nigdy nie kłóci się z następnym workerem?
Bo do tego czasu już wyszedł z szatni.  (._.)
```

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
