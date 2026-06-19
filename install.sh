#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install.sh [--gui] [--yes] [--runtime <horse>] [--ref <branch>] [--archive-url <url> | --archive-file <path>] [--tools-dir <dir>] [make-target]

Bootstrap a local 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. source snapshot into $VIBECRAFTED_ROOT/.vibecrafted/tools and then
run a local staged install path from that copy.

Use `--gui` when you want the browser-based guided installer.
Use `--yes` to skip the attended bootstrap confirmation prompt.
Use `--runtime <horse>` to install and activate a lab runtime: wezterm, vc-apprt, locterm, microsandbox, or none.
Non-interactive runs without `--gui` bypass the browser and call the compact installer directly.

Examples:
  curl -fsSL https://vibecrafted.io/install.sh | bash
  curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui
  curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --yes
  curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --runtime wezterm
  curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --ref develop
  bash install.sh doctor
  bash install.sh --runtime locterm
  bash install.sh --archive-file /tmp/vibecrafted.tar.gz vibecrafted
EOF_USAGE
}

die() {
  printf 'Error: %s\n' "$*" >&2
  exit 1
}

info() {
  printf '%s\n' "$*"
}

# -----------------------------------------------------------------------------
# Platform detection (Plan 03 — cross-platform install)
#
# detect_platform sets PLATFORM_OS to one of: macos, linux, wsl, unsupported.
# detect_linux_distro sets LINUX_DISTRO_ID (e.g. debian, ubuntu, arch, fedora)
# and LINUX_PKG_MGR (apt, dnf, pacman, "") based on /etc/os-release. Both are
# safe to call multiple times. On macOS, the linux helpers are no-ops.
#
# The detection layer is informational only — it does NOT change the staged
# install layout. macOS path (`$HOME/.vibecrafted`) and Linux/WSL path are
# the same; only the pre-flight hints (which package manager to suggest)
# differ. WSL is treated as Linux for runtime; the WSL banner only changes
# the user-facing message.
# -----------------------------------------------------------------------------

PLATFORM_OS=""
LINUX_DISTRO_ID=""
LINUX_PKG_MGR=""

detect_platform() {
  case "$(uname -s)" in
    Darwin*)
      PLATFORM_OS="macos"
      ;;
    Linux*)
      # WSL: kernel release contains 'microsoft' or '/proc/version' mentions it.
      if grep -qiE 'microsoft|wsl' /proc/sys/kernel/osrelease 2>/dev/null \
         || grep -qiE 'microsoft|wsl' /proc/version 2>/dev/null; then
        PLATFORM_OS="wsl"
      else
        PLATFORM_OS="linux"
      fi
      ;;
    MINGW*|MSYS*|CYGWIN*)
      PLATFORM_OS="unsupported"
      ;;
    *)
      PLATFORM_OS="unsupported"
      ;;
  esac
}

detect_linux_distro() {
  LINUX_DISTRO_ID=""
  LINUX_PKG_MGR=""
  [[ "$PLATFORM_OS" == "linux" || "$PLATFORM_OS" == "wsl" ]] || return 0
  if [[ -r /etc/os-release ]]; then
    # shellcheck disable=SC1091
    LINUX_DISTRO_ID="$(. /etc/os-release && printf '%s' "${ID:-}")"
  fi
  case "$LINUX_DISTRO_ID" in
    debian|ubuntu|linuxmint|pop|raspbian)
      LINUX_PKG_MGR="apt"
      ;;
    fedora|rhel|centos|rocky|almalinux)
      LINUX_PKG_MGR="dnf"
      ;;
    arch|manjaro|endeavouros)
      LINUX_PKG_MGR="pacman"
      ;;
    *)
      LINUX_PKG_MGR=""
      ;;
  esac
}

# preflight_pkg_hint emits a copy-pasteable install command for the named
# missing tool, scoped to the detected Linux package manager. macOS path
# uses brew. On unknown distros, emit a generic message. Idempotent and
# silent under non-Linux/macOS hosts.
preflight_pkg_hint() {
  local missing="$1"
  case "$PLATFORM_OS" in
    macos)
      printf '  hint: brew install %s\n' "$missing" >&2
      ;;
    linux|wsl)
      case "$LINUX_PKG_MGR" in
        apt)
          printf '  hint: sudo apt-get update && sudo apt-get install -y %s\n' "$missing" >&2
          ;;
        dnf)
          printf '  hint: sudo dnf install -y %s\n' "$missing" >&2
          ;;
        pacman)
          printf '  hint: sudo pacman -S --noconfirm %s\n' "$missing" >&2
          ;;
        *)
          printf '  hint: install %s via your distro package manager\n' "$missing" >&2
          ;;
      esac
      ;;
    *)
      printf '  hint: install %s for your platform\n' "$missing" >&2
      ;;
  esac
}

