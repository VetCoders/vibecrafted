#!/usr/bin/env bash
# Keep the UniFFI dylib relocatable after extracting operator into this repo.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
LIB_NAME="libvibecrafted_shell_ffi.dylib"
RPATH_NAME="@rpath/${LIB_NAME}"

fix_library_id() {
    local lib_path="$1"
    if [ -f "$lib_path" ]; then
        install_name_tool -id "$RPATH_NAME" "$lib_path"
    fi
}

fix_binary_refs() {
    local binary="$1"
    if [ ! -f "$binary" ]; then
        return 0
    fi

    otool -L "$binary" | awk -v lib="$LIB_NAME" '$1 ~ lib { print $1 }' | while read -r dep; do
        if [ "$dep" != "$RPATH_NAME" ]; then
            install_name_tool -change "$dep" "$RPATH_NAME" "$binary"
        fi
    done

    install_name_tool -add_rpath "@executable_path/../Frameworks" "$binary" 2>/dev/null || true
}

fix_library_id "${REPO_ROOT}/target/release/${LIB_NAME}"
fix_library_id "${REPO_ROOT}/target/release/deps/${LIB_NAME}"

APP_PATH="${1:-}"
if [ -n "$APP_PATH" ]; then
    fix_library_id "${APP_PATH}/Contents/Frameworks/${LIB_NAME}"
    fix_binary_refs "${APP_PATH}/Contents/MacOS/Vibecrafted"
    fix_binary_refs "${APP_PATH}/Contents/MacOS/Vibecrafted.debug.dylib"
fi
