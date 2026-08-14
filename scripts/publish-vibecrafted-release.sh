#!/usr/bin/env bash
# Publish the one installable Vibecrafted artifact after a cold verification of
# the exact bytes downloaded back from a draft GitHub Release.
set -euo pipefail

REPO="${VIBECRAFTED_RELEASE_REPO:-vetcoders/vibecrafted}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST="$ROOT/dist"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION")"
TAG="v$VERSION"
DMG="$DIST/Vibecrafted.dmg"
RELEASE_OUTPUT="$DIST/release-output.json"
RELEASE_SIGNATURE="$DIST/release-output.json.sig"
REPORT_DATE="$(date +%Y_%m%d)"
REPORT_ROOT="${VIBECRAFTED_ARTIFACT_ROOT:-$HOME/.vibecrafted/artifacts}"
REPORT_DIR="$REPORT_ROOT/vetcoders/vibecrafted/$REPORT_DATE/reports"
REPORT="$REPORT_DIR/release-$TAG.md"

die() {
  printf 'publish-release: %s\n' "$*" >&2
  exit 1
}

for command_name in git gh uv shasum xcrun spctl hdiutil; do
  command -v "$command_name" >/dev/null 2>&1 || die "missing command: $command_name"
done
test "$(uname -s)" = "Darwin" || die "the notarized DMG publisher must run on macOS"
test -n "${GH_TOKEN:-}" || die "GH_TOKEN must name an authenticated release publisher"
test -s "$DMG" || die "missing $DMG; run make release first"
test -s "$RELEASE_OUTPUT" || die "missing $RELEASE_OUTPUT"
test -s "$RELEASE_SIGNATURE" || die "missing $RELEASE_SIGNATURE"

cd "$ROOT"
test -z "$(git status --porcelain)" || die "source tree is dirty"
HEAD_SHA="$(git rev-parse HEAD)"
test "$(git cat-file -t "$TAG" 2>/dev/null || true)" = "tag" || die "$TAG must be an annotated tag"
test "$(git rev-list -n 1 "$TAG")" = "$HEAD_SHA" || die "$TAG does not point at HEAD"
REMOTE_TAG_SHA="$(git ls-remote origin "refs/tags/$TAG^{}" | awk '{print $1}')"
test "$REMOTE_TAG_SHA" = "$HEAD_SHA" || die "$TAG is not published at the exact HEAD"
test "$(uv run python3 -c 'import json; print(json.load(open("dist/release-output.json"))["source_revisions"]["vibecrafted"])')" = "$HEAD_SHA" \
  || die "release-output does not name the exact root revision"

uv run --project vibecrafted-core verify-vibecrafted-walkaround verify-release \
  --release-output "$RELEASE_OUTPUT" \
  --signature "$RELEASE_SIGNATURE"
xcrun stapler validate "$DMG"
spctl --assess --type open --context context:primary-signature --verbose=2 "$DMG"

RUN_ID="$(gh run list --repo "$REPO" --workflow release.yml --commit "$HEAD_SHA" \
  --json databaseId,status,conclusion --jq 'map(select(.status == "completed" and .conclusion == "success"))[0].databaseId // empty')"
test -n "$RUN_ID" || die "no successful Release source gate exists for $HEAD_SHA"

OPEN_ALERTS="$(gh api --paginate "/repos/$REPO/code-scanning/alerts?state=open&ref=refs/heads/main&per_page=100" \
  --slurp --jq 'add | length')"
test "$OPEN_ALERTS" = "0" || die "$OPEN_ALERTS open CodeQL alert(s) remain on main"

if gh release view "$TAG" --repo "$REPO" >/dev/null 2>&1; then
  test "$(gh release view "$TAG" --repo "$REPO" --json isDraft --jq .isDraft)" = "true" \
    || die "refusing to mutate already-published release $TAG"
else
  gh release create "$TAG" --repo "$REPO" --target "$HEAD_SHA" \
    --title "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. $TAG" --notes "Verification in progress." \
    --draft --verify-tag
fi

gh release upload "$TAG" --repo "$REPO" \
  "$DMG#Vibecrafted.dmg" \
  "$RELEASE_OUTPUT#release-output.json" \
  "$RELEASE_SIGNATURE#release-output.json.sig" \
  --clobber

DOWNLOAD_DIR="$(mktemp -d "${TMPDIR:-/tmp}/vibecrafted-published.XXXXXX")"
trap 'rm -rf "$DOWNLOAD_DIR"' EXIT
gh release download "$TAG" --repo "$REPO" --dir "$DOWNLOAD_DIR"