platform_banner() {
  case "$PLATFORM_OS" in
    macos)
      info "Platform: macOS ($(uname -m))"
      ;;
    linux)
      if [[ -n "$LINUX_DISTRO_ID" ]]; then
        info "Platform: Linux / $LINUX_DISTRO_ID ($(uname -m))"
      else
        info "Platform: Linux / generic ($(uname -m))"
      fi
      ;;
    wsl)
      if [[ -n "$LINUX_DISTRO_ID" ]]; then
        info "Platform: WSL / $LINUX_DISTRO_ID ($(uname -m))"
      else
        info "Platform: WSL / generic ($(uname -m))"
      fi
      ;;
    *)
      info "Platform: $(uname -s) (unsupported — best-effort only)"
      ;;
  esac
}

extract_tarball() {
  local archive="$1"
  local destination="$2"
  local tar_args=(-xzf "$archive" -C "$destination")

  # Release archives can carry macOS LIBARCHIVE/PAX xattrs. GNU tar prints a
  # wall of harmless "unknown keyword" warnings on Linux unless we quiet them.
  if tar --warning=no-unknown-keyword -tf "$archive" >/dev/null 2>&1; then
    tar --warning=no-unknown-keyword "${tar_args[@]}"
  else
    COPYFILE_DISABLE=1 tar "${tar_args[@]}"
  fi
}

is_interactive_session() {
  [[ -t 0 && -t 1 ]]
}

has_attended_tty() {
  if { exec 9<>/dev/tty; } 2>/dev/null; then
    exec 9>&- 9<&- || true
    return 0
  fi
  return 1
}

default_vibecrafted_home() {
  if [[ -n "${VIBECRAFTED_HOME:-}" ]]; then
    printf '%s\n' "$VIBECRAFTED_HOME"
    return
  fi
  printf '%s\n' "$HOME/.vibecrafted"
}

sanitize_ref() {
  printf '%s' "$1" | tr '/:@ ' '----' | tr -cd '[:alnum:]._-' 
}

bootstrap_next_step() {
  if [[ "$target" == "vibecrafted" && "$use_gui" == "1" ]]; then
    printf '%s\n' "launch the guided installer UI"
    return
  fi

  if [[ "$target" == "vibecrafted" ]] && ! is_interactive_session; then
    printf '%s\n' "run the compact installer"
    return
  fi

  if [[ "$target" == "vibecrafted" ]]; then
    printf '%s\n' "run the terminal-native installer wizard"
    return
  fi

  printf "run make target '%s'\n" "$target"
}

prompt_attended_consent() {
  local source_description next_step response

  [[ "$auto_yes" == "1" ]] && return 0
  has_attended_tty || return 0

  if [[ -n "$archive_file" ]]; then
    source_description="unpack local archive: $archive_file"
  else
    source_description="download snapshot: $archive_url"
  fi
  next_step="$(bootstrap_next_step)"

  {
    printf '\n'
    printf 'This bootstrap will:\n'
    printf '  • %s\n' "$source_description"
    printf '  • stage the control plane under %s\n' "$staged_dir"
    printf '  • refresh the current symlink at %s\n' "$current_link"
    printf '  • %s\n' "$next_step"
    printf '\n'
    printf 'Nothing will be staged or installed until you say yes.\n'
  } > /dev/tty

  while true; do
    printf 'Proceed? [y/N] ' > /dev/tty
    if ! IFS= read -r response < /dev/tty; then
      printf '\nBootstrap cancelled: no confirmation received.\n' > /dev/tty
      exit 1
    fi
    case "$response" in
      [yY]|[yY][eE][sS])
        printf '\n' > /dev/tty
        return 0
        ;;
      ""|[nN]|[nN][oO])
        printf '\nCancelled. Nothing was staged or installed.\n' > /dev/tty
        exit 0
        ;;
      *)
        printf 'Please answer yes or no.\n' > /dev/tty
        ;;
    esac
  done
}

vibecrafted_home="$(default_vibecrafted_home)"
export VIBECRAFTED_HOME="$vibecrafted_home"
default_tools_dir="${VIBECRAFTED_TOOLS_HOME:-$vibecrafted_home/tools}"
default_ref="${VIBECRAFTED_REF:-main}"

