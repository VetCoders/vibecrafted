# Runtime Scripts

Active default runtime entry points live here.

- `<agent>_spawn.sh` scripts launch external agent CLIs.
- `await.sh`, `observe.sh`, and watcher scripts track durable artifacts.
- `lib/` holds shared path, session, launcher, prompt, meta, lock, and zellij
  helpers.
- marbles scripts implement the convergence runtime and watcher path.

Do not fork these helpers into per-workflow directories unless ownership is
exclusive. Shared spawn, await, path, and meta behavior stays here.
