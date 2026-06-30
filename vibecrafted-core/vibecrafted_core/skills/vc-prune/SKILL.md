---
name: vc-prune
version: 3.3.3
description: >
  Repository curation, not clear-cutting. Map what truly participates in runtime
  truth versus what is silently parked — then decide revive, archive, or delete.
  Includes the silencer strip: rip every `#[allow(...)]`, `// nosemgrep`,
  `eslint-disable`, `@ts-ignore`, `# noqa`, `# type: ignore`, panic-vs-skip pattern,
  and any other annotation that mutes a quality gate. Run the gates. Listen.
  Triage with care — `#[allow(dead_code)]` (and equivalents) is often the most
  valuable smell in a repo: parked work the team forgot about. Surface those as
  forgotten gems for the operator to decide.
  This skill is a gem hunter, not a clear-cutter.
  Trigger phrases: "prune", "strip dead code", "wyczyść mądrze", "strip the silencers",
  "zdejmij wszystkie ignore", "zobacz co realne", "forgotten gems",
  "co tam zapomnieliśmy".
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

# vc-prune — Curation, Not Clear-Cutting

> Don't burn the house down. Strip it to the load-bearing walls and report what you found behind the wallpaper.

## Operator Entry

### Living Tree / Worktree Rule

This workflow runs in the operator's current checkout and current branch. Do not create, switch to, or move execution
into a git worktree unless the operator explicitly asks for a worktree in this prompt. Generic words like "isolate", "
parallel", or "clean branch" are not enough. Re-read files before editing, adapt to concurrent changes, and report a
substrate failure if the current tree is too poisoned to continue safely.

See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate

Before this workflow performs repo-specific analysis, planning, implementation, review, release, or delegation, it MUST
run or consume the `vc-init` procedure for the assigned repo. If fresh `vc-init` evidence is absent, perform the init
pass first and treat workflow-specific work as blocked until repo truth exists.

`Loctree:loctree` is the default structural perception skill for that pass. Use Loctree before grep or docs-driven
claims to produce or refresh the Code-Derived Application Map: repo-view, focus, slice, impact, find, and follow as
relevant. Search for existing symbols and contracts before creating new ones; run impact before delete or major
refactor; run slice before editing.

The point is to find the hooks: load-bearing hubs, twins, dead code, drift, runtime entrypoints, and blast-radius traps.
If the task is explicitly non-repo or no-code, state the no-repo exception in the report. Otherwise, missing `vc-init`
/Loctree evidence is a process failure.

Launch through the command deck (see `vc-init` for the full operator-entry contract):

```bash
vibecrafted prune <agent> --file /path/to/prune-plan.md
vc-prune codex --prompt 'Strip silencers and listen'
```

A vibe-coded repo usually accumulates two layers of debris: **dead surface** (abandoned auth experiments, duplicate
Stripe handlers, dead serverless functions) and **silenced surface** (warnings muted in a hurry, tests that always skip,
panics that always fire). `vc-prune` separates both layers from runtime truth — and from each other.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## Axioms

1. **Aggressive pruning, with belief in the VCS archive.** Dead code is not bad code — it's a graveyard of valuable
   ideas. Its place is in Git history, not the runtime. Cut without sentiment — but only after axiom 4.
2. **Move on over backward compatibility.** Rotten abstractions blocking stabilization get cut cleanly. The dependency
   graph is part of runtime truth.
3. **The code knows. Strip the silence and listen.** Every silencer is a deferred conversation. Most were added in a
   hurry. The only honest test of which still earn their keep is to rip them all out and let the toolchain speak.
4. **`#[allow(dead_code)]` (and cousins) is often the most valuable signal in a repo.** It usually marks parked work — a
   90%-complete login flow, an export pipeline for a churned customer, a debug visualizer no one mentioned to new hires.
   These are **forgotten gems**, not garbage. Surface them; never auto-delete.

## Core Contract