ref="$default_ref"
archive_url=""
archive_file=""
tools_dir="$default_tools_dir"
target="vibecrafted"
use_gui=0
auto_yes=0
runtime="none"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gui)
      use_gui=1
      ;;
    --yes|-y)
      auto_yes=1
      ;;
    --runtime)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --runtime"
      runtime="$1"
      ;;
    --ref)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --ref"
      ref="$1"
      ;;
    --archive-url)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --archive-url"
      archive_url="$1"
      ;;
    --archive-file)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --archive-file"
      archive_file="$1"
      ;;
    --tools-dir)
      shift
      [[ $# -gt 0 ]] || die "Missing value for --tools-dir"
      tools_dir="$1"
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      target="$1"
      ;;
  esac
  shift
done

case "$target" in
  vibecrafted)
    target="vibecrafted"
    ;;
esac

if [[ -n "$archive_url" && -n "$archive_file" ]]; then
  die "Use either --archive-url or --archive-file, not both"
fi

if [[ "$use_gui" == "1" && "$target" != "vibecrafted" ]]; then
  die "--gui can only be used with the default vibecrafted install target"
fi

case "$runtime" in
  none|wezterm|vc-apprt|locterm|microsandbox)
    ;;
  vc_apprt|vc-)
    runtime="vc-apprt"
    ;;
  *)
    die "Unknown runtime horse: $runtime (expected wezterm, vc-apprt, locterm, microsandbox, none)"
    ;;
esac

if [[ -z "$archive_url" && -z "$archive_file" ]]; then
  # Resolve latest version from the channel manifest instead of hard-pinning.
  channel_url="https://vibecrafted.io/channel/${ref}.json"
  resolved_url=""
  if command -v curl >/dev/null 2>&1; then
    resolved_url="$(curl -fsSL "$channel_url" 2>/dev/null \
      | python3 -c "import sys,json; print(json.load(sys.stdin).get('archive_url',''))" 2>/dev/null)" || true
  fi
  if [[ -n "$resolved_url" ]]; then
    archive_url="$resolved_url"
    info "Resolved from channel ($ref): $archive_url"
  else
    # Fallback: source snapshot for pre-channel / pre-deploy kickoffs.
    archive_url="https://github.com/VetCoders/vibecrafted/archive/refs/heads/${ref}.tar.gz"
    info "[note] Channel manifest not available — using GitHub source snapshot for ${ref}"
  fi
fi

detect_platform
detect_linux_distro
platform_banner

if [[ "$PLATFORM_OS" == "unsupported" ]]; then
  info ""
  info "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. v1.x ships native Linux + macOS + WSL paths."
  info "On native Windows the installer must run inside WSL2:"
  info "    wsl bash -c 'curl -fsSL https://vibecrafted.io/install.sh | bash'"
  info "Or open: https://github.com/VetCoders/vibecrafted/issues to track v2.x"
  info "native Windows support."
  die "Unsupported platform: $(uname -s). Re-run inside WSL2."
fi

case "$runtime:$PLATFORM_OS" in
  none:*|wezterm:macos|wezterm:linux|wezterm:wsl|vc-apprt:macos|vc-apprt:linux|locterm:macos|microsandbox:macos|microsandbox:linux)
    ;;
  locterm:*)
    die "locterm is macOS-only, try --runtime wezterm or --runtime microsandbox"
    ;;
  vc-apprt:*)
    die "vc-apprt supports macOS and Linux only, try --runtime wezterm"
    ;;
  microsandbox:*)
    die "microsandbox requires macOS HVF or Linux KVM, try --runtime wezterm"
    ;;
  *)
    die "Unsupported platform '$PLATFORM_OS' for runtime '$runtime'"
    ;;
esac

# Pre-flight tool check — on missing tools, emit a copy-pasteable install
# hint for the detected platform (Plan 03). Cross-platform tar/make/python3
# are widely available; the hint only fires when they really are missing
# (slim container, fresh VM, etc.). macOS path preserved exactly.
preflight_require() {
  local tool="$1"
  command -v "$tool" >/dev/null 2>&1 && return 0
  printf 'Error: %s is required\n' "$tool" >&2
  preflight_pkg_hint "$tool"
  exit 1
}

preflight_require tar
preflight_require make
preflight_require python3
if [[ -z "$archive_file" ]]; then
  preflight_require curl
else
  [[ -f "$archive_file" ]] || die "Archive file not found: $archive_file"
fi

safe_ref="$(sanitize_ref "$ref")"
[[ -n "$safe_ref" ]] || safe_ref="current"
staged_dir="$tools_dir/vibecrafted-$safe_ref"
current_link="$tools_dir/vibecrafted-current"

