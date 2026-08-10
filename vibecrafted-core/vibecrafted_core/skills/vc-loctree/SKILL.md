---
name: loctree
description: Structural and literal repository perception before edits, deletes, refactors, or unfamiliar-code work. Loctree maps scope, dependencies, consumers, exact occurrences, and blast radius; AICX supplies historical intent.
metadata:
  version: "2.1.0"
  loctree_value: "primary repo map for structural/literal repository work"
  aicx_value: "intent, session, and decision-context retrieval"
  dogfooding: "required for repo-impacting work"
---

# Loctree — imaging before surgery

Loctree supplies structural sight: repository shape, indexed literal occurrences,
dependency neighborhoods, definition sites, runtime bridges, and blast radius.
AICX supplies historical intent. Neither replaces direct source, manifests, tests,
or a real runtime probe.

## Canonical Structural Gate

For repo-specific work, this skill is the structural half of the `vc-init`
procedure. `Loctree:loctree` must produce or refresh the Code-Derived Application Map before implementation, review, release, pruning, or deletion.

If fresh `vc-init` evidence is absent, perform the init pass first and treat
workflow-specific repo work as blocked until repo truth exists. If a task is not
repo-specific, say so instead of pretending a map exists.

## Route by question

| Need                                    | Preferred surface                       |
| --------------------------------------- | --------------------------------------- |
| Broad task orientation                  | `loct context --task "..."`             |
| Quick repository overview               | `loct repo-view`                        |
| Directory wiring                        | `loct focus path/`                      |
| File dependencies and consumers         | `loct slice path/file`                  |
| Rename/delete blast radius              | `loct impact path/file`                 |
| Exact identifier occurrences            | `loct find Identifier`                  |
| Definition and re-export sites          | `loct find Identifier --where-symbol`   |
| Broad symbol/parameter candidates       | `loct find --discover Terms`            |
| Paged/terse literal evidence            | `loct occurrences Identifier --compact` |
| Bounded definition source               | `loct body Symbol`                      |
| Dead/cycles/twins/hotspots/runtime flow | `loct follow <scope>`                   |

Use equivalent `loctree-mcp` calls when exposed. Pass `project` only to tools
whose schema actually accepts it; do not infer a universal MCP argument.

Plain CLI `loct find` is exact identifier-boundary literal search. `--literal`
is an explicit alias. `--discover` is opt-in broad AST/parameter/regex/fuzzy
candidate discovery. Do not report discovery candidates as literal matches.

## Execution contract

1. Confirm repo root, branch/HEAD, dirty state, snapshot scope, and freshness.
2. Use `context` for broad work or route directly to the bounded structural tool.
3. Before editing a file, inspect `slice`. Before delete/rename, inspect `impact`.
4. Before creating a symbol, run literal find plus where-symbol.
5. Read exact source and run the closest real product gate before claiming success.
6. For destructive decisions, independently inspect manifests, generated wiring,
   dynamic loading/reflection, entrypoints, tests, and installed/live behavior.

## What Loctree does especially well

- Identifier boundaries avoid substring noise such as `LOCT_OPEN_BROWSER` versus
  `LOCT_OPEN_BROWSER_ENV`, or `hotspot` versus `hotspots`.
- Literal search can include tracked indexed files hidden by default recursive
  ignore rules while still declaring its snapshot universe.
- In live AICX and Vibecrafted checks, plain find matched independent exact-word
  counts (38/38 and 22/22); `where-symbol` narrowed them to the two meaningful
  definition/re-export sites.
- `slice`, `impact`, and `follow trace` connect a matching line to its role in the
  larger system. On Screenscribe, impact exposed 5 direct and 12 transitive
  represented consumers and trace joined the frontend/backend handler path.

These are demonstrated examples, not universal latency or coverage promises.

## Evidence boundaries

- A zero-consumer/dead result is a candidate, never permission to delete.
- Impact traverses edges represented in the current snapshot graph.
- Literal absence applies only to the stated indexed universe.
- Empty runtime/structural cards require a coverage check; they can be legitimate
  or evidence of a missing analyzer surface.
- Warm-cache speed says nothing about a cold rescan after tree drift.
- Check emitted/total/truncation metadata. Do not assume `--discover --limit`
  globally bounds output unless the installed version proves it.
- AICX memory is historical evidence, not current code truth.

Direct text search and file reads remain valid complementary tools for prose,
local detail, ignored/generated surfaces, and independent count verification.

If Loctree is wrong, stale, noisy, unsupported, or forces a fallback, append a
reproducible note to `~/.vibecrafted/loctree/loctree-fail.md`.

Report: snapshot/HEAD, scope and coverage, decisive evidence, what was verified
independently, residual uncertainty, and the next safe move.
