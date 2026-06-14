#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# install-foundations.sh — portable installer for 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. foundation layer
#
# Handles:
#   loctree / loctree-mcp  — required Loctree product binaries via Loctree installer
#   aicx / aicx-mcp       — required AICX product binaries via Loctree installer
#   vc-frame               — required Vibecrafted frame binary via canonical installer
#   prview                 — cargo install OR binary from GH releases
#
# Usage:
#   bash scripts/install-foundations.sh                   # validate required foundations
#   bash scripts/install-foundations.sh --all             # validate/install all framework-owned foundations
#   bash scripts/install-foundations.sh loctree           # validate Loctree product binaries
#   bash scripts/install-foundations.sh aicx              # validate AICX product binaries
#   bash scripts/install-foundations.sh vc-frame          # validate Vibecrafted frame binary
#   bash scripts/install-foundations.sh --check           # dry-run: show what would install
#   bash scripts/install-foundations.sh --prefix /usr/local  # custom install prefix
# ---------------------------------------------------------------------------

PRVIEW_CRATE="prview"
PRVIEW_REPO="VetCoders/prview"

LOCTREE_INSTALL_URL="${LOCTREE_INSTALL_URL:-https://loct.io/install.sh}"
VCFRAME_INSTALL_URL="${VCFRAME_INSTALL_URL:-https://vibecrafted.io/install.sh}"

# Agent CLIs — npm packages when the vendor publishes an official package.
AGENT_PACKAGES=(
  "claude:@anthropic-ai/claude-code"
  "codex:@openai/codex"
  "gemini:@google/gemini-cli"
  "junie:@jetbrains/junie"
  "grok:@xai-official/grok"
)

AGENT_MANUAL_INSTALLS=(
  "agy|Install Google Antigravity CLI from its vendor distribution, then run: agy install"
)

# Script/source resolution (used by the bundled-toolchain attempt).
# Respects VIBECRAFTED_SOURCE when set; otherwise resolves the parent of
# scripts/install-foundations.sh.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_DIR="${VIBECRAFTED_SOURCE:-$(cd "$SCRIPT_DIR/.." && pwd)}"

default_vibecrafted_home() {
  if [[ -n "${VIBECRAFTED_HOME:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_HOME"
    return
  fi
  if [[ -n "${VIBECRAFTED_ROOT:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_ROOT/.vibecrafted"
    return
  fi
  printf '%s\n' "$HOME/.vibecrafted"
}

default_vibecrafted_runtime_home() {
  if [[ -n "${VIBECRAFTED_RUNTIME_HOME:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_RUNTIME_HOME"
    return
  fi
  if [[ -n "${XDG_DATA_HOME:-}" ]]; then
    printf '%s\n' "$XDG_DATA_HOME/vibecrafted"
    return
  fi
  printf '%s\n' "$HOME/.local/share/vibecrafted"
}

canonical_vibecrafted_home() {
  printf '%s\n' "$HOME/.vibecrafted"
}

canonical_vibecrafted_runtime_home() {
  printf '%s\n' "$HOME/.local/share/vibecrafted"
}

canonical_vibecrafted_launcher_bin() {
  printf '%s\n' "$HOME/.local/bin"
}

pause_runtime_contract_failure() {
  if ! is_interactive; then
    return
  fi
  printf '\nRuntime root contract failed fast.\n'
  printf 'Manual cleanup required (no dotfiles were modified automatically):\n'
  printf '  1) unset conflicting VIBECRAFTED_* root overrides\n'
  printf '  2) remove stale wrappers from ~/.cargo/bin and /usr/local/bin\n'
  printf '  3) keep launchers in ~/.local/bin and rerun foundations install\n\n'
  printf 'Press Enter to continue after reviewing cleanup steps, or Ctrl-C to abort: '
  read -r _ || true
}

enforce_runtime_root_contract() {
  local expected_store expected_runtime expected_launcher
  local resolved_store resolved_runtime resolved_launcher
  local failed=0

  expected_store="$(canonical_vibecrafted_home)"
  expected_runtime="$(canonical_vibecrafted_runtime_home)"
  expected_launcher="$(canonical_vibecrafted_launcher_bin)"

  resolved_store="$(default_vibecrafted_home)"
  resolved_runtime="$(default_vibecrafted_runtime_home)"
  resolved_launcher="${VIBECRAFTED_LAUNCHER_BIN:-$expected_launcher}"

  if [[ "$resolved_store" != "$expected_store" ]]; then
    warn "Fail-fast: store root drift detected ($resolved_store, expected $expected_store)."
    failed=1
  fi

  if [[ "$resolved_runtime" != "$expected_runtime" ]]; then
    warn "Fail-fast: runtime root drift detected ($resolved_runtime, expected $expected_runtime)."
    failed=1
  fi

  if [[ "$resolved_launcher" != "$expected_launcher" ]]; then
    warn "Fail-fast: launcher root drift detected ($resolved_launcher, expected $expected_launcher)."
    failed=1
  fi

  if [[ "$failed" == "1" ]]; then
    pause_runtime_contract_failure
    return 1
  fi

  return 0
}

VIBECRAFTED_HOME="$(default_vibecrafted_home)"
VIBECRAFTED_RUNTIME_HOME="$(default_vibecrafted_runtime_home)"
PREFIX="${VIBECRAFTED_BIN:-$VIBECRAFTED_RUNTIME_HOME/bin}"
LAUNCHER_PREFIX="${VIBECRAFTED_LAUNCHER_BIN:-$HOME/.local/bin}"
CHECK_ONLY=0
INSTALL_ALL=0
AGENTS_REQUIRED=0
TARGETS=()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

die()  { printf '\033[31mError:\033[0m %s\n' "$*" >&2; exit 1; }
info() { printf '\033[36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*"; }

detect_os() {
  case "$(uname -s)" in
    Linux*)   echo "linux" ;;
    Darwin*)  echo "macos" ;;
    MINGW*|MSYS*|CYGWIN*) echo "windows" ;;
    *)        die "Unsupported OS: $(uname -s)" ;;
  esac
}

detect_arch() {
  case "$(uname -m)" in
    x86_64|amd64)   echo "x86_64" ;;
    aarch64|arm64)   echo "aarch64" ;;
    armv7l)          echo "armv7" ;;
    *)               die "Unsupported architecture: $(uname -m)" ;;
  esac
}

