---
name: vc-followup
version: 2.2.0
description: >
  AUDIT-FIRST post-implementation trajectory check. Evaluates whether
  the work is heading in the right direction, what gaps remain, what
  drift was introduced, and what the next highest-leverage move should
  be. May inspect code, runtime behavior, UX, docs, or packaging
  without requiring a single artifact like a PR or commit range as its
  frame. Sibling to `vc-review` (per-implementation diff perception)
  and `vc-audit` (per-plan spec falsification) in the AUDIT-FIRST
  perception layer of the pipeline. Trigger phrases: "follow-up check",
  "followup audit", "czy sa jeszcze luki", "readiness before hands-on",
  "audit this implementation", "po implementacji", "gaps after agents",
  "co zostało do zrobienia", "post-implementation review",
  "czy to idzie dobrze", "czy ten kierunek ma sens", "what still feels off".
compatibility:
  tools: []
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v3 -->

> **Wywołanie dla `vc-followup` (launcher `followup`)**
>
> Ten sam _kształt_ trzech ścieżek floty, z **literałami tego** skilla — zobacz
> kanoniczną [Matrycę Delegacji](../DELEGATION_MATRIX.md):
>
> - [Wspólne trzy ścieżki](../DELEGATION_MATRIX.md#wspólne-trzy-ścieżki)
> - [Katalog launcherów](../DELEGATION_MATRIX.md#katalog-launcherów-core-runtime)
> - [Reguła per-launcher](../DELEGATION_MATRIX.md#reguła-per-launcher-delta-semantyczna)
> - [Native vs external](../DELEGATION_MATRIX.md#natywne-subagenty-vs-zewnętrzni-workerzy)
>
> | Ścieżka               | Literał tego skilla                                                                                                             |
> | --------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
> | 1. Worker użytkownika | `vibecrafted followup <agent>`                                                                                                  |
> | 2. Interactive        | `/vc-followup` — wykonaj **w tej sesji**; native subagenty gdy trzeba; **nie** zewnętrzniaj tylko dlatego, że launcher istnieje |
> | 3. Agent-operator     | może odpalić formę workera powyżej przez `vc-dispatch` / linie operatora, zachowując tożsamość tego skilla                      |

> Swobodniejszy native na niektórych biegach ≠ porzucenie floty external. `vc-dispatch` i `vc-ship` zachowują własne tożsamości.

<!-- /fleet-imperative -->

# vc-followup — AUDIT-FIRST Trajectory Check

> Krok percepcji AUDIT-FIRST. Brat `vc-review` (per-diff) i
> `vc-audit` (per-plan). Ten pyta **„czy kierunek jest zdrowy?"**
> w poprzek dowolnych powierzchni, które wskaże operator — kodu, UX, dokumentacji,
> pakowania, integracji, ścieżki instalacji — bez wymogu bounded
> artefaktu. Produkuje raport, nigdy nie modyfikuje kodu.

## Pozycja w pipelinie

`vc-followup` mieszka w slocie **percepcji trajektorii**:

```
... → implement (WRITE) → [FOLLOWUP: AUDIT-FIRST] → review (READ) → marbles (WRITE) → ...
```

Followup odpowiada na **„czy trajektoria jest zdrowa?"**. Review odpowiada na
**„czy ten diff jest czysty?"**. Audit odpowiada na **„czy zapisany spec
wylądował?"**. Wszystkie trzy są AUDIT-FIRST; żaden z nich nie modyfikuje kodu. Poprawki
należą dalej w pipelinie, w `vc-marbles`.

## Wejście operatora

### Reguła Living Tree / Worktree

Ten workflow działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie twórz worktree gita, nie przełączaj się na niego ani nie przenoś do niego wykonania, chyba że operator wprost poprosi o worktree w tym prompcie. Ogólne słowa w stylu „isolate", „parallel" czy „clean branch" to za mało. Czytaj pliki ponownie przed edycją, dostosowuj się do równoległych zmian i zgłoś awarię podłoża (substrate failure), jeśli bieżące drzewo jest zbyt zatrute, by bezpiecznie kontynuować.

Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Checkpoint orientacji

Zanim ten workflow wykona analizę specyficzną dla repo, planowanie, implementację, przegląd, release lub delegowanie, MUSI uruchomić lub skonsumować procedurę `vc-init` dla przypisanego repo. Jeśli brakuje świeżych dowodów z `vc-init`, najpierw wykonaj przebieg init i traktuj pracę specyficzną dla workflow jako zablokowaną, dopóki nie ma aktualnej prawdy repo.

`Loctree:loctree` to domyślny skill do mapowania struktury repo dla tego przebiegu. Używaj Loctree przed grepem lub twierdzeniami opartymi na dokumentacji, aby wygenerować lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map): repo-view, focus, slice, impact, find i follow w odpowiednim zakresie. Szukaj istniejących symboli i kontraktów, zanim utworzysz nowe; uruchom impact przed usunięciem lub dużym refactorem; uruchom slice przed edycją.

Chodzi o znalezienie zaczepów: węzłów nośnych, twins (duplikaty), martwego kodu, dryfu, entrypointów runtime'u oraz pułapek o dużym zasięgu zmiany. Jeśli zadanie jawnie nie dotyczy repo lub nie dotyczy kodu, odnotuj w raporcie wyjątek „bez repo". W przeciwnym razie brak dowodów z `vc-init`/Loctree to błąd procesu.

Operator wchodzi do sesji frameworka przez:

```bash
vibecrafted start
# or
vc-start
# same default board as: vc-start operator
```

Następnie uruchom ten workflow przez command deck:

```bash
vibecrafted followup <agent> --file '/path/to/context.md'
```

```bash
vc-followup <agent> --prompt '<prompt>'
```

Jeśli `vc-followup <agent>` zostanie wywołany poza Zellij, framework dołączy do
sesji operatora lub ją utworzy i uruchomi ten workflow w nowej karcie.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Czym to jest

`vc-followup` to poimplementacyjny audyt kierunku.

Zadaje pytania w stylu:

- czy to idzie w dobrym kierunku
- co wciąż sprawia wrażenie niedokończonego lub niestabilnego
- jakie luki pozostały po ostatnim pushu implementacyjnym
- jaki dryf pojawił się między zamierzonym kształtem a obecnym
- jaki jest następny ruch o największej dźwigni

Jest celowo szerszy niż `vc-review`.

`vc-review` ocenia bounded obiekt w obrębie jasnych ram przeglądu:

- PR
- gałąź
- zakres commitów (commit range)
- pakiet artefaktów do przeglądu

`vc-followup` ocenia poimplementacyjny stan pracy, nawet gdy
nie ma żadnego pojedynczego kanonicznego artefaktu do przejrzenia.

## Kiedy używać

Używaj `vc-followup`, gdy:

- kod właśnie zaimplementowano i chcesz ocenić kierunek, nie tylko diff
- task „działa", ale wciąż coś jest nie tak
- agenci skończyli przebieg i chcesz zobaczyć, co pozostaje otwarte
- chcesz rekomendację następnego ruchu po implementacji
- potrzebujesz poimplementacyjnego audytu w poprzek kodu, runtime'u, UX, dokumentacji lub pakowania

Nie używaj `vc-followup`, gdy:

- potrzebujesz findingów dla konkretnego PR, gałęzi lub zakresu commitów
- potrzebujesz framingu przeglądu na poziomie linii
- task wciąż jest w trybie researchu przedimplementacyjnego

W tych przypadkach użyj `vc-review` lub `vc-research`.

## Kontrakt audytu

`vc-followup` powinien oceniać:

- pozostałe luki
- dryf od zamierzonego kształtu
- regresje lub kruchość
- niezgodności między kodem a prawdą runtime'u
- brakujące wykończenie wokół UX, dokumentacji, pakowania, onboardingu lub instalowalności
- czy bieżący kierunek zasługuje na kontynuację, korektę czy eskalację

Wynik nie powinien czytać się jak code review.
Powinien czytać się jak poimplementacyjny check trajektorii.

## Kształt wyjścia

Domyślna struktura wyjścia:

1. **Bieżący stan** — co istnieje teraz i co się zmieniło od ostatniego pushu implementacyjnego
2. **Co wciąż jest nie tak** — luki, dryf, kruchość, niedokończone powierzchnie
3. **Verdict kierunku** — czy praca zmierza w dobrym kierunku, czy nie
4. **Następny ruch** — kontynuacja o największej dźwigni

Jeśli to istotne, jawnie rozdziel:

- luka w kodzie
- luka w runtime
- luka w UX
- luka w dokumentacji/pakowaniu

## Relacja do innych skilli

- Użyj `vc-review` dla bounded, opartej na artefakcie oceny
- Użyj `vc-followup` dla poimplementacyjnego audytu kierunku
- Użyj `vc-marbles`, gdy followup znajdzie nierozwiązaną entropię `P0` / `P1`, która potrzebuje pętli zbieżności
- Użyj `vc-dou`, gdy kod może być w porządku, ale cała powierzchnia produktu jest wciąż niekompletna

## Antywzorce

Nie:

- sprowadzaj `vc-followup` do synonimu `vc-review`
- zmuszaj go do zależności od PR lub zakresu commitów, gdy prawdziwe pytanie jest kierunkowe
- zwracaj samych findingów bez powiedzenia, czy bieżąca trajektoria jest zdrowa
- myl „wciąż są luki" z „kierunek jest zły"
- pomijaj followup powierzchni produktu i patrz tylko na kod
