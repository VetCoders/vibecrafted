---
Description: >-
  Repository health / prune discovery run. Treat the repository investigation as
  real and actionable. The tooling proof dimension is Loctree MCP + loct CLI
  exercised on this repository, but do not describe the workflow itself as a
  test-only run in the final report.

Task target: $REPO_ROOT / current repository.

Tooling proof target: loctree-mcp and loct CLI.

Key distinction:
  - Task target = the repository to investigate.
  - Tooling proof target = the Loctree tools to exercise while investigating.
  - Do not interpret loctree-mcp or loct CLI as repository scope unless the
    current repo actually contains those surfaces.

Mode: Find, classify, prove, scaffold, and cut only verified dead surfaces.
  Prefer discovery, evidence, classification, and vc-scaffold-ready artifacts.
  Commit only removals that are proven safe with zero live references and low
  blast radius.
---

Task:
Investigate the repository for unhealthy, dead, ambiguous, risky, or forgotten
surfaces.

Use Loctree as the primary sensory layer:

- `loct context --full --markdown`
- `loct doctor`
- `loct env-truth`
- `loct follow all`
- `loct health`
- `loct suppressions`
- `loct diff --since <rev>`
- `loct report`
- `loct focus <dir>`
- `loct slice <file>`
- `loct impact <file>`
- `loct find --literal <text>`
- `loct occurrences <id>`
- `loct body <symbol>`
- `loct dist <entrypoint-or-scope>` when available
- `loct blame <file-or-symbol>` when useful

If a Loctree command is missing or fails, report the command, failure, and
fallback in the journal. Use raw text search only as a local fallback after
Loctree evidence is unavailable or insufficient.

Look for:

1. Dead parrots / orphaned surfaces
   - dead code,
   - unused tools,
   - unused scripts,
   - unreachable commands,
   - stale entrypoints,
   - abandoned generated files,
   - orphaned docs that describe removed behavior.

2. Silly exports
   - self-reexports,
   - pointless reexports,
   - exports with no runtime or test usage,
   - public surfaces that are cargo-cult leftovers,
   - bootstrapping/bottle/component/function surfaces without real callers.

3. Missing handlers / missing callers
   - declared commands without handlers,
   - handlers unreachable from runtime,
   - routes/actions/events without callers,
   - UI actions without target/action mapping,
   - config keys with no consumer,
   - consumers of config keys that are never produced.

4. Twins / high semantic similarity
   - duplicated functions,
   - near-identical modules,
   - parallel implementations of the same concept,
   - old/new implementations living side by side.

5. Cycles and race-condition risks
   - dependency cycles,
   - runtime control-plane cycles,
   - async/state races,
   - stale state vs runtime truth mismatches,
   - lock/heartbeat/pid/state divergence.

6. Crowds / ambiguity hotspots
   - symbols with ambiguous naming,
   - too many similarly named commands/components,
   - overloaded concepts,
   - surfaces likely to confuse agents or humans.

7. Shadows
   - code that is technically called but shadowed by a newer path,
   - fallback paths that silently dominate primary paths,
   - old implementations masked by wrappers,
   - features present in code but unreachable in product flow.

8. Linter silencers and policy exceptions
   Catalog, do not blindly remove:
   - Rust clippy `#[allow(...)]`,
   - eslint disable comments,
   - TypeScript `@ts-ignore`, `@ts-expect-error`, `@ts-nocheck`,
   - Python `# noqa`, `# type: ignore`, pylint disables,
   - ShellCheck disables,
   - Semgrep `nosemgrep`,
   - skipped/ignored/theater tests,
   - any local "ignore this warning" mechanism.
     Classify each as justified, stale, dangerous, test theater, forgotten gem, or
     follow-up.

9. Monoliths
   - 1500+ LOC files,
   - files with too many responsibilities,
   - modules that repeatedly become collision hotspots,
   - likely vc-prune/vc-scaffold follow-up candidates.

10. Forgotten local state
    Inspect read-only:
    - local branches,
    - stashes,
    - worktrees,
    - untracked/ignored relevant files,
    - hidden WIP surfaces.
      Do not delete branches, stashes, or worktrees without explicit operator
      approval.

11. Hidden gems
    - useful but unreachable code,
    - dormant capabilities,
    - tooling that could become a robust, smart, secure, or healing extension of
      the living runtime.
      Do not prune hidden gems by default. Classify them separately as preserve,
      scaffold, or revive.

Verdicts:

- `DELETE-NOW`: zero live references, low blast radius, no hidden-gem signal.
- `ARCHIVE-THEN-DELETE`: useful context exists, but runtime surface is dead.
- `REVIVE`: dormant capability should be wired into runtime.
- `SCAFFOLD`: real finding, too broad/risky for prune.
- `VERIFY-FIRST`: evidence is insufficient.
- `KEEP-RUNTIME`: live product/build/test/release surface.
- `KEEP-BUILD`: needed for packaging, CI, generated artifacts, or release.
- `FORGOTTEN-GEM`: valuable dormant code; preserve and ask operator.

Rules:

- Do not remove anything based on vibes.
- Prove every prune candidate with Loctree evidence where possible.
- Before deleting, confirm zero live references or explain residual risk.
- Treat silencers, monoliths, cycles, crowds, shadows, and hidden gems primarily
  as findings unless a safe mechanical cleanup is obvious.
- Be bold when evidence is strong: cut whole dead vertical slices rather than
  trimming symbolic leaves.
- Keep changes scoped and small.
- Commit only verified removals.
- Do not delete branches, stashes, worktrees, or hidden WIP.
- Do not push. Push is an operator button.
- If the repo is dirty at start, report it and avoid sweeping unrelated WIP.
- Never use `--no-verify`.

Report location:
Append the investigation journal to:

`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/YYYY_MMDD/prune/reports/${RUN_ID}_JOURNAL.md`

If RUN_ID or paths are unavailable, create the closest equivalent under the
current Vibecrafted artifacts tree and report the exact path used.

Prepare vc-scaffold-ready artifacts:
Create actionable follow-up artifacts suitable for dispatch to the vc-agents
fleet. Group findings into small cuts, not one giant "fix everything" task.

Expected artifact shape:

- reports/${RUN_ID}\_JOURNAL.md
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
- scaffold/cuts/\*.md

Final report:
Include repository inspected, branch/HEAD/dirty state at start, Loctree MCP
evidence if available, loct CLI evidence, Loctree failures/fallbacks,
candidates found, candidates removed, candidates intentionally kept, hidden gems
worth preserving/reviving, branches/stashes/worktrees observed, artifacts
written, commands/evidence used, and commit SHA(s), files changed, deletion
count, and blast-radius evidence if any commit was made.