has_cmd() { command -v "$1" >/dev/null 2>&1; }

is_interactive() { [[ -t 0 && -t 1 ]]; }

# Verify a binary actually runs (catches dyld / missing shared lib issues).
binary_runs() {
  local bin="$1"
  has_cmd "$bin" || return 1
  "$bin" --version >/dev/null 2>&1 || "$bin" --help >/dev/null 2>&1
}

# ---------------------------------------------------------------------------
# Bundled-toolchain drop-in
# ---------------------------------------------------------------------------
# Resolves the per-arch directory where release tarballs ship notarized
# binaries. Order of precedence:
#   1. $VIBECRAFTED_BUNDLED_BIN (explicit override — absolute path)
#   2. $SOURCE_DIR/tools/bin/<os>-<arch>
#   3. $SOURCE_DIR/tools/bin  (flat fallback for dev / single-arch drops)
bundled_bin_root() {
  local os arch
  if [[ -n "${VIBECRAFTED_BUNDLED_BIN:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_BUNDLED_BIN"
    return
  fi
  os="$(detect_os)"
  arch="$(detect_arch)"
  if [[ -d "$SOURCE_DIR/tools/bin/${os}-${arch}" ]]; then
    printf '%s\n' "$SOURCE_DIR/tools/bin/${os}-${arch}"
    return
  fi
  printf '%s\n' "$SOURCE_DIR/tools/bin"
}

_realpath_quiet() {
  local path="$1"
  if [[ -d "$path" ]]; then
    (cd "$path" && pwd -P)
    return
  fi
  return 1
}

# Attempt 0 for every install_*: copy a drop-in binary from the bundled
# tarball directory before reaching out to GitHub / cargo / npm.
# Returns 0 only when the binary copied, chmod+x'd, and actually runs.
install_from_bundled() {
  local name="$1"
  local root
  root="$(bundled_bin_root)"
  local src="$root/$name"

  [[ -f "$src" ]] || return 1

  if (( CHECK_ONLY )); then
    info "Would install $name from bundled tarball ($src)"
    return 0
  fi

  ensure_prefix
  cp "$src" "$PREFIX/$name" || return 1
  chmod +x "$PREFIX/$name"
  if ! binary_runs "$name"; then
    warn "Bundled $name failed to run — falling back to remote sources."
    rm -f "$PREFIX/$name"
    return 1
  fi
  ok "Installed $name from bundled tarball (notarized): $PREFIX/$name"
  return 0
}

ensure_node() {
  has_cmd node && has_cmd npm && return 0

  # Try brew first (if available)
  if has_cmd brew; then
    info "Installing Node.js via Homebrew..."
    brew install node 2>&1 | tail -3 && has_cmd node && has_cmd npm && return 0
  fi

  # Download official Node.js binary — no sudo needed
  local os arch node_os node_arch node_version="v22.16.0"
  os="$(detect_os)"
  arch="$(detect_arch)"

  case "$os" in
    macos)  node_os="darwin" ;;
    linux)  node_os="linux" ;;
    *)      warn "No Node.js binary for $os"; return 1 ;;
  esac
  case "$arch" in
    x86_64)  node_arch="x64" ;;
    aarch64) node_arch="arm64" ;;
    *)       warn "No Node.js binary for $arch"; return 1 ;;
  esac

  local node_pkg="node-${node_version}-${node_os}-${node_arch}"
  local node_url="https://nodejs.org/dist/${node_version}/${node_pkg}.tar.gz"
  local node_dir="${VIBECRAFTED_HOME}/tools/node"

  if is_interactive; then
    printf '\n'
    info "Node.js is required for npm-installed agent CLIs."
    info "Installing to ${node_dir} (no sudo needed)."
    printf '  Press Enter to proceed, or Ctrl-C to skip: '
    read -r _
  else
    info "Installing Node.js ${node_version} to ${node_dir}..."
  fi

  has_cmd curl || { warn "curl required to download Node.js"; return 1; }

  local tmpdir
  tmpdir="$(mktemp -d)"
  if curl -fsSL -o "$tmpdir/node.tar.gz" "$node_url"; then
    mkdir -p "$node_dir"
    tar -xzf "$tmpdir/node.tar.gz" -C "$node_dir" --strip-components=1
    rm -rf "$tmpdir"
    export PATH="${node_dir}/bin:${PATH}"

    if has_cmd node && has_cmd npm; then
      ok "Node.js $(node --version) installed to ${node_dir}"
      return 0
    fi
  fi

  rm -rf "$tmpdir"
  warn "Could not install Node.js."
  return 1
}

