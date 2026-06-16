# vc-review — PRVIEW: Phase 1 Artifact Generation

> Reference for `prview-rs` invocation, artifact pack layout, and
> tooling-special-cases. Phase 1 of vc-review.

Read alongside [`SKILL.md`](SKILL.md) and [`FINDINGS.md`](FINDINGS.md).

- Binary: `prview` (resolve via `command -v prview`; do not assume cargo path)
- Source: `https://github.com/VetCoders/prview-rs`
- Author: Monika (@m-szymanska) — VetCoders

---

## Dispatch table

| Mode                             | Command                                         | When to use                                |
| -------------------------------- | ----------------------------------------------- | ------------------------------------------ | -------------------- |
| Local branch vs develop/main     | `prview --pr <NUMBER>`                          | Default for active PRs on local checkout   |
| Remote branch (no checkout)      | `prview -R --remote-only <branch> <base>`       | Reviewing a contributor branch on origin   |
| GitHub PR by number              | `prview --pr <NUMBER> --with-tests --with-lint` | Default for thorough PR review             |
| All gates                        | `prview --deep`                                 | Merge gate / high-risk PR                  |
| Fast triage                      | `prview --quick`                                | Explicit fast triage only — NOT default    |
| Refresh after amend / force-push | `prview --update`                               | Avoid duplicate artifact sets              |
| Ambiguous origin                 | add `--gh-repo owner/repo`                      | When the working tree has multiple remotes |
| JSON-only mode                   | `prview --json --quiet                          | jq ...`                                    | Pipeline integration |

Default for vc-review: **do not use `--quick`**. Use `--with-tests
--with-lint` as the baseline. Save `--deep` for merge gate / high-risk.

---

## Artifact Pack Layout

Output: `$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/<timestamp>/`
(newest = default; symlink `latest`).

Top-level structure:

- `report.json` — **default structured report** (parse first)
- `dashboard.html` — interactive HTML
- `AI_INDEX.md` — artifact map + reading order
- `00_summary/` — `MERGE_GATE.json`, `RUN`, `MANIFEST`, `SANITY.json`,
  `pr-metadata.txt`, `file-status.txt`, `commit-list.txt`
- `10_diff/` — `full.patch`, `per-commit-diffs/`, `per-file-diffs/`
- `20_quality/` — per-gate logs/results, `checks-errors.log`,
  `coverage-delta.txt`, `BREAKING_CHANGES.md`
- `30_context/` — `INLINE_FINDINGS.sarif`, `changed-tests.txt`,
  tooling output
- `artifacts.zip` — everything zipped

Empty / missing newest dir → finding **P0**.

---

## JSON pipeline

```bash
prview --json --quiet | jq '.checks[] | select(.status == "Failed")'
```

For agent integration, parse:

- `meta` — RUN summary
- `gate.allow_merge` + `policy_mode` + `reasons` — gate verdict
- `checks[]` — per-gate status / log_path / command
- `diff.stats` + `diff.files[]` — scale / churn / hotspots
- `quality` — breaking / coverage / sarif / heuristics

---

## Subagent delegation context

When dispatching a subagent for analysis, embed:

```
- prview artifacts at: $VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest/
- Parse report.json first (default)
- Read 00_summary/MERGE_GATE.json for quick verdict
- Read 20_quality/checks-errors.log for error details
- Read 10_diff/per-file-diffs/ for hotspot patches
```

---

## Pipeline integration with `vc-followup`

```bash
prview --pr $PR_NUMBER --with-tests --with-lint
ARTIFACTS="$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest"
```

Then dispatch `vc-followup` against `$ARTIFACTS` for trajectory-level
assessment after review.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
