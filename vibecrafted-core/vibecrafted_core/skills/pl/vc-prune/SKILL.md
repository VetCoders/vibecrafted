---
name: vc-prune
version: 3.3.3
description: >
  Repository curation, not clear-cutting. Map what truly participates in runtime 
  truth versus what is silently parked — then decide revive, archive, or delete. 
  Includes the silencer strip: rip every `#[allow(...)]`, `// nosemgrep`, 
  `eslint-disable`, `@ts-ignore`, `# noqa`, `# type: ignore`, panic-vs-skip pattern, 
  and any other annotation that mutes a quality gate. Run the gates. Listen.
  Triage with care — `#[allow(dead_code)]` (and equivalents) is often the most 
  valuable smell in a repo: parked work the team forgot about. Surface those as 
  forgotten gems for the operator to decide.
  This skill is a gem hunter, not a clear-cutter.
  Trigger phrases: "prune", "strip dead code", "wyczyść mądrze", "strip the silencers",
  "zdejmij wszystkie ignore", "zobacz co realne", "forgotten gems",
  "co tam zapomnieliśmy".
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# vc-prune — Kuratorstwo, nie wycinka

> Nie pal domu. Zdejmij wszystko aż do nośnych ścian i zdaj raport z tego, co znalazłeś za tapetą.

## Wejście operatora

### Reguła Living Tree / Worktree

Ten workflow działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie twórz worktree gita, nie przełączaj się na niego ani nie przenoś do niego
wykonania, chyba że operator wprost poprosi o worktree w tym prompcie. Ogólne słowa w stylu „isolate", „
parallel" czy „clean branch" to za mało. Czytaj pliki ponownie przed edycją, dostosowuj się do równoległych zmian i zgłoś
awarię podłoża (substrate failure), jeśli bieżące drzewo jest zbyt zatrute, by bezpiecznie kontynuować.

Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Checkpoint orientacji

Zanim ten workflow wykona analizę specyficzną dla repo, planowanie, implementację, przegląd, release lub delegowanie, MUSI
uruchomić lub skonsumować procedurę `vc-init` dla przypisanego repo. Jeśli brakuje świeżych dowodów z `vc-init`, najpierw wykonaj
przebieg init i traktuj pracę specyficzną dla workflow jako zablokowaną, dopóki nie ma aktualnej prawdy repo.

`Loctree:loctree` to domyślny skill do mapowania struktury repo dla tego przebiegu. Używaj Loctree przed grepem lub twierdzeniami
opartymi na dokumentacji, aby wygenerować lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map):
repo-view, focus, slice, impact, find i follow w odpowiednim zakresie. Szukaj istniejących symboli i kontraktów, zanim utworzysz
nowe; uruchom impact przed usunięciem lub dużym refactorem; uruchom slice przed edycją.

Chodzi o znalezienie zaczepów: węzłów nośnych, twins (duplikaty), martwego kodu, dryfu, entrypointów runtime'u oraz pułapek o dużym zasięgu zmiany.
Jeśli zadanie jawnie nie dotyczy repo lub nie dotyczy kodu, odnotuj w raporcie wyjątek „bez repo". W przeciwnym razie brak dowodów z `vc-init`
/Loctree to błąd procesu.

Uruchom przez command deck (pełny kontrakt wejścia operatora znajdziesz w `vc-init`):

```bash
vibecrafted prune <agent> --file /path/to/prune-plan.md
vc-prune codex --prompt 'Strip silencers and listen'
```

Vibe-codowane repo zwykle zbiera dwie warstwy gruzu: **martwą powierzchnię** (porzucone eksperymenty z auth, zdublowane
handlery Stripe'a, martwe funkcje serverless) oraz **wyciszoną powierzchnię** (warningi zamknięte w pośpiechu, testy, które zawsze się skipują,
paniki, które zawsze odpalają). `vc-prune` oddziela obie warstwy od prawdy runtime'u — i jedną od drugiej.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Aksjomaty

1. **Agresywny prune, z wiarą w archiwum VCS.** Martwy kod to nie zły kod — to cmentarz wartościowych pomysłów. Jego miejsce jest
   w historii Gita, nie w runtimie. Tnij bez sentymentów — ale dopiero po aksjomacie 4.
