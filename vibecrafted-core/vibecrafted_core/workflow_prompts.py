from __future__ import annotations

DEFAULT_PRUNE_DISCOVERY_PROMPT = """---
Description: >-
  This is a smoke test run, but treat the task as valid and actionable.
  The repository investigation is real. The smoke dimension is the tooling used.

Task target:
  $REPO_ROOT / current repository.

Smoke target:
  loctree-mcp and loct CLI tools.

Key distinction:
  - Task target = the repository to investigate.
  - Smoke target = the tooling to exercise during the investigation.
  Do not interpret loctree-mcp or loct CLI as the repository scope unless the
  current repo actually contains those surfaces.

Mode:
  Repository health / prune discovery run.
  Prefer discovery, evidence, classification, and vc-scaffold-ready artifacts.
  Commit only removals that are proven safe with zero live references and low
  blast radius.
---

Task:
Investigate the repository for unhealthy, dead, ambiguous, risky, or forgotten
surfaces.

Look for:

1. Dead parrots / orphaned surfaces
   - dead code, unused tools, unused scripts, unreachable commands, stale
     entrypoints, abandoned generated files, and orphaned docs that describe
     removed behavior.

2. Silly exports
   - self-reexports, pointless reexports, exports with no runtime or test usage,
     cargo-cult public surfaces, and bootstrapping/bottle/component/function
     surfaces without real callers.

3. Missing handlers / missing callers
   - declared commands without handlers, unreachable handlers, routes/actions/
     events without callers, UI actions without target/action mapping, config
     keys with no consumer, and consumers of config keys that are never produced.

4. Twins / high semantic similarity
   - duplicated functions, near-identical modules, parallel implementations of
     the same concept, and old/new implementations living side by side.

5. Cycles and race-condition risks
   - dependency cycles, runtime control-plane cycles, async/state races, stale
     state vs runtime truth mismatches, and lock/heartbeat/pid/state divergence.

6. Crowds / ambiguity hotspots
   - ambiguous names, too many similarly named commands/components, overloaded
     concepts, and surfaces likely to confuse agents or humans.

7. Shadows
   - technically-called code shadowed by a newer path, fallback paths that
     silently dominate primary paths, old implementations masked by wrappers,
     and features present in code but unreachable in product flow.

8. Linter silencers and policy exceptions
   Catalog, do not blindly remove: Rust clippy allow attributes, eslint disable
   comments, ruff ignores, shellcheck disables, nosemgrep rules, and any local
   "ignore this warning" mechanism. Classify each as justified, stale,
   dangerous, or needs follow-up.

9. Monoliths
   - 1500+ LOC files, files with too many responsibilities, modules that become
     collision hotspots, and likely vc-prune/vc-scaffold follow-up candidates.

10. Forgotten local state
   Inspect read-only: local branches, stashes, worktrees, untracked/ignored
   relevant files, and hidden WIP surfaces. Do not delete branches, stashes, or
   worktrees without explicit operator approval.

11. Hidden gems
   - useful but unreachable code, dormant capabilities, and tooling that could
     become a robust, smart, secure, or healing extension of the living runtime.
   Do not prune hidden gems by default. Classify them separately as
   "preserve / scaffold / revive".

Reason:
  Dead code surface cannot live indefinitely in a healthy repository. Forgotten
  branches, stashes, worktrees, stale exports, and unreachable runtime surfaces
  must be made visible. The output should let the operator decide what to
  prune, revive, scaffold, or audit next.

Required tooling behavior:
  - Prefer loctree/loct tools for navigation and evidence where possible.
  - Use loctree-mcp and loct CLI as part of the smoke.
  - If loctree-mcp or loct CLI fails, report the failure as smoke evidence and
    continue with the safest fallback.
  - Do not hide tooling failures.
  - Do not claim a tool worked unless you have command/output evidence.

Rules:
  - Do not remove anything based on vibes.
  - Prove every prune candidate with references/search evidence.
  - Before deleting, confirm zero live references or explain residual risk.
  - Treat linter silencers, monoliths, cycles, crowds, shadows, and hidden gems
    primarily as findings unless a safe mechanical cleanup is obvious.
  - Keep changes scoped and small.
  - Commit only verified removals.
  - Do not delete branches, stashes, worktrees, or hidden WIP.
  - Do not push. Push is an operator button.
  - If the repo is dirty at start, report it and avoid sweeping unrelated WIP.
  - Never use --no-verify.

Report location:
  Append the investigation journal to:

  $VIBECRAFTED_ROOT/artifacts/<org>/<repo>/YYYY_MMDD/prune/reports/${RUN_ID}_JOURNAL.md

  If VIBECRAFTED_ROOT is unavailable, use VIBECRAFTED_HOME. If RUN_ID or paths
  are unavailable, create the closest equivalent under the current Vibecrafted
  artifacts tree and report the exact path used.

Prepare vc-scaffold-ready artifacts for vc-agents:
  Create actionable follow-up artifacts suitable for dispatch to the vc-agents
  fleet. Group findings into small cuts, not one giant "fix everything" task.

Expected artifact shape:
  - ${RUN_ID}_JOURNAL.md
  - findings/dead-parrots.md
  - findings/silly-exports.md
  - findings/missing-handlers-callers.md
  - findings/twins.md
  - findings/cycles-races.md
  - findings/crowds-shadows.md
  - findings/linter-silencers.md
  - findings/monoliths.md
  - findings/forgotten-local-state.md
  - findings/hidden-gems.md
  - scaffold/README.md
  - scaffold/cuts/*.md

Deliverables:
  - Journal appended at the requested artifacts path.
  - Smoke evidence for loctree-mcp and loct CLI.
  - Findings grouped by category.
  - vc-scaffold-ready cut briefs for the vc-agents fleet.
  - One or more scoped commits only if safe removals exist.
  - If nothing is safe to remove, report "nothing to prune" with evidence.

Final report:
  Include the repository inspected, current branch and dirty/clean state at
  start, smoke evidence for loctree-mcp and loct CLI, candidates found,
  candidates removed, candidates intentionally kept, hidden gems worth
  preserving/reviving, branches/stashes/worktrees observed, artifacts written,
  commands/evidence used, and commit SHA(s), files changed, deletion count, and
  blast-radius evidence if any commit was made.
"""

DEFAULT_WORKFLOW_PROMPTS = {
    "prune": DEFAULT_PRUNE_DISCOVERY_PROMPT,
}


def default_workflow_prompt(skill: str) -> str:
    return DEFAULT_WORKFLOW_PROMPTS.get(skill, "")
