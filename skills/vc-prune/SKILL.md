---
name: vc-prune
version: 2.0.0
description: >
  Repository pruning and runtime or publish-cone extraction skill. Use when the
  team wants to strip a repo to the code that truly participates in runtime,
  shipping, or published API, separate product code from tooling, archives,
  experiments, agent exhaust, and stale surfaces, and run ruthless cleanup with
  proof instead of sentiment. External `vc-agents` is the default first
  move for non-trivial prune work.
---

# vc-prune - Runtime / Publish Cone Pruning

> A repo is a living tree.
> Keep the trunk. Cut the scaffolding. Export history out of the hot path.

This skill asks a sharper question than "what looks messy?":
what must survive for runtime truth, build truth, release truth, or publish
truth, and what exists only because the repo kept absorbing tools, reports,
experiments, migrations, and sentiment?

The goal is not cosmetic cleanup.
The goal is to reduce the product surface until the surviving repo is explicit,
defendable, and easier to ship.

## Core Contract

- For any non-trivial prune, external `vc-agents` is the default first
  move.
- Define the cone before proposing deletes.
- For apps, define a runtime cone.
- For libraries, packages, crates, and workspaces, define a publish cone.
- Use `loct` as the first structural map, but choose commands by repo shape
  instead of forcing one favorite command everywhere.
- `loct dist` is optional and only valid when a frontend bundle has usable
  source maps.
- Classify every candidate as `KEEP-RUNTIME`, `KEEP-BUILD`, `KEEP-QA`,
  `KEEP-PUBLISH`, `MOVE-ARCHIVE`, `DELETE-NOW`, or `VERIFY-FIRST`.
- Prefer deleting whole dead vertical slices over trimming symbolic leaves.
- Tighten contracts immediately after each pruning wave: manifests, handlers,
  scripts, features, env flags, exports, docs, and CI.
- Run gates after every wave and require one real smoke, install, import, or
  publish proof for the surface you touched.

## Delegation Doctrine

Pruning mixes archaeology, exact surgery, and bold simplification.
Do not default to native delegation unless the task is tiny and genuinely
model-agnostic.

Use `vc-agents` first whenever the prune goes beyond obvious generated
artifacts.

| Dimension | Best model | Why |
| --- | --- | --- |
| Runtime or publish-cone discovery, hidden reachability, config archaeology, stale glue | Claude | Best at patient investigation, logic tracing, and proving whether a surface is truly live or merely looks live. |
| Exact deletions, manifest tightening, registration cleanup, bounded refactors | Codex | Best at precise, low-noise implementation and keeping the cleanup mechanically correct. |
| Radical simplification, archive taxonomy, "cut the whole subsystem" reframing | Gemini | Best when the repo needs a stronger new shape, not just a safer local trim. |

Rules:

- Use at least one external agent for any repo-wide prune beyond `dist/`,
  caches, logs, and similar disposable output.
- Good default split: Claude as archaeologist plus Codex as surgeon.
- Add Gemini when the repo is bloated enough that the hardest part is deciding
  what shape should survive.
- Native `vc-delegate` is only acceptable for tiny follow-up sweeps that
  do not need model-specific strengths.

## Modes

Choose the mode from user intent.

- `conservative`
  Use when the user wants safety, staging, or archive-first cleanup.
  Default uncertain candidates to `VERIFY-FIRST` or `MOVE-ARCHIVE`.
- `radical`
  Use when the user explicitly asks for ruthless cleanup, no mercy, aggressive
  pruning, or says it is cheaper to rebuild than preserve zombies.
  Once evidence clears the threshold, default to `DELETE-NOW`, not sentimental
  preservation.

If the user says "bez litosci", "radykalnie", or equivalent, use `radical`.

## The Pruning Classes

