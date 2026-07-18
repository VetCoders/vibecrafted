# Operator-Chosen Baseline Rule

The current checkout is an operator decision, not disposable local state. Before
repo-specific scaffolding or any external fleet launch, establish and carry an
`OPERATOR_CHOSEN_BASELINE`. Never tell a worker to use the "latest HEAD" without
naming the ref and proving what "latest" means.

## Trigger

Run this gate whenever a workflow will plan, edit, delete, refactor, verify, or
dispatch work against a Git repository. The gate is automatic; do not wait for
the operator to remember to ask about HEAD freshness.

## Refresh truth without moving the tree

From the operator's current repository root:

```bash
git status --porcelain=v2 --branch
git remote -v
git fetch --all --prune
git rev-parse --show-toplevel
git branch --show-current
git rev-parse HEAD
```

Then determine the configured upstream, if one exists, and record its exact
ahead/behind relation. If no upstream exists, say so. Do not substitute
`origin/main`, fabricate a same-name remote branch, or call an arbitrary remote
ref "latest". Comparing a selected branch with `origin/main` may provide lineage
evidence, but it does not replace the operator's selection.

This refresh is read-only. Never use `git pull`, `git checkout`, `git switch`,
`git reset`, `git rebase`, `git merge`, or `git stash` to make the observation
look clean. A failed remote refresh is `remote_refresh: failed`, not success; the
workflow stops unless the operator explicitly accepts that freshness waiver.

## Required record

Carry this machine-readable block into the plan and every worker prompt:

```text
OPERATOR_CHOSEN_BASELINE
baseline_repo_root: <absolute git toplevel>
baseline_branch: <current branch or DETACHED>
baseline_sha: <full 40-character commit id>
baseline_status: <clean or exact changed paths/status>
remote_refresh: <succeeded|failed|not_applicable> at <UTC timestamp>
upstream_ref: <full upstream ref or none>
upstream_relation: <ahead N, behind N|no_upstream|not_applicable>
selection_source: <current_operator_checkout|explicit_operator_ref>
```

The status field is evidence, not a cleanliness demand. Living Tree changes may
be legitimate concurrent work and must not be discarded.

## Receiver gate

Immediately before acting, the receiving agent re-runs root, branch, HEAD, and
status discovery and applies this decision table:

1. Same root, same branch, exact `baseline_sha`: proceed.
2. Same root and branch, current HEAD is a descendant of `baseline_sha`: inspect
   `git log --oneline baseline_sha..HEAD`, re-read affected files, record the
   reviewed drift in EXTRA/BATON, and proceed only if it does not invalidate the
   task. Prove ancestry with:

   ```bash
   git merge-base --is-ancestor <baseline_sha> HEAD
   ```

3. Different root, different branch, detached unexpectedly, non-descendant HEAD,
   missing baseline, or unreviewed scope-changing drift: **DIVERGED-STOP**. Do not
   repair the mismatch by moving the checkout. Return evidence to the dispatcher.

Concurrent descendant commits are normal. Silent divergence is not. A newer
commit may become the receiving agent's observed start, but it never rewrites the
historical baseline recorded by the operator.

## Artifact ownership

- `vc-scaffold` records the block in the master plan, `DRIVER.md`, and every cut
  brief, then teaches each cut the receiver gate.
- `vc-dispatch` refreshes it immediately before launch, places it in EXTRA/BATON,
  and records any descendant drift in the tracker/journal.
- Recovery and refire prompts inherit the original baseline plus the exact landed
  commit chain; they do not replace provenance with a fresh, context-free HEAD.