2. **Idź naprzód zamiast trzymać się wstecznej kompatybilności.** Zgniłe abstrakcje blokujące stabilizację tnie się czysto. Graf
   zależności jest częścią prawdy runtime'u.
3. **Kod wie. Zdejmij wyciszenie i słuchaj.** Każdy silencer to odroczona rozmowa. Większość dodano w pośpiechu. Jedyny uczciwy test tego,
   które wciąż zarabiają na swoje utrzymanie, to wyrwać je wszystkie i pozwolić mówić toolchainowi.
4. **`#[allow(dead_code)]` (i kuzyni) to często najwartościowszy sygnał w repo.** Zwykle oznacza zaparkowaną pracę — w 90%
   gotowy flow logowania, pipeline eksportu dla utraconego (churned) klienta, debugowy wizualizer, o którym nikt nie wspomniał nowym osobom w zespole.
   To **zapomniane perełki**, nie śmieci. Wydobądź je na powierzchnię; nigdy nie usuwaj automatycznie.

## Główny kontrakt

- Przy nietrywialnym prune zewnętrzny dispatch przez `vc-agents` to domyślny pierwszy ruch.
- Zakładaj, że 30% vibe-codowanego repo to martwe rusztowanie.
- Sklasyfikuj każdego kandydata: `KEEP-RUNTIME`, `KEEP-BUILD`, `MOVE-ARCHIVE`, `DELETE-NOW`, `VERIFY-FIRST` lub
  `FORGOTTEN-GEM`.
