---
name: vc-prview
description: >
  Bounded PR, branch, commit-range, or artifact-pack review pipeline: generate
  prview-rs artifacts then produce a findings-max audit. Use when the user asks
  to "review PR", "analyze branch", "run prview", "sprawdź PR", "zrób review",
  "audit PR", "daj findings", "zbadaj branch", "artifact pack", "PR quality
  check", "merge gate", "findings-max", "deep review", or needs structured diff
  artifacts with line-level analysis for AI review pipelines.
metadata:
  short-description: "Generate + audit PR artifacts, findings-max (v1)"
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# vc-prview — Ograniczony pipeline review (generowanie + audyt)

Skill dwufazowy: **Faza 1** generuje ustrukturyzowane artefakty przez prview-rs,
**Faza 2** wyciska z nich maksimum findingów. Wyjście: findingi z poziomami P
i z evidence + checklista TODO przed mergem.

## Checkpoint orientacji

Zanim użyjesz artefaktów prview jako prawdy o release'ie lub mergu, uruchom lub
skonsumuj procedurę `vc-init` dla przydzielonego repo. `Loctree:loctree` to
domyślny skill do mapowania struktury repo dla tego przebiegu i musi wyprodukować lub
odświeżyć Mapę Aplikacji Wyprowadzoną z Kodu (Code-Derived Application Map).

Jeśli brakuje świeżego evidence z `vc-init`, najpierw wykonaj przebieg init i
traktuj wnioski z review jako zablokowane, dopóki nie ma aktualnej prawdy repo.

Użyj Loctree do zidentyfikowania plików nośnych i zasięgu zmiany; użyj prview do
zaudytowania żądanego diffa lub artifact packa względem tej aktualnej struktury.

Binarka: `prview` (zainstalowana w `~/.cargo/bin/prview`)
Źródło: `https://github.com/LibraxisAI/prview-rs`
Autor: Vetcoders

---

## Doktryna pracy z repozytorium

W pracy z repozytorium zacznij od Loctree jako mapy: użyj `loct context`,
`loct occurrences`, `loct body` i `loct find --literal` przed szerokim ręcznym
przeszukiwaniem. Używaj AICX do kontekstu intencji i sesji. Używaj rg/grep jako
fallbacku lub lokalnej lupy, nie jako zamiennika mapowania strukturalnego. Jeśli
Loctree zawiedzie lub przeoczy jakąś powierzchnię, dopisz feedback do
`~/.vibecrafted/loctree/loctree-fail.md`.

## Faza 1 — Generowanie artefaktów

### Najczęstszy przypadek: review lokalnej gałęzi

```bash
prview --pr <NUMBER>
```

Analizuje HEAD bieżącej gałęzi vs develop/main. Szybkie (<20s). Najlepsze do
codziennej pracy.

### Zdalna gałąź (bez checkoutu)

```bash
prview -R --remote-only <branch> <base>
```

- `<branch>`: nazwa bez `origin/` (np. `feat/x`)
- `<base>`: domyślnie `develop`

Ścieżki fallbackowe:

- `~/Git/prview-rs/target/release/prview -R --remote-only <branch> <base>`
- `prview --use-bash-full -R --remote-only <branch> <base>` (mostek kompatybilności)

### PR z GitHuba po numerze

```bash
prview --pr <NUMBER> --with-tests --with-lint
```

Dodaj `--gh-repo owner/repo`, jeśli origin jest niejednoznaczny.

Domyślnie dla tego skilla: **nie używaj `--quick` do review PR-a**.
Używaj `--quick` tylko do jawnego szybkiego triage'u, odświeżenia artefaktów pod
presją czasu albo gdy ciężkie bramki są niemożliwe w bieżącym środowisku.

### Deep review (wszystkie bramki)

```bash
prview --deep
# albo selektywnie:
prview --with-tests --with-lint --with-security
```

### Inne tryby

| Komenda                      | Cel                                                             |
| ---------------------------- | --------------------------------------------------------------- |
| `prview --ci`                | Tryb CI: wszystkie sprawdzenia, bez koloru, exit 1 przy porażce |
| `prview --json --quiet`      | Wyjście JSON do automatyzacji / pipowania przez jq              |
| `prview --update`            | Inkrementalnie: regeneruj tylko zmienione artefakty             |
| `prview --tui`               | Interaktywny terminalowy UI                                     |
| `prview feat/x develop main` | Jawny target + gałęzie bazowe                                   |

