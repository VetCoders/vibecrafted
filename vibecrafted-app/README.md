# Vibecrafted App Workspace

Product surface for the desktop/control workspace: terminal cockpit (`voc`),
MCP multiplexer, tray agent, and macOS shell wrapper as one Rust-first pack.
Installed into `~/.local/bin` by root `make install-app-binaries` /
`make install` as real files (`voc`, `vc-admin`).

## Workspace Shape

The root `Cargo.toml` is a workspace, not an application crate:

| Path                          | Package                      | Role                                            |
| ----------------------------- | ---------------------------- | ----------------------------------------------- |
| `mux-agent/`                  | `rmcp-mux`                   | MCP transport multiplexer and daemon supervisor |
| `tui-agent/`                  | `voc`                        | terminal control cockpit (`voc`, `vc-admin`)    |
| `tray-agent/`                 | `tray-agent`                 | menu bar/tray control surface                   |
| `shell-agent/ffi/`            | `vibecrafted-shell-ffi`      | Rust/UniFFI bridge for the macOS app            |
| `shell-agent/uniffi-bindgen/` | `vibecrafted-uniffi-bindgen` | local binding generator wrapper                 |

The package was renamed from `vc-tui` to `voc`. The single source of truth for
the terminal cockpit is `tui-agent/`. Deck entry: `vibecrafted tui` (also the
`voc` / legacy `vc-tui` wrappers).

## Quality Gates

Use the root Makefile:

```bash
make gates
cargo check --workspace
cargo check --workspace --all-features
cargo check --workspace --no-default-features
```

`make gates` runs:

```text
cargo fmt --all --check
cargo clippy --workspace --all-targets -- -D warnings
cargo test --workspace
```

## macOS App Build

The root app targets delegate to `shell-agent/`:

```bash
make app
make dmg
make dmg-signed
```

`make app` generates UniFFI bindings, regenerates the Xcode project through
`xcodegen`, builds `Vibecrafted.app`, and embeds the Rust helper binaries:

- `vc-mux-daemon`
- `vc-mux-tray`
- `voc`

`make dmg` creates an unsigned local DMG. `make dmg-signed` requires a
Developer ID Application signing identity in the local keychain and prints the
notarization commands after a signed DMG is created.

## Runtime State Contract

The TUI reads the shared local control-plane state:

```text
$VIBECRAFTED_HOME/control_plane/
  runs/*.json
  events.jsonl
```

The mux status panel reads `rmcp-mux` JSON status snapshots, preferring
`VIBECRAFTED_MUX_STATUS_PATHS` before defaulting to
`~/.rmcp_servers/rmcp_mux/status.json` and sibling JSON files.

## Repository Rule

This repo is a living tree. Do not commit build products, `.loctree` snapshots,
`.DS_Store`, Xcode DerivedData, generated daily artifact symlinks, or nested
source-repo CI baggage. Keep `Cargo.lock` tracked: this is an application and
release workspace, not only a library crate.