| Class | Meaning | Action |
| --- | --- | --- |
| `KEEP-RUNTIME` | Participates directly or transitively in app or service runtime | Keep; refactor separately if ugly |
| `KEEP-BUILD` | Required to build, package, sign, bundle, release, or ship | Keep; do not delete with runtime cuts |
| `KEEP-QA` | Required to verify behavior, preview flows, smoke paths, or release confidence | Keep; move later only with replacement proof |
| `KEEP-PUBLISH` | Required for published library/crate/package API, installability, docs examples, or release process | Keep; delete only with explicit publish-path proof |
| `MOVE-ARCHIVE` | Historical but still intentionally worth preserving outside the hot repo surface | Move to archive branch, attic repo, or external archive |
| `DELETE-NOW` | Generated, disposable, reproducible, whole-dead, or clearly unreachable | Delete directly |
| `VERIFY-FIRST` | Suspicious and probably dead, but dynamic loading, registries, features, or configs may still reach it | Prove with structural evidence plus gates before removal |

## Workflow

### Phase 1 - Define the Cone

Start by naming what kind of repo you are pruning:

- app or service
- desktop app or mixed frontend/backend product
- CLI
- library, package, crate, or workspace
- mixed product plus tooling monorepo

Then define what must survive.

For apps and services, capture:

- real entrypoints
- mandatory user flows that must still work after pruning
- build, bundle, and release path
- preview or smoke path that gives user-visible proof

For libraries, packages, crates, and workspaces, capture:

- importable or published public API
- bins, examples, or docs paths that are part of the contract
- workspace members that are intentionally shippable
- release, package, or publish path

Useful shell evidence by repo family:

```bash
# JS / TS
rg -n '"(main|module|exports|bin|workspaces|scripts)"\s*:' package.json

# Python
rg -n "console_scripts|project.scripts|tool.poetry.scripts|entry-points" pyproject.toml setup.cfg setup.py

# Rust
rg -n '^\[workspace\]|^\[package\]|^\[lib\]|^\[\[bin\]\]|^members =|^default-members =|^publish =|^path =' -g 'Cargo.toml'
```

Do not start with "unused exports".
Start with "what must boot, build, or publish".

### Phase 2 - Map the Cone with `loct`

Run the generic structural pass first:

```bash
loct auto
loct manifests
loct health
loct hotspots
```

Then choose commands based on repo shape.

Use these in most repos:

```bash
loct focus <dir>
loct slice <file>
loct impact <file>
loct query who-imports <path-or-symbol>
loct dead
loct zombie
loct twins
loct coverage
loct findings --summary
```

Framework-aware branches:

- Web/API backends: `loct routes`
- Tauri/event-driven desktop apps: `loct commands`, `loct events`,
  `loct pipelines`, `loct trace <handler>`
- Frontend bundles with source maps: `loct dist`
- CSS-heavy frontends: `loct layoutmap`
- Rust crates and workspaces: prioritize `loct manifests`, `loct hotspots`,
  `loct zombie`, `loct health`, and `loct coverage` over `loct dist`

Doctrine:

- `loct manifests` is mandatory early because it reveals the real build,
  package, and workspace contract.
- `loct hotspots` tells you which files are structural hubs and therefore high
  blast-radius.
- `loct coverage` helps explain why some surface still matters even when it is
  not on the main runtime path.
- `loct dist` is a specialist proof tool, not the universal first step.
- Do not make prune methodology Vite-centric, Tauri-centric, or Visto-centric.
  The repo decides which `loct` evidence matters.

### Phase 3 - Classify the Repo Surface

Classify root directories before diving into leaf files.
This prevents wasting time micro-pruning a subtree that should simply move out.

Typical early classifications in AI-grown repos:

- Usually `DELETE-NOW`:
  `dist/`, `build/`, coverage outputs, test reports, logs, caches, generated
  screenshots, and reproducible proof artifacts
- Usually `MOVE-ARCHIVE`:
  `.ai-*`, `.codex/`, `.claude/`, `.junie/`, `.trash/`, `.attic/`,
  `docs/archive/`, abandoned prototypes, superseded landing experiments
- Usually `KEEP-BUILD`:
  `.github/workflows/`, release scripts, bundling resources, packaging helpers,
  `build.rs`, `xtask/`, installer scripts
- Usually `KEEP-QA`:
  `tests/`, `e2e/`, smoke harnesses, fixtures, test snapshots, integration
  scripts
- Usually `KEEP-PUBLISH`:
  `examples/`, `benches/`, docs examples, crate/package metadata, publish
  scripts, public API shims that are intentionally shipped