### Referencja flag

| Flaga                  | Co                                                 |
| ---------------------- | -------------------------------------------------- |
| `--quick`              | Pomiń testy/lint/bundle/heurystyki; tylko triage   |
| `--deep`               | Wszystkie sprawdzenia włączone                     |
| `--ci`                 | Tryb CI (ścisły exit)                              |
| `--pr N`               | Analizuj PR #N z GitHuba                           |
| `--gh-repo owner/repo` | Jawne repo dla --pr                                |
| `--with-tests`         | Włącz runner testów                                |
| `--with-lint`          | Włącz lintery                                      |
| `--with-security`      | Włącz cargo geiger                                 |
| `--update`             | Inkrementalna regeneracja                          |
| `--json`               | Wyjście JSON                                       |
| `-q, --quiet`          | Minimalne wyjście                                  |
| `--tui`                | Interaktywny TUI                                   |
| `--watch`              | Monitoruj + regeneruj przy zmianach                |
| `-R, --remote`         | Zdalna gałąź, bez checkoutu                        |
| `--no-fetch`           | Pomiń git fetch                                    |
| `--no-cache`           | Wyłącz cache'owanie sprawdzeń                      |
| `--no-zip`             | Pomiń tworzenie ZIP-a                              |
| `--soft-exit`          | Zawsze exit 0                                      |
| `--profile <P>`        | Wymuś profil języka (rust/js/python/mixed/generic) |
| `--policy-mode <M>`    | Nadpisz politykę (shadow/warn/block)               |
| `--breaking-change`    | Oznacz PR jako breaking                            |
| `-v, --verbose`        | Wyjście verbose                                    |

Istnieją aliasy shellowe (`prv`, `prvpr`, `prvjson`), ale ten skill nie powinien
używać szybkich aliasów do wyjścia o jakości review.

---

## Układ artifact packa

Wyjście: `.tools/pr-artifacts/<branch>/<timestamp>/`
Symlink: `.tools/pr-artifacts/<branch>/latest`

Zawsze wybieraj **najnowszy** `<timestamp>`. Pusty lub brakujący katalog → **P0**.

```
.tools/pr-artifacts/<branch>/<timestamp>/
├── dashboard.html                # Interactive HTML report
├── AI_INDEX.md                   # Artifact map + suggested reading order
├── report.json                   # Canonical structured report (PARSE FIRST)
├── 00_summary/
│   ├── MERGE_GATE.json           # Machine-readable merge decision
│   ├── MERGE_GATE.md             # Human-readable merge decision
│   ├── RUN.json                  # Run metadata (timing, config, version)
│   ├── MANIFEST.json             # SHA256 hashes of all generated files
│   ├── SANITY.json               # Post-generation integrity checks
│   ├── pr-metadata.txt           # Branch/base/profile metadata
│   ├── file-status.txt           # A/M/D + file paths
│   └── commit-list.txt           # hash date author message
├── 10_diff/
│   ├── full.patch                # Full diff with diff-stat header
│   ├── per-commit-diffs/         # Batched commit patches + 00-SUMMARY.md
│   └── per-file-diffs/           # Hotspot files (>80 lines changed) + 00-INDEX.txt
├── 20_quality/
│   ├── <gate>.result.json        # Per-gate result + provenance
│   ├── <gate>.log                # Per-gate raw output
│   ├── full-checks.log           # All check output concatenated
│   ├── checks-errors.log         # Filtered: errors/warnings only (±2 context)
│   ├── coverage-delta.txt        # Source↔test mapping with change status
│   └── BREAKING_CHANGES.md       # Removed pub symbols, changed signatures
├── 30_context/
│   ├── INLINE_FINDINGS.sarif     # Machine-readable SARIF findings
│   ├── changed-tests.txt         # Test files modified in this PR
│   └── <tooling>.txt             # cargo-tree, tsc-trace, etc.
└── artifacts.zip                 # Everything zipped
```

Uwaga: niektóre przebiegi mają duplikaty w podkatalogu `artifacts/` — preferuj
pliki w roocie.

---

