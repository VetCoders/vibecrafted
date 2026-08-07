#!/usr/bin/env bash
# post-install-launch.sh — backyard product spine end of install (SF-3 / SF-4)
#
# After foundations + tools are on disk: offer to open the operator session
# with the Start here layout (operator.kdl / default_layout vibecrafted).
#
# Does NOT claim full agent-process restore — see docs/installer/RESTORE_CONTRACT.md.
set -euo pipefail

info() { printf '\033[36m▸\033[0m %s\n' "$*"; }
ok()   { printf '\033[32m✓\033[0m %s\n' "$*"; }
warn() { printf '\033[33m!\033[0m %s\n' "$*"; }

NONINTERACTIVE="${VIBECRAFTED_INSTALL_NONINTERACTIVE:-0}"
YES="${VIBECRAFTED_LAUNCH_YES:-0}"
NO_LAUNCH="${VIBECRAFTED_NO_LAUNCH:-0}"
FORCE_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes|-y) FORCE_YES=1 ;;
    --no-launch) NO_LAUNCH=1 ;;
  esac
done

if [[ "$NO_LAUNCH" == "1" ]]; then
  info "Launch skipped (--no-launch / VIBECRAFTED_NO_LAUNCH=1)."
  info "When ready: vc-start    # operator session · Start here tab"
  exit 0
fi

if ! command -v vc-frame >/dev/null 2>&1; then
  warn "vc-frame not on PATH — cannot launch cockpit."
  warn "Fix foundations, then: vc-start"
  exit 0
fi

# Best-effort: project frontier config so Super binds + operator scripts exist.
# Prefer the deck command; fall back to in-tree Python when the published
# generation is older than this script.
if command -v vibecrafted >/dev/null 2>&1 \
  && vibecrafted help 2>/dev/null | grep -q 'config'; then
  info "Projecting operator config (frontier + view)…"
  vibecrafted config install 2>/dev/null || warn "config install skipped (non-fatal)"
elif [[ -f "${VIBECRAFTED_SOURCE:-}/vibecrafted-core/vibecrafted_core/vc_frame_delivery.py" ]] \
  || [[ -f "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/vibecrafted-core/vibecrafted_core/vc_frame_delivery.py" ]]; then
  info "Projecting operator config via checkout Python…"
  root="${VIBECRAFTED_SOURCE:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
  (
    cd "$root"
    PYTHONPATH="$root/vibecrafted-core${PYTHONPATH:+:$PYTHONPATH}" \
      python3 -c "from vibecrafted_core.vc_frame_delivery import stage_vc_frame_config; print(stage_vc_frame_config().render())"
  ) 2>/dev/null || warn "config projection skipped (non-fatal)"
fi

answer="y"
if [[ "$FORCE_YES" == "1" || "$YES" == "1" ]]; then
  answer="y"
elif [[ "$NONINTERACTIVE" == "1" ]] || [[ ! -t 0 ]]; then
  info "Non-interactive install: not auto-launching the cockpit."
  info "Start when ready:"
  info "  vc-start"
  info "  # or: vibecrafted start"
  exit 0
else
  printf '\n'
  printf 'Install complete.\n'
  printf '  Frame:     %s\n' "$(command -v vc-frame)"
  printf '  Cockpit:   operator session with tab "Start here" (map of the workspace)\n'
  printf '  Restore:   layout/session resurrection is frame-level — not a full agent\n'
  printf '             process freeze. See docs/installer/RESTORE_CONTRACT.md\n'
  printf '\n'
  printf 'Launch Vibecrafted now? [Y/n] '
  read -r answer || answer="y"
  answer="$(printf '%s' "${answer:-y}" | tr '[:upper:]' '[:lower:]')"
fi

case "$answer" in
  n|no)
    info "OK. Later:"
    info "  vc-start              # open / attach operator session"
    info "  vibecrafted doctor    # health"
    info "  vibecrafted help      # command deck"
    exit 0
    ;;
esac

# Prefer public launcher wrappers installed by the framework.
if command -v vc-start >/dev/null 2>&1; then
  ok "Opening operator session via vc-start…"
  # Do not exec — installer should still exit cleanly after spawn attempt.
  vc-start operator || vc-start || true
  exit 0
fi

if command -v vibecrafted >/dev/null 2>&1; then
  ok "Opening operator session via vibecrafted start…"
  vibecrafted start operator 2>/dev/null || vibecrafted start || true
  exit 0
fi

# Last resort: direct frame with default_layout from config (vibecrafted).
ok "Opening vc-frame session 'vibecrafted'…"
vc-frame attach --create vibecrafted 2>/dev/null \
  || vc-frame --session vibecrafted 2>/dev/null \
  || warn "Could not spawn frame; run: vc-frame attach --create vibecrafted"
exit 0
