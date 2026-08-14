#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TERMINAL_REPO="${VIBECRAFTED_TERMINAL_REPO:-$REPO_ROOT/../vc-terminal}"
FRAME_REPO="${VIBECRAFTED_FRAME_REPO:-$REPO_ROOT/../vc-frame}"
DIST_DIR="${VIBECRAFTED_RELEASE_DIR:-$REPO_ROOT/dist}"
BUILD_DIR="$REPO_ROOT/build/unified-release"
APP="$DIST_DIR/Vibecrafted.app"
DMG="$DIST_DIR/Vibecrafted.dmg"
KEYS="${KEYS:-$HOME/.keys}"
SIGNING_IDENTITY_FILE="$KEYS/signing-identity.txt"
CERT_P12="$KEYS/Certificates.p12"
CERT_PASSWORD_FILE="$KEYS/cert_password.txt"
SIGNING_KEY="$KEYS/vibecrafted-signing.key"
NOTARY_ENV="$KEYS/.notary.env"
VERSION="$(tr -d '[:space:]' < "$REPO_ROOT/VERSION")"
BUILD_NUMBER="${BUILD_NUMBER:-$(date -u +%Y%m%d%H%M%S)}"
MODE="release"
SIGNING_IDENTITY=""
TEMP_KEYCHAIN_PATH=""
ORIGINAL_DEFAULT_KEYCHAIN=""
CODESIGN_KEYCHAIN_ARGS=()
export MACOSX_DEPLOYMENT_TARGET=14.0

case "${1:-}" in
  --app-only) MODE="app" ;;
  --no-notarize) MODE="dmg" ;;
  --notarize-only) MODE="notarize" ;;
  "") ;;
  *) echo "usage: $0 [--app-only|--no-notarize|--notarize-only]" >&2; exit 2 ;;
esac

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'FATAL: %s\n' "$*" >&2; exit 1; }
require() { command -v "$1" >/dev/null 2>&1 || die "$1 is required"; }

