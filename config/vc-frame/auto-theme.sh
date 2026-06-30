#!/usr/bin/env bash
# auto-theme.sh — host-aware vc_frame theme name resolver.
#
# Plan 12 (META_22) — Wave 4 agent-native runtime cut.
#
# Maps the current workstation to one of the canonical mesh themes shipped
# in config/vc-frame/themes/vetcoders-mesh.kdl. Falls back to "vibecrafted"
# (the neutral default in config.kdl) when the host is unknown.
#
# Mesh mapping (kronika 2026-05-05 — Vetcoders mesh topology):
#   dragon   -> red    (LibraxisAI server, central hub)
#   sztudio  -> purple (Monika's desktop)
#   silver   -> cyan   (Monika's laptop)
#   div0     -> green  (Maciej's laptop, primary dev)
#   *        -> vibecrafted (neutral fallback)
#
# Host detection order:
#   1. VIBECRAFTED_HOST_NAME (operator override, single source of truth)
#   2. scutil --get LocalHostName        (macOS canonical local name)
#   3. scutil --get ComputerName         (macOS user-friendly name)
#   4. hostname -s                       (Linux short hostname)
#   5. hostname                          (final fallback)
#
# Output: theme name on stdout. Exit 0 always; unknown host is not an error.
#
# Environment:
#   VIBECRAFTED_HOST_NAME  override detected host (for tests/staging)
#   VIBECRAFTED_THEME      pin the theme outright (skips detection)
#
# Vibecrafted with AI Agents (c)2024-2026 LibraxisAI

set -euo pipefail

# Detect the current host name using a layered probe. The first non-empty
# answer wins. Each layer is forgiving — a missing tool is silently skipped.
detect_host() {
    local name=""

    if [[ -n "${VIBECRAFTED_HOST_NAME:-}" ]]; then
        name="$VIBECRAFTED_HOST_NAME"
    elif command -v scutil >/dev/null 2>&1; then
        name=$(scutil --get LocalHostName 2>/dev/null || true)
        if [[ -z "$name" ]]; then
            name=$(scutil --get ComputerName 2>/dev/null || true)
        fi
    fi

    if [[ -z "$name" ]]; then
        name=$(hostname -s 2>/dev/null || hostname 2>/dev/null || true)
    fi

    # Normalize: strip .local / .lan suffixes, then lowercase. Override paths
    # MUST flow through the same normalization so DRAGON, dragon.local, and
    # dragon all resolve identically.
    name="${name%.local}"
    name="${name%.lan}"
    name=$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')

    printf '%s' "$name"
}

resolve_theme() {
    if [[ -n "${VIBECRAFTED_THEME:-}" ]]; then
        printf '%s\n' "$VIBECRAFTED_THEME"
        return 0
    fi

    local host
    host=$(detect_host)

    case "$host" in
        dragon|dragon-*)
            printf 'vetcoders-dragon\n' ;;
        sztudio|sztudio-*)
            printf 'vetcoders-sztudio\n' ;;
        silver|silver-*)
            printf 'vetcoders-silver\n' ;;
        div0|div0-*|mgbook16|mgbook16-*)
            # mgbook16 is the macOS LocalHostName for div0 (kronika 2026-05-05).
            printf 'vetcoders-div0\n' ;;
        *)
            printf 'vibecrafted\n' ;;
    esac
}

resolve_theme
