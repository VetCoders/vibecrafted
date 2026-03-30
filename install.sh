#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF_USAGE'
Usage: install.sh [--ref <branch>] [--archive-url <url> | --archive-file <path>] [--tools-dir <dir>] [make-target]

Bootstrap a local VibeCrafted source snapshot into ~/.vibecrafted/tools and then
run a local staged install path from that copy.

Interactive terminals always enter the installer TUI.
Non-interactive runs bypass TUI and call the compact installer directly.

Examples:
  curl -fsSLO <raw-install-url> && bash install.sh
  curl -fsSLO <raw-install-url> && bash install.sh --ref develop
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

sanitize_ref() {
  printf '%s' "$1" | tr '/:@ ' '----' | tr -cd '[:alnum:]._-' 
}

vibecrafted_home="${VIBECRAFTED_HOME:-$HOME/.vibecrafted}"
default_tools_dir="${VIBECRAFTED_TOOLS_HOME:-$vibecrafted_home/tools}"
default_ref="${VIBECRAFTED_REF:-main}"

ref="$default_ref"
archive_url=""
archive_file=""
tools_dir="$default_tools_dir"
target="vibecrafted"

while [[ $# -gt 0 ]]; do
  case "$1" in
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
  install|vibecrafted)
    target="vibecrafted"
    ;;
esac

if [[ -n "$archive_url" && -n "$archive_file" ]]; then
  die "Use either --archive-url or --archive-file, not both"
fi

if [[ -z "$archive_url" && -z "$archive_file" ]]; then
  archive_url="https://github.com/VetCoders/vibecrafted/archive/refs/heads/${ref}.tar.gz"
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

if [[ -n "$archive_file" ]]; then
  info "Unpacking local archive: $archive_file"
  tar -xzf "$archive_file" -C "$extract_root"
else
  info "Downloading VibeCrafted snapshot: $archive_url"
  curl -fsSL "$archive_url" | tar -xzf - -C "$extract_root"
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

if [[ "$target" == "vibecrafted" ]] && ! is_interactive_session; then
  installer="$current_link/scripts/vetcoders_install.py"
  [[ -f "$installer" ]] || die "Installer not found: $installer"
  info "Non-interactive bootstrap detected:"
  info "  bypassing TUI and running compact installer"
  info "Launching installer:"
  info "  python3 $installer install --source $current_link --with-shell --compact --non-interactive"
  printf '\n'
  exec python3 "$installer" install --source "$current_link" --with-shell --compact --non-interactive
fi

info "Launching local make target:"
info "  make -C $current_link $target"
printf '\n'

exec make -C "$current_link" "$target"
