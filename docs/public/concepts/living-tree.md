---
title: "Living Tree"
description: "The shared-checkout doctrine: agents work in one moving tree, adapt to concurrent edits, and commit in disciplined packs."
section: concepts
order: 20
---

# Living Tree

Vibecrafted fleets do not isolate every agent in its own git worktree.
Agents share one checkout — one live, moving tree — and concurrent changes
are expected. This is a deliberate discipline, not an accident: it keeps
all work converging on a single state instead of fragmenting into stale
branches that someone must later reconcile.

## The core rules

1. **Always assume the tree is alive.** Another agent may have edited a
   file since you last saw it.
2. **Re-read before you edit.** If time has passed since you read a file,
   read it again before changing it. A stale local assumption is never
   ground truth.
3. **Never revert concurrent work.** A dirty worktree is often intentional.
   Do not "clean up" or overwrite other agents' changes unless explicitly
   asked.
4. **No worktrees for active implementation.** Never create, switch to, or
   move execution into a git worktree unless the operator explicitly asks
   for one. "Isolate this" or "work in parallel" is not enough.
5. **Never change branches during active work.** Stay on the current
   working branch and keep building inside that living tree. If the
   checkout is too damaged to continue safely, report the substrate
   failure instead of escaping into a side tree.

## Commit discipline

Work on a Living Tree is preserved through frequent, well-shaped commits:

- Commit in packs of roughly 5–6 files where possible, rather than one
  giant end-of-task snapshot.
- Commit titles always follow the convention:

  ```text
  [<agent>/<workflow>] <description>
  ```

  for example `[codex/vc-implement] fix(parser): handle empty frontmatter`.

- Commit messages are never empty; describe the change, as a bulleted list
  where applicable.
- Commit is an obligation, not an option: delivered work must not be left
  uncommitted. Pushing, however, stays a human decision.
- During iterative polish rounds, prefer numbered incremental commits
  (`decorate 1: …`, `decorate 2: …`) over a single end snapshot.

## The Living Tree preamble

Every plan or prompt handed to a fleet worker carries this exact preamble:

```text
You work on a living tree with Vibecraftsmanship methodology, so concurrent changes are expected.
Adapt proactively and continue, but this is never permission to skip quality, security, or test gates.
Run required checks. If something is blocked, report the exact blocker and run the closest safe equivalent.
```

The preamble is repo-agnostic on purpose. It tells the worker two things at
once: concurrent edits are normal, and "the tree moved" is never an excuse
to skip gates.

## Coordination without micromanagement

Plans state explicitly whether a worker runs solo at its stage or alongside
other agents. A worker needs to know the coordination mode, but it does not
need to read other agents' plan files unless its plan says so.

Before any handoff — to another agent, another stage, or a recovery
dispatch — the outgoing worker captures a pre-handoff baseline:

| Baseline item                          | Why it matters                                |
| -------------------------------------- | --------------------------------------------- |
| Branch and `HEAD`                      | Anchors regression attribution                |
| `git status --short` and changed files | Distinguishes your work from concurrent drift |
| Gates run and known failures           | The receiver does not re-discover them        |
| Unverified surfaces                    | Honest gaps, stated up front                  |
| Exact next instruction / report path   | The receiver starts working, not guessing     |

The receiving agent compares that baseline against the live tree before
editing. These checkpoints are regression attribution boundaries — skipping
them launders failures into "some agent did something".

## Why not worktrees?

Worktrees look safer but hide cost: every isolated tree is a fork of
reality that must be merged back, and background agents multiply those
forks faster than a human can reconcile them. The Living Tree trades a
merge problem for an awareness problem — and awareness is what the
perception tooling (structure maps, blast-radius checks, baselines) is
built to provide. Living Tree is not chaos; it is disciplined awareness
inside a shared moving system.
