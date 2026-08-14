#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:?usage: build-vibecrafted-icon.sh MASTER.png OUTPUT.icns [REFERENCE.png]}"
OUTPUT="${2:?usage: build-vibecrafted-icon.sh MASTER.png OUTPUT.icns [REFERENCE.png]}"
REFERENCE="${3:-}"

[[ -f "$SOURCE" ]] || {
  printf 'FATAL: canonical Vibecrafted icon source is missing: %s\n' "$SOURCE" >&2
  exit 1
}
command -v sips >/dev/null 2>&1 || {
  printf 'FATAL: sips is required to build the Vibecrafted icon\n' >&2
  exit 1
}
command -v iconutil >/dev/null 2>&1 || {
  printf 'FATAL: iconutil is required to build the Vibecrafted icon\n' >&2
  exit 1
}

WORK="$(mktemp -d "${TMPDIR:-/tmp}/vibecrafted-icon.XXXXXX")"
trap 'rm -rf "$WORK"' EXIT
ICONSET="$WORK/Vibecrafted.iconset"
mkdir -p "$ICONSET" "$(dirname "$OUTPUT")"

render() {
  local pixels="$1" name="$2"
  sips -z "$pixels" "$pixels" "$SOURCE" --out "$ICONSET/$name" >/dev/null
}

render 16 icon_16x16.png
render 32 icon_16x16@2x.png
render 32 icon_32x32.png
render 64 icon_32x32@2x.png
render 128 icon_128x128.png
render 256 icon_128x128@2x.png
render 256 icon_256x256.png
render 512 icon_256x256@2x.png
render 512 icon_512x512.png
render 1024 icon_512x512@2x.png

if [[ -n "$REFERENCE" ]]; then
  [[ -f "$REFERENCE" ]] || {
    printf 'FATAL: canonical icon reference is missing: %s\n' "$REFERENCE" >&2
    exit 1
  }
  cmp -s "$ICONSET/icon_128x128.png" "$REFERENCE" || {
    printf 'FATAL: icon master does not reproduce canonical reference: %s\n' "$REFERENCE" >&2
    exit 1
  }
fi

iconutil -c icns "$ICONSET" -o "$OUTPUT"
[[ -s "$OUTPUT" ]] || {
  printf 'FATAL: iconutil did not produce %s\n' "$OUTPUT" >&2
  exit 1
}
