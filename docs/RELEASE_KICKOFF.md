# Vibecrafted release kickoff

## Public product

- Owner: `vetcoders/vibecrafted`
- Artifact: one installable `Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg`
- App: `Vibecrafted.app`
- Download: `https://github.com/vetcoders/vibecrafted/releases/latest` → `Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg`
- Embedded donors: `vc-terminal`, `vc-frame`
- Entry: bundled `vc-start` with durable `workspace_id`

The donor repositories never publish an app, DMG, MSI, installer or update
channel. The root tag workflow is read-only. Apple signing, notarization and
publication run from the explicit macOS operator boundary:

```bash
make release
GH_TOKEN=... make publish-release
```

`publish-release` refuses a dirty tree, a non-annotated or unpushed tag, a
failed source gate, any open CodeQL alert on `main`, an invalid signature,
unexpected release assets, failed Apple validation or failed mounted-DMG
walk-around. It publishes only after downloading and byte-comparing the draft
assets.

The ordered command sequence to cut 3.7.1 with that DMG attached — including
which `$HOME/.keys` files must be present and what each verification step
proves — is [RELEASE_CHECKLIST.md](RELEASE_CHECKLIST.md).

## Public CTA

Download the canonical `Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg` and its
`.dmg.sha256` from the latest release, verify the checksum, and open the DMG.

## Required proof

The generated release report must contain:

1. Security gate.
2. Exposed surface inventory.
3. Deployment topology and rollback decision.
4. Post-release smoke from the published URL.

The canonical report lives under
`~/.vibecrafted/artifacts/vetcoders/vibecrafted/<YYYY_MMDD>/reports/` and is
also used as the GitHub Release notes.
