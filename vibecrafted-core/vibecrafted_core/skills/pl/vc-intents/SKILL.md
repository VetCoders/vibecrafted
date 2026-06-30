---
name: vc-intents
version: 1.0.1
description: >
  Operator-side intention-to-runtime truth audit. Use when the team needs to
  know which planned implementations actually landed in code, which are only
  partially present, which never materialized, and what the highest remaining
  truth is. This skill pulls intentions from aicx, reduces them to a bounded
  implementation checklist, then verifies each item against the live repo.
  Trigger phrases: "intents", "co z planu siedzi", "which planned items exist",
  "what from the plan is in code", "check intent coverage", "planned vs code",
  "highest truth", "checklist from intents".
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# vc-intents — Od intencji do prawdy runtime'u

## Wejście operatora

### Reguła Living Tree / Worktree

Ten workflow działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie twórz worktree gita, nie przełączaj się na niego ani nie przenoś do niego wykonania, chyba że operator wprost poprosi o worktree w tym prompcie. Ogólne słowa w stylu „isolate", „parallel" czy „clean branch" to za mało. Czytaj pliki ponownie przed edycją, dostosowuj się do równoległych zmian i zgłoś awarię podłoża (substrate failure), jeśli bieżące drzewo jest zbyt zatrute, by bezpiecznie kontynuować.

Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Checkpoint orientacji

Zanim ten workflow wykona analizę specyficzną dla repo, planowanie, implementację, przegląd, release lub delegowanie, MUSI uruchomić lub skonsumować procedurę `vc-init` dla przypisanego repo. Jeśli brakuje świeżych dowodów z `vc-init`, najpierw wykonaj przebieg init i traktuj pracę specyficzną dla workflow jako zablokowaną, dopóki nie ma aktualnej prawdy repo.

`Loctree:loctree` to domyślny skill do mapowania struktury repo dla tego przebiegu. Używaj Loctree przed grepem lub twierdzeniami opartymi na dokumentacji, aby wygenerować lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map): repo-view, focus, slice, impact, find i follow w odpowiednim zakresie. Szukaj istniejących symboli i kontraktów, zanim utworzysz nowe; uruchom impact przed usunięciem lub dużym refactorem; uruchom slice przed edycją.

Chodzi o znalezienie zaczepów: węzłów nośnych, twins (duplikaty), martwego kodu, dryfu, entrypointów runtime'u oraz pułapek o dużym zasięgu zmiany. Jeśli zadanie jawnie nie dotyczy repo lub nie dotyczy kodu, odnotuj w raporcie wyjątek „bez repo". W przeciwnym razie brak dowodów z `vc-init`/Loctree to błąd procesu.

Standardowy launcher (`vibecrafted start` / `vc-start`, następnie `vc-<workflow> <agent> [--prompt|--file ...]`).
Preferuj `--prompt` dla świeżego audytu, a `--file` wtedy, gdy istniejący plan, raport
lub wyekstrahowany bundle intencji ma być porównany z drzewem.

```bash
vibecrafted intents codex --prompt 'Check which planned implementations actually landed in Codescribe'
vc-intents claude --prompt 'Build a 20-item checklist from intents and mark done/partial/missing'
vibecrafted intents gemini --file ~/.vibecrafted/artifacts/Vetcoders/Codescribe/2026_0419/plans/research-plan.md
```

Zależności fundamentowe: `vc-aicx` (pozyskiwanie intencji, source chunks, pamięć
ostatnich decyzji), `vc-loctree` (żywa percepcja repo, weryfikacja strukturalna).

> Plany są tanie.
> Prawdą jest to, czy plan faktycznie wylądował w runtimie.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Główna doktryna

`vc-intents` to nie skill przeglądu i nie skill planowania. To warstwa
uzgadniania między:

- tym, co zespół zamierzał zbudować
- tym, co sesje wskazały jako następne
- tym, co baza kodu faktycznie zawiera teraz

Ten skill istnieje, bo pozostałe powierzchnie zatrzymują się za wcześnie:

- `vc-init` przywraca kontekst, ale nie uzgadnia ukończenia
- `vc-review` ocenia diff, nie pierwotną intencję
- `vc-scaffold` tworzy przyszły kształt, nie obecną prawdę
- `vc-marbles` utwardza to, co istnieje, ale nie normalizuje najpierw, które obietnice są realne

Odpowiada na węższe pytanie operatora: co z planu naprawdę jest w
kodzie, co wylądowało połowicznie, co nigdy się nie wydarzyło, co zostało zastąpione
lepszym kształtem i jaka jest najwyższa pozostała prawda.

