#!/usr/bin/env bash
set -euo pipefail
# ---------------------------------------------------------------------------
# install-foundations.sh — portable installer for 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. foundation layer
#
# Handles:
#   loctree / loctree-mcp  — binary from GitHub releases (Loctree/Loctree)
#   ai-contexters (aicx-mcp) — cargo install OR binary from GH releases
#   prview                 — cargo install OR binary from GH releases
#
# Usage:
#   bash scripts/install-foundations.sh                   # install all required
#   bash scripts/install-foundations.sh --all             # install all (including optional)
#   bash scripts/install-foundations.sh loctree           # install only loctree
#   bash scripts/install-foundations.sh aicx              # install only ai-contexters
#   bash scripts/install-foundations.sh --check           # dry-run: show what would install
#   bash scripts/install-foundations.sh --prefix /usr/local  # custom install prefix
# ---------------------------------------------------------------------------

LOCTREE_VERSION="${LOCTREE_VERSION:-0.8.16}"
LOCTREE_REPO="Loctree/Loctree"

AICX_CRATE="ai-contexters"
AICX_REPO="VetCoders/ai-contexters"

PRVIEW_CRATE="prview"
PRVIEW_REPO="VetCoders/prview"

ZELLIJ_REPO="zellij-org/zellij"

# Agent CLIs — all npm packages
AGENT_PACKAGES=(
  "claude:@anthropic-ai/claude-code"
  "codex:@openai/codex"
  "gemini:@google/gemini-cli"
)

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

VIBECRAFTED_HOME="$(default_vibecrafted_home)"
PREFIX="${VIBECRAFTED_BIN:-$VIBECRAFTED_HOME/bin}"
CHECK_ONLY=0
INSTALL_ALL=0
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
# Toolchain bootstrap — brew → node → npm (macOS only)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Toolchain bootstrap — userspace-first, no sudo required
# ---------------------------------------------------------------------------

ensure_rustup() {
  has_cmd cargo && return 0
  has_cmd curl || return 1

  if is_interactive; then
    printf '\n'
    info "Rust toolchain not found."
    info "Installing rustup (no sudo needed, installs to ~/.cargo)..."
    printf '  Press Enter to proceed, or Ctrl-C to skip: '
    read -r _
  else
    info "Installing rustup (non-interactive)..."
  fi

  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path 2>&1 | tail -5 || {
    warn "rustup installation failed."
    return 1
  }

  # Source cargo env for this session
  # shellcheck disable=SC1091
  [[ -f "$HOME/.cargo/env" ]] && . "$HOME/.cargo/env"
  has_cmd cargo
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
    info "Node.js is required for agent CLIs (claude, codex, gemini)."
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

github_release_json() {
  local repo="$1" endpoint="$2"
  curl -fsSL -H 'Accept: application/vnd.github+json' \
    "https://api.github.com/repos/$repo/releases/$endpoint"
}

github_release_asset_url() {
  local repo="$1" endpoint="$2"
  shift 2
  local patterns=("$@")
  local json

  has_cmd curl || return 1
  has_cmd python3 || return 1
  json="$(github_release_json "$repo" "$endpoint")" || return 1

  python3 - "$json" "${patterns[@]}" <<'PY'
import json
import re
import sys

payload = json.loads(sys.argv[1])
assets = payload.get("assets") or []
patterns = [re.compile(p) for p in sys.argv[2:]]

for pattern in patterns:
    for asset in assets:
        name = asset.get("name") or ""
        if pattern.fullmatch(name):
            print(asset.get("browser_download_url") or "")
            raise SystemExit(0)

raise SystemExit(1)
PY
}

# ---------------------------------------------------------------------------
# Loctree installer — binary release from GitHub
# ---------------------------------------------------------------------------

loctree_asset_patterns() {
  local os="$1" arch="$2"
  case "$os" in
    linux)
      case "$arch" in
        x86_64)  printf '%s\n' '^loctree-linux-x86_64\.tar\.gz$' ;;
        aarch64) printf '%s\n' '^loctree-linux-aarch64\.tar\.gz$' ;;
        *)       die "No loctree binary for linux/$arch" ;;
      esac
      ;;
    macos)
      case "$arch" in
        x86_64)  printf '%s\n' '^loctree-darwin-x86_64\.tar\.gz$' ;;
        aarch64)
          printf '%s\n' '^loctree-darwin-aarch64\.tar\.gz$'
          printf '%s\n' '^loctree-darwin-aarch64-notarized\.zip$'
          ;;
        *)       die "No loctree binary for macos/$arch" ;;
      esac
      ;;
    windows)
      printf '%s\n' '^loctree-windows-x86_64\.exe\.zip$'
      ;;
  esac
}