install_from_npm() {
  local package="$1" binary="${2:-$1}"

  if binary_runs "$binary"; then
    ok "$binary already installed: $(command -v "$binary")"
    return 0
  fi

  ensure_node || {
    warn "npm not available — cannot install $package."
    return 1
  }

  info "Installing $package via npm..."
  npm install -g "$package" 2>&1 | tail -3 || {
    warn "npm install $package failed."
    return 1
  }

  binary_runs "$binary"
}

ensure_prefix() {
  mkdir -p "$PREFIX"
  # Add to PATH for the rest of this script
  case ":$PATH:" in
    *":$PREFIX:"*) ;;
    *) export PATH="$PREFIX:$PATH" ;;
  esac
}

install_vc_wrappers() {
  local source_bin="$SOURCE_DIR/bin"
  local name src
  [[ -d "$source_bin" ]] || return 0
  mkdir -p "$LAUNCHER_PREFIX"
  for src in "$source_bin"/vc-* "$source_bin"/vibecrafted-resume; do
    [[ -f "$src" ]] || continue
    name="$(basename "$src")"
    if (( CHECK_ONLY )); then
      info "Would install $name -> $LAUNCHER_PREFIX/$name"
      continue
    fi
    cp "$src" "$LAUNCHER_PREFIX/$name"
    chmod +x "$LAUNCHER_PREFIX/$name"
    ok "Installed $name -> $LAUNCHER_PREFIX/$name"
  done
}

