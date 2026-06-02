#!/usr/bin/env bash
# T6 implementation: multi-binary embed
# Builds all agents and packages them into the macOS app DMG.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VERSION=$(cat "$REPO_ROOT/../VERSION" 2>/dev/null || echo "0.1.0")
SIGNING_IDENTITY="${SIGNING_IDENTITY:--}"
BUILD_DIR="${REPO_ROOT}/shell-agent/build"
export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-14.0}"

require_signing_identity() {
  local identity="$1"
  if ! security find-identity -v -p codesigning | grep -Fq "$identity"; then
    echo "BLOCKER: signing identity not found in keychain: ${identity}" >&2
    echo "Action: install the Developer ID Application certificate or run 'make dmg' for an unsigned local DMG." >&2
    exit 2
  fi
}

echo "Building multi-binary bundle for Vibecrafted v${VERSION}"

if [ "${SIGNING_IDENTITY}" != "-" ]; then
  require_signing_identity "${SIGNING_IDENTITY}"
fi

# Step 1: Rust release builds
echo "Building Rust binaries..."
cd "$REPO_ROOT"
cargo build -p rust-mux --release --bin rust-mux
cargo build -p tray-agent --release --bin vc-mux-tray
cargo build -p vibecrafted-operator --release --bin vc-operator
cargo build -p vibecrafted-shell-ffi --release
./shell-agent/scripts/fix-dylib-install-names.sh

# Step 2: UniFFI bindings generate
echo "Generating Swift bindings..."
cargo run -p vibecrafted-uniffi-bindgen -- generate \
  --library target/release/libvibecrafted_shell_ffi.dylib \
  --language swift \
  --out-dir shell-agent/app/Vibecrafted/Bridge/
./shell-agent/scripts/normalize-bindings.sh shell-agent/app/Vibecrafted/Bridge

# Step 3: Xcodegen + xcodebuild Release
echo "Running xcodebuild Release..."
cd shell-agent/app
xcodegen generate
rm -rf build/DerivedData
xcodebuild -project Vibecrafted.xcodeproj \
           -scheme Vibecrafted \
           -configuration Release \
           -derivedDataPath build/DerivedData \
           CODE_SIGN_IDENTITY="${SIGNING_IDENTITY}" \
           CODE_SIGN_STYLE=Manual \
           PRODUCT_BUNDLE_IDENTIFIER=io.vetcoders.vibecrafted \
           build

# Step 4: Multi-binary embed
APP_PATH=$(find build/DerivedData -name Vibecrafted.app -type d | head -1)
if [ -z "$APP_PATH" ]; then
    echo "ERROR: Vibecrafted.app not found after xcodebuild"
    exit 1
fi
echo "Found App at $APP_PATH. Embedding Rust binaries..."
cp "$REPO_ROOT/target/release/rust-mux" "$APP_PATH/Contents/MacOS/vc-mux-daemon"
cp "$REPO_ROOT/target/release/vc-mux-tray" "$APP_PATH/Contents/MacOS/vc-mux-tray"
cp "$REPO_ROOT/target/release/vc-operator" "$APP_PATH/Contents/MacOS/vc-operator-tui"
chmod +x "$APP_PATH/Contents/MacOS/"*
./../scripts/fix-dylib-install-names.sh "$APP_PATH"

# Step 5: Codesign deep + verify
echo "Signing bundled application with identity: ${SIGNING_IDENTITY}"
if [ "${SIGNING_IDENTITY}" = "-" ]; then
  codesign --force --deep --sign - "${APP_PATH}"
else
  codesign --force --deep --options runtime --sign "${SIGNING_IDENTITY}" "${APP_PATH}"
  codesign --verify --deep --strict "${APP_PATH}"
fi

# Step 6: DMG via hdiutil UDZO + optional DMG signing
echo "Creating DMG..."
DMG_NAME="Vibecrafted-${VERSION}-arm64"
DMG_STAGING="${BUILD_DIR}/dmg-staging"
mkdir -p "$DMG_STAGING"
rm -rf "$DMG_STAGING/Vibecrafted.app"
cp -R "$APP_PATH" "$DMG_STAGING/Vibecrafted.app"
ln -sf /Applications "$DMG_STAGING/Applications"

rm -f "${BUILD_DIR}/${DMG_NAME}.dmg"
hdiutil create -volname "Vibecrafted" -srcfolder "$DMG_STAGING" -ov \
               -format UDZO "${BUILD_DIR}/${DMG_NAME}.dmg"

if [ "${SIGNING_IDENTITY}" = "-" ]; then
    echo "Unsigned local DMG created; skipping DMG codesign because SIGNING_IDENTITY=-"
else
    echo "Signing DMG..."
    codesign --force --sign "${SIGNING_IDENTITY}" "${BUILD_DIR}/${DMG_NAME}.dmg"
fi

echo "Success! DMG created at: ${BUILD_DIR}/${DMG_NAME}.dmg"

# Step 7: Notary instructions
if [ "${SIGNING_IDENTITY}" != "-" ]; then
    echo "--------------------------------------------------------"
    echo "To notarize the release, run:"
    echo "  xcrun notarytool submit ${BUILD_DIR}/${DMG_NAME}.dmg --keychain-profile \"vista-build\" --wait"
    echo "  xcrun stapler staple ${BUILD_DIR}/${DMG_NAME}.dmg"
    echo "--------------------------------------------------------"
fi