- For non-trivial prune, `vc-agents` external dispatch is the default first move.
- Assume 30% of a vibe-coded repo is dead scaffolding.
- Classify every candidate: `KEEP-RUNTIME`, `KEEP-BUILD`, `MOVE-ARCHIVE`, `DELETE-NOW`, `VERIFY-FIRST`, or
  `FORGOTTEN-GEM`.
- Prefer cutting whole dead vertical slices over trimming symbolic leaves.
- Tighten contracts after every wave: manifests, docs, CI, package bounds.
- Run gates after every wave. Require one real smoke or build proof.

## Delegation Doctrine

| Need                                             | Best model |
| ------------------------------------------------ | ---------- |
| Archaeology, hidden reachability, gem-hunting    | Claude     |
| Exact deletions, manifest tightening, mech. work | Codex      |
| Radical simplification, cutting whole subsystems | Gemini     |

## Workflow

### Phase 1 — Define the runtime cone

Capture: real entrypoints, mandatory user flows, build/release path. Do not start from "unused exports" — start from "
does this serve live traffic?"

### Phase 2 — Map with `loct`

```bash
loct auto && loct manifests && loct hotspots && loct dead
loct routes      # web/API
loct commands    # desktop/Tauri
loct events
```

### Phase 3 — Prune in waves (safest → riskiest)

- **Wave 1 — AI exhaust & prototype scaffolding.** `v1_backup.ts`, `old_auth_handler.js`, `stripe_test_claude.ts`, dead
  `.claude/` `.codex/` session folders, stale screenshots.
- **Wave 2 — Whole dead vertical slices.** Frontends with no consumers, alternate login pages never mounted, webhook
  handlers replaced by SaaS. Cut the strand, let Git archive it.
- **Wave 3 — Unreachable product surface.** Unmounted routes, duplicate engines (Prisma + raw SQL doing the same thing),
  dead feature flags retained after launch.
- **Wave 4 — Contract tightening.** `package.json` deps, `Cargo.toml` features, `pyproject.toml` extras, `.env.example`
  stale secrets, CI workflows.
- **Wave 5 — The Silencer Strip.** Separate wave because it's not about removing dead code — it's about un-muting the
  toolchain so live code can speak. See below.

### Phase 4 — Verify reality

Green static gates are necessary, not sufficient. Add one real proof path: boot the app, run the CLI, hit the main
route.

---

## Wave 5 — The Silencer Strip (Strip and Listen)

### Inventory

```bash
# Rust
rg -n '#\[allow\(' src-tauri/src
rg -n 'nosemgrep' .

# TypeScript / JavaScript
rg -n 'eslint-disable' src
rg -n '@ts-(ignore|nocheck|expect-error)' src
rg -n 'biome-ignore' src

# Python
rg -n '# noqa' .
rg -n '# type: ignore' .
rg -n '# pylint: disable' .
rg -n '@pytest\.mark\.skip' .

# Go
rg -n '//nolint' .
rg -n 'testing\.Short\(\) \|\| t\.Skip' .

# Test theater across languages
rg -n 'panic!\("Test requires|throw new Error\("requires' .
rg -n 'it\.skip|test\.skip|describe\.skip' .
```

Capture **counts per category**. That's your before-baseline.

### Strip ALL of them in one pass

Bulk-delete the lines. Do not pre-curate "obvious keepers" — the bias that put them there is the same bias that would
protect them. Let the toolchain decide.

### Run gates

Whatever the repo already has — do not invent new ones:

```bash
cargo clippy --all -- -D warnings && cargo test --all
pnpm lint:tsc && pnpm code:all && pnpm vitest run
ruff check . && mypy . && pytest          # Python
golangci-lint run && go test ./...        # Go
semgrep --config=auto .                   # if available
pre-commit run --all-files                # if installed
```

### Triage with care

