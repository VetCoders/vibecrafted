---
name: vc-prune
version: 5.0.0
description: >-
  Action-first repository prune: find proven-dead weight with Loctree, prove it,
  and CUT it (git rm + commit) — not a findings report. Use this whenever the
  operator wants to prune, tree-shake, remove dead code/tools/scripts, kill
  orphans/twins/shadows, clean a repo, catalog linter silencers, or surface
  forgotten state and hidden gems. This is the INTERACTIVE orchestration layer:
  it dispatches the prune worker (whose action-brief is
  runtime/workflows/prune/default_prompt.md) and verifies real cuts before
  calling the run done. Reach for it even when the operator just says "this repo
  is messy" or "what's dead here".
loctree_value: "primary sensory layer for dead code, twins, shadows, suppressions, env truth, blast radius, and literal reference truth"
aicx_value: "intent/decision recovery before classifying dormant work as dead"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v2 -->

> **Operator CLI / slash-command layer:** invoking `/vc-<workflow>` or
> `vibecrafted <workflow> <agent>` means dispatching the external Vibecrafted
> fleet through the launcher. In that layer, the invocation is an imperative to
> act, not a no-op, and not native in-process subagents.
>
> **Skill-loading / chat layer:** loading this `SKILL.md` inside Codex, Claude,
> Gemini, or another local agent does not mean self-dispatch. Read and apply the
> skill in the current thread; do not spawn another agent unless the operator
> explicitly asks you to launch, dispatch, run the fleet, or gives a concrete
> command such as `vc-prune codex` / `vibecrafted prune claude`.
>
> The sole native in-process carve-out is `vc-delegate`.

<!-- /fleet-imperative -->

# vc-prune — Find, Prove, Cut

`vc-prune` removes proven-dead weight from a repository. The product of a run is
**committed cuts**, not a findings document. A run that only describes deletable
surface without cutting it has failed.

## Two artifacts — do not conflate them

| Artifact           | Lives in                                    | Audience                  | Job                                                                              |
| ------------------ | ------------------------------------------- | ------------------------- | -------------------------------------------------------------------------------- |
| **This SKILL**     | `skills/vc-prune/SKILL.md`                  | **you, interactively**    | the orchestration ritual: orient, dispatch, await, verify cuts, flip, checkpoint |
| **Runtime prompt** | `runtime/workflows/prune/default_prompt.md` | **the dispatched worker** | the action directives the worker obeys: DISCOVER → PROVE → CUT → COMMIT          |

When you run `vibecrafted prune [agent]`, the launcher injects the runtime prompt
into the worker. The worker cuts. This skill is how _you_ drive that and prove it
landed. Improve the worker's behavior by editing the runtime prompt — not by
softening this skill into a report.

## The dispatcher ritual

### 1. Orient (Loctree first — read whole, don't rummage)

```bash
loct context --full --markdown   # read it WHOLE (pelikan); it gives you the map up front
loct doctor                      # snapshot identity + staleness
git status -sb                   # branch + dirty state (record it; never an excuse for inaction)
```

Reading the full context pack once is cheaper and truer than blind grep/find
sweeps. Grep is a last-resort magnifier, never the orientation plan.

### 2. Decide scope: cut-yourself vs dispatch

- **Hotfix-wprost (you cut directly):** a single, obviously-dead file/symbol you
  have _already proven_ dead this turn — `loct impact <file>` = 0 **and**
  `loct find --literal <name>` = 0 references. Trivial, mechanical, recoverable.
  `git rm` + one canonical commit. This is the explicit exception to "you don't
  cut code".
- **Dispatch the worker (the default for a sweep):** anything broad, multi-file,
  or requiring real classification. `vibecrafted prune codex` runs the action
  prompt. You stay the brain; the worker is the hands.

```bash
vibecrafted prune codex                         # default action brief (runtime prompt)
vibecrafted prune codex --file <scoped-brief>   # a narrowed prune cut
```

### 3. Spanko (await without staring)

Await by **process liveness + transcript growth + report materialization** — the
control-plane `observe`/`await` surface can be transiently inconsistent, so the
trustworthy signal is "the log grows and the run process is alive", then "the run
process exited and the report/commit exist". Do not poll tightly.