EXPECTED_ASSETS="Vibecrafted.dmg
release-output.json
release-output.json.sig"
ACTUAL_ASSETS="$(find "$DOWNLOAD_DIR" -maxdepth 1 -type f -exec basename {} \; | LC_ALL=C sort)"
test "$ACTUAL_ASSETS" = "$EXPECTED_ASSETS" || die "draft release contains unexpected assets"
cmp "$DMG" "$DOWNLOAD_DIR/Vibecrafted.dmg"
cmp "$RELEASE_OUTPUT" "$DOWNLOAD_DIR/release-output.json"
cmp "$RELEASE_SIGNATURE" "$DOWNLOAD_DIR/release-output.json.sig"

uv run --project vibecrafted-core verify-vibecrafted-walkaround verify-release \
  --release-output "$DOWNLOAD_DIR/release-output.json" \
  --signature "$DOWNLOAD_DIR/release-output.json.sig"
uv run --project vibecrafted-core verify-vibecrafted-walkaround walkaround \
  --release-output "$DOWNLOAD_DIR/release-output.json" \
  --signature "$DOWNLOAD_DIR/release-output.json.sig" \
  --output "$DOWNLOAD_DIR/walkaround.json"
xcrun stapler validate "$DOWNLOAD_DIR/Vibecrafted.dmg"
spctl --assess --type open --context context:primary-signature --verbose=2 \
  "$DOWNLOAD_DIR/Vibecrafted.dmg"

DMG_SHA="$(shasum -a 256 "$DOWNLOAD_DIR/Vibecrafted.dmg" | awk '{print $1}')"
DMG_SIZE="$(stat -f %z "$DOWNLOAD_DIR/Vibecrafted.dmg")"
VC_FRAME_SHA="$(uv run python3 -c 'import json; print(json.load(open("dist/release-output.json"))["source_revisions"]["vc-frame"])')"
VC_TERMINAL_SHA="$(uv run python3 -c 'import json; print(json.load(open("dist/release-output.json"))["source_revisions"]["vc-terminal"])')"
DOWNLOAD_URL="https://github.com/$REPO/releases/download/$TAG/Vibecrafted.dmg"

mkdir -p "$REPORT_DIR"
umask 022
cat > "$REPORT" <<EOF
# Vibecrafted $TAG release report

## 1. Security gate

- Semgrep: PASS via the tag source gate and local release gate.
- CodeQL: PASS; zero open alerts on \`main\` immediately before publication.
- Signed release-output verification: PASS.
- Apple notarization ticket, Gatekeeper assessment and staple validation: PASS on local and downloaded bytes.

## 2. Exposed surface inventory

| Surface | Bind / endpoint | Proxy / TLS | Auth boundary | Secret materialization |
| --- | --- | --- | --- | --- |
| Vibecrafted.app desktop UI | local process | none | logged-in macOS user | app-owned runtime environment |
| vc-server service | typed Vibecrafted settings; default loopback, operator may choose any host:port such as \`100.82.232.70:3025\` | operator-owned for non-loopback exposure | configured service policy | runtime service environment, never host config rewrites |
| vc-frame web client | disabled unless explicitly configured | operator-owned | vc-frame auth boundary | runtime-only |

## 3. Deployment mode decision

The shipped topology is one signed and notarized macOS desktop product. \`Vibecrafted.app\` owns app/DMG/install/update and carries the complete runtime. \`vc-terminal\` is a deterministic embedded terminal substrate and \`vc-frame\` is the embedded session interior. The app sources its own XDG/runtime environment at startup and does not overwrite user terminal or vc-frame configuration. Rollback is replacement with the prior notarized Vibecrafted.app; live tmux/vc-frame session processes remain separate runtime state.

Source tuple:

- vibecrafted: \`$HEAD_SHA\`
- vc-frame: \`$VC_FRAME_SHA\`
- vc-terminal: \`$VC_TERMINAL_SHA\`

## 4. Post-release install smoke

- Source: [$DOWNLOAD_URL]($DOWNLOAD_URL)
- SHA-256: \`$DMG_SHA\`
- Size: \`$DMG_SIZE\` bytes
- Draft assets downloaded into a fresh temporary directory and byte-compared: PASS.
- Signed release-output verified against the downloaded DMG: PASS.
- Mounted-DMG walk-around probes from downloaded bytes: PASS.
- Stapler and Gatekeeper validation on downloaded bytes: PASS.

## Sign-off

PASS — the release has one installable artifact, \`Vibecrafted.dmg\`, and no donor repo owns a competing app, installer or update channel.
EOF

gh release edit "$TAG" --repo "$REPO" --notes-file "$REPORT" --draft=false --latest
test "$(gh release view "$TAG" --repo "$REPO" --json isDraft --jq .isDraft)" = "false"

printf 'Published %s\nReport: %s\nDMG: %s\nSHA-256: %s\n' \
  "$DOWNLOAD_URL" "$REPORT" "$DMG_SIZE" "$DMG_SHA"