- Wolej wycinać całe martwe pionowe wycinki (slice'y) niż przycinać symboliczne liście.
- Dociskaj kontrakty po każdej fali: manifesty, dokumentacja, CI, bounds pakietów.
- Uruchamiaj bramki po każdej fali. Wymagaj jednego prawdziwego dowodu smoke albo build.

## Doktryna delegacji

| Potrzeba                                                | Najlepszy model |
| ------------------------------------------------------- | --------------- |
| Archeologia, ukryta osiągalność, łowienie perełek       | Claude          |
| Dokładne usunięcia, dociskanie manifestów, robota mech. | Codex           |
| Radykalne upraszczanie, wycinanie całych podsystemów    | Gemini          |

## Workflow

### Faza 1 — Zdefiniuj stożek runtime'u

Wychwyć: prawdziwe entrypointy, obowiązkowe flow użytkownika, ścieżkę build/release. Nie zaczynaj od „nieużywanych eksportów" — zacznij od „
czy to obsługuje żywy ruch?"

### Faza 2 — Zmapuj przez `loct`

```bash
loct auto && loct manifests && loct hotspots && loct dead
loct routes      # web/API
loct commands    # desktop/Tauri
loct events
```

### Faza 3 — Prune falami (od najbezpieczniejszej → do najryzykowniejszej)

- **Fala 1 — spaliny AI i rusztowanie prototypu.** `v1_backup.ts`, `old_auth_handler.js`, `stripe_test_claude.ts`, martwe
  foldery sesji `.claude/` `.codex/`, nieaktualne zrzuty ekranu.
- **Fala 2 — całe martwe pionowe wycinki (slice'y).** Frontendy bez konsumentów, alternatywne strony logowania nigdy niezamontowane, handlery
  webhooków zastąpione przez SaaS. Przetnij pasmo, pozwól Gitowi je zarchiwizować.
- **Fala 3 — nieosiągalna powierzchnia produktu.** Niezamontowane route'y, zdublowane silniki (Prisma + surowy SQL robiące to samo),
  martwe feature flagi zachowane po launchu.
- **Fala 4 — dociskanie kontraktów.** Zależności w `package.json`, features w `Cargo.toml`, extras w `pyproject.toml`, nieaktualne sekrety
  w `.env.example`, workflowy CI.
- **Fala 5 — Silencer Strip (zdejmowanie wyciszeń).** Osobna fala, bo nie chodzi o usuwanie martwego kodu — chodzi o odciszanie
  toolchaina, żeby żywy kod mógł przemówić. Patrz niżej.

### Faza 4 — Zweryfikuj rzeczywistość

Zielone statyczne bramki są konieczne, ale niewystarczające. Dodaj jedną prawdziwą ścieżkę dowodu: zbootuj aplikację, uruchom CLI, uderz w główny
route.

---

## Fala 5 — Silencer Strip (Zdejmij i słuchaj)

### Inwentaryzacja

```bash
# Rust
rg -n '#\[allow\(' src-tauri/src
rg -n 'nosemgrep' .

# TypeScript / JavaScript
rg -n 'eslint-disable' src
rg -n '@ts-(ignore|nocheck|expect-error)' src
rg -n 'biome-ignore' src

# Python
rg -n '# noqa' .
rg -n '# type: ignore' .
rg -n '# pylint: disable' .
rg -n '@pytest\.mark\.skip' .

# Go
rg -n '//nolint' .
rg -n 'testing\.Short\(\) \|\| t\.Skip' .

# Test theater across languages
rg -n 'panic!\("Test requires|throw new Error\("requires' .
rg -n 'it\.skip|test\.skip|describe\.skip' .
```

Wychwyć **liczniki per kategoria**. To twoja linia bazowa „przed".

### Zdejmij je WSZYSTKIE w jednym przebiegu

Masowo usuń linie. Nie wstępnie kuratuj „oczywistych zatrzymanek" — to ten sam bias, który je tam wstawił, broniłby ich. Pozwól
zdecydować toolchainowi.

### Uruchom bramki

Cokolwiek repo już ma — nie wymyślaj nowych:

```bash
cargo clippy --all -- -D warnings && cargo test --all
pnpm lint:tsc && pnpm code:all && pnpm vitest run
ruff check . && mypy . && pytest          # Python
golangci-lint run && go test ./...        # Go
semgrep --config=auto .                   # if available
pre-commit run --all-files                # if installed
```

### Triażuj z rozwagą

| Finding                                  | Rozwiązanie                                                                                                                                                                                 |
| ---------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Prawdziwy smell/code smell (zapaszek)    | **Napraw przyczynę źródłową.** Zrefaktoruj, napisz porządne typy, dodaj adapter, zdejmij locka przed await.                                                                                 |
| False positive                           | **Zrefaktoruj stylistycznie** tak, by warning nigdy nie odpalał. Bez ponownego dodawania.                                                                                                   |
| Faktyczne ograniczenie techniczne        | **Dodaj silencer z powrotem z komentarzem klasy incydentu**: DLACZEGO (powód techniczny), KIEDY (pod jakimi warunkami), GDZIE (konkretna ścieżka kodu). Nie „intentional", nie „by design". |
| **Zapomniana perełka (łagodna ścieżka)** | **Nie usuwaj. Zgłoś.** Warning `dead_code` na 200-liniowym module o przemyślanej strukturze to zaparkowana praca. Dodaj do **Raportu Zapomnianych Perełek**. Decyduje operator.             |
| Zdemaskowany teatr testów                | **Stop. To większe niż silencer.** Wzorzec panic-or-skip, który zawsze ewaluuje w jedną stronę, oznacza, że test nigdy nie był prawdziwy. Otwórz osobny plan na realne podpięcie.           |
| Ujawniony naprawdę martwy kod            | Silencer ukrywał `dead_code` na jednolinijkowym stubie lub pliku roboczym. Usuń — ale dopiero po szybkim sprawdzeniu pod kątem zapomnianej perełki.                                         |

Zasada: **silencer zarabia na swoje utrzymanie tylko z pisemnym powodem technicznym, który inny inżynier za pół roku
przyjąłby jako poważny.** Mgliste komentarze „intentional" nie są poważne. Tak samo: **usuwaj kod tylko wtedy, gdy jest
jednoznacznie śmieciem** — wszystko pomiędzy idzie do Raportu Zapomnianych Perełek.

### Raport Zapomnianych Perełek

Wynikiem Fali 5 **nie** jest mniejsze repo — to pisemny raport. Zapisz do
`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_forgotten-gems.md`.

> Zobacz [references/case-studies.md](references/case-studies.md), gdzie znajdziesz pełny szablon Raportu Zapomnianych Perełek, szablon
> raportu teatru testów oraz konkretne realne/hipotetyczne studia przypadków (example-app 0.67.3 silencer-strip, odpowiednik
> billing-service w sample-portal, katalog zaskakujących findingów).

Teatr testów to dług, nie perełka. Zawsze dostaje plan followupu zapisany do `<timestamp>_test-theater.md`. Nigdy przywrócenia
silencera.

### Kryteria akceptacji dla fali

- Pozostała liczba silencerów to **mały ułamek** inwentaryzacji (cel ≤25%, często ≤10%).
- Każdy pozostały silencer niesie komentarz klasy incydentu.
- Każda bramka przechodzi na zielono bez `--no-verify`, `cargo clippy --allow-dirty`, `pnpm lint --fix --quiet` ani żadnego innego triku „
  zazielenić to przez ukrycie".

### Zaskakujące findingi są nagrodą

Wypatruj: testów, które zawsze się skipują / zawsze panikują, allow `dead_code` na funkcjach, których jedyny caller usunięto trzy
release'y temu, `@ts-ignore` na typach poprawnych od roku, `eslint-disable jsx-a11y/...` na prawdziwych naruszeniach a11y,
`nosemgrep: react-dangerouslysetinnerhtml` na HTML-u, który **nie** jest sanityzowany, `# type: ignore[arg-type]` na funkcji,
której sygnaturę naprawiono dwa refactory temu. Każdy z nich to prawdziwy bug albo prawdziwe kłamstwo, które silencer ukrywał.

## Antywzorce

- Usuwanie dziesięciu martwych symboli, podczas gdy cały porzucony podsystem wciąż stoi.
- Ufanie raportom „unused" bez sprawdzenia dynamicznego ładowania przez router frameworka.
- Zachowywanie chaotycznego pliku na 2000 linii, bo „może się przyda" — od tego jest historia Gita.
- Czyszczenie kodu z pozostawieniem nieaktualnych zależności w lockfile'u.
- Selektywne zdejmowanie silencerów. Cały sens Fali 5 to ominięcie tego biasu.
- Masowe przywracanie silencerów, bo było „za dużo warningów". To znów zakopywanie komunikatu.
- Dodawanie nowych silencerów, by wyciszyć świeżo odkryte warningi. Napraw warning albo zrefaktoruj go.
- Traktowanie `panic!("Test requires X")` jak prawdziwej bramki albo `it.skip` / `@pytest.mark.skipif` jak nieszkodliwych. Testy, które
  zawsze się skipują, nie istnieją; kosztują uwagę recenzenta.
- Automatyczne usuwanie kodu, który ukrywał allow `dead_code`, bez wcześniejszego sprawdzenia pod kątem zapomnianej perełki.
- Traktowanie Fali 5 jako konfrontacyjnej. Dawni inżynierowie dodawali silencery z prawdopodobnych powodów. Fala 5 to ponowne czytanie, nie
  wyrok.

## Zasada prune

Nie żądaj od repo, by wyjaśniło każdą bliznę. Żądaj, by uzasadniło każdą przetrwałą powierzchnię.

Jeśli powierzchnia nie działa na produkcji, nie buduje release'u ani nie testuje integralności — ruchem **nie** jest automatycznie
usunięcie. Ruchem jest **zdecydować z intencją**: revive, archive albo delete. Skill istnieje po to, by wydobywać decyzje na powierzchnię, a nie podejmować
je na autopilocie.

**Toolchain to nie wróg do wyciszenia. To świadek do przesłuchania.** Zdejmij wyciszenie. Uruchom bramki.
Słuchaj. Potem zdecyduj — przypadek po przypadku, z pisemnym powodem — co naprawdę zasługuje na milczenie, co potrzebuje prawdziwej
naprawy, a co było zapomnianą perełką ukrytą za silencerem przez cały ten czas.

Repo, które przeszło przez `vc-prune`, niekoniecznie jest mniejsze. Jest **czytelne**. Każda przetrwała powierzchnia, każdy
przetrwały silencer, każdy przetrwały test ma pisemny powód, by tam być. To jest wygrana.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
