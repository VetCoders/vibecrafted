# Runtime Layer (Canonical)

- `runtime/helpers/` contains helper functions used by interactive shell wrappers.
- `runtime/scripts/` and `runtime/tools/` are reserved for shell wrappers and
  runtime CLI tools moved in later phases.
- `runtime/docs/` describes runtime boundaries and migration contracts.
- `runtime/vc-<workflow>/` dirs hold per-workflow runtime (see below).

## Per-workflow runtime extraction pattern

A workflow = skill + launcher/helpers/watchers + telemetry. Each workflow that
owns runtime pieces gets its own `runtime/vc-<workflow>/` dir, one
subdirectory per component, on the `runtime/vc-marbles/` pattern:

- `runtime/vc-marbles/orchestrator/` — marbles loop plugin
  (commands/hooks/scripts/docs).
- `runtime/vc-research/shell/` — facade-sourced shell modules for the
  research swarm launcher.
- `runtime/vc-operator/mission-control/` — operator console / dashboard
  watcher scripts used by the zellij layouts.

### What belongs in a workflow dir

- Scripts and shell modules used ONLY by that workflow (its launcher, its
  watchers, its prompt composition).
- A `README.md` stating ownership and listing what intentionally stays
  shared.

### What stays shared (never copy into workflow dirs)

- `runtime/scripts/lib/` — the single common launcher/meta/telemetry library.
- `runtime/scripts/<agent>_spawn.sh` + stream filters — frontier spawners are
  parameterized per workflow via env (`VIBECRAFTED_SKILL_*`), not forked.
- `runtime/scripts/await.sh` — one awaiter, mode flags per workflow.
- `runtime/shell/lib/` — facade modules shared across workflows.
- `runtime/helpers/vetcoders-runtime-core.sh` — degraded-path core helpers.

### How to migrate the next workflow

1. Map ownership: `loct impact` + `loct find --literal <script-name>` for
   every candidate file; string-path consumers (Makefile, zellij `*.kdl`
   layouts, tests, installer staging) do not show up as import edges, grep
   them explicitly.
2. `git mv` the workflow-owned files into `runtime/vc-<workflow>/<component>/`.
   Do not move anything with consumers in two or more workflows.
3. Update consumers:
   - facade-sourced shell modules → `_vetcoders_source_workflow_module
<workflow> <module>` in `runtime/shell/vetcoders.sh` (keep load order);
   - scripts resolved at runtime → `_vetcoders_workflow_script <workflow>
<relative-path>` from `runtime/helpers/vetcoders-runtime-core.sh`;
   - literal paths in zellij layouts/tests → point at
     `<runtime-root>/vc-<workflow>/...`.
4. Installer staging needs no edits: the whole repo tree (including
   `runtime/vc-*/`) is synced into `vibecrafted-current` by
   `sync_control_plane_tree`.
5. Write the workflow `README.md`, run the gates, one workflow per commit.

`../runtime/shell/vetcoders.sh` is intentionally a compatibility shim in
this phase: it only loads helpers from the default runtime layer and keeps the
installed command surface unchanged.

Migration boundary for phase 1:

1. Keep the command contract and launcher behavior compatible.
2. Route helper resolution through runtime helper files.
3. Move only low-risk helper slices first (path/store/run-id/session/research
   helpers), then expand ownership in later phases.