- Usually `VERIFY-FIRST`:
  alternate app shells, preview shims, duplicate engines, workspace members,
  feature-gated modules, vendor folders, macro helpers, manifest generators

Special handling:

- Do not assume `scripts/` is trash.
  In messy repos, `scripts/` often contains half the actual build contract.
- Do not assume `examples/`, `benches/`, `fuzz/`, or `xtask/` are disposable in
  Rust repos.
  They often encode publish, test, or operational truth.
- Do not assume docs-site glue is dead just because the product runtime does
  not import it.
  If it supports installability, onboarding, or publish proof, classify it
  intentionally.

### Phase 4 - Prune in Waves

Never do the whole cleanup in one cut.
Prune in waves from safest to riskiest.

#### Wave 0 - Disposable Surface

Remove generated and reproducible output first:

- build outputs
- report folders
- logs
- cached artifacts
- stale screenshots and preview outputs

This wave should not change runtime or publish truth at all.

#### Wave 1 - Agent Exhaust and Archaeology

Move or remove:

- agent session folders
- planning/report residue
- superseded prototypes
- attic/trash buckets inside the repo
- archived docs that are no longer part of the working product surface

This wave reduces noise for every later analysis.

#### Wave 2 - Dev-Only Bleed Into Boot or Publish

Look for code that exists only for local hacking but leaks into the main app,
package, or release path:

- browser mocks imported by default
- preview-only providers in real entrypoints
- dual shells and duplicate startup paths
- env-gated branches with broad permanent imports
- diagnostics exposed only for local inspection
- dead feature flags or compatibility adapters retained after migration
- docs/demo crates or packages that no release, CI, or docs path still uses

These are high-value cuts because they sharpen the boundary between product and
debug scaffolding.

#### Wave 3 - Whole Dead Vertical Slice

Before trimming leaves, ask whether an entire feature strand is already dead.

Good candidates:

- frontend service with no runtime consumers
- companion types or DTOs used only by that service
- test file covering only that dead slice
- backend command or module serving only that slice
- workspace member or crate serving only a dead feature
- examples, benches, or docs glue kept alive only by that dead member
- barrel exports or public shims that keep pretending the slice exists

If the answer is "only tests, registries, or docs glue remain", cut the whole
slice.

#### Wave 4 - Unreachable Product or Publish Surface

Now prune inside the surviving code surface:

- unmounted routes
- unregistered commands and handlers
- dead event bridges
- panels or pages no live route reaches
- duplicate services or engines
- stale fallback systems retained after migration
- feature folders that survive only through legacy glue
- crate modules behind dead feature flags
- examples and benches nobody runs and no docs or CI path references

Use the dead-subtree rule here:
if a subtree exists only to support a removed path, delete the whole subtree
instead of trimming leaves forever.

#### Wave 5 - Contract Tightening

After every removal wave, immediately clean the references that still point at
deleted surface:

- package scripts
- Python entrypoints and tool config
- Cargo workspace members, features, and bins
- env vars and typings
- CI workflows
- manifests
- docs indexes
- test matrices
- import aliases
- re-export barrels
- handler and route registration
- release and setup scripts

If you skip this wave, the repo still behaves as if dead code is alive.

API narrowing belongs here too:
do not only delete files; also shrink public module surfaces when runtime or
publish truth needs a smaller contract.

### Phase 5 - Verify Reality

After each wave, run the closest safe gates for the repo in this order.

TypeScript / JavaScript repos:

```bash
<package-manager> lint
<package-manager> typecheck
<package-manager> test
<package-manager> build
```

Python repos:

```bash
uv run ruff check .
uv run mypy .            # when configured
uv run pytest
```

Rust crates and workspaces:

```bash
cargo fmt --check
cargo clippy --workspace --all-targets --all-features -- -D warnings
cargo test --workspace --all-features
cargo publish --dry-run -p <crate>   # when publish truth matters
```

Mixed repos:

- combine the relevant gates from each runtime slice
- add semgrep when available
- run `loct dist` only when a source-map-backed frontend bundle exists

Always add one real proof path after structural pruning:

- smoke the live app
- run the CLI for a meaningful command
- import the library from a real sample
- dry-run the package or publish path

