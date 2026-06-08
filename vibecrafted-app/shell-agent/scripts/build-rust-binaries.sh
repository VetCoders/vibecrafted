#!/usr/bin/env bash
# Helper script to build rust binaries.
# Called by the Xcode Run Script build phase or independently.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-14.0}"

echo "Building Rust binaries (Helper)..."
cd "$REPO_ROOT"
cargo build -p rmcp-mux --release --bin rmcp-mux
cargo build -p tray-agent --release --bin vc-mux-tray
cargo build -p vc-tui --release --bin vc-tui
cargo build -p vibecrafted-shell-ffi --release
./shell-agent/scripts/fix-dylib-install-names.sh

if [ -n "${TARGET_BUILD_DIR:-}" ] && [ -n "${CONTENTS_FOLDER_PATH:-}" ]; then
    APP_MACOS_DIR="${TARGET_BUILD_DIR}/${CONTENTS_FOLDER_PATH}/MacOS"
    if [ -d "$APP_MACOS_DIR" ]; then
        echo "Embedding Rust binaries into ${APP_MACOS_DIR}"
        cp "$REPO_ROOT/target/release/rmcp-mux" "$APP_MACOS_DIR/vc-mux-daemon"
        cp "$REPO_ROOT/target/release/vc-mux-tray" "$APP_MACOS_DIR/vc-mux-tray"
        cp "$REPO_ROOT/target/release/vc-tui" "$APP_MACOS_DIR/vc-tui"
        chmod +x "$APP_MACOS_DIR/vc-mux-daemon" "$APP_MACOS_DIR/vc-mux-tray" "$APP_MACOS_DIR/vc-tui"
        ./shell-agent/scripts/fix-dylib-install-names.sh "${TARGET_BUILD_DIR}/${CONTENTS_FOLDER_PATH}"
    else
        echo "ERROR: expected app MacOS directory not found: ${APP_MACOS_DIR}" >&2
        exit 1
    fi
fi
