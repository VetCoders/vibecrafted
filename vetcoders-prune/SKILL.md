---
name: vetcoders-prune
description: >
  Repository pruning and runtime cone extraction skill. Use when the team wants
  to strip a large AI-grown repo down to the code that actually participates in
  runtime, separate product code from tooling, archives, experiments, agent
  exhaust, reports, and stale surfaces, or run a radical "cut the dead limb"
  cleanup without preserving zombies for sentiment. Trigger phrases:
  "prune repo", "sprzatanie repo", "obierz repo", "strip non-runtime",
  "remove cruft", "cleanup architecture", "runtime cone", "odchudz repo",
  "co mozna usunac", "what can we delete", "safe repo cleanup",
  "trim the tree", "living tree cleanup", "bez litosci", "radykalny prune".
---

# vetcoders-prune - Runtime Cone Pruning

> A repo is a living tree.
> Keep the trunk, cut the scaffolding, archive the fossils.

This skill answers a narrower and more useful question than "what looks messy?":
what code, files, and directories are required for runtime truth, and what only
exists because the repo kept absorbing tools, experiments, reports, and history.

The goal is not cosmetic cleanup.
The goal is to reduce the product surface until runtime, build, and QA are
explicit and defendable.

## Core Contract

- Use loctree as the first exploration layer.
- Define the runtime cone before proposing deletes.
- Use `loct dist` as the frontend pruning scoreboard when source maps exist.
- Treat `loct dist` as a score, not a verdict.
- Classify every candidate as `KEEP-RUNTIME`, `KEEP-BUILD`, `KEEP-QA`,
  `MOVE-ARCHIVE`, `DELETE-NOW`, or `VERIFY-FIRST`.
- Prefer deleting whole dead vertical slices over trimming symbolic leaves.
- Run gates after every pruning wave.
- Tighten contracts immediately after each wave: re-exports, scripts, handler
  registrations, policies, env flags, manifests, and docs.
- Treat runtime leaks from dev-only code as high-priority cleanup.

## Modes

Choose the mode from user intent.

- `conservative`
  Use when the user wants safety, staging, or archive-first cleanup.
  Default uncertain candidates to `VERIFY-FIRST` or `MOVE-ARCHIVE`.
- `radical`
  Use when the user explicitly asks for ruthless cleanup, no mercy, aggressive
  pruning, or says it is better to write fresh code than keep zombies.
  Once evidence clears the threshold, default to `DELETE-NOW`, not sentimental
  preservation.

If the user says "bez litosci", "radykalnie", or equivalent, use `radical`.

## The Pruning Classes

| Class          | Meaning                                                                                   | Action                                                  |
|----------------|-------------------------------------------------------------------------------------------|---------------------------------------------------------|
| `KEEP-RUNTIME` | Participates directly or transitively in app runtime                                      | Keep; refactor separately if ugly                       |
| `KEEP-BUILD`   | Required to build, package, sign, bundle, or release                                      | Keep; do not delete with runtime cuts                   |
| `KEEP-QA`      | Required to verify behavior, smoke flows, preview paths, or release confidence            | Keep; move later only with replacement proof            |
| `MOVE-ARCHIVE` | Historical but still worth preserving outside main working tree                           | Move to archive branch, attic repo, or external archive |
| `DELETE-NOW`   | Generated, disposable, reproducible, whole-dead, or clearly unreachable                   | Delete directly                                         |
| `VERIFY-FIRST` | Suspicious, possibly dead, but dynamic imports, registries, or configs may still reach it | Prove with impact + grep + gates before removal         |

## Workflow

### Phase 1 - Establish Runtime Truth

Start by declaring what "runtime" means for this repo:

- Desktop app, web app, CLI, library, or mixed surface
- Primary entrypoints
- Mandatory user flows that must still work after pruning
- Packaging/build path that must stay intact

For a Tauri + Vite repo, usually inspect:

- Frontend entrypoints such as `src/main.tsx` and `src/App.tsx`
- Backend entrypoints such as `src-tauri/src/main.rs` and `src-tauri/src/lib.rs`
- Tauri command registration such as `tauri::generate_handler![...]`
- Plugin setup, state injection, background jobs, and window/tray bootstrap
- Backend resources such as migrations, bundled sidecars, capabilities, and
  files copied through `tauri.conf.json`
- Tauri config such as `src-tauri/tauri.conf.json`
- Build scripts referenced by `beforeDevCommand`, `beforeBuildCommand`,
  bundling resources, and package scripts

Use shell-level evidence for build truth:

```bash
rg -n "before(Build|Dev)Command|frontendDist|resources|externalBin|capabilities" src-tauri/tauri.conf.json*
rg -n '"(dev|build|test|lint|tauri:dev|tauri:build|preview)"\s*:' package.json
```

Do not start with "unused exports".
Start with "what must boot".

### Phase 2 - Map the Runtime Cone

Build the transitive runtime cone from the true entrypoints outward.

Use loctree in this order:

```text
repo-view(project)
slice(file="src/main.tsx", consumers=true)
slice(file="src/App.tsx", consumers=true)
slice(file="src-tauri/src/lib.rs", consumers=true)
focus(directory="src")
focus(directory="src-tauri/src")
follow(scope="all") when cycles, hotspots, or twins look relevant
impact(file=<candidate>) before deleting any non-obvious file
find(mode="who-imports", name=<candidate>) for reverse dependency checks
```

Evidence that something is runtime-critical includes:

- Imported from a real entrypoint
- Registered in router, providers, command registries, plugin registries, event
  bridges, state stores, background job setup, or global shell bootstrap
- Registered in Tauri command handlers, plugin init, `manage(...)` state,
  startup hooks, migrations, or backend schedulers
- Referenced from build, bundle, preview, smoke, or packaging config
- Required by smoke flows the product cannot lose

Evidence that something is not runtime includes:

- Generated artifacts
- Reports, logs, review packs, or screenshots
- Agent memory and session residue
- Playground or prototype code not referenced by build or packaging
- Archived docs or superseded experiments

### Phase 2.5 - `loct dist` Doctrine

When the frontend uses Vite source maps, `loct dist` becomes mandatory.

Run it before and after every frontend pruning wave:

```bash
pnpm exec vite build --sourcemap
loct dist --src src --source-map dist/assets --report .loctree/dist-report.json
```

Rules:

- For Vite repos, prefer `dist/assets`, not bare `dist`, as the source map path.
- Track deltas in:
    - `dead_exports`
    - `source_exports`
    - `bundled_exports`
    - source map count
- Treat the delta as your scoreboard.
- Never treat a symbol-level dead-export report as deletion proof by itself.
- Use it to discover dead slices, stale public APIs, barrel bleed, and
  dev-only runtime leakage.

Good use of `loct dist`:

- find a dead service slice and remove the frontend file, test, types, Rust
  command, policy seed, and handler registration together
- identify a bootstrap import that only exists for diagnostics
- tighten public API by removing dead re-exports after proving consumers are gone

Bad use of `loct dist`:

- deleting a registry-backed symbol because it appears dead once
- trimming ten type exports while ignoring a fully dead vertical slice nearby

### Phase 3 - Classify the Repo Surface

Classify root directories before diving into leaf files.
This prevents wasting time micro-pruning a subtree that should simply move out.

Typical early classifications in AI-grown repos:

- Usually `DELETE-NOW`:
  `dist/`, `playwright-report/`, logs, cached outputs, generated proof artifacts
- Usually `MOVE-ARCHIVE`:
  `.ai-*`, `.codex/`, `.claude/`, `.junie/`, `.trash/`, `.attic/`,
  `docs/archive/`, prototype folders, abandoned landing experiments
- Usually `KEEP-BUILD`:
  `.github/workflows/`, packaging scripts, release scripts, bundle resources
- Usually `KEEP-QA`:
  `e2e/`, `tests/`, smoke scripts, fixtures, test harnesses
- Usually `VERIFY-FIRST`:
  Storybook hooks, preview shims, alternate app shells, duplicate engines,
  legacy adapters, vendor folders, manifest generators

Special handling for `devtools/`:

- `KEEP-QA` if the file is wired into preview, browser-only flows, smoke flows,
  or explicit dev scripts the team still uses
- `DELETE-NOW` if it is boot-time diagnostics or debug exposure code with no
  transitive consumers beyond the app bootstrap
- `VERIFY-FIRST` if it alters boot behavior under env gates or mock routing

Do not assume `scripts/` is trash.
In messy repos, `scripts/` often contains half the actual build contract.

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

This wave should not change runtime at all.

#### Wave 1 - Agent Exhaust and Archaeology

Move or remove:

- agent session folders
- planning/report residue
- superseded prototypes
- attic/trash buckets inside the repo
- archived docs that are no longer part of the working product surface

This wave reduces noise for all later analysis.

#### Wave 2 - Dev-Only Bleed Into Runtime

Look for code that exists only for local hacking but leaks into the main app path:

- browser mocks imported by default
- preview-only providers in app entrypoints
- dual shells and duplicate startup paths
- env-gated branches with broad permanent imports
- diagnostics exposed on `window` only for local inspection
- debug scripts or env vars that still shape boot-time behavior

These are high-value cuts because they sharpen the boundary between product and
debug scaffolding.

#### Wave 3 - Whole Dead Vertical Slice

Before trimming leaves, ask whether an entire feature strand is already dead.

Good candidates:

- frontend service with no runtime consumers
- companion types used only by that service
- test file covering only that service
- backend Rust command module serving only that service
- `generate_handler!` entries for those commands
- policy or permission seeds for those commands
- barrel exports that keep pretending the slice exists

If the answer is "only tests and registries remain", cut the whole slice.

This wave is usually higher ROI than symbol-chasing.

#### Wave 4 - Unreachable Product Surface

Now prune inside `src/` and `src-tauri/src/`:

- unmounted routes
- unregistered commands
- unregistered Tauri handlers and plugin surfaces
- panels no live route reaches
- duplicate services
- duplicate Rust engines, background workers, or stale migration paths
- stale fallback systems retained after migration
- feature folders that survive only through legacy glue

