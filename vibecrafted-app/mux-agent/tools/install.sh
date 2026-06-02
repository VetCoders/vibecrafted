#!/usr/bin/env bash
set -euo pipefail
umask 022

# rust-mux install script
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/Loctree/rust-mux/main/tools/install.sh | sh
# Env overrides:
#   INSTALL_DIR   where to place the runnable `rust-mux` wrapper (default: $HOME/.local/bin)
#   CARGO_HOME    override cargo home (default: ~/.cargo)
#   MUX_REF       branch/tag/commit to install (default: main)
#   MUX_NO_LOCK   set to 1 to skip --locked

INSTALL_DIR=${INSTALL_DIR:-"$HOME/.local/bin"}
CARGO_HOME=${CARGO_HOME:-"$HOME/.cargo"}
CARGO_BIN="$CARGO_HOME/bin"
REPO_URL="https://github.com/Loctree/rust-mux"
# Allow pinning a branch/tag/commit; defaults to main.
MUX_REF=${MUX_REF:-"main"}

info() { printf "[rust-mux] %s\n" "$*"; }
warn() { printf "[rust-mux][warn] %s\n" "$*" >&2; }

command -v cargo >/dev/null 2>&1 || {
  warn "cargo not found. Install Rust (e.g. https://rustup.rs) then re-run.";
  exit 1;
}

info "Installing rust-mux from $REPO_URL (ref: $MUX_REF)"
# --locked keeps dependency resolution reproducible; override with MUX_NO_LOCK=1 if needed.
lock_flag="--locked"
[ "${MUX_NO_LOCK:-0}" = "1" ] && lock_flag=""
# --rev accepts branches, tags, or commits.
cargo install --git "$REPO_URL" --rev "$MUX_REF" $lock_flag --force rust-mux >/dev/null

installed_bin="$CARGO_BIN/rust-mux"
if [[ ! -x $installed_bin ]]; then
  warn "rust-mux binary not found at $installed_bin after install";
  exit 1;
fi

mkdir -p "$INSTALL_DIR"
wrapper="$INSTALL_DIR/rust-mux"
cat >"$wrapper" <<WRAP
#!/usr/bin/env bash
exec "$installed_bin" "\$@"
WRAP
chmod +x "$wrapper"

info "Installed binary: $installed_bin"
info "Wrapper: $wrapper"

print_path_notice() {
  local missing="$1"
  warn "$missing is not on PATH."
  warn "Add it manually if you want shell-wide access:"
  warn "  export PATH=\"$CARGO_BIN:$INSTALL_DIR:\$PATH\""
}

case ":$PATH:" in
  *":$CARGO_BIN:"*) :;;
  *) print_path_notice "cargo bin";;
esac

case ":$PATH:" in
  *":$INSTALL_DIR:"*) :;;
  *) print_path_notice "rust-mux wrapper dir";;
esac

info "Done. Try: rust-mux --socket /tmp/mcp.sock --cmd npx -- @modelcontextprotocol/server-memory --tray"
