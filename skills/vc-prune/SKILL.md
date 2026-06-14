---
name: vc-prune
version: 4.0.0
description: "Loctree-first repository health and prune discovery: find, classify, prove, scaffold, and cut only verified dead surfaces."
loctree_value: "primary sensory layer for dead code, shadows, suppressions, env truth, drift, literal evidence, blast radius, and tree-shaking"
aicx_value: "intent, session, and decision-context retrieval before classifying dormant work"
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
> command such as `vc-init codex` / `vibecrafted init claude`.
>
> The sole native in-process carve-out is `vc-delegate`.

<!-- /fleet-imperative -->

# vc-prune — Find, Prove, Cut

`vc-prune` is not "delete unused stuff." It is a repository health and prune
discovery workflow that turns hidden dead weight into operator-grade decisions:
delete, archive, revive, scaffold, or leave alone with evidence.

The default posture is bold, but not sloppy:

- **Find broadly.** Dead surfaces, shadows, twins, missing handlers, forgotten
  state, silencers, monoliths, and hidden gems are all in scope.
- **Classify honestly.** Not every smell is a deletion. Many findings become
  `vc-scaffold` cuts.
- **Prove before cutting.** A prune commit is allowed only when live references,
  runtime reachability, and blast radius are understood.
- **Cut whole dead verticals.** When a slice is proven dead, prefer deleting the
  full stale path over trimming leaves forever.

## Operator Entry

Launch through the runtime, not legacy shell helper thinking:

```bash
vibecrafted prune
vibecrafted prune claude
vibecrafted prune codex --file /path/to/prune-brief.md
vibecrafted prune gemini --prompt "Map dead workflow surfaces and prepare cuts"
```

With no agent, `vibecrafted prune` defaults to the configured prune agent. With
no `--prompt` or `--file`, it launches the built-in repository health / prune
discovery brief. That default brief is actionable: it should produce artifacts
and may commit only removals proven safe.

## Target Contract

Keep two targets separate:

| Target                   | Meaning                                                                  |
| ------------------------ | ------------------------------------------------------------------------ |
| **Task target**          | `$REPO_ROOT`, the repository being investigated.                         |
| **Tooling proof target** | Loctree MCP and `loct` CLI, exercised as the sensory/runtime proof path. |

Do not confuse Loctree with the repository scope unless the current repository
actually contains Loctree code. The repo is the patient. Loctree is the scanner.

Do not market this as a test-only run. In practice, the workflow is a strong
runtime proof because it forces Loctree, dispatch, artifacts, reports, and
verification to cooperate on a real repository.

## Living Tree Rule

This workflow runs in the operator's current checkout and current branch. Do not
create, switch to, or move execution into a git worktree unless the operator
explicitly asks for a worktree. Re-read files before editing. Adapt to
concurrent work. Never revert someone else's changes.

If the repo is dirty at start, record that fact and avoid sweeping unrelated WIP
into prune commits.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Loctree First

Loctree is the canonical tool of choice. Grep is not the plan.

Start with current structure:

```bash
loct context --full --markdown
loct doctor
loct env-truth
loct follow all
```

Use the strongest available Loctree surfaces:

| Need                        | Primary command                                                             |
| --------------------------- | --------------------------------------------------------------------------- |
| Repo map and task framing   | `loct context --task "<task>" --full --markdown`                            |
| Module ownership            | `loct focus <dir>`                                                          |
| Edit/deletion blast radius  | `loct slice <file>` and `loct impact <file>`                                |
| Literal evidence            | `loct find --literal <text>`, `loct occurrences <id>`, `loct body <symbol>` |
| Dead/twins/cycles/hotspots  | `loct follow all` and `loct health`                                         |
| Silencers/policy exceptions | `loct suppressions`                                                         |
| Env/config truth            | `loct env-truth`                                                            |
| Drift since a base          | `loct diff --since <rev>`                                                   |
| Attribution when useful     | `loct blame <file-or-symbol>`                                               |
| Tree-shaking / distance map | `loct dist <entrypoint-or-scope>`                                           |
| Report artifact             | `loct report`                                                               |

If a command is missing in the installed `loct`, record that as tooling evidence
in the prune journal and use the closest Loctree alternative. If Loctree cannot
answer and a raw text fallback is necessary, include the failed Loctree command,
the reason for fallback, and the fallback command in the report artifact. Then
use the fallback as a local magnifier only. Do not present fallback grep as the
primary method.

## AICX Check

Before deleting dormant or surprising surfaces, check intent history when
available:

