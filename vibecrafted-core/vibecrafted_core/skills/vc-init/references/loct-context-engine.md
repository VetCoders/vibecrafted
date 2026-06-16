# `loct context` engine — full reference

Companion to `SKILL.md` Sense 2. The skill body keeps the contract and the
primary call; this file holds the full lookup tables, parameter map, and
operational reflexes.

## Atlas anatomy — six cards plus receipt

| #   | Card                       | Read for                                                                 | When required                              |
| --- | -------------------------- | ------------------------------------------------------------------------ | ------------------------------------------ |
| 0   | `00-core-map.md`           | repo identity, current risk, authority labels, safe next commands        | **always**                                 |
| 1   | `01-structural-map.md`     | files, symbols, imports, consumers, entrypoints                          | **always** (empty unscoped — pass `file:`) |
| 2   | `02-runtime-map.md`        | idiom tags, reachability, framework hints, env contracts, dispatch edges | **always** (empty unscoped — pass `file:`) |
| 3   | `03-memory-trail.md`       | AICX continuity: outcomes, tasks, operator intents                       | when resuming or in Living Tree            |
| 4   | `04-verification-gates.md` | likely_tests, verification commands, next safe loct calls                | before edits / pre-commit                  |
| 5   | `05-risk-register.md`      | hotspots, fan-in, cache_scope, snapshot_health, dirty_worktree           | before release / structural surgery        |
| ·   | `receipt`                  | scan provenance, snapshot fingerprint, `git_commit`, scan timestamp      | Living Tree: detect concurrent rescans     |

A repo-level answer is **incomplete** until cards 0, 1, 2 have been read.
Atlas cache path: `~/Library/Caches/loctree/projects/<hash>/<branch>@<commit>/context-atlas/`.

## `context()` parameters — scope, hygiene, format

| Param                | When to use                                                                          |
| -------------------- | ------------------------------------------------------------------------------------ |
| _(none)_             | Bootstrap orientation. Structural/runtime cards are intentionally empty.             |
| `file: "<path>"`     | Before touching a file: fills structural with target + deps + consumers + symbols.   |
| `task: "<text>"`     | Token-overlap relevance — pulls in semantically related files outside the dep graph. |
| `changed: true`      | Living Tree WIP filter — limits to git-changed files.                                |
| `no_aicx: true`      | Offline / sensitive sessions; drops the AICX memory overlay.                         |
| `no_scan: true`      | CI mode — fail if no snapshot rather than auto-scan.                                 |
| `fail_stale: true`   | CI gate — fail if snapshot drifted from the current commit.                          |
| `fresh: true`        | Force rescan (after deep structural edits or branch switch).                         |
| `format: "markdown"` | Operator-style markdown pill; default `"json"` for structured agents.                |
| `force_no_git: true` | Bypass repo-detection guard (rare — staged checkouts, generated trees).              |

## Authority labels (always check before acting)

| Label              | Trust                                                                 |
| ------------------ | --------------------------------------------------------------------- |
| `repo_verified`    | Hard fact from the snapshot. Highest trust.                           |
| `loctree_derived`  | Inferred by the analyzer (importer counts, dead/cycle, etc.). Strong. |
| `aicx_operator`    | From operator intents in prior sessions. Treat as sticky preference.  |
| `aicx_agent`       | From prior agent outcomes (other agents, this repo, recent).          |
| `aicx_failure`     | Prior failed attempt — read carefully, don't repeat the path.         |
| `semantic_guess`   | Heuristic. Verify before acting.                                      |
| `stale_or_unknown` | Re-check repo state; do not trust as-is.                              |

## Atlas sub-tools (drill-down without re-fetching the world)

- `context_manifest(project, with_aicx)` — list available sections (including
  `receipt`) with sizes + cursor.
- `context_section(project, section)` — direct fetch of `core` / `structural` /
  `runtime` / `memory` / `receipt`.
- `context_next(cursor)` — paginated chunk retrieval after the initial call.

## Drill-down tools (after the atlas, when scope is known)

| Tool                  | Trigger condition                                             |
| --------------------- | ------------------------------------------------------------- |
| `slice(file)`         | About to modify that specific file.                           |
| `impact(file)`        | About to delete or rename that file.                          |
| `find(pattern)`       | Need to locate a symbol — **never grep first**.               |
| `follow(scope)`       | Pursuing `dead` / `cycles` / `twins` / `hotspots` / `trace`.  |
| `focus(directory)`    | Module-level deep-dive after orientation.                     |
| `query(kind, target)` | Graph queries: `who-imports`, `where-symbol`, `component-of`. |

## Analysis tools (signal, not orientation)

| Tool          | When to use                                                  |
| ------------- | ------------------------------------------------------------ |
| `health()`    | Quick sanity sweep (cycles + dead + twins) at session start. |
| `findings()`  | Full issues JSON for triage / before release.                |
| `audit()`     | Comprehensive audit pass (CI gate, vc-marbles convergence).  |
| `doctor()`    | Cache identity + snapshot fingerprint + drift status.        |
| `coverage()`  | Test coverage gaps (structural).                             |
| `manifests()` | `package.json` / `Cargo.toml` summaries.                     |
| `dist()`      | Verify tree-shaking from source maps.                        |
| `insights()`  | AI insights summary.                                         |

## Living Tree pre-edit reflex

Before any edit window longer than a few minutes, call `doctor()` (or read
`fingerprint` from `repo-view`) to detect a concurrent rescan from another
agent. If the fingerprint moved since your last call, re-issue
`context(fresh: true)` before continuing. Skipping this in shared
directories is how multi-agent coordination silently fails.

## CLI as operator surface (not agent fallback)

`loct context`, `loct slice`, `loct find`, `loct doctor`, etc. exist for
direct operator inspection — markdown pill (`--markdown`), interactive
debugging, shell pipes (`loct findings | jq ...`). The two surfaces share
the same engine and the same atlas cache; they differ in ergonomics, not
capability. Agents do **not** use CLI as a parity fallback for MCP. The
single exception: when an operator hands you a literal CLI command in a
prompt ("run `loct doctor` and report"), execute as instructed — the
operator is exercising the interactive surface deliberately.