| Finding                         | Resolution                                                                                                                                                             |
| ------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Authentic code smell            | **Fix root cause.** Refactor, write proper types, add adapter, drop lock before await.                                                                                 |
| False positive                  | **Refactor stylistically** so the warning never fires. No re-add.                                                                                                      |
| Genuine technical constraint    | **Re-add silencer with incident-grade comment**: WHY (technical reason), WHEN (under what conditions), WHERE (specific code path). Not "intentional", not "by design". |
| **Forgotten gem (gentle path)** | **Do not delete. Report.** A `dead_code` warning on a 200-line module with thoughtful structure is parked work. Add to **Forgotten Gems Report**. Operator decides.    |
| Test theater unmasked           | **Stop. Bigger than the silencer.** A panic-or-skip pattern that always evaluates one way means the test was never real. Open a separate plan for real wiring.         |
| Truly dead code revealed        | The silencer was hiding `dead_code` on a one-liner stub or scratch file. Delete — but only after a fast forgotten-gem check.                                           |

The rule: **a silencer earns its keep only with a written technical reason that another engineer six months from now
would accept as serious.** Vague "intentional" comments are not serious. Equally: **delete code only when it is
unambiguously trash** — anything in between goes to the Forgotten Gems Report.

### Forgotten Gems Report

Output of Wave 5 is **not** a smaller repo — it's a written report. Save to
`$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_forgotten-gems.md`.

> See [references/case-studies.md](references/case-studies.md) for the full Forgotten Gems Report template, the
> test-theater report template, and concrete real/hypothetical case studies (Vista 0.67.3 silencer-strip, vista-portal
> billing-service equivalent, surprise-findings catalog).

Test theater is debt, not gem. It always gets a follow-up plan saved to `<timestamp>_test-theater.md`. Never a silencer
reinstatement.

### Acceptance for the wave

- Remaining silencer count is a **small fraction** of the inventory (target ≤25%, often ≤10%).
- Every remaining silencer carries an incident-grade comment.
- Every gate runs green without `--no-verify`, `cargo clippy --allow-dirty`, `pnpm lint --fix --quiet`, or any other "
  make it green by hiding it" trick.

### Surprise findings are the prize

Watch for: tests that always skip / always panic, `dead_code` allow on functions whose only caller was deleted three
releases ago, `@ts-ignore` on types correct for a year, `eslint-disable jsx-a11y/...` on real a11y violations,
`nosemgrep: react-dangerouslysetinnerhtml` on HTML that is **not** sanitized, `# type: ignore[arg-type]` on a function
whose signature was fixed two refactors ago. Each is a real bug or a real lie the silencer was hiding.

## Anti-Patterns

- Deleting ten dead symbols while a whole abandoned subsystem still stands.
- Trusting "unused" reports without checking dynamic loading via framework router.
- Preserving a chaotic 2000-line file because "we might need it" — that's what Git history is for.
- Cleaning code but leaving stale dependencies in the lockfile.
- Stripping silencers selectively. The whole point of Wave 5 is to bypass that bias.
- Mass-restoring silencers because there were "too many warnings". That's burying the message again.
- Adding new silencers to silence newly-uncovered warnings. Fix the warning or refactor it away.
- Treating `panic!("Test requires X")` as a real gate, or `it.skip` / `@pytest.mark.skipif` as harmless. Tests that
  always skip do not exist; they cost reviewer attention.
- Auto-deleting code that a `dead_code` allow was hiding without a forgotten-gem check first.
- Treating Wave 5 as adversarial. Past engineers added silencers for plausible reasons. Wave 5 is the reread, not a
  verdict.

## The Pruning Principle

Do not ask the repo to explain every scar. Ask it to justify every surviving surface.

If a surface does not run in production, build the release, or test integrity — the move is **not** automatically
delete. The move is **decide with intent**: revive, archive, or delete. The skill exists to surface decisions, not make
them on autopilot.

**The toolchain is not an enemy to be muted. It is a witness to be interrogated.** Strip the silence. Run the gates.
Listen. Then decide — case by case, with a written reason — what genuinely deserves to stay quiet, what needs a real
fix, and what was a forgotten gem hiding behind the silencer all along.

A repo that has been through `vc-prune` is not necessarily smaller. It is **legible**. Every surviving surface, every
surviving silencer, every surviving test has a written reason to be there. That is the win.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
