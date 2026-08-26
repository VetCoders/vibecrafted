# Distribution packaging (staged)

This directory holds package-manager artifacts this repository can own
without creating remotes, taps, or store listings. Nothing here is a
published channel until the operator presses the publish button.

Canonical stranger install truth lives in [docs/INSTALL.md](../docs/INSTALL.md):

| Channel                      | Who it is for             | Status                                  |
| ---------------------------- | ------------------------- | --------------------------------------- |
| Bootstrap `install.sh`       | macOS, Linux, WSL2        | Published; CI-gated                     |
| Signed `Vibecrafted.app` DMG | macOS 14+ arm64           | Build path exists; no published DMG yet |
| Source checkout              | maintainers / power users | Published                               |
| Container                    | isolated operator runtime | Published                               |
| `install.ps1`                | Windows native Runtime Pack | In repo; not a published channel        |

## Homebrew (staged)

See [homebrew/README.md](homebrew/README.md).

- Formula `vibecrafted` — CLI / command-deck path.
- Cask `vibecrafted-app` — signed DMG once a release actually carries one.

Do **not** create `vetcoders/homebrew-tap` from this worker. Copy the files
into that repo when the operator is ready.

## winget (not staged this cut)

Native Windows now installs a receipted Runtime Pack (`install.ps1` →
`scripts/install-runtime-pack.ps1`). That is a product-owned tarball plus
checksum/signature, not a winget installer type. Do not list a winget
manifest until an operator-owned `.exe`/`.msi` carrier exists.

Until then, Windows users follow the native Runtime Pack path in
`docs/INSTALL.md`. WSL2 remains an optional Linux channel, not the native
product.

## Other stores (not staged)

No AppImage, `.deb`, `.rpm`, or Scoop manifest is staged here. Those
channels would claim a packaged Linux/Windows binary this repo does not
publish. The bootstrap and the source tarball remain the Linux surfaces.

## Operator buttons this directory does not press

- Create `github.com/vetcoders/homebrew-tap`
- `brew bump-formula-pr` / `brew bump-cask-pr`
- Submit to `microsoft/winget-pkgs`
- Attach a DMG to a GitHub Release (see [docs/RELEASE_CHECKLIST.md](../docs/RELEASE_CHECKLIST.md))