prompt_attended_consent

mkdir -p "$tools_dir"

tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/vibecrafted-bootstrap.XXXXXX")"
cleanup() {
  rm -rf "$tmpdir"
}
trap cleanup EXIT

extract_root="$tmpdir/extract"
mkdir -p "$extract_root"

verify_signature() {
  local file="$1" base_url="$2"
  local sig_file="${file}.sig"
  local pub_file="$tmpdir/vibecrafted-signing.pub"
  local sums_file="$tmpdir/SHA256SUMS"

  if ! curl -fsSL "${base_url}/vibecrafted-signing.pub" -o "$pub_file" 2>/dev/null; then
    info "  [warn] Could not fetch signing key — skipping signature verification"
    return 0
  fi
  if ! curl -fsSL "${base_url}/SHA256SUMS" -o "$sums_file" 2>/dev/null; then
    info "  [warn] Could not fetch SHA256SUMS — skipping checksum verification"
    return 0
  fi

  local expected actual
  expected="$(grep "$(basename "$file")" "$sums_file" | awk '{print $1}')"
  actual="$(shasum -a 256 "$file" 2>/dev/null || sha256sum "$file" 2>/dev/null)"
  actual="${actual%% *}"
  if [[ -n "$expected" && "$actual" != "$expected" ]]; then
    die "SHA256 mismatch for $(basename "$file"): expected $expected, got $actual"
  fi
  [[ -n "$expected" ]] && info "  SHA256 ✓"

  if curl -fsSL "${base_url}/$(basename "$sig_file")" -o "$sig_file" 2>/dev/null; then
    if openssl dgst -sha256 -verify "$pub_file" -signature "$sig_file" "$file" >/dev/null 2>&1; then
      info "  Signature ✓  (Maciej Gad / MW223P3NPX)"
    else
      die "Signature verification FAILED for $(basename "$file")"
    fi
  else
    info "  [warn] No .sig file found — skipping signature verification"
  fi
}

if [[ -n "$archive_file" ]]; then
  info "Staging source: local archive"
  extract_tarball "$archive_file" "$extract_root"
else
  info "Staging source: download snapshot"
  local_archive="$tmpdir/$(basename "$archive_url")"
  curl -fsSL "$archive_url" -o "$local_archive"

  base_url="${archive_url%/*}"
  verify_signature "$local_archive" "$base_url"

  extract_tarball "$local_archive" "$extract_root"
fi

source_dir=""
if [[ -f "$extract_root/Makefile" && -d "$extract_root/scripts" ]]; then
  source_dir="$extract_root"
else
  candidate_dir="$(find "$extract_root" -mindepth 1 -maxdepth 1 -type d | head -n 1)"
  if [[ -n "${candidate_dir:-}" && -f "$candidate_dir/Makefile" && -d "$candidate_dir/scripts" ]]; then
    source_dir="$candidate_dir"
  fi
fi
[[ -n "$source_dir" ]] || die "Could not find extracted source directory"

incoming_dir="$tools_dir/.incoming-$safe_ref-$$"

rm -rf "$incoming_dir"
mv "$source_dir" "$incoming_dir"
rm -rf "$staged_dir"
mv "$incoming_dir" "$staged_dir"
ln -sfn "$staged_dir" "$current_link"

# Read canonical VERSION file from the staged source tree for the post-install banner.
# The repo ships VERSION at the root; fall back to 'unknown' if absent (e.g. custom tarballs).
_installed_version=""
if [[ -f "$staged_dir/VERSION" ]]; then
  _installed_version="$(tr -d '[:space:]' < "$staged_dir/VERSION" 2>/dev/null || true)"
fi
[[ -n "$_installed_version" ]] || _installed_version="unknown"

post_install_banner() {
  printf '\n'
  info "---------------------------------------------------------------"
  info " Staged: vibecrafted $_installed_version"
  info " Channel:   tarball"
  info ""
  info " The archive has been extracted and symlinked."
  info " Shell integration runs next — if the step below fails,"
  info " re-run the install command."
  info ""
  info " Update:  vibecrafted update"
  info " Health:  vibecrafted doctor"
  info "---------------------------------------------------------------"
}

bootstrap_log="$vibecrafted_home/bootstrap.log"

write_bootstrap_log_header() {
  mkdir -p "$(dirname "$bootstrap_log")"
  {
    printf 'vibecrafted bootstrap\n'
    printf 'version: %s\n' "$_installed_version"
    printf 'staged: %s\n' "$staged_dir"
    printf 'current: %s\n' "$current_link"
    printf '\n'
  } > "$bootstrap_log"
}

