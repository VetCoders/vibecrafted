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
| `install.ps1`                | Windows WSL2 handoff only | In repo; not a native installer         |

## Homebrew (staged)

See [homebrew/README.md](homebrew/README.md).

- Formula `vibecrafted` — CLI / command-deck path.
- Cask `vibecrafted-app` — signed DMG once a release actually carries one.

Do **not** create `vetcoders/homebrew-tap` from this worker. Copy the files
into that repo when the operator is ready.

## winget (skipped)

No native Windows build exists. `install.ps1` only probes WSL2 and prints
the Linux bootstrap. winget's installer types (`exe`, `msi`, `msix`,
`burn`, `inno`, `nullsoft`, `portable`, `zip`) all describe a Windows PE
payload. There is no honest installer type for "requires WSL2, then run a
POSIX script."

A winget manifest that pointed at `install.ps1`, a `.zip` of this repo, or
a dummy EXE would list Vibecrafted as a Windows application. That is the
lie this hydration pass refuses to ship.

When a native Windows installer exists, start a new manifest under
`packaging/winget/` against the [winget-pkgs schema](https://github.com/microsoft/winget-pkgs).
Until then, Windows users follow the WSL2 path in `docs/INSTALL.md`.

## Other stores (not staged)

No AppImage, `.deb`, `.rpm`, or Scoop manifest is staged here. Those
channels would claim a packaged Linux/Windows binary this repo does not
publish. The bootstrap and the source tarball remain the Linux surfaces.

## Operator buttons this directory does not press

- Create `github.com/vetcoders/homebrew-tap`
- `brew bump-formula-pr` / `brew bump-cask-pr`
- Submit to `microsoft/winget-pkgs`
- Attach a DMG to a GitHub Release (see [docs/RELEASE_CHECKLIST.md](../docs/RELEASE_CHECKLIST.md))