## Dlaczego to działa

Sesje agentów są bogate w intencje, ale zaszumione w formie. `aicx intents` ekstrahuje
ustrukturyzowane sygnały intencji z wcześniejszej pracy — ale surowy output intencji to wciąż
nie prawda. To pragnienie, rozpęd, niedokończona rozmowa, czasem
zhalucynowana pewność.

Druga połowa jest tym, co się liczy: zredukuj surowy strumień intencji do kandydatów
do implementacji, zbadaj żywe repo, odmów przeszacowywania, sklasyfikuj każdego kandydata
względem obecnej prawdy runtime'u. Tak przestajemy traktować plany, changelogi
i podsumowania sesji tak, jakby były produktem.

## Co robi ten skill

Jedna inwokacja = jeden bounded audyt od intencji do prawdy:

1. pozyskaj ostatnie intencje projektu z `aicx`
2. otwórz pliki `source_chunk` przywoływane przez wytypowane pozycje
3. zredukuj zaszumiony strumień do bounded checklisty kandydatów do implementacji
4. zweryfikuj każdego kandydata względem żywego drzewa
5. sklasyfikuj każdego kandydata
6. wyemituj checklistę + najwyższą pozostałą prawdę
7. zatrzymaj się

Domyślny cel checklisty: **20 znaczących pozycji implementacyjnych**. Jeśli realnych
kandydatów jest mniej, raportuj mniej. Nie nadymaj watą ani powielonymi obietnicami.

## Protokół pozyskiwania

### Szybki tor operatora

```bash
aicx intents -p <ProjectName> --emit json 2>&1 | tail -200
```

Powierzchnia do triażu, nie ostateczny dowód.

### Tor prawdy

Przed klasyfikacją otwórz przywoływane pliki `source_chunk` i odtwórz
faktyczny kontekst planu wokół wytypowanych intencji. Dyscyplina:

1. pociągnij `aicx intents`
2. wytypuj kandydatów do implementacji
3. otwórz chunki źródłowe stojące za nimi
4. dopiero wtedy znormalizuj do pozycji checklisty

Nie klasyfikuj na podstawie samego jednolinijkowego podsumowania, gdy dostępny jest
source chunk.

## Protokół weryfikacji

Po wyekstrahowaniu checklisty zweryfikuj każdą pozycję względem żywego repo.
Preferowana kolejność:

1. `vc-loctree` / loctree MCP — kształt repo, scope, gorące pliki
2. ukierunkowane sprawdzenia symboli lub ścieżek
3. `rg` / odczyty z shella dla lokalnego detalu
4. dokumentacja tylko jako materiał wspierający

Repozytorium to główny sąd. Dokumentacja to świadkowie wspierający.

### Hierarchia dowodów

1. **Ścieżka kodu runtime'u** — żywa implementacja osiągalna z bieżącego kodu
2. **Ścieżka z testami** — testy dowodzą, że ścieżka istnieje lub że kontrakt jest ćwiczony
3. **Powierzchnia UI / CLI / config** — istnieje powierzchnia widoczna dla użytkownika/operatora
4. **Dokumentacja / CHANGELOG / plany** — tylko wspierające, nigdy same w sobie wystarczające do `done`

Jeśli wszystko, co masz, to dokumentacja lub changelog, ta pozycja nie jest `done`.

## Kontrakt klasyfikacji

Każda pozycja checklisty musi kończyć się dokładnie jednym stanem: `done`, `partial`,
`missing`, `superseded`, `non-code`.

- **`done`** — zamierzona implementacja jest materialnie obecna. Realna ścieżka kodu,
  powierzchnia config lub kontrakt runtime'u. Nie tylko wzmianka w dokumentacji.
- **`partial`** — kształt istnieje, ale pierwotna obietnica nie wylądowała w pełni
  (config bez UI, treść UI bez runtime'u, główna logika bez ścieżki dostarczenia
  lub powierzchni operatora).
- **`missing`** — plan jest realny i konkretny, ale w żywym drzewie nie ma żadnej znaczącej
  powierzchni implementacji. Wymaga rzetelnego przeszukania, nie wzruszenia ramionami.
- **`superseded`** — pierwotna intencja nie ma już sensu, bo zastąpił ją
  inny kształt. Nazwij zastępujący kształt wprost. Nie używaj
  tego, by ukryć porażkę.
