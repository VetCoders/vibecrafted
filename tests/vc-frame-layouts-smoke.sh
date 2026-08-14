#!/usr/bin/env bash
# vc-frame-layouts-smoke.sh — Plan 12 (META_22) verification gate.
#
# Asserts that the Wave 4 agent-native runtime cut is internally consistent:
#
#   1. Every shipped layout in config/vc-frame/layouts/*.kdl parses via
#      `vc-frame --layout <name> setup --check`.
#   2. All four mesh themes in themes/vetcoders-mesh.kdl load alongside
#      config.kdl without parse errors.
#   3. auto-theme.sh passes `bash -n` and shellcheck (if shellcheck is
#      installed).
#   4. auto-theme.sh maps each canonical host name to the expected theme
#      (dragon → vetcoders-dragon, sztudio → vetcoders-sztudio, etc.)
#      including the mgbook16 → vetcoders-div0 alias from kronika 2026-05-05
#      and the neutral fallback for unknown hosts.
#
# Designed to run inside `make test-vc-frame`. Tolerant of missing vc-frame
# (e.g. CI image without the binary) — it warns and skips KDL syntax checks
# rather than failing.
#
# Vibecrafted with AI Agents (c)2024-2026 LibraxisAI

set -euo pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT=$(cd "$HERE/.." && pwd)
CFG_DIR="$REPO_ROOT/vibecrafted-core/vibecrafted_core/config/vc-frame"
LAYOUT_DIR="$CFG_DIR/layouts"
THEMES_FILE="$CFG_DIR/themes/vetcoders-mesh.kdl"

PASS=0
FAIL=0

red()   { printf '\033[31m%s\033[0m' "$*"; }
green() { printf '\033[32m%s\033[0m' "$*"; }
amber() { printf '\033[33m%s\033[0m' "$*"; }

vc_frame_bin() {
    command -v vc-frame 2>/dev/null || return 1
}

ok() {
    printf '  %s %s\n' "$(green ok)" "$1"
    PASS=$((PASS + 1))
}

fail() {
    printf '  %s %s\n' "$(red FAIL)" "$1"
    if [[ -n "${2:-}" ]]; then
        printf '       %s\n' "$2"
    fi
    FAIL=$((FAIL + 1))
}

skip() {
    printf '  %s %s\n' "$(amber skip)" "$1"
}

# ───── 1. shipped artifacts exist ───────────────────────────────────────────
printf '\n[1] shipped artifacts\n'

for f in \
    "$CFG_DIR/auto-theme.sh" \
    "$THEMES_FILE" \
    "$CFG_DIR/config.kdl"
do
    if [[ -f "$f" ]]; then
        ok "$f present"
    else
        fail "$f missing"
    fi
done

if [[ -x "$CFG_DIR/auto-theme.sh" ]]; then
    ok "auto-theme.sh executable"
else
    fail "auto-theme.sh not executable" "chmod +x $CFG_DIR/auto-theme.sh"
fi

# ───── 2. bash -n + shellcheck ──────────────────────────────────────────────
printf '\n[2] script lint\n'

if bash -n "$CFG_DIR/auto-theme.sh" 2>/dev/null; then
    ok "bash -n auto-theme.sh"
else
    fail "bash -n auto-theme.sh"
fi

if command -v shellcheck >/dev/null 2>&1; then
    if shellcheck "$CFG_DIR/auto-theme.sh" >/dev/null 2>&1; then
        ok "shellcheck auto-theme.sh"
    else
        fail "shellcheck auto-theme.sh"
    fi
else
    skip "shellcheck not installed — install with 'brew install shellcheck'"
fi

# ───── 3. KDL layout parse ──────────────────────────────────────────────────
printf '\n[3] vc-frame layout parse\n'

if ! vc_frame_bin="$(vc_frame_bin)"; then
    skip "vc-frame not installed — KDL syntax check deferred to CI"
else
    layouts=()
    while IFS= read -r l; do
        layouts+=("$l")
    done < <(find "$LAYOUT_DIR" -maxdepth 1 -name "*.kdl" | sort)

    if [[ "${#layouts[@]}" -eq 0 ]]; then
        fail "no layouts found under $LAYOUT_DIR"
    fi

    for l in "${layouts[@]}"; do
        name=$(basename "$l" .kdl)
        out=$(VC_FRAME_CONFIG_DIR="$CFG_DIR" "$vc_frame_bin" --layout "$name" setup --check 2>&1 || true)
        if echo "$out" | grep -qiE "Failed to parse|error parsing|invalid layout"; then
            fail "layout $name failed to parse" "$(echo "$out" | head -3)"
        else
            ok "layout $name parses"
        fi
    done
fi

# ───── 4. mesh themes parse ─────────────────────────────────────────────────
printf '\n[4] mesh themes parse\n'

if ! vc_frame_bin="$(vc_frame_bin)"; then
    skip "vc-frame missing — mesh theme parse skipped"
else
    tmpcfg=$(mktemp -d)
    trap 'rm -rf "$tmpcfg"' EXIT
    cp "$CFG_DIR/config.kdl" "$tmpcfg/config.kdl"
    cp -R "$CFG_DIR/themes" "$tmpcfg/themes"
    cp -R "$LAYOUT_DIR" "$tmpcfg/layouts"

    for theme_name in vetcoders-dragon vetcoders-sztudio vetcoders-silver vetcoders-div0; do
        sed -i.bak "s/^theme \".*\"$/theme \"$theme_name\"/" "$tmpcfg/config.kdl"
        out=$(VC_FRAME_CONFIG_DIR="$tmpcfg" "$vc_frame_bin" setup --check 2>&1 || true)
        if echo "$out" | grep -qiE "Failed to parse|error parsing|invalid theme"; then
            fail "theme $theme_name failed to parse" "$(echo "$out" | head -3)"
        else
            ok "theme $theme_name parses"
        fi
    done
fi

# ───── 5. host-aware theme resolver ─────────────────────────────────────────
printf '\n[5] auto-theme host mapping\n'

declare -a host_cases=(
    "dragon:vetcoders-dragon"
    "DRAGON:vetcoders-dragon"
    "dragon.local:vetcoders-dragon"
    "sztudio:vetcoders-sztudio"
    "silver:vetcoders-silver"
    "div0:vetcoders-div0"
    "mgbook16:vetcoders-div0"
    "MGBOOK16:vetcoders-div0"
    "unknown-laptop:vibecrafted"
    "ci-runner-7:vibecrafted"
)

for case in "${host_cases[@]}"; do
    host="${case%%:*}"
    expected="${case#*:}"
    actual=$(VIBECRAFTED_HOST_NAME="$host" "$CFG_DIR/auto-theme.sh" 2>/dev/null)
    if [[ "$actual" == "$expected" ]]; then
        ok "host $host -> $actual"
    else
        fail "host $host -> $actual (expected $expected)"
    fi
done

# VIBECRAFTED_THEME pin should bypass detection.
forced=$(VIBECRAFTED_THEME="custom-theme" VIBECRAFTED_HOST_NAME="dragon" "$CFG_DIR/auto-theme.sh" 2>/dev/null)
if [[ "$forced" == "custom-theme" ]]; then
    ok "VIBECRAFTED_THEME override honored"
else
    fail "VIBECRAFTED_THEME override broken" "got: $forced"
fi

# ───── summary ──────────────────────────────────────────────────────────────
printf '\nsummary: %d passed, %d failed\n' "$PASS" "$FAIL"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
exit 0