cleanup() {
  if [[ -n "$ORIGINAL_DEFAULT_KEYCHAIN" ]]; then
    security default-keychain -d user -s "$ORIGINAL_DEFAULT_KEYCHAIN" >/dev/null 2>&1 || true
  fi
  if [[ -n "$TEMP_KEYCHAIN_PATH" ]]; then
    security delete-keychain "$TEMP_KEYCHAIN_PATH" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

read_trimmed_file() {
  sed -e 's/[[:space:]]*$//' -e '/^$/d' "$1" | head -n1
}

prepare_signing_identity() {
  SIGNING_IDENTITY="$(read_trimmed_file "$SIGNING_IDENTITY_FILE")"
  [[ -n "$SIGNING_IDENTITY" ]] || die "signing identity is empty"
  if [[ -f "$CERT_P12" && -f "$CERT_PASSWORD_FILE" ]]; then
    local cert_password temp_password existing_keychains
    cert_password="$(read_trimmed_file "$CERT_PASSWORD_FILE")"
    [[ -n "$cert_password" ]] || die "certificate password is empty"
    temp_password="$(uuidgen)"
    TEMP_KEYCHAIN_PATH="$DIST_DIR/Vibecrafted-signing.keychain-db"
    rm -f "$TEMP_KEYCHAIN_PATH"
    existing_keychains="$(security list-keychains -d user | tr -d '"' | tr '\n' ' ')"
    ORIGINAL_DEFAULT_KEYCHAIN="$(security default-keychain -d user 2>/dev/null | tr -d ' "' || true)"
    security create-keychain -p "$temp_password" "$TEMP_KEYCHAIN_PATH"
    security set-keychain-settings -lut 21600 "$TEMP_KEYCHAIN_PATH"
    security unlock-keychain -p "$temp_password" "$TEMP_KEYCHAIN_PATH"
    # shellcheck disable=SC2086
    security list-keychains -d user -s "$TEMP_KEYCHAIN_PATH" $existing_keychains >/dev/null
    security default-keychain -d user -s "$TEMP_KEYCHAIN_PATH"
    security import "$CERT_P12" -k "$TEMP_KEYCHAIN_PATH" -P "$cert_password" \
      -T /usr/bin/codesign >/dev/null
    security set-key-partition-list -S apple-tool:,apple:,codesign: -s \
      -k "$temp_password" "$TEMP_KEYCHAIN_PATH" >/dev/null
    security find-identity -v -p codesigning "$TEMP_KEYCHAIN_PATH" \
      | grep -Fq "$SIGNING_IDENTITY" \
      || die "Developer ID identity is absent from temporary keychain"
    CODESIGN_KEYCHAIN_ARGS=(--keychain "$TEMP_KEYCHAIN_PATH")
    return
  fi
  security find-identity -v -p codesigning | grep -Fq "$SIGNING_IDENTITY" \
    || die "Developer ID identity is not available in the keychain"
}

for command in cargo codesign git hdiutil install_name_tool make otool uv xcodebuild xcodegen xcrun; do
  require "$command"
done
[[ -f "$SIGNING_IDENTITY_FILE" ]] || die "missing $SIGNING_IDENTITY_FILE"
prepare_signing_identity

git_sha() { git -C "$1" rev-parse HEAD; }
require_clean_repo() {
  local repo="$1" label="$2"
  [[ -z "$(git -C "$repo" status --porcelain --untracked-files=normal)" ]] \
    || die "$label is dirty; release receipts refuse moving source"
}

notary_submit() {
  local artifact="$1"
  if [[ -n "${NOTARY_PROFILE:-}" ]]; then
    xcrun notarytool submit "$artifact" --keychain-profile "$NOTARY_PROFILE" \
      --wait --timeout 30m
    return
  fi
  [[ -f "$NOTARY_ENV" ]] || die "NOTARY_PROFILE is unset and $NOTARY_ENV is missing"
  # shellcheck disable=SC1090
  source "$NOTARY_ENV"
  : "${NOTARY_APPLE_ID:?NOTARY_APPLE_ID missing}"
  : "${NOTARY_TEAM_ID:?NOTARY_TEAM_ID missing}"
  : "${NOTARY_PASSWORD:?NOTARY_PASSWORD missing}"
  xcrun notarytool submit "$artifact" --apple-id "$NOTARY_APPLE_ID" \
    --team-id "$NOTARY_TEAM_ID" --password "$NOTARY_PASSWORD" \
    --wait --timeout 30m
}

sign_macho_tree() {
  local outer="$APP/Contents/MacOS/Vibecrafted" candidate
  while IFS= read -r -d '' candidate; do
    [[ "$candidate" != "$outer" ]] || continue
    if /usr/bin/file -b "$candidate" | grep -q 'Mach-O'; then
      codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" \
        "${CODESIGN_KEYCHAIN_ARGS[@]}" "$candidate"
    fi
  done < <(find "$APP/Contents" -type f -print0)
}

remove_ambient_swift_rpath() {
  local executable="$APP/Contents/MacOS/Vibecrafted"
  local rpaths
  rpaths="$(otool -l "$executable" | awk '
    $1 == "cmd" && $2 == "LC_RPATH" { in_rpath = 1; next }
    in_rpath && $1 == "path" { print $2; in_rpath = 0 }
  ')"
  if grep -Fxq '/usr/lib/swift' <<<"$rpaths"; then
    install_name_tool -delete_rpath /usr/lib/swift "$executable"
  fi
  rpaths="$(otool -l "$executable" | awk '
    $1 == "cmd" && $2 == "LC_RPATH" { in_rpath = 1; next }
    in_rpath && $1 == "path" { print $2; in_rpath = 0 }
  ')"
  if grep -Eq '^/' <<<"$rpaths"; then
    die "Swift host contains an ambient absolute LC_RPATH"
  fi
}

build_product() {
  require_clean_repo "$REPO_ROOT" vibecrafted
  require_clean_repo "$TERMINAL_REPO" vc-terminal
  require_clean_repo "$FRAME_REPO" vc-frame

  log "Building vc-terminal through its release binary target"
  make -C "$TERMINAL_REPO" \
    DEPLOYMENT_TARGET='MACOSX_DEPLOYMENT_TARGET=14.0' release-bins
  local terminal_source="$TERMINAL_REPO/target/release/alacritty"
  [[ -x "$terminal_source" ]] || die "vc-terminal release binary is missing"

  log "Building vc-frame through its canonical release target"
  make -C "$FRAME_REPO" release
  local frame_source="$FRAME_REPO/target/release/vc-frame"
  [[ -x "$frame_source" ]] || die "vc-frame release binary is missing"

  log "Building the native hermetic vc-start"
  (cd "$REPO_ROOT/vibecrafted-app" && cargo build -p voc --bin vc-start --release)
  local start_source="$REPO_ROOT/vibecrafted-app/target/release/vc-start"
  [[ -x "$start_source" ]] || die "vc-start release binary is missing"

  log "Building the single Swift host app"
  make -C "$REPO_ROOT/vibecrafted-app/shell-agent" bindings xcode
  rm -rf "$BUILD_DIR/DerivedData" "$APP"
  mkdir -p "$BUILD_DIR" "$DIST_DIR"
  xcodebuild \
    -project "$REPO_ROOT/vibecrafted-app/shell-agent/app/Vibecrafted.xcodeproj" \
    -scheme Vibecrafted -configuration Release \
    -derivedDataPath "$BUILD_DIR/DerivedData" \
    CODE_SIGNING_ALLOWED=NO CODE_SIGNING_REQUIRED=NO build
  local built_app
  built_app="$(find "$BUILD_DIR/DerivedData" -type d -name Vibecrafted.app -print -quit)"
  [[ -n "$built_app" ]] || die "xcodebuild did not produce Vibecrafted.app"
  /usr/bin/ditto "$built_app" "$APP"
  remove_ambient_swift_rpath

  log "Embedding product modules and the checkout-free runtime"
  local resources="$APP/Contents/Resources"
  local runtime="$resources/runtime"
  mkdir -p "$APP/Contents/Helpers" "$resources/terminal" "$runtime/bin"
  install -m 0755 "$terminal_source" "$APP/Contents/Helpers/vc-terminal"
  install -m 0755 "$frame_source" "$APP/Contents/Helpers/vc-frame"
  install -m 0755 "$start_source" "$runtime/bin/vc-start"
  install -m 0644 "$REPO_ROOT/config/vc-terminal/vibecrafted.toml" \
    "$resources/terminal/vibecrafted.toml"
  install -m 0644 "$REPO_ROOT/VERSION" "$runtime/VERSION"
  mkdir -p "$runtime/scripts" "$runtime/vibecrafted-core" "$runtime/config"
  install -m 0755 "$REPO_ROOT/scripts/vibecrafted" "$runtime/scripts/vibecrafted"
  install -m 0755 "$REPO_ROOT/scripts/vibecrafted" "$runtime/bin/vibecrafted"
  /bin/cp -RL "$REPO_ROOT/vibecrafted-core/vibecrafted_core" \
    "$runtime/vibecrafted-core/"
  /bin/cp -RL "$REPO_ROOT/vibecrafted-core/vibecrafted_core/runtime" \
    "$runtime/runtime"
  /bin/cp -RL "$REPO_ROOT/config/." "$runtime/config/"

  log "Embedding a private Python runtime; no shell profile or host Python is used"
  local python_seed seed_python python_home
  python_seed="$(mktemp -d "$BUILD_DIR/python-seed.XXXXXX")"
  uv python install 3.12.3 --install-dir "$python_seed" --no-bin
  seed_python="$(find "$python_seed" -type f -path '*/bin/python3.12' -print -quit)"
  [[ -n "$seed_python" ]] || die "uv did not produce the requested CPython"
  python_home="$(cd "$(dirname "$seed_python")/.." && pwd)"
  mkdir -p "$runtime/python" "$runtime/python-site"
  /bin/cp -RL "$python_home/." "$runtime/python/"
  uv pip install --python "$seed_python" --target "$runtime/python-site" \
    'jsonschema>=4.23,<5' 'PyYAML>=6.0,<7'
  find "$runtime" -type f -name '*.pyc' -delete
  find "$runtime" -depth -type d -name __pycache__ -empty -delete
  # These literals are the relocatable wrapper payload and expand only when
  # the installed wrapper runs inside Vibecrafted.app.
  # shellcheck disable=SC2016
  printf '%s\n' \
    '#!/bin/bash' \
    'set -euo pipefail' \
    'runtime_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"' \
    'export PYTHONPATH="$runtime_root/vibecrafted-core:$runtime_root/python-site"' \
    'exec "$runtime_root/python/bin/python3.12" "$@"' \
    > "$runtime/bin/python3"
  chmod 0755 "$runtime/bin/python3"

  if find "$APP" -type l -print -quit | grep -q .; then
    die "assembled app contains symlinks"
  fi

  log "Signing nested code and binding exact source receipts"
  sign_macho_tree
  require_clean_repo "$REPO_ROOT" vibecrafted
  require_clean_repo "$TERMINAL_REPO" vc-terminal
  require_clean_repo "$FRAME_REPO" vc-frame
  PYTHONPATH="$REPO_ROOT/vibecrafted-core" "$REPO_ROOT/scripts/project-python" \
    "$REPO_ROOT/scripts/unified_product_manifest.py" app \
    --app "$APP" --terminal-source "$terminal_source" --frame-source "$frame_source" \
    --version "$VERSION" --build "$BUILD_NUMBER" \
    --vibecrafted-sha "$(git_sha "$REPO_ROOT")" \
    --terminal-sha "$(git_sha "$TERMINAL_REPO")" \
    --frame-sha "$(git_sha "$FRAME_REPO")"
  codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" \
    "${CODESIGN_KEYCHAIN_ARGS[@]}" "$APP"
  codesign --verify --deep --strict --verbose=2 "$APP"
  "$REPO_ROOT/scripts/verify-vibecrafted-product.sh" app "$APP" --require-clean
}

create_dmg() {
  local staging="$BUILD_DIR/dmg-staging"
  rm -rf "$staging" "$DMG"
  mkdir -p "$staging"
  /usr/bin/ditto "$APP" "$staging/Vibecrafted.app"
  ln -s /Applications "$staging/Applications"
  hdiutil create -volname Vibecrafted -srcfolder "$staging" -ov -format UDZO "$DMG"
  codesign --force --timestamp --sign "$SIGNING_IDENTITY" \
    "${CODESIGN_KEYCHAIN_ARGS[@]}" "$DMG"
}

notarize_product() {
  local app_zip="$BUILD_DIR/Vibecrafted.app.zip"
  rm -f "$app_zip"
  /usr/bin/ditto -c -k --keepParent "$APP" "$app_zip"
  notary_submit "$app_zip"
  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
  spctl --assess --type execute --verbose=2 "$APP"
  create_dmg
  notary_submit "$DMG"
  xcrun stapler staple "$DMG"
  xcrun stapler validate "$DMG"
  spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"
}

emit_release_tuple() {
  PYTHONPATH="$REPO_ROOT/vibecrafted-core" "$REPO_ROOT/scripts/project-python" \
    "$REPO_ROOT/scripts/unified_product_manifest.py" release \
    --app "$APP" --dmg "$DMG" --output "$DIST_DIR/release-output.json"
  /usr/bin/openssl dgst -sha256 -sign "$SIGNING_KEY" \
    -out "$DIST_DIR/release-output.json.sig" "$DIST_DIR/release-output.json"
  "$REPO_ROOT/scripts/verify-vibecrafted-product.sh" release-output \
    "$DIST_DIR/release-output.json" "$DIST_DIR/release-output.json.sig"
}

if [[ "$MODE" == "notarize" ]]; then
  [[ -d "$APP" ]] || die "missing $APP; run make dmg-signed first"
  notarize_product
  emit_release_tuple
  exit 0
fi

build_product
[[ "$MODE" == "app" ]] && exit 0
if [[ "$MODE" == "dmg" ]]; then
  create_dmg
  exit 0
fi
notarize_product
emit_release_tuple
log "Release complete: $DMG"
