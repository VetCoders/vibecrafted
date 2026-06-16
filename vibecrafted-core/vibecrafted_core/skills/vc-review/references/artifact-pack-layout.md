# prview Artifact Pack — Full Layout & Flag Reference

## Output paths

```
$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/<timestamp>/
$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest      # symlink to newest
```

Always select the **newest** `<timestamp>`. Empty or missing directory → finding **P0**.

## Full directory layout

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

Note: some runs have duplicates in `artifacts/` subdir — prefer files in root.

## Full flag reference

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

Shell aliases exist (`prv`, `prvpr`, `prvjson`), but vc-review should not use the quick aliases for review-quality output.

## Mode reference

| Command                                         | Purpose                                          |
| ----------------------------------------------- | ------------------------------------------------ |
| `prview --pr <NUMBER>`                          | Most common: local branch HEAD vs develop/main   |
| `prview -R --remote-only <branch> <base>`       | Remote branch, no checkout                       |
| `prview --pr <NUMBER> --with-tests --with-lint` | GitHub PR by number                              |
| `prview --deep`                                 | All gates                                        |
| `prview --ci`                                   | CI mode: all checks, no color, exit 1 on failure |
| `prview --json --quiet`                         | JSON for automation / jq piping                  |
| `prview --update`                               | Incremental: only regenerate changed artifacts   |
| `prview --tui`                                  | Interactive terminal UI                          |
| `prview feat/x develop main`                    | Explicit target + base branches                  |

## Profiles

Auto-detected. Override with `--profile <PROFILE>`.

| Profile | Detection                   | Checks                                        |
| ------- | --------------------------- | --------------------------------------------- |
| rust    | Cargo.toml                  | cargo test, clippy, cargo audit, cargo geiger |
| js      | package.json + source files | vitest, eslint, tsc, pnpm build               |
| python  | pyproject.toml              | pytest, ruff, mypy                            |
| mixed   | multiple detected           | all applicable                                |
| generic | fallback                    | basic file analysis                           |

## Policy system

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

## Special cases (tooling findings)

- **Cargo Geiger panic** (`Matching variant not found`) = tooling/misconfig (case-sensitive `--output-format`). → P1 [TOOLING] if it blocks quality signal. Recommend: fix flag or pin/upgrade.
- **Timeouts / "killed"** for tsc trace / eslint json: → P2 [TOOLING] (missing quality signal). Recommend: increase timeout or disable with justification.
- **Gate inconsistencies**: `MERGE_GATE.json` says "All checks passed" but WARN/findings exist → P2 [TOOLING]. Recommend: distinguish "All blocking checks passed" vs "Non-blocking issues present".
- **Branch drift**: files changed outside PR scope (CI, infra, unrelated config) → P1 if >10 files. Recommend: rebase on base branch.

## ScreenScribe integration

vc-review can analyze screencast recordings alongside code diffs when ScreenScribe is available as a foundation tool. Use for:

- Runtime behavior review (visual confirmation of what the code does)
- Bug demo analysis (narrated screen recordings → structured findings)
- UX review passes (screencast of user flow → P-leveled UX issues)

ScreenScribe is optional. If not installed, vc-review operates on code artifacts only.