- **`non-code`** — realna pozycja planu, ale należy przede wszystkim do dystrybucji,
  operacji, choreografii release'u, powierzchni klienta/produktu. Nadal ma znaczenie;
  po prostu nie należy do verdictu „siedzi w kodzie".

## Najwyższa prawda

Każdy przebieg musi kończyć się sekcją o nazwie **Najwyższa prawda**. Nie podsumowaniem —
pojedynczą najważniejszą nierozwiązaną rzeczywistością, na którą operator powinien zadziałać jako następną.

Dobrze:

- „UI mówi, że qube-daemon uruchamia się automatycznie, ale żadna ścieżka runtime'u faktycznie go nie startuje."
- „Dyskryminator ciszy istnieje w core, ale operator nie ma powierzchni ustawień, by nim sterować."
- „Bundle aplikacji jest podpisany i notaryzowalny, ale ścieżka aktualizacji wciąż jest ręczna."

Źle:

- „Część pozycji jest partial."
- „Jest jeszcze trochę pracy do zrobienia."
- „Powinniśmy dalej się poprawiać."

Najwyższa prawda powinna trochę boleć. Jeśli nie tworzy dźwigni, jest
zbyt miękka.

## Kontrakt outputu

1. **Źródło intencji** — projekt, okno pozyskiwania lub pliki źródłowe, metoda typowania
2. **Checklista** — do 20 pozycji, każda z `status`, `item`, `why`, `evidence`
3. **Najwyższa prawda** — jeden akapit
4. **Następna dźwignia** — 1-3 najwartościowsze ruchy następcze

### Format evidence

Preferuj zwięzłe odniesienia do repo: ścieżka pliku, nazwa symbolu, komenda użyta do weryfikacji.
Nie zrzucaj ogromnych logów ani nie zakopuj verdictu pod spamem grepa.

## Dyscyplina scope'u

Jednostką analizy nie jest „wszystkie myśli, jakie kiedykolwiek padły o projekcie". Preferuj
ostatnie, trafne okna intencji; pozycje w kształcie implementacji; prawdę jednej bieżącej
gałęzi / workspace'u.

Odfiltruj: czystą ideologię · filozofię narzędziową bez konsekwencji
implementacyjnej · powielone sformułowania · gadanie operatora, które nigdy nie utwardziło się w
konkretnego kandydata.

## Czego ten skill nie robi

- Zamienia `aicx intents` w ślepy generator backlogu
- Oznacza pozycje jako `done` na podstawie samej dokumentacji
- Myli nazwę gałęzi z dowiezioną implementacją
- Liczy komentarz TODO jako wylądowaną funkcję
- Nadyma checklistę do 20 niskosygnałowym szumem
- Dryfuje w przegląd PR na poziomie linii
- Przepisuje plan na nowy roadmap (chyba że operator o to poprosił)
- Traktuje „obecne w kodzie" i „działające end-to-end" jako automatycznie tożsame

Jeśli operator chce jakości diffa → `vc-review`. Nowa architektura →
`vc-scaffold` lub `vc-partner`. Domknięcie luk → `vc-ownership` lub `vc-marbles`.

## Relacja do innych skillów

- **Po `vc-init`** — znacznie silniejszy, bo worker zna już
  kształt strukturalny i powierzchnię intencji.
- **Przed `vc-marbles`** — gdy operator pyta „co z planu faktycznie
  wylądowało?" / „które obietnice są fake-complete (fałszywie ukończone)?", uruchom najpierw `vc-intents`, a potem
  wyślij najostrzejsze pozostałe kłamstwo do `vc-marbles`.
- **Przed `vc-ownership`** — zdefiniuj powierzchnię prawdy, żeby tryb ownership działał
  na rzeczywistości, nie na dryfie.

## Heurystyki operatora

- Mniej, ostrzejszych pozycji zamiast rozdętej listy
- Jawne evidence zamiast teatru pewności
- Prawda runtime'u zamiast lojalności wobec planu
- Nazwanie kłamstwa zamiast kosmetycznego zmiękczania go

Celem nie jest udowodnienie, że dokonano postępu. Celem jest dokładne wiedzieć, jaki
kształt postęp naprawdę przyjął.

## Końcowe przypomnienie

Ten skill nie chodzi o zachowanie godności planu. Chodzi o
zachowanie godności rzeczywistości.

Gdy plan i repo się nie zgadzają, ufaj najpierw repo. Gdy repo i runtime
się nie zgadzają, ufaj najpierw runtime'owi. Gdy wszystkie trzy się nie zgadzają, nazwij pęknięcie
jasno i nazwij je najwyższą prawdą.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