## Faza 2 — Analiza artefaktów (Findings-Max)

### Filozofia

Tryb: **Findings-max**. Nie kończ na "kilku punktach". Jeśli widać 25 osobnych
problemów, wypisz 25. Lepiej 20 celnych findingów niż 5 ogólników.

Każdy finding MUSI mieć:

- **Dowód**: artefakt + ścieżka (najlepiej 1–2 linie z patcha/logu)
- **Komentarz**: dlaczego to ważne (1 zdanie) + co grozi
- **Rekomendacja**: co zrobić / jak zweryfikować

Zasady:

- Nie łącz różnych tematów w 1 punkt. Jeden punkt = jeden problem.
- Jeśli czegoś nie da się potwierdzić z artefaktów: oznacz **[VERIFY]**.
- Rozdzielaj: **problem w kodzie** vs **problem narzędzia [TOOLING]**.

### Skala poziomów P

| P-level | Definicja                                                          | Przykłady                                                              |
| ------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| **P0**  | Blocker merge / security / data loss / failing blocking check      | Failing tsc, leaked credentials, missing artifacts                     |
| **P1**  | Wysoki risk regresji w core flow, niekompatybilne zmiany kontraktu | Breaking API, duże zmiany bez testów, import cycles in critical module |
| **P2**  | Średni risk: edge-cases, a11y, telemetria, częściowy brak testów   | Missing i18n keys, hardcoded URLs, no error handling on external call  |
| **P3**  | Niskie ryzyko / higiena / drobne niespójności                      | Empty doc titles, test setup duplication, cosmetic naming              |

---

## Kolejność czytania (Obowiązkowy)

Czytaj artefakty w tej kolejności. Dla każdego: co wyciągnąć.

### 1) `AI_INDEX.md` (jeśli istnieje)

- Zweryfikuj, czy wskazuje na prawdziwe ścieżki. Kłamliwy indeks → finding P3 [TOOLING].

### 2) `report.json` (domyślne źródło prawdy)

- `meta`: PR url, branch, base
- `gate`: allow_merge + policy_mode + reasons
- `checks[]`: status (PASS/WARN/FAIL/ERROR), log_path, command
- `diff.stats` + `diff.files[]`: skala, churn, hotspoty, patch_path
- `quality`: breaking / coverage / sarif / heuristics

### 3) `00_summary/MERGE_GATE.json` + `SANITY.json`

- Sprawdź krzyżowo z `report.json`. Niespójność → finding P2 [TOOLING].
- Uwaga: "All checks passed" przy obecnym WARN/INLINE_FINDINGS = mylące.

### 4) `00_summary/pr-metadata.txt` + `file-status.txt` + `commit-list.txt`