install_loctree() {
  loctree_suite_ready() {
    local missing=() bin
    for bin in loct loctree loctree-mcp; do
      binary_runs "$bin" || missing+=("$bin")
    done
    if (( ${#missing[@]} == 0 )); then
      return 0
    fi
    warn "Loctree incomplete; missing or broken: ${missing[*]}"
    return 1
  }

  if loctree_suite_ready; then
    ok "loctree suite already installed: loct=$(command -v loct), loctree-mcp=$(command -v loctree-mcp)"
    return 0
  fi

  if (( CHECK_ONLY )); then
    info "Would install Loctree foundations from canonical installer:"
    info "  curl -fsSL $LOCTREE_INSTALL_URL | sh"
    return 0
  fi

  warn "Loctree foundations are required, but Vibecrafted will not guess crates, npm packages, or local checkout paths."
  warn "Use the canonical installer, then rerun this check:"
  warn "  curl -fsSL $LOCTREE_INSTALL_URL | sh"
  return 1
}

# ---------------------------------------------------------------------------
# Generic cargo installer
# ---------------------------------------------------------------------------

install_from_cargo() {
  local crate="$1" binary="${2:-$1}"

  if has_cmd "$binary"; then
    ok "$binary already installed: $(command -v "$binary")"
    return 0
  fi

  if (( CHECK_ONLY )); then
    if has_cmd cargo; then
      info "Would run: cargo install $crate"
    else
      warn "$binary not found and cargo not available"
      info "Install Rust (https://rustup.rs) then: cargo install $crate"
    fi
    return 0
  fi

  if ! has_cmd cargo; then
    warn "cargo not found. Cannot install $crate from crates.io."
    warn "Options:"
    warn "  1. Install Rust: curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    warn "  2. Download binary from GitHub releases"
    return 1
  fi

  ensure_prefix

  info "Installing $crate via cargo..."
  # Install to a temp dir, then copy binaries to PREFIX
  local cargo_root
  cargo_root="$(mktemp -d)"

  if cargo install "$crate" --root "$cargo_root" 2>&1; then
    local installed=0
    for bin in "$cargo_root/bin/"*; do
      [ -f "$bin" ] || continue
      local name
      name="$(basename "$bin")"
      cp "$bin" "$PREFIX/$name"
      chmod +x "$PREFIX/$name"
      ok "Installed $name -> $PREFIX/$name"
      installed=1
    done
    if (( !installed )); then
      rm -rf "$cargo_root"
      warn "cargo install $crate succeeded but no binaries found"
      return 1
    fi
  else
    rm -rf "$cargo_root"
    warn "cargo install $crate failed"
    return 1
  fi

  rm -rf "$cargo_root"
}

# ---------------------------------------------------------------------------
# aicx installer
# ---------------------------------------------------------------------------

install_aicx() {
  if has_cmd aicx-mcp; then
    ok "aicx-mcp already installed: $(command -v aicx-mcp)"
    return 0
  fi

  if (( CHECK_ONLY )); then
    info "Would install AICX foundations from canonical Loctree installer:"
    info "  curl -fsSL $LOCTREE_INSTALL_URL | sh"
    return 0
  fi

  warn "AICX foundations are required, but Vibecrafted will not guess crates, npm packages, or local checkout paths."
  warn "Use the canonical installer, then rerun this check:"
  warn "  curl -fsSL $LOCTREE_INSTALL_URL | sh"
  return 1
}

# ---------------------------------------------------------------------------
# Zellij installer boundary — vc-frame validation only
# ---------------------------------------------------------------------------

install_vcframe() {
  if binary_runs vc-frame; then
    ok "vc-frame already installed: $(command -v vc-frame)"
    if (( CHECK_ONLY )); then
      info "Canonical vc-frame installer:"
      info "  curl -fsSL $VCFRAME_INSTALL_URL | sh"
    fi
    return 0
  fi

  if (( CHECK_ONLY )); then
    info "Would install vc-frame from canonical Vibecrafted installer:"
    info "  curl -fsSL $VCFRAME_INSTALL_URL | sh"
    return 0
  fi

  warn "vc-frame is required; stock zellij is not accepted as the Vibecrafted frame."
  warn "Use the canonical installer, then rerun this check:"
  warn "  curl -fsSL $VCFRAME_INSTALL_URL | sh"
  return 1
}

# ---------------------------------------------------------------------------
# Agent CLI installer
# ---------------------------------------------------------------------------

install_agents() {
  local entry binary package hint installed=0 total=0

  for entry in "${AGENT_PACKAGES[@]}"; do
    binary="${entry%%:*}"
    package="${entry#*:}"
    total=$((total + 1))

    if has_cmd "$binary"; then
      ok "$binary already installed: $(command -v "$binary")"
      installed=$((installed + 1))
      continue
    fi

    if (( CHECK_ONLY )); then
      info "Would install $binary via: npm install -g $package"
      continue
    fi

    install_from_npm "$package" "$binary" && installed=$((installed + 1))
  done

  for entry in "${AGENT_MANUAL_INSTALLS[@]}"; do
    binary="${entry%%|*}"
    hint="${entry#*|}"
    total=$((total + 1))

    if has_cmd "$binary"; then
      ok "$binary already installed: $(command -v "$binary")"
      installed=$((installed + 1))
      continue
    fi

    if (( CHECK_ONLY )); then
      info "Would verify $binary; install manually: $hint"
    else
      warn "$binary not installed. $hint"
    fi
  done

  if (( installed == total )); then
    ok "All agent CLIs installed ($installed/$total)"
    return 0
  else
    warn "Agent CLIs: $installed/$total installed"
    if (( CHECK_ONLY )); then
      info "Check-only mode: missing agent CLIs are reported but do not fail the run"
      return 0
    fi
    return 1
  fi
}

# ---------------------------------------------------------------------------
# prview installer
# ---------------------------------------------------------------------------

install_prview() {
  if has_cmd prview; then
    ok "prview already installed: $(command -v prview)"
    return 0
  fi

  # --- Attempt 0: bundled tarball (notarized drop-in) ---
  install_from_bundled "prview" && return 0

  info "Installing prview from crate metadata; release repo is $PRVIEW_REPO"
  install_from_cargo "$PRVIEW_CRATE" "prview"
}

# ---------------------------------------------------------------------------
# Microsandbox installer hint
# ---------------------------------------------------------------------------

install_sandbox() {
  if binary_runs msbserver; then
    ok "msbserver already installed: $(command -v msbserver)"
    return 0
  fi

  local os arch source_root microsandbox_dir answer
  os="$(detect_os)"
  arch="$(detect_arch)"
  source_root="$(_realpath_quiet "$SOURCE_DIR/../experimental/microsandbox" 2>/dev/null || true)"
  microsandbox_dir="${MICROSANDBOX_SOURCE:-$source_root}"

  case "$os" in
    linux|macos) ;;
    *)
      warn "microsandbox is not supported on $os"
      return 1
      ;;
  esac

  if [[ "$os" == "linux" && ! -e /dev/kvm ]]; then
    warn "libkrun requires KVM on Linux; /dev/kvm is missing."
    return 1
  fi

  if (( CHECK_ONLY )); then
    info "Would install microsandbox runtime for ${os}/${arch}"
    info "  Source: ${microsandbox_dir:-<set MICROSANDBOX_SOURCE>}"
    return 0
  fi

  if is_interactive; then
    printf '\n'
    info "Detected libkrun-capable platform candidate (${os}/${arch})."
    printf '  Install microsandbox runtime from %s? (y/N): ' "${microsandbox_dir:-MICROSANDBOX_SOURCE}"
    read -r answer
    [[ "$answer" == "y" || "$answer" == "Y" ]] || {
      warn "Skipping optional microsandbox runtime."
      return 0
    }
  else
    warn "Skipping optional microsandbox runtime in non-interactive mode."
    warn "Run: cd ${microsandbox_dir:-/path/to/microsandbox} && make build"
    return 0
  fi

  [[ -n "$microsandbox_dir" && -f "$microsandbox_dir/Makefile" ]] || {
    warn "microsandbox source not found. Set MICROSANDBOX_SOURCE and rerun."
    return 1
  }
  make -C "$microsandbox_dir" build
}

# ---------------------------------------------------------------------------
# iTerm2 / locterm AutoLaunch plugin (macOS, opt-in)
# ---------------------------------------------------------------------------

iterm2_app_present() {
  [[ "$(detect_os)" == "macos" ]] || return 1
  local candidate
  for candidate in \
    "/Applications/iTerm.app" \
    "/Applications/locterm.app" \
    "$HOME/Applications/iTerm.app" \
    "$HOME/Applications/locterm.app"; do
    [[ -d "$candidate" ]] && return 0
  done
  return 1
}

install_iterm2_integration() {
  if ! iterm2_app_present; then
    info "iTerm2 / locterm not detected — skipping vibecrafted plugin install"
    return 0
  fi

  if (( CHECK_ONLY )); then
    info "Would install vibecrafted iTerm2 / locterm AutoLaunch plugin"
    return 0
  fi

  local answer
  if is_interactive; then
    printf '\n'
    info "Detected iTerm2 (or locterm) — install vibecrafted plugin? (y/N): "
    read -r answer
    case "${answer:-}" in
      [yY]|[yY][eE][sS]) ;;
      *)
        warn "Skipping vibecrafted iTerm2 plugin (run later: python -m vibecrafted_iterm2.install_autolaunch)"
        return 0
        ;;
    esac
  else
    warn "Skipping iTerm2 plugin install in non-interactive mode."
    warn "Run later: python -m vibecrafted_iterm2.install_autolaunch"
    return 0
  fi

  local python_bin
  python_bin="$(command -v python3 || command -v python || true)"
  if [[ -z "$python_bin" ]]; then
    warn "no python3 on PATH — cannot install vibecrafted iTerm2 plugin"
    return 1
  fi

  "$python_bin" -m vibecrafted_iterm2.install_autolaunch --force \
    || { warn "vibecrafted iTerm2 plugin install failed"; return 1; }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

