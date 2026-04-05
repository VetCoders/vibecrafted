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

ensure_prefix() {
  mkdir -p "$PREFIX"
  # Add to PATH for the rest of this script
  case ":$PATH:" in
    *":$PREFIX:"*) ;;
    *) export PATH="$PREFIX:$PATH" ;;
  esac
}

# ---------------------------------------------------------------------------
# Loctree installer — binary release from GitHub
# ---------------------------------------------------------------------------

loctree_asset_name() {
  local os="$1" arch="$2"
  case "$os" in
    linux)
      case "$arch" in
        x86_64)  echo "loctree-x86_64-unknown-linux-gnu.tar.gz" ;;
        aarch64) echo "loctree-aarch64-unknown-linux-gnu.tar.gz" ;;
        *)       die "No loctree binary for linux/$arch" ;;
      esac
      ;;
    macos)
      case "$arch" in
        x86_64)  echo "loctree-x86_64-apple-darwin.tar.gz" ;;
        aarch64) echo "loctree-aarch64-apple-darwin.tar.gz" ;;
        *)       die "No loctree binary for macos/$arch" ;;
      esac
      ;;
    windows)
      echo "loctree-x86_64-pc-windows-msvc.zip"
      ;;
  esac
}

install_loctree() {
  if has_cmd loctree-mcp; then
    ok "loctree-mcp already installed: $(command -v loctree-mcp)"
    return 0
  fi

  local os arch asset url tmpdir
  os="$(detect_os)"
  arch="$(detect_arch)"
  asset="$(loctree_asset_name "$os" "$arch")"
  url="https://github.com/$LOCTREE_REPO/releases/download/v${LOCTREE_VERSION}/${asset}"

  if (( CHECK_ONLY )); then
    info "Would download loctree v${LOCTREE_VERSION} from:"
    info "  $url"
    info "  Install to: $PREFIX"
    return 0
  fi

  has_cmd curl || die "curl is required to download loctree"
  ensure_prefix

  info "Downloading loctree v${LOCTREE_VERSION} for ${os}/${arch}..."
  tmpdir="$(mktemp -d)"
  # shellcheck disable=SC2064 # intentional: expand $tmpdir now
  trap "rm -rf '$tmpdir'" RETURN

  local archive="$tmpdir/$asset"
  if ! curl -fsSL -o "$archive" "$url"; then
    warn "Failed to download loctree binary from release."
    warn "URL: $url"
    warn "Falling back to cargo install..."
    install_from_cargo "loctree" "loctree"
    return $?
  fi

  info "Extracting..."
  if [[ "$asset" == *.zip ]]; then
    has_cmd unzip || die "unzip required to extract Windows archive"
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

  if (( !found )); then
    warn "No loctree binaries found in release archive. Trying cargo..."
    install_from_cargo "loctree-mcp" "loctree-mcp"
    return $?
  fi

  ok "Loctree v${LOCTREE_VERSION} installed to $PREFIX"
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
  # shellcheck disable=SC2064 # intentional: expand $cargo_root now
  trap "rm -rf '$cargo_root'" RETURN

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
      warn "cargo install $crate succeeded but no binaries found"
      return 1
    fi
  else
    warn "cargo install $crate failed"
    return 1
  fi
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
    # Try to fetch latest release asset
    local url="https://github.com/$AICX_REPO/releases/latest/download/${asset_prefix}-${target}.tar.gz"

    if (( CHECK_ONLY )); then
      info "Would try: $url"
      info "Fallback: cargo install $AICX_CRATE"
      return 0
    fi

    local tmpdir
    tmpdir="$(mktemp -d)"

    if curl -fsSL -o "$tmpdir/aicx.tar.gz" "$url" 2>/dev/null; then
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
    info "No binary release found, falling back to cargo..."
  fi

  install_from_cargo "$AICX_CRATE" "aicx-mcp"
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
    prview)      TARGETS+=("prview") ;;
    *)           die "Unknown argument: $1" ;;
  esac
  shift
done

# Default: install required foundations
if (( ${#TARGETS[@]} == 0 )); then
  TARGETS=("loctree" "aicx")
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
