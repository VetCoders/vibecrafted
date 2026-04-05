---
name: prview
description: >
  Generate persistent review artifacts for deep analysis and gatekeeping.
  Use prview CLI as the foundation for automated and manual PR audits.
---

# PRView — Persistent Review Artifacts

PRView creates structured, persistent engineering findings from pull requests.
It is the foundation for `vc-review` and any high-stakes code verification.

## Hard Rules

1. **Don't review in the dark**: always run `prview` before deep audit.
2. **Artifact-first**: use the generated artifacts for reporting, not volatile terminal output.
3. **P-level severity**: use the findings-max standard for all issues (P0-P2).
4. **CI visibility**: prefer `prview --ci` in automation pipelines.

## Standard Workflow

### 1) Generate artifacts

- Run `prview --pr <NUMBER>` or `prview -R <branch> <base>`.
- Artifacts are stored at `$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest`.

### 2) Deep Audit

- Review the generated findings and line-level notes.
- Integrate findings into the main report.

### 3) Incremental Update

- If changes are made, run `prview --update` to refresh artifacts.

## CLI Reference

| Command                     | Purpose                                 |
| --------------------------- | --------------------------------------- |
| `prview --pr <NUMBER>`      | Basic PR audit (fetch from remote)      |
| `prview -R <branch> <base>` | Remote comparison (no PR number needed) |
| `prview --update`           | Refresh existing artifacts              |
| `prview --ci`               | CI mode: all checks, exit 1 on failure  |
| `prview --json --quiet`     | JSON output for automation              |

## Binary Details

- Binary: `prview` (resolve via `command -v prview`)
- Source: `https://github.com/VetCoders/prview-rs`
- Author: Monika (@m-szymanska) — VetCoders