install_loctree() {
  if binary_runs loctree-mcp; then
    ok "loctree-mcp already installed: $(command -v loctree-mcp)"
    return 0
  fi

  local os arch asset url tmpdir patterns_text
  local patterns=()
  os="$(detect_os)"
  arch="$(detect_arch)"
  patterns_text="$(loctree_asset_patterns "$os" "$arch")"
  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] && patterns+=("$pattern")
  done <<< "$patterns_text"

  if (( CHECK_ONLY )); then
    info "Would download loctree v${LOCTREE_VERSION} release asset for ${os}/${arch}"
    info "  Install to: $PREFIX"
    return 0
  fi

  has_cmd curl || die "curl is required to download loctree"
  ensure_prefix

  # --- Attempt 1: prebuilt binary from GH releases ---
  local binary_ok=0
  url="$(github_release_asset_url "$LOCTREE_REPO" "tags/v${LOCTREE_VERSION}" "${patterns[@]}")" && {
    asset="${url##*/}"

    info "Downloading loctree v${LOCTREE_VERSION} for ${os}/${arch}..."
    tmpdir="$(mktemp -d)"
    local archive="$tmpdir/$asset"
    if curl -fsSL -o "$archive" "$url"; then
      info "Extracting..."
      if [[ "$asset" == *.zip ]]; then
        has_cmd unzip || die "unzip required to extract archive"
        unzip -qo "$archive" -d "$tmpdir/out"
      else
        mkdir -p "$tmpdir/out"
        tar -xzf "$archive" -C "$tmpdir/out"
      fi

      # Find and install binaries (loctree, loctree-mcp, loct)
      local found=0
      while IFS= read -r -d '' bin; do
        local name
        name="$(basename "$bin")"
        case "$name" in
          loctree|loctree-mcp|loct|loctree.exe|loctree-mcp.exe)
            cp "$bin" "$PREFIX/$name"
            chmod +x "$PREFIX/$name"
            ok "Installed $name -> $PREFIX/$name"
            found=1
            ;;
        esac
      done < <(find "$tmpdir/out" -type f \( -name 'loctree*' -o -name 'loct' \) -print0 2>/dev/null)
      rm -rf "$tmpdir"

      # Verify the installed binary actually loads (dyld check)
      if (( found )) && binary_runs loctree; then
        ok "Loctree v${LOCTREE_VERSION} installed to $PREFIX"
        binary_ok=1
      elif (( found )); then
        warn "Loctree binary installed but fails to run (missing shared libraries)."
        warn "Removing broken binaries..."
        rm -f "$PREFIX/loctree" "$PREFIX/loct" "$PREFIX/loctree-mcp"
      fi
    else
      rm -rf "$tmpdir"
      warn "Failed to download loctree binary."
    fi
  }

  # Binary path succeeded — done
  (( binary_ok )) && return 0

  # --- Attempt 2: cargo (will bootstrap rustup if needed) ---
  info "Trying cargo install path for loctree-mcp..."
  if ensure_rustup; then
    install_from_cargo "loctree-mcp" "loctree-mcp" && return 0
  fi

  # --- Attempt 3: npm (will bootstrap node if needed) ---
  info "Trying npm install path for loctree-mcp..."
  install_from_npm "loctree-mcp" "loctree-mcp" && return 0

  warn "All loctree install paths exhausted."
  warn "Install manually: cargo install loctree-mcp | npm i -g loctree-mcp"
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
# ai-contexters installer
# ---------------------------------------------------------------------------