```bash
aicx sessions list --cwd
aicx extract --agent <agent> --session <id> --conversation
```

Memory does not overrule code, but it can reveal whether "dead" is actually a
parked customer feature, a half-finished migration, or a known abandoned path.

## Findings Taxonomy

Every candidate receives one verdict:

| Verdict               | Meaning                                                                    |
| --------------------- | -------------------------------------------------------------------------- |
| `DELETE-NOW`          | Zero live references, low blast radius, no hidden-gem signal, safe commit. |
| `ARCHIVE-THEN-DELETE` | Useful context exists, but runtime surface is dead; archive summary first. |
| `REVIVE`              | Dormant capability is valuable and should be wired into runtime.           |
| `SCAFFOLD`            | Real problem, too broad/risky for prune; create a focused follow-up cut.   |
| `VERIFY-FIRST`        | Evidence is insufficient; no deletion yet.                                 |
| `KEEP-RUNTIME`        | Live product/build/test/release surface.                                   |
| `KEEP-BUILD`          | Needed for packaging, CI, generated artifacts, or release machinery.       |
| `FORGOTTEN-GEM`       | Valuable dormant code; preserve and ask operator to decide.                |

## Investigation Scope

Look for these classes of repository truth.

### 1. Dead Parrots / Orphaned Surfaces

- dead code
- unused tools
- unused scripts
- unreachable commands
- stale entrypoints
- abandoned generated files
- orphaned docs that describe removed behavior

### 2. Silly Exports

- self-reexports
- pointless reexports
- exports with no runtime or test usage
- public surfaces that are cargo-cult leftovers
- bootstrapping, bottle, component, or function surfaces without real callers

### 3. Missing Handlers / Missing Callers

- declared commands without handlers
- handlers unreachable from runtime
- routes, actions, or events without callers
- UI actions without target/action mapping
- config keys with no consumer
- consumers of config keys that are never produced

### 4. Twins / High Semantic Similarity

- duplicated functions
- near-identical modules
- old/new implementations living side by side
- parallel implementations of the same concept

### 5. Cycles and Race Risks

- dependency cycles
- runtime control-plane cycles
- async/state races
- stale state vs runtime truth mismatches
- lock, heartbeat, pid, or state divergence

### 6. Crowds / Ambiguity Hotspots

- overloaded names
- too many similarly named commands or components
- symbols likely to confuse humans or agents
- command/workflow/skill ambiguity

### 7. Shadows

- code technically called but shadowed by a newer path
- fallback paths silently dominating primary paths
- old implementations masked by wrappers
- features present in code but unreachable in product flow

### 8. Linter Silencers and Policy Exceptions

Catalog, do not blindly remove:

- Rust `#[allow(...)]`
- ESLint disable comments
- TypeScript `@ts-ignore`, `@ts-expect-error`, `@ts-nocheck`
- Python `# noqa`, `# type: ignore`, pylint disables
- ShellCheck disables
- Semgrep `nosemgrep`
- skipped, ignored, or theater tests
- any local "ignore this warning" mechanism

Use `loct suppressions` first. Classify each as justified, stale, dangerous,
test theater, forgotten gem, or follow-up.

### 9. Monoliths

- 1500+ LOC files
- files with too many responsibilities
- modules that repeatedly become collision hotspots
- candidates for decomposition cuts rather than immediate deletion

### 10. Forgotten Local State

Inspect read-only:

- local branches
- stashes
- worktrees
- untracked/ignored relevant files
- hidden WIP surfaces

Do not delete branches, stashes, worktrees, or hidden WIP without explicit
operator approval.

### 11. Hidden Gems

- useful but unreachable code
- dormant capabilities
- tooling that could become a robust, smart, secure, or healing extension of the
  living runtime

Do not prune hidden gems by default. Classify them as preserve, scaffold, or
revive.

## Cut Rules

You may be bold when the evidence is strong:

- Delete whole dead vertical slices.
- Remove obsolete compatibility wrappers when the new path is proven dominant.
- Collapse twins when one implementation clearly shadows the other.
- Remove stale docs and generated artifacts that describe dead behavior.
- Tighten manifests, package metadata, and config after code deletion.

But these are hard gates:

- No deletion based on vibes.
- No deletion without Loctree or equivalent evidence.
- No deletion of hidden WIP, branches, stashes, or worktrees.
- No deletion of live build/release/test scaffolding just because product code
  does not import it.
- No `--no-verify`.
- No push. Push is an operator button.

If a candidate is broad, ambiguous, or high-blast-radius, produce a scaffold cut
instead of forcing a prune commit.

## Workflow

### Phase 0 — Orientation