- Scope: ile plików, jakie kategorie (A/M/D), progresja commitów
- Wypatruj dryfu gałęzi (pliki infra spoza scope'u PR-a)

### 5) `30_context/INLINE_FINDINGS.sarif`

- Każdy wynik SARIF = gotowy finding. Przenieś wszystkie na listę findingów.

### 6) `20_quality/*` (logi + wyniki)

- Bramki PASS: wyciągnij warningi z logów (cargo warns, tsc non-errors)
- Bramki WARN/ERROR/FAIL: przyczyna źródłowa + rekomendacja
- `checks-errors.log`: przefiltrowane błędy o wysokim sygnale
- `BREAKING_CHANGES.md`: oceń realną wagę (P?)
- `coverage-delta.txt`: oflaguj krytyczne wpisy "NO_TEST_CHANGE"

### 7) `30_context/changed-tests.txt`

- Skonfrontuj ze zmianami w źródłach — nieprzetestowane pliki źródłowe → finding

### 8) Diffy (selektywnie, nie wyczerpująco)

- `10_diff/per-file-diffs/00-INDEX.txt` → pliki o największym churnie
- Patche per plik dla hotspotów
- `10_diff/per-commit-diffs/00-SUMMARY.md` → commity o największym wpływie
- Batche per commit do analizy na poziomie linii

---

## Obowiązkowe skany wzorców

W patchach per plik i/lub w `full.patch` przeskanuj te wzorce:

### Rust

- `.unwrap()`, `.expect(` — nieobsłużone paniki
- `panic!`, `todo!` — niekompletny kod
- `unsafe` — sprawdź uzasadnienie
- `dbg!`, `println!` — pozostałości po debugu
- `#[allow(` — wyciszone warningi

### TypeScript / JavaScript

- `any` — ucieczka od typów
- `as unknown as` — podwójny cast (pranie typów)
- `@ts-ignore`, `@ts-expect-error` — wyciszanie typów
- `eslint-disable` — wyciszanie linta
- `// TODO`, `// FIXME`, `// HACK` — odłożona robota
- Puste `catch {}` lub `catch (e) {}` bez logu/rethrow
- Asercja non-null `!` na niepewnych wartościach
- `console.log`, `console.warn`, `console.error` — powinno używać secureLogger (example-app)

### Security / PII

- Logowanie tokenów, e-maili, haseł, ID osobowych
- Nowe zdarzenia telemetrii bez privacy review
- Nowe endpointy / handlery komend bez sprawdzeń auth
- Hardkodowane URL-e, klucze API, sekrety

### Dane / Wydajność

- Query w pętli (N+1)
- Brak batchowania operacji masowych
- Duże payloady bez paginacji
- Niepotrzebne I/O na gorących ścieżkach

Każde "trafienie" w diffie = potencjalny finding z evidence.

---

## Minimalne wymagania pokrycia

Żeby zapobiec lakonicznym raportom:

- **Wszystkie** wpisy w `INLINE_FINDINGS.sarif`
- **Top 10** plików wg churnu (z `report.json` lub `file-status.txt`) — przeczytaj patch per plik
- **Wszystkie** pliki w kluczowych kategoriach ryzyka (po ścieżce): auth, payments, database, session, security, encryption, middleware
- **Wszystkie** krytyczne wpisy "NO_TEST_CHANGE" z `coverage-delta.txt`
- **Wszystkie** wpisy w `BREAKING_CHANGES.md` z ocenionym poziomem P
- **Progresja per commit** dla PR-ów z >5 commitami — zidentyfikuj fazy, ryzykowne przejścia

---

## Przypadki specjalne (Tooling)

### Panika Cargo Geiger

`Matching variant not found` = tooling/misconfig (case-sensitive `--output-format`).
→ Finding **P1 [TOOLING]**, jeśli blokuje sygnał jakości. Rekomendacja: napraw flagę albo przypnij/zaktualizuj.

### Timeouty / "killed"

`killed (>timeout)` dla tsc trace / eslint json:
→ Finding **P2 [TOOLING]** (brakujący sygnał jakości). Rekomendacja: zwiększ timeout albo wyłącz z uzasadnieniem.

### Niespójności bramki

`MERGE_GATE.json` mówi "All checks passed", ale istnieją WARN/findingi:
→ Finding **P2 [TOOLING]** z rekomendacją: "All blocking checks passed" vs "Non-blocking issues present".

### Dryf gałęzi

Pliki zmienione poza scope'em PR-a (CI, infra, niezwiązany config):
→ Finding **P1**, jeśli >10 plików. Rekomendacja: rebase na gałąź bazową.

---

## Format wyjścia (Obowiązkowy)

Finalne wyjście ZAWSZE ma te 2 obowiązkowe sekcje (w tej kolejności):

### 1) Findingi (P0/P1/P2/P3)

Każdy finding w tym formacie:

```
- **[P?] <Title>** (opcjonalnie: [VERIFY] lub [TOOLING])
  - **Evidence:** `<artifact-path>` + `<file:line>` + krótki fragment (1-2 linie)
  - **Komentarz:** 1 zdanie o ryzyku/wpływie
  - **Rekomendacja:** konkretne "co zrobić" / "jak zweryfikować"
  - **Owner:** `author` / `reviewer` / `infra` (opcjonalnie)
```

Numeruj findingi do odsyłaczy krzyżowych: P1-01, P1-02, P2-01 itd.

### 2) TODO przed mergem (markdownowe checkboxy)

```markdown
- [ ] **(P0)** ... (ref: P0-01)
- [ ] **(P1)** ... (ref: P1-01, P1-02)
- [ ] **(P2)** ... (ref: P2-01)
- [ ] **(P3)** ... (ref: P3-01)
```

Każde TODO odsyła do ID findingów. Dołączaj komendy weryfikacyjne w code fence'ach tam, gdzie to zasadne.

### 3) Sekcje opcjonalne (zalecane)

Dodaj, gdy wnoszą wartość:

- **Executive Summary** (max 8 punktów): verdict bramki, top 3 ryzyka, sygnał testów, najważniejsze hotspoty, delta scope'u
- **Architecture Context**: diagram lub opis dotkniętego podsystemu
- **Scope / Co się zmieniło**: na bazie `diff.stats` + topowe katalogi + topowe pliki
- **Progresja commitów**: fazy pracy dla PR-ów wielocommitowych
- **Macierz pokrycia testami**: plik źródłowy → plik testowy → liczba nowych testów
- **Security & Privacy Check**: PII w logach, przepływy danych, filtrowanie zdarzeń
- **QA Plan**: 5-15 rekomendacji testów manualnych + automatycznych
- **Evidence Index**: linki do kluczowych użytych artefaktów

---

## System polityk

Utwórz `.prview-policy.yml` w roocie repo:

```yaml
version: 1
mode: warn # shadow | warn | block
default_severity: warn
checks:
  cargo_audit: block
  vitest: warn
  eslint: ignore
```

Nadpisanie w CLI: `--policy-mode block`

Tryby:

- **shadow**: nigdy nie blokuje (tylko obserwowalność)
- **warn**: blokuje tylko przy porażkach o severity `block`
- **block**: blokuje przy porażkach o severity `block` ORAZ `warn`

---

## Profile

Auto-wykrywane z zawartości repo. Nadpisanie: `--profile <PROFILE>`.

| Profil  | Wykrywanie                    | Sprawdzenia                                   |
| ------- | ----------------------------- | --------------------------------------------- |
| rust    | Cargo.toml                    | cargo test, clippy, cargo audit, cargo geiger |
| js      | package.json + pliki źródłowe | vitest, eslint, tsc, pnpm build               |
| python  | pyproject.toml                | pytest, ruff, mypy                            |
| mixed   | wykryto kilka                 | wszystkie pasujące                            |
| generic | fallback                      | podstawowa analiza plików                     |

---

## Vibecrafted. Integracja z pipelinem

### Jako wejście do vc-followup

```bash
prview --pr $PR_NUMBER --with-tests --with-lint
ARTIFACTS=".tools/pr-artifacts/<branch>/latest"
```

### Kontekst delegacji do subagenta

```
## Context Bootstrap
- prview artifacts at: .tools/pr-artifacts/<branch>/latest/
- Parse report.json first (default)
- Read 00_summary/MERGE_GATE.json for quick verdict
- Read 20_quality/checks-errors.log for error details
- Read 10_diff/per-file-diffs/ for hotspot patches
```

### Pipeline JSON

```bash
prview --json --quiet | jq '.checks[] | select(.status == "Failed")'
```

---

## Antywzorce

### Użycie narzędzia

- Używanie `--quick` jako domyślnego do review PR-a w tym skillu (gubi sygnał test/lint/security)
- Odpalanie `--deep` na każdym PR-ze, gdy `--with-tests --with-lint` wystarcza (zostaw `--deep` na merge gate / PR-y wysokiego ryzyka)
- Czytanie całego `full.patch` przy dużych PR-ach (użyj `per-file-diffs/` do skupionego review)
- Ignorowanie `report.json` i `MERGE_GATE.json` (najpierw parsuj dane ustrukturyzowane)
- Niekorzystanie z `--update` po amendzie/force-pushu (generuje zduplikowane zestawy artefaktów)
- Uruchamianie bez `--no-fetch` na wolnych sieciach

### Analiza

- Zatrzymywanie się na 5 findingach, gdy widać 25 (findings-max znaczy wyczerpująco)
- Findingi bez evidence (każdy punkt potrzebuje ścieżki artefaktu + fragmentu kodu)
- Mieszanie osobnych problemów w jeden finding (jeden punkt = jeden problem)
- Ignorowanie problemów narzędziowych (crash narzędzia ≠ problem kodu, ale wciąż finding)
- Pomijanie skanów wzorców (checklista `.unwrap()` / `any` / PII jest obowiązkowa)
- Brak skonfrontowania coverage-delta ze zmienionymi plikami źródłowymi

---

_Created by Vetcoders (c)2026_