### 4. Verify before flip (HARD-GATE)

A worker's "I cut X" is a claim, not a flip. Before you accept a cut as done:

- the **commit SHA exists** and its diff is scoped to the claimed removals;
- **gates are green** (the worker ran them; verify via SHA + report, do not
  re-run gates and collide with concurrent work);
- the **proof holds** — especially: a delete justified by `impact = 0` alone is
  **not proven**. Confirm the worker cross-checked `loct find --literal`. The
  structural edge-graph undercounts some cross-module imports (e.g. Rust
  `use crate::a::b::Sym`); the literal scan is the authoritative reference layer.
- no **FORGOTTEN-GEM**, operator-deferred surface, or env-gated engine was
  deleted as "dead" (those are false-positive-dead — preserve).

### 5. Checkpoint / terminal state (HARD-GATE)

A prune run is done only in one of two states:

1. **CUTS LANDED** — ≥1 verified commit removing proven-dead surface; OR
2. **NOTHING TO PRUNE** — explicit, with per-candidate keep-evidence.

A findings report with no cuts when cuts were provable is not a finished run —
re-dispatch with the action directives, or cut the obvious ones yourself.

## Verdicts (reference)

`DELETE-NOW` · `ARCHIVE-THEN-DELETE` · `REVIVE` · `SCAFFOLD` · `VERIFY-FIRST` ·
`KEEP-RUNTIME` · `KEEP-BUILD` · `FORGOTTEN-GEM`.

`DELETE-NOW` / small `ARCHIVE-THEN-DELETE` are cut this run. `SCAFFOLD` becomes a
small fleet-executable follow-up. `FORGOTTEN-GEM` is never auto-deleted.

## Loctree command deck (loct 0.13.0-dev)

`loct health` · `loct dead` · `loct twins` · `loct cycles` · `loct follow all` ·
`loct hotspots` · `loct suppressions` · `loct env-truth` · `loct focus <dir>` ·
`loct slice <file>` · `loct impact <file>` · `loct query who-imports <file>` ·
`loct diff --since <rev>`.

Loctree's primary power is the structural map + embedded findings — lead with
`dead` · `twins` · `cycles` · `impact` · `slice` · `focus` · `hotspots` ·
`suppressions` · `env-truth`. The **literal trio** — `loct find --literal <text>` ·
`loct occurrences <id>` · `loct body <symbol>` (verified in loct 0.13.0-dev) —
came last, as a necessity: it keeps a raw identifier check _inside_ the map
instead of dropping to grep. Each hit still carries map context (`occurrence_kind`
— identifier vs string vs comment, symbol identity, file role, authority), which
for prune separates a real call from a comment/string/doc mention (DELETE-NOW vs
KEEP), and it backstops the edge-graph where it undercounts cross-module imports.
Fall back to grep only when `loct` is unavailable. If a probe is missing in the
installed `loct`, say so in the journal — do not pretend it ran.

## Living Tree Rule

Run in the operator's current checkout and branch. Do not create/switch branches
or worktrees unless the operator says the word "worktree". Re-read before editing;
adapt to concurrent hands. Never delete branches, stashes, worktrees, or hidden
WIP. If the repo is dirty at start, commit your cuts by explicit pathspec so you
do not sweep a peer's staged WIP. Never `--no-verify`. Never push — push is an
operator button. See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Anti-patterns

- Producing a findings report and calling the run done while provable cuts sit uncut.
- Deleting on `impact = 0` without a `loct find --literal` cross-check.
- Flipping a cut to done on the worker's claim instead of SHA + scoped diff.
- Auto-deleting hidden gems, FORGOTTEN-GEMs, or env-gated engines flagged "dead".
- Starting with `grep`/`find` inventory when Loctree can answer.
- Mandating a dozen `findings/*.md` files instead of one journal + real commits.
- Treating `loctree-mcp`/`loct` as the repo scope instead of the tooling layer.
- Pushing from a prune run.

## Final principle

The best run is not the one with the biggest deletion count. It is the one where
every surviving surface has a reason, every dead surface got cut or a verdict,
and every risky truth has a small next cut ready for the fleet. Make the repo
braver and more legible — by cutting, not by reporting.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
