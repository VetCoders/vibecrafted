#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install.sh [--gui] [--ref <branch>] [--archive-url <url> | --archive-file <path>] [--tools-dir <dir>] [make-target]

Bootstrap a local 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. source snapshot into $VIBECRAFTED_ROOT/.vibecrafted/tools and then
run a local staged install path from that copy.

Use `--gui` when you want the browser-based guided installer.
Non-interactive runs without `--gui` bypass the browser and call the compact installer directly.

Examples:
  curl -fsSL https://vibecrafted.io/install.sh | bash
  curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui
  curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --ref develop
  bash install.sh doctor
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

is_interactive_session() {
  [[ -t 0 && -t 1 ]]
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

while [[ $# -gt 0 ]]; do
  case "$1" in
    --gui)
      use_gui=1
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

command -v tar >/dev/null 2>&1 || die "tar is required"
command -v make >/dev/null 2>&1 || die "make is required"
command -v python3 >/dev/null 2>&1 || die "python3 is required"
if [[ -z "$archive_file" ]]; then
  command -v curl >/dev/null 2>&1 || die "curl is required"
else
  [[ -f "$archive_file" ]] || die "Archive file not found: $archive_file"
fi

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
  info "Unpacking local archive: $archive_file"
  tar -xzf "$archive_file" -C "$extract_root"
else
  info "Downloading 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. snapshot: $archive_url"
  local_archive="$tmpdir/$(basename "$archive_url")"
  curl -fsSL "$archive_url" -o "$local_archive"

  base_url="${archive_url%/*}"
  info "Verifying integrity..."
  verify_signature "$local_archive" "$base_url"

  tar -xzf "$local_archive" -C "$extract_root"
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

safe_ref="$(sanitize_ref "$ref")"
[[ -n "$safe_ref" ]] || safe_ref="current"
staged_dir="$tools_dir/vibecrafted-$safe_ref"
current_link="$tools_dir/vibecrafted-current"
incoming_dir="$tools_dir/.incoming-$safe_ref-$$"

rm -rf "$incoming_dir"
mv "$source_dir" "$incoming_dir"
rm -rf "$staged_dir"
mv "$incoming_dir" "$staged_dir"
ln -sfn "$staged_dir" "$current_link"

info "Staged bootstrap source:"
info "  $staged_dir"
info "Current control plane:"
info "  $current_link"

# Extract version from the archive URL or staged Makefile for the post-install banner.
_installed_version=""
if [[ -f "$staged_dir/Makefile" ]]; then
  _installed_version="$(grep -oP 'VERSION\s*:?=\s*\K\S+' "$staged_dir/Makefile" 2>/dev/null || true)"
fi
[[ -n "$_installed_version" ]] || _installed_version="$(basename "$archive_url" .tar.gz 2>/dev/null || echo 'unknown')"

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

if [[ "$target" == "vibecrafted" && "$use_gui" == "1" ]]; then
  gui_installer="$current_link/scripts/installer_gui.py"
  [[ -f "$gui_installer" ]] || die "Guided installer not found: $gui_installer"
  post_install_banner
  info "Launching guided installer UI:"
  info "  python3 $gui_installer --source $current_link"
  printf '\n'
  exec python3 "$gui_installer" --source "$current_link"
fi

if [[ "$target" == "vibecrafted" ]] && ! is_interactive_session; then
  installer="$current_link/scripts/vetcoders_install.py"
  [[ -f "$installer" ]] || die "Installer not found: $installer"
  info "Non-interactive bootstrap detected:"
  info "  bypassing the browser UI and running compact installer"

  # Install foundations (loctree, aicx) from GH releases before the main installer.
  foundations_script="$current_link/scripts/install-foundations.sh"
  if [[ -x "$foundations_script" ]] || [[ -f "$foundations_script" ]]; then
    info "Installing foundations..."
    bash "$foundations_script" || info "  [warn] Foundation install had issues (non-fatal)"
  fi

  # Ensure foundations and tools installed by install-foundations.sh are visible.
  for _p in "${vibecrafted_home}/bin" "${vibecrafted_home}/tools/node/bin" "$HOME/.cargo/bin"; do
    case ":${PATH}:" in
      *":${_p}:"*) ;;
      *) [[ -d "$_p" ]] && export PATH="${_p}:${PATH}" ;;
    esac
  done

  post_install_banner
  info "Launching installer:"
  info "  python3 $installer install --source $current_link --with-shell --compact --non-interactive"
  printf '\n'
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
    [[ -f "$HOME/.local/bin/env" ]] && source "$HOME/.local/bin/env"
    export PATH="$HOME/.local/bin:$PATH"
  fi

  post_install_banner
  info "Running built-in installer:"
  info "  uv run --project $installer_dir vetcoders-installer $manifest"
  printf '\n'
  exec uv run --project "$installer_dir" --quiet vetcoders-installer "$manifest"
fi

post_install_banner
info "Launching local make target:"
info "  make -C $current_link $target"
printf '\n'

exec make -C "$current_link" "$target"
