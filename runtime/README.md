# Runtime Layer (Canonical)

`runtime/` is the new canonical home for shared shell runtime helpers.

- `runtime/helpers/` contains helper functions used by interactive shell wrappers.
- `runtime/scripts/` and `runtime/tools/` are reserved for shell wrappers and
  runtime CLI tools moved in later phases.
- `runtime/docs/` describes runtime boundaries and migration contracts.

`skills/vc-agents/shell/vetcoders.sh` is intentionally a compatibility shim in
this phase: it only loads helpers from the canonical runtime layer and keeps the
installed command surface unchanged.

Migration boundary for phase 1:

1. Keep the command contract and launcher behavior compatible.
2. Route helper resolution through runtime helper files.
3. Move only low-risk helper slices first (path/store/run-id/session/research
   helpers), then expand ownership in later phases.