usage() {
  cat <<EOF
Usage: install-foundations.sh [options] [targets...]

Targets:
  loctree         Validate loctree + loctree-mcp product binaries
  aicx            Validate aicx / aicx-mcp product binaries
  vc-frame        Validate vc-frame product binary
  prview          Install prview (cargo)
  sandbox         Optional microsandbox/libkrun runtime
  iterm2-plugin   vibecrafted iTerm2 / locterm AutoLaunch plugin (macOS, opt-in)
  (no target)     Validate required foundations; install only framework-owned tools

Options:
  --all        Install all foundations (including optional)
  --check      Dry-run: show what would be installed
  --prefix DIR Install framework-owned runtime binaries to DIR (default: $PREFIX)
  --help       Show this help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --all)       INSTALL_ALL=1 ;;
    --check)     CHECK_ONLY=1 ;;
    --prefix)    shift; PREFIX="${1:?Missing prefix value}" ;;
    --help|-h)   usage; exit 0 ;;
    loctree)     TARGETS+=("loctree") ;;
    aicx)        TARGETS+=("aicx") ;;
    vc-frame)    TARGETS+=("vc-frame") ;;
    agents)      TARGETS+=("agents"); AGENTS_REQUIRED=1 ;;
    prview)      TARGETS+=("prview") ;;
    sandbox)     TARGETS+=("sandbox") ;;
    iterm2-plugin) TARGETS+=("iterm2-plugin") ;;
    *)           die "Unknown argument: $1" ;;
  esac
  shift