Use the dead parrots rule here:
if a subtree exists only to support a removed path, delete the whole subtree
instead of trimming leaves forever.

#### Wave 5 - Contract Tightening

After every removal wave, immediately clean the references that still point at
deleted surface:

- package scripts
- env vars and vite env typings
- CI workflows
- manifests
- docs indexes
- test matrices
- import aliases
- re-export barrels
- Tauri handler registration
- policy seeds and permission tables
- release and setup scripts

If you skip this wave, the repo still behaves as if dead code is alive.

API narrowing belongs here too:
do not only delete files; also shrink public module surfaces when runtime only
needs a smaller contract.

### Phase 5 - Verify

After each wave, run the closest safe gates for the repo in this order.

For mixed TypeScript + Rust desktop repos, prefer:

```bash
pnpm exec tsc --noEmit
cargo clippy --manifest-path src-tauri/Cargo.toml -- -D warnings
scripts/run-semgrep.sh --config=p/security-audit <touched-files>
pnpm exec vite build --sourcemap
loct dist --src src --source-map dist/assets --report .loctree/dist-report-next.json
pnpm test:e2e:ts
```

For Tauri-heavy repos, also verify:

```bash
rg -n "generate_handler!|plugin\(|manage\(|Builder::default|setup\(" src-tauri/src
rg -n "resources|externalBin|capabilities|frontendDist" src-tauri/tauri.conf.json*
```

Add targeted tests for the surfaces touched in the wave.
Run at least one real smoke flow after any structural pruning.

## False Positive Families

Treat these as suspicious until proven dead:

- icon registries and giant visual barrels
- barrel re-exports that mirror live internal types
- context modules that re-export convenience types
- event hub alias wrappers
- dynamic tool registries and slash-command registries
- huge DTO/type files where only some exports are dead
- test-only helpers that appear in the same report as runtime code
- env-gated imports in boot files

Rule:
when a file belongs to a false-positive family, do not trim by symbol first.
Use `impact`, `who-imports`, `rg`, and contract checks to decide whether the
whole file is dead, only the public API is stale, or the report is noisy.

## Evidence Rules

Use this hierarchy when deciding whether a candidate can go:

1. `impact(file)` and `who-imports` say nothing consumes it
2. `rg` finds no config, script, glob, manifest, handler, or policy reference
3. No dynamic import, registry, env gate, or preview path points to it
4. Build and compile gates still pass
5. `loct dist` delta improves or stays clean
6. One real smoke flow still passes

If only rules 1-2 are true, classify as `VERIFY-FIRST`.
If rules 1-5 are true in `radical` mode, deletion is usually safe.
If all six are true, deletion is strongly justified.

Static tools are hints, not verdicts.
`knip`, `madge`, dead-export scanners, and "unused file" heuristics help, but
they do not understand runtime registries, Tauri commands, dynamic imports, or
preview/dev contracts by themselves.

## Prioritization Heuristic

When multiple candidates are available, prefer this order:

1. whole dead vertical slice
2. dev-only bleed from runtime boot
3. dead public API or stale barrel re-export
4. isolated dead helper with zero blast radius
5. cosmetic symbol trimming

If you are spending time trimming leaf exports while a dead service/backend
slice is still present, you are pruning in the wrong order.

## Output Format

Use this exact top-level structure in the final response:

```text
Current state: <what is bloated, mixed, or leaking>
Proposal: <target repo shape and why it is safer>
Migration plan: <ordered pruning waves>
Quick win: <one immediate high-impact cleanup>
```

Then include:

- Runtime cone summary
- `KEEP/MOVE/DELETE/VERIFY` classification list
- Wave plan with blast radius
- `loct dist` delta summary when applicable
- Gate results
- Open risks and what still needs proof

## Integration with VetCoders Pipeline

Use this flow for major cleanup:

```text
vetcoders-init -> vetcoders-prune -> vetcoders-followup -> vetcoders-marbles
```

- `vetcoders-init` gives memory plus structure
- `vetcoders-prune` defines the cone and removes non-runtime surface
- `vetcoders-followup` verifies runtime truth after the cuts
- `vetcoders-marbles` loops if residual P1/P2 chaos remains

## Anti-Patterns

- Deleting by folder name intuition alone
- Treating docs, tests, and build scripts as equally disposable
- Running one giant cleanup PR across runtime, QA, docs, CI, and packaging
- Trusting "unused" reports without checking dynamic loading paths
- Trusting `loct dist` without understanding false-positive families
- Keeping dev-only imports inside real app entrypoints
- Preserving fossils because deleting them feels emotionally risky
- Archiving everything inside the same repo forever instead of moving it out
- Trimming ten dead symbols while a whole dead subsystem is still standing
- Cleaning code but leaving handlers, policies, scripts, or env flags behind

## The Pruning Principle

Do not ask the repo to explain every scar.
Ask it to justify every surviving surface.

If a file, folder, or subsystem cannot clearly answer one of these questions,
it is a pruning candidate:

- Does runtime load it?
- Does build or packaging require it?
- Does QA or preview require it?
- Does the team intentionally preserve it as archive?

If the answer is no, cut it.
