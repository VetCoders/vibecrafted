# Artifact pack prview — pełny layout i referencja flag

## Ścieżki wyjściowe

```
$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/<timestamp>/
$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest      # symlink to newest
```

Zawsze wybieraj **najnowszy** `<timestamp>`. Pusty lub brakujący katalog → finding **P0**.

## Pełny layout katalogów

```
<timestamp>/
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

Uwaga: niektóre przebiegi mają duplikaty w podkatalogu `artifacts/` — preferuj pliki w roocie.

## Pełna referencja flag

| Flaga                  | Co robi                                              |
| ---------------------- | ---------------------------------------------------- |
| `--quick`              | Pomija testy/lint/bundle/heurystyki; tylko triage    |
| `--deep`               | Wszystkie sprawdzenia włączone                       |
| `--ci`                 | Tryb CI (ścisły exit)                                |
| `--pr N`               | Analizuje GitHub PR #N                               |
| `--gh-repo owner/repo` | Jawne repo dla --pr                                  |
| `--with-tests`         | Włącza runner testów                                 |
| `--with-lint`          | Włącza lintery                                       |
| `--with-security`      | Włącza cargo geiger                                  |
| `--update`             | Inkrementalna regeneracja                            |
| `--json`               | Wyjście JSON                                         |
| `-q, --quiet`          | Minimalne wyjście                                    |
| `--tui`                | Interaktywne TUI                                     |
| `--watch`              | Monitoruje + regeneruje przy zmianach                |
| `-R, --remote`         | Gałąź zdalna, bez checkoutu                          |
| `--no-fetch`           | Pomija git fetch                                     |
| `--no-cache`           | Wyłącza cache'owanie sprawdzeń                       |
| `--no-zip`             | Pomija tworzenie ZIP                                 |
| `--soft-exit`          | Zawsze kończy z exit 0                               |
| `--profile <P>`        | Wymusza profil języka (rust/js/python/mixed/generic) |
| `--policy-mode <M>`    | Nadpisuje politykę (shadow/warn/block)               |
| `--breaking-change`    | Oznacza PR jako breaking                             |
| `-v, --verbose`        | Wyjście szczegółowe                                  |

Istnieją aliasy shellowe (`prv`, `prvpr`, `prvjson`), ale vc-review nie powinien używać szybkich aliasów dla wyjścia o jakości review.

## Referencja trybów

| Komenda                                         | Cel                                                             |
| ----------------------------------------------- | --------------------------------------------------------------- |
| `prview --pr <NUMBER>`                          | Najczęstszy: lokalny branch HEAD vs develop/main                |
| `prview -R --remote-only <branch> <base>`       | Gałąź zdalna, bez checkoutu                                     |
| `prview --pr <NUMBER> --with-tests --with-lint` | GitHub PR po numerze                                            |
| `prview --deep`                                 | Wszystkie bramki                                                |
| `prview --ci`                                   | Tryb CI: wszystkie sprawdzenia, bez koloru, exit 1 przy porażce |
| `prview --json --quiet`                         | JSON do automatyzacji / pipe'owania jq                          |
| `prview --update`                               | Inkrementalnie: regeneruje tylko zmienione artefakty            |
| `prview --tui`                                  | Interaktywny UI terminalowy                                     |
| `prview feat/x develop main`                    | Jawne gałęzie target + base                                     |

## Profile

Wykrywane automatycznie. Nadpisz przez `--profile <PROFILE>`.

| Profil  | Wykrywanie                    | Sprawdzenia                                   |
| ------- | ----------------------------- | --------------------------------------------- |
| rust    | Cargo.toml                    | cargo test, clippy, cargo audit, cargo geiger |
| js      | package.json + pliki źródłowe | vitest, eslint, tsc, pnpm build               |
| python  | pyproject.toml                | pytest, ruff, mypy                            |
| mixed   | wykryto wiele                 | wszystkie mające zastosowanie                 |
| generic | fallback                      | podstawowa analiza plików                     |

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

Nadpisanie z CLI: `--policy-mode block`

Tryby:

- **shadow**: nigdy nie blokuje (tylko obserwowalność)
- **warn**: blokuje wyłącznie przy porażkach o severity `block`
- **block**: blokuje przy porażkach o severity `block` ORAZ `warn`

## Przypadki specjalne (findingi narzędziowe)

- **Panic cargo geiger** (`Matching variant not found`) = narzędzie/błąd konfiguracji (wrażliwe na wielkość liter `--output-format`). → P1 [TOOLING], jeśli blokuje sygnał jakości. Rekomendacja: napraw flagę lub przypnij/zaktualizuj.
- **Timeouty / „killed"** dla tsc trace / eslint json: → P2 [TOOLING] (brak sygnału jakości). Rekomendacja: zwiększ timeout lub wyłącz z uzasadnieniem.
- **Niespójności bramek**: `MERGE_GATE.json` mówi „All checks passed", ale istnieją WARN/findingi → P2 [TOOLING]. Rekomendacja: rozróżnij „All blocking checks passed" vs „Non-blocking issues present".
- **Dryf gałęzi**: pliki zmienione poza scope PR-a (CI, infra, niezwiązany config) → P1 przy >10 plikach. Rekomendacja: zrób rebase na gałęzi bazowej.

## Integracja ze Screenscribe

vc-review może analizować nagrania screencastów obok diffów kodu, gdy Screenscribe jest dostępny jako narzędzie fundamentowe. Użyj do:

- Przeglądu zachowania runtime (wizualne potwierdzenie tego, co kod robi)
- Analizy demo buga (narracyjne nagrania ekranu → ustrukturyzowane findingi)
- Przebiegów review UX (screencast flow użytkownika → problemy UX z poziomem P)

Screenscribe jest opcjonalny. Jeśli nie jest zainstalowany, vc-review operuje wyłącznie na artefaktach kodu.
