---
name: vc-review
version: 1.0.0
description: >
  Full PR review pipeline: generate prview-rs artifacts then produce a findings-max
  audit. Use when the user asks to "review PR", "analyze branch", "run prview",
  "sprawdź PR", "zrób review", "audit PR", "daj findings", "zbadaj branch",
  "artifact pack", "PR quality check", "merge gate", "findings-max", "deep review",
  or needs structured PR artifacts with line-level analysis for AI review pipelines.
---

# vc-review — Code Review Pipeline (Generate + Audit)

Two-phase skill: **Phase 1** generates structured artifacts with prview-rs,
**Phase 2** squeezes maximum findings from them. Output: P-leveled findings
with evidence + before-merge TODO checklist.

Binary: `prview` (resolve via `command -v prview`; do not assume cargo path)
Source: `https://github.com/VetCoders/prview-rs`
Author: Monika (@m-szymanska) — VetCoders

---

## Phase 1 — Generate Artifacts

### Most common: local branch review

```bash
prview --pr <NUMBER>
```

Analyzes current branch HEAD vs develop/main. Fast (<20s). Best for daily work.

### Remote branch (no checkout needed)

```bash
prview -R --remote-only <branch> <base>
```

- `<branch>`: name without `origin/` (e.g. `feat/x`)
- `<base>`: defaults to `develop`

### GitHub PR by number

```bash
prview --pr <NUMBER> --with-tests --with-lint
```

Add `--gh-repo owner/repo` if origin is ambiguous.

Default for this skill: **do not use `--quick` for PR review**.
Use `--quick` only for explicit fast triage, artifact refresh under time pressure,
or when heavy gates are impossible in the current environment.

### Deep review (all gates)

```bash
prview --deep
# or selective:
prview --with-tests --with-lint --with-security
```

### Other modes

| Command                      | Purpose                                          |
| ---------------------------- | ------------------------------------------------ |
| `prview --ci`                | CI mode: all checks, no color, exit 1 on failure |
| `prview --json --quiet`      | JSON output for automation / jq piping           |
| `prview --update`            | Incremental: only regenerate changed artifacts   |
| `prview --tui`               | Interactive terminal UI                          |
| `prview feat/x develop main` | Explicit target + base branches                  |

### Flag Reference

| Flag                   | What                                                  |
| ---------------------- | ----------------------------------------------------- |
| `--quick`              | Skip tests/lint/bundle/heuristics; triage only        |
| `--deep`               | All checks enabled                                    |
| `--ci`                 | CI mode (strict exit)                                 |
| `--pr N`               | Analyze GitHub PR #N                                  |
| `--gh-repo owner/repo` | Explicit repo for --pr                                |
| `--with-tests`         | Enable test runner                                    |
| `--with-lint`          | Enable linters                                        |
| `--with-security`      | Enable cargo geiger                                   |
| `--update`             | Incremental regeneration                              |
| `--json`               | JSON output                                           |
| `-q, --quiet`          | Minimal output                                        |
| `--tui`                | Interactive TUI                                       |
| `--watch`              | Monitor + regenerate on changes                       |
| `-R, --remote`         | Remote branch, no checkout                            |
| `--no-fetch`           | Skip git fetch                                        |
| `--no-cache`           | Disable check caching                                 |
| `--no-zip`             | Skip ZIP creation                                     |
| `--soft-exit`          | Always exit 0                                         |
| `--profile <P>`        | Force language profile (rust/js/python/mixed/generic) |
| `--policy-mode <M>`    | Override policy (shadow/warn/block)                   |
| `--breaking-change`    | Mark PR as breaking                                   |
| `-v, --verbose`        | Verbose output                                        |

Shell aliases exist (`prv`, `prvpr`, `prvjson`), but this skill should not use
the quick aliases for review-quality output.

---

## ScreenScribe Integration

vc-review can analyze screencast recordings alongside code diffs when
ScreenScribe is available as a foundation tool. Use this for:

- Runtime behavior review (visual confirmation of what the code does)
- Bug demo analysis (narrated screen recordings -> structured findings)
- UX review passes (screencast of user flow -> P-leveled UX issues)

ScreenScribe is optional. If not installed, vc-review operates on code
artifacts only.

---

## Artifact Pack Layout

Output: `$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/<timestamp>/`
Symlink: `$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest`

Always select the **newest** `<timestamp>`. Empty or missing directory → **P0**.

