# Cut 3.7.1 with a DMG attached

Operator sequence. This file does not change the security boundary:
`.github/workflows/release.yml` stays `contents: read` and does not run
`gh release create`. Apple signing, notarization, and publication stay on
this macOS machine.

Positioning and product identity stay in
[RELEASE_KICKOFF.md](RELEASE_KICKOFF.md). This page is the ordered
commands.

Live install truth for strangers is [INSTALL.md](INSTALL.md): bootstrap
today; DMG when a release actually carries one. The build path exists and
is contract-gated, but it has not been exercised since the hermetic
runtime layout changed — treat the first 3.7.1 DMG as unproven until the
walk-around below passes.

## 0. What this cut must produce

One GitHub Release `v3.7.1` whose assets are exactly:

| Asset                                     | Proves                                     |
| ----------------------------------------- | ------------------------------------------ |
| `Vibecrafted_3.7.1-<YYYYMMDD>-<sha8>.dmg` | signed, notarized desktop product          |
| that name plus `.dmg.sha256`              | checksum a stranger can `shasum -a 256 -c` |
| `release-output.json`                     | bound source revisions + DMG path          |
| `release-output.json.sig`                 | detached signature over that receipt       |

`publish-release` refuses extra assets. Do not also upload the old
source-tarball set onto this tag.

`VERSION` is already `3.7.1`. There is a local tag `v3.7.0` and no
`v3.7.1`. Latest **published** GitHub Release is still `v3.5.0`.

## 1. Signing material that must already exist

`make release` reads `$KEYS` (default `$HOME/.keys`):

| Path                                                 | Required for                       | What a missing file does                                          |
| ---------------------------------------------------- | ---------------------------------- | ----------------------------------------------------------------- |
| `$KEYS/signing-identity.txt`                         | codesign                           | `make release` dies before the app is signed                      |
| `$KEYS/Certificates.p12` + `$KEYS/cert_password.txt` | import into a temporary keychain   | skipped only if the Developer ID is already in the login keychain |
| `$KEYS/vibecrafted-signing.key`                      | detached `release-output.json.sig` | receipt signature cannot be produced                              |
| `$KEYS/.notary.env` **or** `NOTARY_PROFILE`          | `notarytool submit`                | notarization dies; `make dmg` still works for local testing       |

`.notary.env` must export `NOTARY_APPLE_ID`, `NOTARY_TEAM_ID`,
`NOTARY_PASSWORD`. Prefer a keychain profile (`NOTARY_PROFILE`) so the
password never sits in a file.

Also required on this Mac:

- Xcode CLI tools (`codesign`, `notarytool`, `stapler`, `xcrun`, `xcodebuild`, `xcodegen`)
- `cargo`, `uv`, `git`, `gh`, `hdiutil`, `otool`, `spctl`
- Sibling donor checkouts, clean:
  - `../vc-terminal` (override: `VIBECRAFTED_TERMINAL_REPO`)
  - `../vc-frame` (override: `VIBECRAFTED_FRAME_REPO`)
- This repo clean (`git status --porcelain` empty)

`make app` / `make dmg` can run without notarization for a local look.
`make release` and `make publish-release` cannot.

## 2. Confirm the tree you are about to tag

```bash
# this repo
test "$(tr -d '[:space:]' < VERSION)" = "3.7.1"
git status --porcelain          # must be empty
git rev-parse --abbrev-ref HEAD

# donors
git -C ../vc-terminal status --porcelain
git -C ../vc-frame status --porcelain

# signing material is present (names only — do not cat secrets)
ls -1 "$HOME/.keys/signing-identity.txt" \
      "$HOME/.keys/vibecrafted-signing.key"
test -f "$HOME/.keys/.notary.env" || test -n "${NOTARY_PROFILE:-}"

# local gates that the tag workflow will also run
make check
make unified-product-contract-gate
make test-core
make semgrep
```

What this proves: the version file, the donors, and the source gates agree
before you spend an hour in notarization.

## 3. Build, sign, notarize

```bash
make release
```

This is `scripts/build-vibecrafted-release.sh` with `KEYS=$HOME/.keys`.
It remaps `RUSTFLAGS` so panic/debug metadata never contain `$HOME` or
the checkout path, and sets `MACOSX_DEPLOYMENT_TARGET=14.0`.

Expected outputs under `dist/`:

```text
Vibecrafted.app
Vibecrafted_3.7.1-<YYYYMMDD>-<sha8>.dmg
Vibecrafted_3.7.1-<YYYYMMDD>-<sha8>.dmg.sha256
release-output.json
release-output.json.sig
```

## 4. Local verification (before any tag)

```bash
cd dist
shasum -a 256 -c Vibecrafted_3.7.1-*.dmg.sha256
xcrun stapler validate Vibecrafted_3.7.1-*.dmg
spctl --assess --type open --context context:primary-signature --verbose=2 \
  Vibecrafted_3.7.1-*.dmg

uv run --project vibecrafted-core verify-vibecrafted-walkaround verify-release \
  --release-output dist/release-output.json \
  --signature dist/release-output.json.sig

uv run --project vibecrafted-core verify-vibecrafted-walkaround walkaround \
  --release-output dist/release-output.json \
  --signature dist/release-output.json.sig \
  --output /tmp/vibecrafted-3.7.1-walkaround.json
```

| Command                      | What a pass proves                                       |
| ---------------------------- | -------------------------------------------------------- |
| `shasum -a 256 -c`           | the checksum file matches the bytes on disk              |
| `stapler validate`           | Apple stapled a notarization ticket to the DMG           |
| `spctl --assess --type open` | Gatekeeper will open that DMG                            |
| `verify-release`             | the signed receipt names this tree and this DMG          |
| `walkaround`                 | the mounted DMG is the product, not a sibling look-alike |

## 5. Operator buttons — tag and source gate

`publish-release` will not invent a tag and will not push one.

```bash
# annotated tag at this exact HEAD (not a lightweight tag)
git tag -a v3.7.1 -m "Vibecrafted 3.7.1"

# OPERATOR BUTTON — this worker does not push
git push origin v3.7.1
```

Wait for `.github/workflows/release.yml` (`Release source gate`) to go
green on that tag. `publish-release` looks up that run and dies if it is
missing.

```bash
gh run list --workflow release.yml --commit "$(git rev-parse HEAD)"
```

What this proves: VERSION matches the tag, the tag is annotated, Semgrep
and the product-contract / core / installer gates passed on the immutable
tag SHA. It does **not** build or upload a DMG. That is intentional.
Do not add `contents: write` or `gh release create` to `release.yml`.

Also required: zero open CodeQL alerts on `main`.

```bash
gh api "/repos/vetcoders/vibecrafted/code-scanning/alerts?state=open&ref=refs/heads/main&per_page=1"
```

## 6. Publish

```bash
GH_TOKEN=... make publish-release
```

`scripts/publish-vibecrafted-release.sh` then:

1. refuses a dirty tree, a missing/unpushed/non-annotated tag, or a tag
   that is not HEAD
2. verifies the local signed receipt
3. creates a **draft** release if needed
4. uploads the four assets
5. downloads them back into a temp dir and `cmp`s every byte
6. re-runs `verify-release`, `walkaround`, `stapler`, and `spctl` on the
   downloaded DMG
7. writes the four-section release report under
   `~/.vibecrafted/artifacts/vetcoders/vibecrafted/<YYYY_MMDD>/reports/`
8. undrafts the release and marks it latest

What a pass proves: the bytes a stranger downloads are the bytes you
notarized, and the mounted app matches the signed receipt.

## 7. Public confirmation

```bash
gh release view v3.7.1 --json tagName,isDraft,isLatest,assets \
  --jq '{tag:.tagName,draft:.isDraft,latest:.isLatest,assets:[.assets[].name]}'
```

Expected: `draft=false`, `latest=true`, four names, one of them matching
`Vibecrafted_3.7.1-*.dmg`.

Then update the staged Homebrew cask coordinates in
`packaging/homebrew/Casks/vibecrafted-app.rb` (in the tap repo, after the
tap exists). See [packaging/homebrew/README.md](../packaging/homebrew/README.md).

## 8. Stop conditions

- Dirty vibecrafted / vc-terminal / vc-frame tree
- Missing `$HOME/.keys` material
- `release.yml` red or still running
- Open CodeQL alert on `main`
- `spctl` or `stapler` fail on either the local or the downloaded DMG
- Temptation to "just `gh release upload`" a source tarball onto `v3.7.1`
  — `publish-release` will reject unexpected assets

If you only need a local unsigned look, stop after `make dmg` and do not
tag.