done

enforce_runtime_root_contract || exit 1

# Default: install required foundations
if (( ${#TARGETS[@]} == 0 )); then
  TARGETS=("loctree" "aicx" "vc-frame" "agents")
  if (( INSTALL_ALL )); then
    TARGETS+=("prview" "sandbox")
  fi
  # macOS users always get the optional iTerm2 plugin prompt; the
  # install function itself is a no-op on Linux/Windows and in
  # non-interactive shells.
  if [[ "$(detect_os)" == "macos" ]]; then
    TARGETS+=("iterm2-plugin")
  fi
fi

printf '\n\033[1m  Foundation Installer\033[0m\n'
printf '  ─────────────────────\n'
printf '  Runtime bin:  %s\n' "$PREFIX"
printf '  Launcher bin: %s\n\n' "$LAUNCHER_PREFIX"

exit_code=0
for target in "${TARGETS[@]}"; do
  case "$target" in
    loctree) install_loctree || exit_code=1 ;;
    aicx)    install_aicx    || exit_code=1 ;;
    vc-frame) install_vcframe || exit_code=1 ;;
    agents)
      if ! install_agents; then
        if (( AGENTS_REQUIRED )); then
          exit_code=1
        else
          warn "agent CLIs incomplete — optional, install later: vibecrafted doctor"
        fi
      fi
      ;;
    prview)  install_prview  || exit_code=1 ;;
    sandbox) install_sandbox || exit_code=1 ;;
    iterm2-plugin) install_iterm2_integration || exit_code=1 ;;
  esac
  echo
done

if (( exit_code == 0 )) && (( !CHECK_ONLY )); then
  install_vc_wrappers || exit_code=1
fi

if (( exit_code == 0 )) && (( !CHECK_ONLY )); then
  printf '\033[1mFoundation install complete.\033[0m\n'
  # Remind about PATH
  case ":$PATH:" in
    *":$LAUNCHER_PREFIX:"*) ;;
    *)
      printf '\n\033[33mAdd to your shell profile:\033[0m\n'
      # shellcheck disable=SC2016 # $PATH is literal output for the user
      printf '  export PATH="%s:$PATH"\n\n' "$LAUNCHER_PREFIX"
      ;;
  esac
fi

exit $exit_code