```
$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/<timestamp>/
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

Note: some runs have duplicates in `artifacts/` subdir — prefer files in root.

---

## Phase 2 — Analyze Artifacts (Findings-Max)

### Philosophy

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

### P-Level Scale

| P-level | Definicja                                                          | Przykłady                                                              |
| ------- | ------------------------------------------------------------------ | ---------------------------------------------------------------------- |
| **P0**  | Blocker merge / security / data loss / failing blocking check      | Failing tsc, leaked credentials, missing artifacts                     |
| **P1**  | Wysoki risk regresji w core flow, niekompatybilne zmiany kontraktu | Breaking API, duże zmiany bez testów, import cycles in critical module |
| **P2**  | Średni risk: edge-cases, a11y, telemetria, częściowy brak testów   | Missing i18n keys, hardcoded URLs, no error handling on external call  |
| **P3**  | Niskie ryzyko / higiena / drobne niespójności                      | Empty doc titles, test setup duplication, cosmetic naming              |

---

## Reading Order (Obowiązkowy)

Read artifacts in this order. For each: what to extract.

### 1) `AI_INDEX.md` (if exists)

- Verify it points to real paths. Lying index → finding P3 [TOOLING].

### 2) `report.json` (canonical source of truth)

- `meta`: PR url, branch, base
- `gate`: allow_merge + policy_mode + reasons
- `checks[]`: status (PASS/WARN/FAIL/ERROR), log_path, command
- `diff.stats` + `diff.files[]`: scale, churn, hotspots, patch_path
- `quality`: breaking / coverage / sarif / heuristics

### 3) `00_summary/MERGE_GATE.json` + `SANITY.json`

- Cross-check with `report.json`. Inconsistency → finding P2 [TOOLING].
- Note: "All checks passed" with WARN/INLINE_FINDINGS present = misleading.

### 4) `00_summary/pr-metadata.txt` + `file-status.txt` + `commit-list.txt`

- Scope: how many files, what categories (A/M/D), commit progression
- Look for branch drift (infra files not in PR scope)

### 5) `30_context/INLINE_FINDINGS.sarif`

- Every SARIF result = ready-made finding. Transfer all to findings list.

### 6) `20_quality/*` (logs + results)

- PASS gates: extract warnings from logs (cargo warns, tsc non-errors)
- WARN/ERROR/FAIL gates: root cause + recommendation
- `checks-errors.log`: high-signal filtered errors
- `BREAKING_CHANGES.md`: assess real weight (P?)
- `coverage-delta.txt`: flag critical "NO_TEST_CHANGE" entries

### 7) `30_context/changed-tests.txt`

- Cross-reference with source changes — untested source files → finding

### 8) Diffs (selective, not exhaustive)

- `10_diff/per-file-diffs/00-INDEX.txt` → top churn files
- Per-file patches for hotspots
- `10_diff/per-commit-diffs/00-SUMMARY.md` → commits of highest impact
- Per-commit batches for line-level analysis

---

## Mandatory Pattern Scans

In per-file patches and/or `full.patch`, scan for these patterns:

### Rust

- `.unwrap()`, `.expect(` — unhandled panics
- `panic!`, `todo!` — incomplete code
- `unsafe` — review justification
- `dbg!`, `println!` — debug leftovers
- `#[allow(` — suppressed warnings

### TypeScript / JavaScript

- `any` — type escape
- `as unknown as` — double cast (type laundering)
- `@ts-ignore`, `@ts-expect-error` — type suppression
- `eslint-disable` — lint suppression
- `// TODO`, `// FIXME`, `// HACK` — deferred work
- Empty `catch {}` or `catch (e) {}` without log/rethrow
- Non-null assertion `!` on uncertain values
- `console.log`, `console.warn`, `console.error` — should use secureLogger (Vista)

### Security / PII

- Logging of tokens, emails, passwords, personal IDs
- New telemetry events without privacy review
- New endpoints / command handlers without auth checks
- Hardcoded URLs, API keys, secrets

### Data / Performance

- Query in loop (N+1)
- Missing batching for bulk operations
- Large payloads without pagination
- Unnecessary I/O in hot paths

Each "hit" in the diff = potential finding with evidence.

---

## Minimum Coverage Requirements

To prevent laconic reports:

- **All** entries in `INLINE_FINDINGS.sarif`
- **Top 10** files by churn (from `report.json` or `file-status.txt`) — read per-file patch
- **All** files in core risk categories (by path): auth, payments, database, session, security, encryption, middleware
- **All** critical "NO_TEST_CHANGE" entries from `coverage-delta.txt`
- **All** entries in `BREAKING_CHANGES.md` with assessed P-level
- **Per-commit progression** for PRs with >5 commits — identify phases, risky transitions

---

## Special Cases (Tooling)

### Cargo Geiger panic

`Matching variant not found` = tooling/misconfig (case-sensitive `--output-format`).
→ Finding **P1 [TOOLING]** if it blocks quality signal. Recommend: fix flag or pin/upgrade.

### Timeouts / "killed"

`killed (>timeout)` for tsc trace / eslint json:
→ Finding **P2 [TOOLING]** (missing quality signal). Recommend: increase timeout or disable with justification.

### Gate inconsistencies

`MERGE_GATE.json` says "All checks passed" but WARN/findings exist:
→ Finding **P2 [TOOLING]** with recommendation: "All blocking checks passed" vs "Non-blocking issues present".

### Branch drift

Files changed outside PR scope (CI, infra, unrelated config):
→ Finding **P1** if >10 files. Recommend: rebase on base branch.

---

## Output Format (Obowiązkowy)

Final output ALWAYS has these 2 mandatory sections (in this order):

### 1) Findings (P0/P1/P2/P3)

Each finding in this format:

```
- **[P?] <Title>** (optionally: [VERIFY] or [TOOLING])
  - **Evidence:** `<artifact-path>` + `<file:line>` + short fragment (1-2 lines)
  - **Comment:** 1 sentence on risk/impact
  - **Recommendation:** concrete "what to do" / "how to verify"
  - **Owner:** `author` / `reviewer` / `infra` (optional)
```

Number findings for cross-referencing: P1-01, P1-02, P2-01, etc.

### 2) Before-Merge TODO (Markdown Checkboxes)

```markdown
- [ ] **(P0)** ... (ref: P0-01)
- [ ] **(P1)** ... (ref: P1-01, P1-02)
- [ ] **(P2)** ... (ref: P2-01)
- [ ] **(P3)** ... (ref: P3-01)
```

Each TODO references finding IDs. Include verification commands in code fences where applicable.

### 3) Optional Sections (recommended)

Add when they provide value:

- **Executive Summary** (max 8 bullets): gate verdict, top 3 risks, test signal, top hotspots, scope delta
- **Architecture Context**: diagram or description of affected subsystem
- **Scope / What Changed**: based on `diff.stats` + top directories + top files
- **Commit Progression**: phases of work for multi-commit PRs
- **Test Coverage Matrix**: source file → test file → new tests count
- **Security & Privacy Check**: PII in logs, data flows, event filtering
- **QA Plan**: 5-15 manual + automated test recommendations
- **Evidence Index**: links to key artifacts used

---

## Policy System

Create `.prview-policy.yml` in repo root:

```yaml
version: 1
mode: warn # shadow | warn | block
default_severity: warn
checks:
  cargo_audit: block
  vitest: warn
  eslint: ignore
```

Override at CLI: `--policy-mode block`

Modes:

- **shadow**: never blocks (observability only)
- **warn**: blocks on `block` severity failures only
- **block**: blocks on `block` AND `warn` severity failures

---

## Profiles

Auto-detected from repo contents. Override: `--profile <PROFILE>`.

| Profile | Detection                   | Checks                                        |
| ------- | --------------------------- | --------------------------------------------- |
| rust    | Cargo.toml                  | cargo test, clippy, cargo audit, cargo geiger |
| js      | package.json + source files | vitest, eslint, tsc, pnpm build               |
| python  | pyproject.toml              | pytest, ruff, mypy                            |
| mixed   | multiple detected           | all applicable                                |
| generic | fallback                    | basic file analysis                           |

---

## 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Pipeline Integration

### As input to vc-followup

```bash
prview --pr $PR_NUMBER --with-tests --with-lint
ARTIFACTS="$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest"
```

### Subagent delegation context

```
## Context Bootstrap
- prview artifacts at: $VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest/
- Parse report.json first (canonical)
- Read 00_summary/MERGE_GATE.json for quick verdict
- Read 20_quality/checks-errors.log for error details
- Read 10_diff/per-file-diffs/ for hotspot patches
```

### JSON pipeline

```bash
prview --json --quiet | jq '.checks[] | select(.status == "Failed")'
```

---

## Anti-Patterns

### Tool usage

- Using `--quick` as the default for PR review in this skill (it drops test/lint/security signal)
- Running `--deep` on every PR when `--with-tests --with-lint` is enough (save `--deep` for merge gate / high-risk PRs)
- Reading `full.patch` entirely for large PRs (use `per-file-diffs/` for focused review)
- Ignoring `report.json` and `MERGE_GATE.json` (parse structured data first)
- Not using `--update` after amend/force-push (generates duplicate artifact sets)
- Running without `--no-fetch` on slow networks

### Analysis

- Stopping at 5 findings when 25 are visible (findings-max means exhaustive)
- Findings without evidence (every point needs artifact path + code fragment)
- Mixing separate problems into one finding (one point = one problem)
- Ignoring tooling issues (tool crash ≠ code issue, but still a finding)
- Skipping pattern scans (the `.unwrap()` / `any` / PII checklist is mandatory)
- Not cross-referencing coverage-delta with changed source files

---

_Created by M&K (c)2024-2026 VetCoders_