install_aicx() {
  if has_cmd aicx-mcp; then
    ok "aicx-mcp already installed: $(command -v aicx-mcp)"
    return 0
  fi

  # Try binary release first, fall back to cargo
  local os arch
  os="$(detect_os)"
  arch="$(detect_arch)"

  # ai-contexters may publish platform binaries — try GitHub release
  local asset_prefix="ai-contexters"
  local target
  case "$os" in
    linux)
      case "$arch" in
        x86_64)  target="x86_64-unknown-linux-gnu" ;;
        aarch64) target="aarch64-unknown-linux-gnu" ;;
        *)       target="" ;;
      esac
      ;;
    macos)
      case "$arch" in
        x86_64)  target="x86_64-apple-darwin" ;;
        aarch64) target="aarch64-apple-darwin" ;;
        *)       target="" ;;
      esac
      ;;
    *) target="" ;;
  esac

  if [[ -n "$target" ]] && has_cmd curl; then
    local patterns=(
      "^${asset_prefix}-v[0-9.]+-${target}\\.tar\\.gz$"
    )

    if (( CHECK_ONLY )); then
      info "Would resolve latest ai-contexters release asset for $target"
      info "Fallback: cargo install $AICX_CRATE"
      return 0
    fi

    local tmpdir url
    tmpdir="$(mktemp -d)"

    if url="$(github_release_asset_url "$AICX_REPO" "latest" "${patterns[@]}")" &&
      curl -fsSL -o "$tmpdir/aicx.tar.gz" "$url" 2>/dev/null; then
      ensure_prefix
      mkdir -p "$tmpdir/out"
      tar -xzf "$tmpdir/aicx.tar.gz" -C "$tmpdir/out"
      local found=0
      while IFS= read -r -d '' bin; do
        local name
        name="$(basename "$bin")"
        case "$name" in
          aicx|aicx-mcp|aicx-extract|aicx.exe|aicx-mcp.exe)
            cp "$bin" "$PREFIX/$name"
            chmod +x "$PREFIX/$name"
            ok "Installed $name -> $PREFIX/$name"
            found=1
            ;;
        esac
      done < <(find "$tmpdir/out" -type f \( -name 'aicx*' \) -print0 2>/dev/null)
      rm -rf "$tmpdir"
      if (( found )); then
        ok "ai-contexters installed from release"
        return 0
      fi
    fi
    rm -rf "$tmpdir"
    info "No matching binary release found, falling back to cargo..."
  fi

  install_from_cargo "$AICX_CRATE" "aicx-mcp"
}

# ---------------------------------------------------------------------------
# Zellij installer — prebuilt binary from GitHub releases
# ---------------------------------------------------------------------------

zellij_asset_patterns() {
  local os="$1" arch="$2"
  case "$os" in
    linux)
      case "$arch" in
        x86_64)  printf '%s\n' '^zellij-x86_64-unknown-linux-musl\.tar\.gz$' ;;
        aarch64) printf '%s\n' '^zellij-aarch64-unknown-linux-musl\.tar\.gz$' ;;
        *)       die "No zellij binary for linux/$arch" ;;
      esac
      ;;
    macos)
      case "$arch" in
        x86_64)  printf '%s\n' '^zellij-x86_64-apple-darwin\.tar\.gz$' ;;
        aarch64) printf '%s\n' '^zellij-aarch64-apple-darwin\.tar\.gz$' ;;
        *)       die "No zellij binary for macos/$arch" ;;
      esac
      ;;
    *) die "No zellij binary for $os" ;;
  esac
}