1. Run or consume fresh `vc-init` evidence.
2. Record branch, HEAD, dirty state, and artifact root.
3. Run `loct context --full --markdown`.
4. Run `loct doctor` and record tool health.
5. If Loctree is stale or broken, record the failure and choose the safest
   Loctree fallback before any raw text search.

### Phase 1 — Runtime Cone

Map what must stay:

- product entrypoints
- CLI commands
- app routes
- event handlers
- build/release/installer paths
- generated artifact paths
- tests that genuinely prove runtime behavior
- config/env producers and consumers

Use `loct focus`, `loct slice`, `loct impact`, `loct env-truth`, and literal
queries.

### Phase 2 — Discovery Sweep

Run the Loctree probes available in this checkout:

```bash
loct follow all
loct health
loct suppressions
loct env-truth
loct diff --since HEAD~1
loct report
```

Also run `loct dead`, `loct dist`, `loct blame`, `loct twins`, `loct cycles`,
`loct shadows`, or `loct zombies` when the installed Loctree exposes them. If a
named probe is unavailable, say so in the report instead of pretending.

### Phase 3 — Classification

Group findings into the taxonomy above. For each candidate, capture:

- path/symbol
- finding class
- Loctree command evidence
- live references or absence evidence
- blast radius
- hidden-gem check
- recommended verdict
- whether a commit is allowed

### Phase 4 — Safe Cuts

Commit only `DELETE-NOW` or small `ARCHIVE-THEN-DELETE` items with:

- zero live references or an explained dynamic-loading exception
- low blast radius
- no hidden-gem signal
- passing focused verification
- deletion count and files changed in the report

Prefer one coherent vertical deletion per commit. Do not mix unrelated cleanup
with discovery artifacts.

### Phase 5 — Scaffold the Rest

Most valuable prune output is not a deletion. It is a clean follow-up queue.
Prepare small, fleet-executable `vc-scaffold` cuts for:

- monolith decomposition
- ambiguous workflow/command surfaces
- race/state repair
- shadow replacement
- hidden gem revival
- silencer root-cause fixes
- test-theater rewiring

## Required Artifacts

Write under:

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/prune/
```

Expected shape:

```text
reports/${RUN_ID}_JOURNAL.md
findings/dead-parrots.md
findings/silly-exports.md
findings/missing-handlers-callers.md
findings/twins.md
findings/cycles-races.md
findings/crowds-shadows.md
findings/linter-silencers.md
findings/monoliths.md
findings/forgotten-local-state.md
findings/hidden-gems.md
scaffold/README.md
scaffold/cuts/*.md
```

If runtime variables are unavailable, create the closest equivalent under the
current Vibecrafted artifacts tree and report the exact path used.

## Journal Requirements

The final journal must include:

- repository inspected
- branch, HEAD, and dirty/clean state at start
- Loctree MCP evidence, if available
- `loct` CLI evidence
- any Loctree failures or fallback notes
- AICX/session evidence consulted, if any
- candidates found
- candidates removed
- candidates intentionally kept
- hidden gems worth preserving or reviving
- branches, stashes, worktrees, and hidden WIP observed
- artifacts written
- commands/evidence used
- commit SHA(s), files changed, deletion count, and blast-radius evidence for
  each prune commit
- "nothing to prune" with evidence when no deletion is safe

## Model Bias

Use model strengths deliberately:

| Need                                                              | Best fit |
| ----------------------------------------------------------------- | -------- |
| Archaeology, hidden-gem interpretation, intent recovery           | Claude   |
| Exact deletion, tests, manifests, mechanical cleanup              | Codex    |
| Radical simplification, monolith decomposition, architecture cuts | Gemini   |

For broad repo health runs, multiple agents are useful only when the artifacts
are separated into small cuts. Do not launch a crowd into one giant prompt.

## Anti-Patterns

- Starting with `grep` inventory when Loctree can answer.
- Treating `loctree-mcp` or `loct` as the repo scope instead of the tooling
  proof target.
- Calling a finding "dead" without runtime cone evidence.
- Deleting linter silencers blindly and calling that prune.
- Preserving a dead subsystem because deleting one function feels safer.
- Producing one giant "fix everything" scaffold.
- Auto-deleting hidden gems.
- Hiding Loctree failures.
- Pushing from a prune run.

## Final Principle

`vc-prune` should make a repo braver and more legible.

The best run is not necessarily the one with the biggest deletion count. The
best run is the one where every surviving surface has a reason, every dead
surface has a verdict, and every risky truth has a small next cut ready for the
fleet.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
