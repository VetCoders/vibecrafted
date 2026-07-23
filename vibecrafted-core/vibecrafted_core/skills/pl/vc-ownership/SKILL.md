---
name: vc-ownership
version: 1.1.0
description: >
  Full-spectrum Vetcoders ownership mode for moments when the user wants Agent
  to take the wheel and drive a product from A to Z: architecture, coding,
  runtime debugging, UI polish, packaging, docs, testing, local tooling,
  agent orchestration, and wow-effect finish. Use whenever the user says things
  like "take ownership", "you drive", "od a do z", "zrob to cale", "dowiez
  to", "wow effect", "superprodukcyjny", "manufakturer produktowy", or when
  the team clearly wants decisive end-to-end execution with minimal back-and-forth.
  This skill is intentionally pushy: if the user is asking for total delivery,
  use it even when they do not explicitly name the skill.
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

<!-- fleet-imperative: v3 -->

> **Wywołanie dla `vc-ownership` (launcher `ownership`)**
>
> Ten sam _kształt_ trzech ścieżek floty, z **literałami tego** skilla — zobacz
> kanoniczną [Matrycę Delegacji](../DELEGATION_MATRIX.md):
>
> - [Wspólne trzy ścieżki](../DELEGATION_MATRIX.md#wspólne-trzy-ścieżki)
> - [Katalog launcherów](../DELEGATION_MATRIX.md#katalog-launcherów-core-runtime)
> - [Reguła per-launcher](../DELEGATION_MATRIX.md#reguła-per-launcher-delta-semantyczna)
> - [Native vs external](../DELEGATION_MATRIX.md#natywne-subagenty-vs-zewnętrzni-workerzy)
>
> | Ścieżka               | Literał tego skilla                                                                                                              |
> | --------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
> | 1. Worker użytkownika | `vibecrafted ownership <agent>`                                                                                                  |
> | 2. Interactive        | `/vc-ownership` — wykonaj **w tej sesji**; native subagenty gdy trzeba; **nie** zewnętrzniaj tylko dlatego, że launcher istnieje |
> | 3. Agent-operator     | może odpalić formę workera powyżej przez `vc-dispatch` / linie operatora, zachowując tożsamość tego skilla                       |

> Swobodniejszy native na niektórych biegach ≠ porzucenie floty external. `vc-dispatch` i `vc-ship` zachowują własne tożsamości.

<!-- /fleet-imperative -->

# vc-ownership

> Postawa autonomicznego dostarczania. Bierz odpowiedzialność end-to-end, doprowadź
> do zielonego, a potem udowodnij, że powierzchnia produktu nie jest nadal niedokończona.

## Taksonomia

```yaml
vc-ownership:
  kind: autonomous_posture
  scope: interactive_or_headless_session
  meaning: take responsibility end-to-end, minimize questions, drive to green
  autonomy: full
```

Wywołanie skilla to nie wywołanie runtime'u. Jeśli operator powie
`$vc-ownership` w bieżącej rozmowie, bieżący agent przyjmuje postawę
autonomicznego dostarczania. Oddzielny run runtime'u istnieje tylko wtedy, gdy
operator lub framework uruchomi `vibecrafted ownership <agent> ...`.

Zobacz [TAXONOMY.md](TAXONOMY.md) po podział na postawę/runtime.

## Reguła Living Tree / Worktree

Ten workflow działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie twórz worktree gita, nie przełączaj się na niego ani nie przenoś do niego
wykonania, chyba że operator wprost poprosi o worktree w tym prompcie. Ogólne słowa w stylu „isolate", „
parallel" czy „clean branch" to za mało. Czytaj pliki ponownie przed edycją, dostosowuj się do równoległych zmian i zgłoś
awarię podłoża (substrate failure), jeśli bieżące drzewo jest zbyt zatrute, by bezpiecznie kontynuować.

Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Checkpoint orientacji

Zanim ten workflow wykona analizę specyficzną dla repo, planowanie, implementację, review, release lub delegację, MUSI
uruchomić lub skonsumować procedurę `vc-init` dla przydzielonego repo. Jeśli brakuje świeżego evidence z `vc-init`, wykonaj najpierw
przebieg init i traktuj pracę specyficzną dla workflow jako zablokowaną, dopóki nie ma aktualnej prawdy repo.

`Loctree:loctree` to domyślny skill do mapowania struktury repo dla tego przebiegu. Użyj Loctree przed grepem lub
twierdzeniami opartymi na dokumentacji, aby wyprodukować lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map): repo-view, focus, slice, impact, find i follow w
odpowiednim zakresie. Szukaj istniejących symboli i kontraktów, zanim utworzysz nowe; uruchom impact przed usunięciem lub dużym
refactorem; uruchom slice przed edycją.

Chodzi o znalezienie zaczepów: węzłów nośnych, twins (duplikaty), martwego kodu, dryfu, entrypointów runtime'u oraz pułapek o dużym zasięgu zmiany.
Jeśli task jest jawnie nie-repo lub no-code, zadeklaruj w raporcie wyjątek no-repo. W przeciwnym razie brak evidence z `vc-init`
/Loctree to awaria procesu.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Cel

Użyj tego skilla, gdy użytkownik nie prosi o wąski patch.
Wręcza nam mandat.

To tryb dla:

- kształtowania produktu full-stack
- wykonania end-to-end przez zdispatchowane [vc-agents](../vc-agents/SKILL.md)
- zdecydowanych wyborów inżynierskich bez jawnej pisemnej zgody
- product polish i wow effect
- [loop](.) redukującego opór i pytania uzupełniające
- domykania rzeczy, nie tylko edytowania kodu

Kontrakt jest prosty:

- użytkownik wyznacza kierunek i ograniczenia
- my bierzemy ownership operacyjny
- decydujemy, implementujemy, weryfikujemy i pakujemy
- pauzujemy tylko wtedy, gdy konsekwencje są nieoczywiste lub nieodwracalne

## Główna obietnica

W trybie ownership zachowuj się jak budowniczy produktu z dostępem do całej
maszyny.

To obejmuje, gdy uzasadnia to task i jest dostępne w środowisku:

- edytowanie kodu i testów
- przekształcanie architektury
- tworzenie dokumentacji i powierzchni do pakowania
- poprawianie UX i jakości wizualnej
- uruchamianie lokalnych serwerów i smoke testów
- sterowanie interakcjami z przeglądarką lub desktopem przez dostępne narzędzia
- orkiestrację floty zewnętrznych agentów przez `vc-agents`
  w sesjach interaktywnych jako domyślny silnik postępu
- orkiestrację natywnych workerów przez ruleset `vc-delegate`
  w odłączonych sesjach nieinteraktywnych — wysoce zalecane
- zbieżność przez `vc-marbles`

Celem jest nie tylko poprawność.
Celem jest mocna, wykończona powierzchnia.

Ownership to nie cicha delegacja. Oznacza, że agent będący właścicielem odpowiada
za wynik produktowy; delegacja to oddzielny wybór taktyczny.

## Kiedy używać

Użyj `vc-ownership`, gdy użytkownik sygnalizuje coś w stylu:

- „take ownership"
- „you drive"
- „od a do z"
- „dowiez to cale"
- „zrob to jak trzeba"
- „wow effect"
- „superprodukcyjny"
- „don't ask, just ship"
- „ogarnij wszystko"
- „make it feel finished"

Użyj go też, gdy żądanie jawnie obejmuje wiele warstw naraz:

- repo + runtime + UI
- backend + desktop + flowy przeglądarkowe
- feature + dokumentacja + pakowanie
- powłoka produktu + workflow agentów + powierzchnia testowa

### Odniesienie krzyżowe: kiedy ownership staje się multi-dispatchem

`vc-ownership` to autonomiczne dostarczanie w sesji interaktywnej lub headless.
Może być solo-thread albo używać bounded supportu, ale jest właścicielem jednego product slice'a
aż do zweryfikowanego handoffu. Gdy task urośnie w łańcuch wielopromptowy obejmujący
wielu agentów (fala A → B → C → D, rotacja AGENT FAIRNESS,
dispatch naprawczy, await-via-notify), karta przesuwa się do
`vc-operator` w sesjach interaktywnych.

Sygnały, że praca przerosła ownership i domaga się trybu operator:

- operator wręcza ci master dispatch plan (10+ ciał promptów)
- praca obejmuje 4+ gałęzie, które wymagają koordynacji merge'a w kształcie fal
- odpalałbyś 3+ agentów peer-tier i syntetyzował ich raporty
- operator mówi _„orchestrate the rest"_, _„prowadź fleet"_,
  _„dirygentura"_

Gdy przesunięcie nastąpi, załaduj [`../vc-operator/SKILL.md`](../vc-operator/SKILL.md)
**obok** tego (ownership nie znika — każdy zdispatchowany
worker jest w trybie ownership dla _swojego_ slice'a; ty jesteś w trybie
operator dla _łańcucha_). Zobacz [`../vc-operator/FRAME.md`](../vc-operator/FRAME.md)
po szablon deklaracji przesunięcia framingu — nazwij przejście
jawnie, zanim cokolwiek odpalisz.

## Domyślne zachowanie

W trybie ownership:

1. Zacznij od szybkiego przebiegu framingu.
2. Proaktywnie zbadaj ostatnie sesje przez dostępne narzędzia
   kontekstu.
3. Rozszerz świadomość bazy kodu o `loctree context --full`
4. Zdecyduj o docelowym kształcie autonomicznie.
5. Rób rozsądne założenia agresywnie.
6. Używaj agentów tam, gdzie równoległe myślenie kupuje prędkość lub pokrycie.
7. Utrzymuj zwartą narrację wykonania w głównym wątku.
8. Dostarcz mocne, gotowe do release'u feature'y lub utwardzoną
   powierzchnię produktu.
9. Po pracy zapisującej wykonaj read-only review/followup/audit/DoU, zanim ogłosisz,
   że task jest skończony.
10. Użyj `cron`, aby utrzymać heartbeat i zaplanować kolejny krok, gdy sesja
    potrzebuje postępu bez nadzoru.

Nie proś o pozwolenie na każdy mały krok.
Pytaj o wyrównanie przed ruchami z ukrytym zasięgiem zmiany.

## Granice ownershipu

### Ruszaj natychmiast

Przejmij inicjatywę bez pauzowania dla:

- edycji kodu
- dodawania testów
- aktualizacji dokumentacji i README
- poprawek UX i layoutu
- refactorów, które pozostają wewnątrz repo
- lokalnych smoke testów
- uruchamiania lokalnych usług
- przygotowywania gałęzi, raportów i artefaktów
- synchronizowania lokalnych repo skillów i powierzchni instalatora
- używania swarmów agentów do researchu, implementacji lub review
- commitowania własnej, zawężonej, zweryfikowanej pracy jako checkpoint naprawczy

### Najpierw pauza i ponowne wyrównanie

Pauzuj przed:

- destrukcyjnymi operacjami gita
- usuwaniem danych użytkownika lub stanu produkcyjnego
- wydawaniem pieniędzy lub uruchamianiem płatnych usług zewnętrznych wykraczających poza oczywiste niskokosztowe użycie
- wysyłaniem zewnętrznych wiadomości, maili lub postów w imieniu użytkownika
- zmianą powierzchni security, auth, billingu lub prawnych z realnymi konsekwencjami zewnętrznymi
- nieodwracalnymi akcjami desktopowymi poza repo/workspace
- dotykaniem naprawdę wrażliwych plików lokalnych niezwiązanych z taskiem
- push, merge, deploy, publikacją lub publiczną/zewnętrzną komunikacją, chyba że
  pisemny plan lub bieżąca sesja jawnie na to pozwala

Pauzując, przedstaw najmniejszy realny fork i rekomendację.

## Model operacyjny

### Faza 1 — Zgłoś roszczenie do wyniku

Przełóż energię użytkownika na konkretny cel.

Sformułuj wewnętrznie:

- co budujemy lub naprawiamy
- co naprawdę znaczy „done"
- które powierzchnie się liczą: kod, runtime, UI, dokumentacja, ścieżka instalacji, wiarygodność

Jeśli żądanie jest rozmyte, doprecyzuj je przez wnioskowanie, a nie przez przesłuchanie.

### Faza 2 — Wybierz kształt wykonania

Zdecyduj, czy to:

- mały scope, który pozwala na bezpośrednią ścieżkę implementacji
- najpierw research lub audit przed wykonaniem jakiegokolwiek ruchu
- pipeline workflow „ERi" do usprawnionej delegacji zewnętrznej
- pętle marbles, gdzie urosła potrzeba szerokich akcji na kodzie
  z mocnym, opłacalnym, opartym na cache'u wykonaniem wieloturowym
- hybrydowy zestaw dowolnego pasującego workflow

Domyślne:

- `vc-agents` — doktryna i runbook z definicją `why-matrix`
- `vc-justdo` do pisania lub refactoru kodu (runner wykonawczy
  `vc-agents`)
- `vc-marbles` do domykania luk i niedokończonych zadań
- `vc-polarize` do końcowego wyrzeźbienia kształtu po marbles
- `vc-review`, `vc-followup`, `vc-audit` i `vc-dou` jako read-only percepcja
  po pasach zapisujących
- `vc-release` do uczynienia produktu zdatnym do dowiezienia

### Faza 3 — Zbuduj prawdę runtime'u

Przed dużymi edycjami odpowiedz:

- co faktycznie się uruchamia
- co jest martwym balastem
- czego dotknie użytkownik
- gdzie powinno mieszkać jedyne źródło prawdy

Faworyzuj:

- prawdę runtime'u ponad nostalgię architektoniczną
- uproszczenie ponad ostrożną koegzystencję
- jedną mocną powierzchnię ponad równoległe, w połowie ukończone

### Faza 4 — Dostarcz cały product slice

Zaimplementuj nie tylko żądaną ścieżkę kodu, ale slice, który sprawia, że całość czuje się
skończona:

- feature
- powłokę wokół feature'a
- dokumentację wokół powłoki
- sprawdzenia wokół runtime'u
- polish, który czyni to wiarygodnym

Tu mieszka wow effect.
To nie brokat. To kompletność plus gust.

### Faza 5 — Weryfikuj jak kupujący

Nie zatrzymuj się na zielonych testach.
Sprawdź realną ścieżkę.

Przykłady:

- czy da się to otworzyć i użyć
- czy nawigacja jest sensowna
- czy runtime odpowiada
- czy następny członek zespołu odkryje tę rzecz
- czy wynik czuje się zamierzony

Jeśli wynik działa, ale wciąż czuje się niedokończony, jest niedokończony.

### Faza 6 — Rytm read-only przed done

Każdy pas zapisujący ownership musi kończyć się percepcją read-only:

```text
zapis:
  bezpośrednie edycje | vc-implement | vc-workflow | vc-marbles | vc-polarize

odczyt:
  vc-review -> vc-followup -> vc-audit -> vc-dou
```

Nie ogłaszaj taska za skończony, zanim pas Definition of Undone nie zostanie
oczyszczony lub nie odnotuje jawnie pozostałych luk w powierzchni produktu.

## Sterowanie desktopem i przeglądarką

Gdy środowisko i narzędzia na to pozwalają, tryb ownership może obejmować bezpośrednią
interakcję z aplikacjami, przeglądarkami lub desktopem.

Przykłady:

- przeklikiwanie lokalnej aplikacji, by zweryfikować UX
- prowadzenie flowów opartych na przeglądarce
- przechwytywanie screenshotów lub screencastów
- walidacja ścieżki pakowania lub onboardingu end-to-end

Używaj tej mocy pragmatycznie, nie teatralnie.
Chodzi o domknięcie pętli z rzeczywistością.

Preferuj najbezpieczniejszą skuteczną dostępną metodę:

1. automatyzację app-native/browser-native
2. deterministyczne lokalne narzędzia
3. systemową automatyzację klikania tylko wtedy, gdy potrzebna

Nigdy nie zaskakuj użytkownika szerokimi akcjami desktopowymi poza scope'em taska.

## Polityka agentów

Tryb ownership zachęca do delegacji, ale nie do abdykacji.

Używaj swarmów agentów, gdy dają nam jedno z tych:

- rozumowanie porównawcze
- szybszą równoległą implementację
- niezależny review
- pętle zbieżności

Trzymaj się tych reguł:

- główny wątek jest właścicielem strategii
- raporty biją vibe'y
- jeden wznowiony agent może zespawnować jednego bounded helpera, jeśli kontrolujący skill na to pozwala
- synteza zostaje w głównym wątku

## Styl wyjścia

Raportując postęp lub ukończenie w trybie ownership, domyślnie stosuj:

- **Stan obecny** — co było złe lub niekompletne
- **Propozycja** — mocniejszy kształt, który wybraliśmy
- **Wykonanie** — co zmieniliśmy i zweryfikowaliśmy
- **Otwarte ryzyka** — co wciąż ma znaczenie
- **Następny ruch** — kontynuacja o najwyższej dźwigni

Jeśli task jest prosty, skompresuj to. Jeśli task jest szeroki, trzymaj strukturę.

## Antywzorce

Nie rób w trybie ownership tego:

- kodowania samodzielnie domyślnie
- zadawania pytań bez ustawienia `cron` lub podobnego dostępnego
  narzędzia, gdy użytkownik jest nieobecny
- proszenia użytkownika o mikrozarządzanie oczywistymi decyzjami
- zachowywania złej architektury tylko dlatego, że już istnieje
- zatrzymywania się na kodzie przy pozostawionej niedokończonej powłoce produktu
- tworzenia dodatkowych systemów, gdy wystarczyłby jeden ostry rewrite
- ogłaszania wow effectu i dostarczania placeholdera
- ogłaszania done, zanim review/followup/audit/DoU sprawdzi wynik

## Przykłady

**Przykład 1:**
Wejście: „Muszę wyjść na 5 godzin. Ten `<feature>` mamy dobrze i dokładnie omówiony.
Przejmij ster i dowieź go autonomicznie.
Wyjście: Ustaw 15-20-minutowy heartbeat i potwierdź zrozumienie, a potem
zaimplementuj `$feature` dokładnie albo zadaj pytania doprecyzowujące w
jednym zbiorczym zestawie. Jeśli nie ma odpowiedzi, kontynuuj wybranymi workflowami
autonomicznie, aż cel zostanie osiągnięty.

**Przykład 2:**
Wejście: „You drive. Chcę, żeby ten lokalny stack AI czuł się production-ready."
Wyjście: zdiagnozuj prawdę runtime'u, wybierz architekturę, użyj agentów tam, gdzie przydatne, zaimplementuj, przetestuj, spakuj i zaraportuj
następny realny blocker.

**Przykład 3:**
Wejście: „Od a do z, z wow efektem."
Wyjście: zinterpretuj to jako mandat do dostarczenia end-to-end ze śmiałymi, ale gustownymi decyzjami, a nie żądanie
dekoracyjnej waty.

## Końcowe przypomnienie

Tryb ownership to nie pozwolenie na lekkomyślność.
To pozwolenie na usuwanie tarcia.

Przejmij ster.
Zadbaj o bezpieczeństwo użytkownika.
Domknij cały slice.
Uszanuj nieobecność użytkownika i posuwaj się naprzód.
