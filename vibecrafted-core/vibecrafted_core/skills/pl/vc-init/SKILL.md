---
name: vc-init
version: 4.4.0
description: >
  Technical due diligence before stabilization. The vibe-coding weekend
  got the app to launch. Now we find the taped-together auth, god tables, and silent
  failures. Init equips the agent with Perception (via the MCP-first loctree
  context engine), Intentions (AICX), and Security/Stability Ground Truth.
  Trigger: "init", "initialize", "bootstrap", "daj kontekst", "zainicjuj",
  "przygotuj agenta", "start fresh with context".
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v3 -->

> **Wywołanie dla `vc-init` (launcher `init`)**
>
> Ten sam _kształt_ trzech ścieżek floty, z **literałami tego** skilla — zobacz
> kanoniczną [Matrycę Delegacji](../DELEGATION_MATRIX.md):
>
> - [Wspólne trzy ścieżki](../DELEGATION_MATRIX.md#wspólne-trzy-ścieżki)
> - [Katalog launcherów](../DELEGATION_MATRIX.md#katalog-launcherów-core-runtime)
> - [Reguła per-launcher](../DELEGATION_MATRIX.md#reguła-per-launcher-delta-semantyczna)
> - [Native vs external](../DELEGATION_MATRIX.md#natywne-subagenty-vs-zewnętrzni-workerzy)
>
> | Ścieżka               | Literał tego skilla                                                                                                         |
> | --------------------- | --------------------------------------------------------------------------------------------------------------------------- |
> | 1. Worker użytkownika | `vibecrafted init [agent]` / `vc-init`                                                                                      |
> | 2. Interactive        | `/vc-init` — wykonaj **w tej sesji**; native subagenty gdy trzeba; **nie** zewnętrzniaj tylko dlatego, że launcher istnieje |
> | 3. Agent-operator     | może odpalić formę workera powyżej przez `vc-dispatch` / linie operatora, zachowując tożsamość tego skilla                  |
>
> **Uwaga:** Orientation gate, not a write pipeline. Worker form is `vibecrafted init [agent]`.

> Swobodniejszy native na niektórych biegach ≠ porzucenie floty external. `vc-dispatch` i `vc-ship` zachowują własne tożsamości.

<!-- /fleet-imperative -->

# vc-init — Techniczne due diligence

## Wejście operatora

### Reguła Living Tree / Worktree

Ten workflow działa w bieżącym checkoucie i na bieżącej gałęzi operatora. Nie twórz worktree gita, nie przełączaj się na niego ani nie przenoś do niego wykonania, chyba że operator wprost poprosi o worktree w tym prompcie. Ogólne słowa w stylu „isolate", „parallel" czy „clean branch" to za mało. Jedyny usankcjonowany drugi tryb to dispatch Fleet Worktrees (pisany plan, zacommitowane wcześniej verifiery, rozłączne domeny plików, jednowątkowy integrator — patrz Reguła Living Tree, Tryb B); poza tą formacją zostań we wspólnym drzewie. Czytaj pliki ponownie przed edycją, dostosowuj się do równoległych zmian i zgłoś awarię podłoża (substrate failure), jeśli bieżące drzewo jest zbyt zatrute, by bezpiecznie kontynuować.

Zobacz [Reguła Living Tree](../LIVING_TREE_RULE.md).

## Checkpoint strukturalny

`vc-init` to procedura orientacji, którą konsumuje każdy inny workflow związany z repo.
Nie wchodzi rekurencyjnie w kolejny przebieg init; produkuje prawdę repo, która
odblokowuje `vc-workflow`, `vc-marbles`, `vc-review`, `vc-dou`, `vc-release` oraz
delegowaną pracę agentów.

`Loctree:loctree` jest domyślne dla tej procedury. Zacznij od prawdy strukturalnej,
nie od twierdzeń z README: repo-view, focus, slice, impact, find i follow w odpowiednim zakresie.
Użyj go, aby wygenerować lub odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived
Application Map) przed testami, lintem, Semgrepem, sprawdzeniami release'u, porównaniem
dokumentacji lub klasyfikacją intencji.

Chodzi o znalezienie zaczepów: węzłów nośnych, twins (duplikaty), martwego kodu, dryfu,
entrypointów runtime'u oraz pułapek o dużym zasięgu zmiany. Jeśli Loctree MCP jest
niedostępne, zadeklaruj degradację i przejdź na CLI `loct` lub ręczne śledzenie; nie
udawaj, że odkrywanie tylko przez grep to domyślna mapa.

Standardowy launcher (`vibecrafted start` / `vc-start`, następnie `vc-<launcher> <agent> [--prompt|--file ...]`).
`vc-init` zwykle nie potrzebuje dodatkowego wejścia z taskiem — pomiń `--file`/`--prompt`,
gdy niepotrzebne. Uruchamia się w natywnym trybie interaktywnym, nie w headless `-p` / `exec`.

```bash
vibecrafted init claude
vc-init codex
vibecrafted init agy --prompt 'Bootstrap context for the payments module'
```

Zależności fundamentowe (ładowane wraz z frameworkiem): `vc-loctree`, `vc-aicx`.

> 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚜𝚖𝚊𝚗𝚜𝚑𝚒𝚙 to odpowiedź na porażkę vibe codingu uwięzionego w
> pułapce 80/20 ↔ 20/80. Zobacz [MANIFESTO_EN.md](https://raw.githubusercontent.com/vetcoders/vibecrafted/refs/heads/main/docs/runtime/MANIFESTO_EN.md).
> „Nie hejtuję vibe codingu. Doprowadził cię do launchu... ale founderzy, którzy zbudowali
> w weekend na Cursorze, utknęli. Nie domkną dealów enterprise. Nie przejdą
> security review. Ich integracja ze Stripe działa, dopóki nie przestanie."

Init to **techniczne due diligence**. Jesteśmy tu, żeby stabilizować. Działanie bez
kompletnego wstępnego przeglądu na vibe-codowanej bazie kodu, która złożonością przerosła
połowę agenta logowania Google'a, to szybka droga do katastrofalnej awarii.

Stosujemy aksjomaty Vetcoders: **Percepcja ponad pamięć** oraz **Pozyskiwanie intencji
ponad RAG**. Nie ładujemy na ślepo miliona tokenów historycznego kontekstu — widzimy,
czym kod jest _teraz_, i znajdujemy to, co zepsute na ścieżce krytycznej, zanim dotkniemy
choćby jednej linii.

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli Loctree
zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do `~/.vibecrafted/loctree/loctree-fail.md`.

## Pozycja w pipelinie

Init to pierwsze ważne działanie w każdej sesji. Jakość wykonanej tutaj pracy
wpływa na wszystko, co następuje później.

## Kiedy używać

Wykonaj na początku każdej sesji, **przed jakąkolwiek pracą implementacyjną**:

- **Zimny start** — pierwsza sesja na repo (zero wcześniejszego kontekstu)
- **Wznowienie po przerwie** — stale context po 24+ godzinach nieobecności
- **Delegacja do subagentów** — agenci dziedziczą ustrukturyzowany kontekst
- **Dryf strukturalny** — duże zmiany wprowadzone przez innych od ostatniej sesji

Jeśli kusi cię, żeby pominąć init, bo „to mały task" — to właśnie wtedy init
zapobiega największym szkodom.

---

## Triada staranności

### Zmysł 1 — Intencje (pozyskiwanie przez `aicx intents`)

Wyciągnij historyczny kontekst z poprzednich sesji AI. Szukamy _dlaczego_, nie ślepego
zrzutu _jak_:

- Jaka była pierwotna intencja stojąca za architekturą?
- Jaką prowizorkę nałożono późną nocą, żeby „po prostu zadziałało"?

**Dyscyplina:** AICX to silnik pozyskiwania intencji, nie ślepe działo RAG. Pozyskaj
kontekst decyzji, a potem zweryfikuj ich aktualną prawdziwość w Zmyśle 2.

Masz dostęp do `aicx` (CLI) oraz `aicx-mcp` (stdio + streamable-http). Tryb HTTP
umożliwia pozyskiwanie sesji ze źródeł zdalnych (inne stacje robocze, zdalni agenci) —
nie polegaj wyłącznie na pozyskiwaniu lokalnym, jeśli skonfigurowano zdalny endpoint `aicx-mcp`.

Kluczowe narzędzia MCP: `aicx_rank` (ranguje chunki wg jakości), `aicx_search` (fuzzy search
z normalizacją polskich znaków diakrytycznych), `aicx_steer` (pozyskiwanie filtrowane po
frontmatterze wg run_id/prompt_id/agent/kind/project/date).

CLI: `aicx intents -p <project> --emit json | tee intents.json`, a potem `jq` do
podsumowania. Pełna dokumentacja w skillach `vc-intents` i `vc-aicx` lub `aicx --help`.

### Zmysł 2 — Percepcja (ponad pamięć)

**MCP-first, w kształcie atlasu.** `loctree-mcp` to główny kanał odkrywania dla agenta.
Pojedyncze wywołanie `context()` materializuje Atlas Kontekstu (Context Atlas,
`loctree.context_atlas.v1`) — strukturalny + runtime + ryzyko + następne ruchy +
nakładka AICX — do wersjonowanego cache'u na dysku. Kolejne wywołania to natychmiastowe
odczyty. CLI (`loct ...`) to powierzchnia **operatora** (markdown pill, shell pipes,
interaktywny debugging); agenci współdzielą ten sam silnik przez MCP i mogą używać CLI
**tylko jeśli serwer MCP jest** **niedostępny**.

#### Wywołanie główne

```jsonc
// Single first move — every session
{ "tool": "context", "project": "<repo-root>", "with_aicx": true }
```

MCP **kończy się błędem natychmiast (fail-fast)**, jeśli `<repo-root>` nie ma `.git`.
Atlas materializuje siedem sekcji (sześć kart + `receipt`): core, structural, runtime,
memory-trail, verification-gates, risk-register, receipt. Odpowiedź na poziomie repo
jest niekompletna, dopóki nie odczytano **core + structural + runtime**.

Zawężaj zakres, przekazując `file: "<path>"` (przed edycją), `task: "<text>"` (trafność
semantyczna) lub `changed: true` (WIP Żywego Drzewa). Strażnicy CI: `no_scan`,
`fail_stale`, `fresh`. Pełna mapa parametrów i indeks kart atlasu znajdują się w
[`references/loct-context-engine.md`](references/loct-context-engine.md).

#### Etykiety autorytetu — przeczytaj przed działaniem

`repo_verified` (fakt ze snapshotu, najwyższe zaufanie) · `loctree_derived` (wnioskowanie
analizatora) · `aicx_operator` (trwała intencja operatora) · `aicx_agent` (wynik
poprzedniego agenta) · `aicx_failure` (poprzednia nieudana ścieżka — nie powtarzaj) ·
`semantic_guess` (heurystyka — zweryfikuj) · `stale_or_unknown` (sprawdź ponownie).

#### Drill-down (po atlasie, gdy zakres jest znany)

- `slice(file)` przed edycją · `impact(file)` przed usunięciem/zmianą nazwy ·
  `find(pattern)` zamiast grepa · `follow(scope)` dla dead/cycles/twins/hotspots/trace ·
  `focus(directory)` dla pogłębionej analizy modułu · `query(kind, target)` dla zapytań grafowych.
- Analiza (sygnał, nie orientacja): `health` · `findings` · `audit` · `doctor` ·
  `coverage` · `manifests` · `dist` · `insights`.
- Stronicowanie atlasu: `context_manifest` · `context_section` · `context_next`.

**Odruch Żywego Drzewa:** przed każdym oknem edycji dłuższym niż kilka minut wywołaj
`doctor()`, aby porównać fingerprint z poprzednim wywołaniem. Jeśli się zmienił, ponów
`context(fresh: true)` — tak współbieżni agenci unikają cichego dryfu.

### Zmysł 3 — Twarde fakty (ground truth) ponad intuicję

#### 3a. Wyprowadź konwencje z historii gita

Uruchom kanoniczny helper:

```bash
zsh -ic repo-full
```

Daje głęboki stan wykraczający poza `git log` / `git status`. Fallback:
`git log --oneline --decorate --graph -n 15` i `git status -sb`.

**Fokus due diligence:**

- Schemat Prisma/SQL z 35-kolumnową „User" God Table i zerową liczbą indeksów?
- NextAuth/Clerk, gdzie każdy jest „admin" albo „user" bez zabezpieczeń na poziomie wiersza?
- Pliki `.env` śledzone w gicie?

#### 3b. Wchłoń istniejące konfiguracje agentów

- Przeczytaj `.claude/CLAUDE.md`, `.gemini/GEMINI.md`, `.codex/AGENTS.md`.
- Przeczytaj `AGENTS.md` — domyślna referencja międzynarzędziowa.
- Zweryfikuj względem kodu. Jeśli konfiguracja deklaruje komendę sprzeczną z aktualnym
  kodem, zaufaj kodowi i zaktualizuj pliki agentów.

#### 3c. Poluj na myliki przed aktualizacją dokumentacji

**Mylik** to prawdopodobne błędne odczytanie, które powoduje dryf dokumentacji:
przeniesienie prawdziwego stwierdzenia z jednego aktora/warstwy/runtime'u w miejsce,
gdzie nie jest już prawdziwe.

Zanim zmienisz dokumentację, notatki o topologii, runbooki lub `AGENTS.md`,
rozdziel:

- **aktor** — operator, zespawnowany agent, użytkownik aplikacji, CI, instalator, runtime
- **funkcja** — admin UI, ingestia DSN/zdarzeń, lokalny helper, ścieżka deploya, fallback
- **zakres** — publiczny Internet, tailnet, lokalna maszyna, checkout źródeł, instalacja staged
- **źródło prawdy** — kod, wygenerowany szablon, wdrożony env, żywy endpoint, artefakt runtime'u

Ten sam URL/komenda/plik w dwóch rolach → nie scalaj. Ścieżki fallbackowe operatora to
nie ścieżki runtime'u aplikacji. Placeholdery w szablonach to nie wdrożone wartości.
Ścieżka w kodzie to nie twierdzenie o topologii, dopóki nie potwierdzi tego live/runtime.

### Zmysł 4 — Bramki jakości (opcjonalnie)

Vibecraftsmanship głęboko zależy na bramkach jakości, ale **nie** uruchamiają się one
na initcie. Init to punkt wejścia dla nadchodzących tasków; bramki uruchamiają się jako
część wykonania taska. Uruchamianie ich przy bootstrapie marnuje czas i zasoby.

Referencja na przyszłość (wkrótce): skille fundamentowe `vc-gates` i `vc-tdd`.

Jeśli używasz instrumentów testowych przed cięciem, zlokalizuj komendy bramek projektu
i zapisz wyniki:

```bash
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
cargo clippy --workspace -- -D warnings 2>&1 | tail -5
```

Zielony zestaw testów na zepsutej architekturze to tylko szybszy pociąg na złych torach.
Prawda strukturalna bije sztuczne sprawdzenia.

## Polityka `.env`

- Nigdy nie commituj plików `.env` do kontroli wersji.
- Warianty `.env*` (`.env.local`, `.env.production`, ...) dodane do `.gitignore`.
- Utwardzone hooki pre-commit / pre-push blokują przypadkowe commity `.env`.
- Bezpośrednie, otwarte raportowanie wycieków zmiennych env → szybki revoke / mitygacja.
- Pracujemy z plikami `.env` **lokalnie** bez lęku; wahanie przy lokalnym użyciu to samo
  w sobie przyszła podatność bezpieczeństwa (workflow degenerują się wokół tego).

---

## Antywzorce

- Rozpoczynanie implementacji bez uruchomienia initu (ślepe kodowanie)
- Ogłaszanie weekendowej architektury MVP jako „production-ready" bez weryfikacji
- Zakładanie, że Auth obsługuje przypadki brzegowe w stylu wygaśnięcia tokenu
- Pisanie „uruchom pytest" bez faktycznego uruchomienia pytest (niezweryfikowane twierdzenia)
- Commitowanie `.env` przy jednoczesnym wahaniu się przed lokalną pracą z nim, bo „ryzyko bezpieczeństwa"
- Sięganie po kaskadę `repo-view` + `tree` + `focus`, gdy jedno wywołanie `context()`
  materializuje ten sam atlas plus ryzyko, akcję, autorytet i nakładkę AICX
- Grepowanie lub `find -name` przed wywołaniem `context()` / `find()` —
  etykiety autorytetu i odwrotne zależności (reverse deps) przepadają w momencie ominięcia atlasu
- Traktowanie pustych kart `structural` / `runtime` jako zepsutych — to atlas
  mówi ci, żeby zawęzić zakres przez `file:` lub `task:`
- Pomijanie `doctor()` / sprawdzenia fingerprintu podczas długich edycji Żywego Drzewa —
  koordynacja wieloagentowa cicho się sypie, gdy fingerprinty rozjeżdżają się pod tobą
- Wywoływanie `loct ...` z shella przez agenta dla funkcji, które MCP już
  udostępnia — split-brain między powierzchniami agenta i operatora, utracona proweniencja

---

_„Percepcja. Intencje. Twarde fakty. Wtedy — i dopiero wtedy — stabilizuj."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