compact_bootstrap_banner() {
  printf '\n'
  info "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. bootstrap"
  info "  Staged      vibecrafted $_installed_version"
  info "  Control     $current_link"
  info "  Log         $bootstrap_log"
}

if [[ "$target" == "vibecrafted" && "$use_gui" == "1" ]]; then
  gui_installer="$current_link/scripts/installer_gui.py"
  [[ -f "$gui_installer" ]] || die "Guided installer not found: $gui_installer"
  post_install_banner
  info "Launching guided installer UI:"
  info "  python3 $gui_installer --source $current_link"
  printf '\n'
  export VIBECRAFTED_RUNTIME="$runtime"
  exec python3 "$gui_installer" --source "$current_link"
fi

if [[ "$target" == "vibecrafted" ]] && ! is_interactive_session; then
  installer="$current_link/scripts/vetcoders_install.py"
  [[ -f "$installer" ]] || die "Installer not found: $installer"
  write_bootstrap_log_header
  compact_bootstrap_banner

  # Install foundations (loctree, aicx) from GH releases before the main installer.
  foundations_script="$current_link/scripts/install-foundations.sh"
  if [[ -x "$foundations_script" ]] || [[ -f "$foundations_script" ]]; then
    if bash "$foundations_script" >> "$bootstrap_log" 2>&1; then
      info "  [ok]        foundations ready"
    else
      info "  [warn]      foundations had issues; continuing"
    fi
  fi

  runtime_script="$current_link/scripts/install-runtime.sh"
  if [[ "$runtime" != "none" ]]; then
    [[ -f "$runtime_script" ]] || die "Runtime installer not found: $runtime_script"
    if bash "$runtime_script" --runtime "$runtime" --yes >> "$bootstrap_log" 2>&1; then
      info "  [ok]        runtime $runtime ready"
    else
      die "Runtime installer failed; see $bootstrap_log"
    fi
  fi

  # Ensure foundations and tools installed by install-foundations.sh are visible.
  for _p in "${vibecrafted_home}/bin" "${vibecrafted_home}/tools/node/bin" "$HOME/.cargo/bin"; do
    case ":${PATH}:" in
      *":${_p}:"*) ;;
      *) [[ -d "$_p" ]] && export PATH="${_p}:${PATH}" ;;
    esac
  done

  printf '\n'
  info "  Running     compact installer"
  printf '\n'
  export VIBECRAFTED_RUNTIME="$runtime"
  exec python3 "$installer" install --source "$current_link" --with-shell --compact --non-interactive
fi

# Interactive terminal session: default target is the built-in
# vetcoders-installer sequential runner, executed out of the staged repo's
# own scripts/installer/ sub-package via `uv run --project`. The browser
# GUI is opt-in via `--gui` (handled above). Other make targets still fall
# through to the Makefile.
if [[ "$target" == "vibecrafted" ]]; then
  manifest="$current_link/install.toml"
  installer_dir="$current_link/scripts/installer"
  [[ -f "$manifest" ]] || die "Install manifest not found: $manifest"
  [[ -d "$installer_dir" ]] || die "Built-in installer package not found: $installer_dir"

  # Make sure user-local binaries (cargo, .local) are visible to the installer's
  # subprocesses — otherwise tools installed outside PATH won't be detected.
  for _p in "${vibecrafted_home}/bin" "${vibecrafted_home}/tools/node/bin" "$HOME/.cargo/bin" "$HOME/.local/bin"; do
    case ":${PATH}:" in
      *":${_p}:"*) ;;
      *) [[ -d "$_p" ]] && export PATH="${_p}:${PATH}" ;;
    esac
  done

  if ! command -v uv >/dev/null 2>&1; then
    info "Bootstrapping uv (one-time setup)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh \
      || die "Failed to bootstrap uv"
    # shellcheck disable=SC1090
    # shellcheck disable=SC1091
    [[ -f "$HOME/.local/bin/env" ]] && source "$HOME/.local/bin/env"
    export PATH="$HOME/.local/bin:$PATH"
  fi

  post_install_banner
  info "Running built-in installer:"
  info "  uv run --project $installer_dir vetcoders-installer $manifest"
  printf '\n'
  export VIBECRAFTED_RUNTIME="$runtime"
  exec uv run --project "$installer_dir" --quiet vetcoders-installer "$manifest"
fi

post_install_banner
info "Launching local make target:"
info "  make --no-print-directory -C $current_link $target"
printf '\n'

exec make --no-print-directory -C "$current_link" "$target"