install_zellij() {
  if binary_runs zellij; then
    ok "zellij already installed: $(command -v zellij)"
    return 0
  fi

  local os arch patterns_text
  local patterns=()
  os="$(detect_os)"
  arch="$(detect_arch)"
  patterns_text="$(zellij_asset_patterns "$os" "$arch")"
  while IFS= read -r pattern; do
    [[ -n "$pattern" ]] && patterns+=("$pattern")
  done <<< "$patterns_text"

  if (( CHECK_ONLY )); then
    info "Would download zellij release asset for ${os}/${arch}"
    info "  Install to: $PREFIX"
    return 0
  fi

  has_cmd curl || die "curl is required to download zellij"
  ensure_prefix

  local url asset tmpdir
  url="$(github_release_asset_url "$ZELLIJ_REPO" "latest" "${patterns[@]}")" || {
    warn "Could not resolve a zellij release asset for ${os}/${arch}."
    warn "Falling back to cargo install..."
    if ensure_rustup; then
      install_from_cargo "zellij" "zellij" && return 0
    fi
    return 1
  }
  asset="${url##*/}"

  info "Downloading zellij for ${os}/${arch}..."
  tmpdir="$(mktemp -d)"
  local archive="$tmpdir/$asset"
  if ! curl -fsSL -o "$archive" "$url"; then
    rm -rf "$tmpdir"
    warn "Failed to download zellij."
    return 1
  fi

  info "Extracting..."
  mkdir -p "$tmpdir/out"
  tar -xzf "$archive" -C "$tmpdir/out"

  local found=0
  while IFS= read -r -d '' bin; do
    local name
    name="$(basename "$bin")"
    if [[ "$name" == "zellij" ]]; then
      cp "$bin" "$PREFIX/$name"
      chmod +x "$PREFIX/$name"
      ok "Installed $name -> $PREFIX/$name"
      found=1
    fi
  done < <(find "$tmpdir/out" -type f -name 'zellij' -print0 2>/dev/null)

  rm -rf "$tmpdir"

  if (( found )) && binary_runs zellij; then
    ok "Zellij installed to $PREFIX"
    return 0
  fi

  warn "Zellij binary failed. Trying cargo..."
  if ensure_rustup; then
    install_from_cargo "zellij" "zellij" && return 0
  fi
  return 1
}

# ---------------------------------------------------------------------------
# Agent CLI installer — all via npm
# ---------------------------------------------------------------------------

install_agents() {
  local entry binary package installed=0 total=0

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

  if (( installed == total )); then
    ok "All agent CLIs installed ($installed/$total)"
  else
    warn "Agent CLIs: $installed/$total installed"
  fi
}

# ---------------------------------------------------------------------------
# prview installer
# ---------------------------------------------------------------------------

install_prview() {
  install_from_cargo "$PRVIEW_CRATE" "prview"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

usage() {
  cat <<EOF
Usage: install-foundations.sh [options] [targets...]

Targets:
  loctree      Install loctree + loctree-mcp (binary from GH releases)
  aicx         Install ai-contexters / aicx-mcp (binary or cargo)
  prview       Install prview (cargo)
  (no target)  Install required foundations (loctree + aicx)

Options:
  --all        Install all foundations (including optional)
  --check      Dry-run: show what would be installed
  --prefix DIR Install binaries to DIR (default: $PREFIX)
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
    zellij)      TARGETS+=("zellij") ;;
    agents)      TARGETS+=("agents") ;;
    prview)      TARGETS+=("prview") ;;
    *)           die "Unknown argument: $1" ;;
  esac
  shift
done

# Default: install required foundations
if (( ${#TARGETS[@]} == 0 )); then
  TARGETS=("loctree" "aicx" "zellij" "agents")
  if (( INSTALL_ALL )); then
    TARGETS+=("prview")
  fi
fi

printf '\n\033[1m  Foundation Installer\033[0m\n'
printf '  ─────────────────────\n'
printf '  Prefix: %s\n\n' "$PREFIX"

exit_code=0
for target in "${TARGETS[@]}"; do
  case "$target" in
    loctree) install_loctree || exit_code=1 ;;
    aicx)    install_aicx    || exit_code=1 ;;
    zellij)  install_zellij  || exit_code=1 ;;
    agents)  install_agents  || exit_code=1 ;;
    prview)  install_prview  || exit_code=1 ;;
  esac
  echo
done

if (( exit_code == 0 )) && (( !CHECK_ONLY )); then
  printf '\033[1mFoundation install complete.\033[0m\n'
  # Remind about PATH
  case ":$PATH:" in
    *":$PREFIX:"*) ;;
    *)
      printf '\n\033[33mAdd to your shell profile:\033[0m\n'
      # shellcheck disable=SC2016 # $PATH is literal output for the user
      printf '  export PATH="%s:$PATH"\n\n' "$PREFIX"
      ;;
  esac
fi

exit $exit_code