Green static gates are necessary, not sufficient.

## False Positive Families

Treat these as suspicious until proven dead:

- icon registries and giant visual barrels
- barrel re-exports that mirror live internal types
- context modules that re-export convenience types
- event hub alias wrappers
- dynamic registries and plugin systems
- feature-gated modules
- proc-macro or macro-generated helper surfaces
- huge DTO/type files where only some exports are dead
- workspace glue crates and examples tied to docs or CI
- env-gated imports in boot files

Rule:
when a file belongs to a false-positive family, do not trim by symbol first.
Use `loct impact`, `loct query who-imports`, `rg`, manifest checks, and gates
to decide whether the whole file is dead, only the public API is stale, or the
report is noisy.

## Evidence Rules

Use this hierarchy when deciding whether a candidate can go:

1. `loct impact` and `loct query who-imports` say nothing consumes it
2. `loct manifests` plus `rg` find no config, script, manifest, route,
   handler, workspace, feature, or publish reference
3. No dynamic import, registry, env gate, macro expansion, plugin init, or
   `build.rs` path still reaches it
4. Build and compile gates still pass
5. `loct dist` delta improves or stays clean when `loct dist` is applicable
6. One real smoke, import, install, or publish proof still passes

If only rules 1-2 are true, classify as `VERIFY-FIRST`.
If rules 1-5 are true in `radical` mode, deletion is usually safe.
If all six are true, deletion is strongly justified.

Static tools are hints, not verdicts.
Dead-export scanners, unused-file detectors, and generic lints do not
understand registries, feature flags, publish contracts, or dynamic loading by
themselves.

## Prioritization Heuristic

When multiple candidates are available, prefer this order:

1. whole dead vertical slice
2. dev-only bleed from boot or publish path
3. dead workspace member or duplicate subsystem
4. dead public API or stale barrel re-export
5. isolated dead helper with zero blast radius
6. cosmetic symbol trimming

If you are spending time trimming leaf exports while a dead subsystem or stale
workspace member is still present, you are pruning in the wrong order.

## Output Format

Use this exact top-level structure in the final response:

```text
Current state: <what is bloated, mixed, or leaking>
Proposal: <target repo shape and why it is safer>
Migration plan: <ordered pruning waves>
Quick win: <one immediate high-impact cleanup>
```

Then include:

- Runtime or publish cone summary
- `KEEP/MOVE/DELETE/VERIFY` classification list
- Wave plan with blast radius
- `loct` evidence summary, including `loct dist` only when applicable
- Gate results
- Open risks and what still needs proof

## Integration with VibeCraft Pipeline

Use this flow for major cleanup:

```text
vc-init -> vc-agents -> vc-prune -> vc-followup -> vc-marbles
```

- `vc-init` gives history plus structure
- `vc-agents` is the default first move for non-trivial prune work
- `vc-prune` defines the cone and removes non-runtime or non-publish
  surface
- `vc-followup` verifies truth after the cuts
- `vc-marbles` loops if residual P1/P2 chaos remains

## Anti-Patterns

- Making prune methodology Vite-centric, Tauri-centric, or Visto-centric
- Centering the whole skill around `loct dist`
- Using native delegation first when the cleanup clearly wants model-specific
  strengths
- Deleting by folder-name intuition alone
- Treating docs, tests, build scripts, and publish scaffolding as equally
  disposable
- Running one giant cleanup PR across runtime, QA, docs, CI, and packaging
- Trusting "unused" reports without checking registries, dynamic loading, or
  feature gates
- Preserving fossils because deleting them feels emotionally risky
- Archiving everything inside the same repo forever instead of moving it out
- Trimming ten dead symbols while a whole dead subsystem is still standing
- Cleaning code but leaving handlers, manifests, features, scripts, or env
  flags behind

## The Pruning Principle

Do not ask the repo to explain every scar.
Ask it to justify every surviving surface.

If a file, folder, or subsystem cannot clearly answer one of these questions,
it is a pruning candidate:

- Does runtime load it?
- Does build, release, or packaging require it?
- Does QA, preview, docs, or onboarding intentionally require it?
- Does publish or install truth require it?
- Does the team intentionally preserve it as archive?

If the answer is no, cut it.
