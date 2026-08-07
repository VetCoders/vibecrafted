---
title: "Install"
description: "Install Vibecrafted with the curl installer, from a local checkout with make, or in Docker, and verify the result with doctor."
section: getting-started
order: 20
---

# Install

Vibecrafted installs local-first: it stages a runtime under your home directory, never uses `sudo`, and is idempotent — re-running the installer never breaks an existing install.

## Requirements

| Requirement                          | Notes                                                                           |
| ------------------------------------ | ------------------------------------------------------------------------------- |
| macOS 13+ (arm64 / x86_64) or Linux  | Debian/Ubuntu/Arch/Fedora tested; WSL2 fully supported                          |
| `bash`, `tar`, `make`, `curl`, `git` | Pre-flight prints the exact install command per platform if missing             |
| `python3` 3.11+                      | Runs the compact installer and GUI                                              |
| `uv`                                 | Auto-bootstrapped by the installer if missing                                   |
| `zsh`                                | Used by the spawn runtime — agents load your real shell environment             |
| Agent CLIs                           | claude · codex · agy · junie · grok — install and authenticate the ones you use |

Native Windows is not supported today; use WSL2. The installer auto-detects your platform and prints copy-pasteable package-manager hints (`apt`, `dnf`, `pacman`, `brew`) for anything missing.

## Path 1 — curl installer (recommended)

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
```

For the browser-guided onboarding surface:

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui
```

The bootstrap is trust-first: it prints the snapshot source, staging location, and next installer step, then asks before proceeding on an attended terminal. Pass `--yes` to pre-approve that prompt in automation.

### Signature verification

The bootstrap verifies the downloaded archive before extracting it:

1. Fetches the signing public key (`vibecrafted-signing.pub`) and `SHA256SUMS` from the release base URL.
2. Compares the archive's SHA-256 against `SHA256SUMS` — a mismatch aborts the install.
3. Verifies the detached signature (`<archive>.sig`, plus `install.sh.sig` for the entry script) with `openssl dgst -sha256 -verify`.

A failed signature check is fatal. If the key or checksum file cannot be fetched, the installer warns and continues — so run it on a network you trust.

## Path 2 — local checkout with make

```bash
git clone https://github.com/vetcoders/vibecrafted.git
cd vibecrafted
make install              # interactive terminal wizard
```

Variants:

| Command                            | Behavior                                                                      |
| ---------------------------------- | ----------------------------------------------------------------------------- |
| `make install`                     | Terminal-native wizard with checkpoints and stated reasons                    |
| `make install-auto`                | Non-interactive, CI-friendly                                                  |
| `make install RUNTIME=<horse>`     | Also stage a runtime horse (`wezterm`, `vc-apprt`, `locterm`, `microsandbox`) |
| `make install SOURCE=<path>`       | Install from a different source tree (default: current checkout)              |
| `make setup-dev`                   | Same meta-installer with advanced options                                     |
| `make wizard` / `make gui-install` | Browser-guided installer from the checkout                                    |

The install is driven by the `install.toml` manifest: it validates foundations, installs shared skills and launchers, stages the Python CLI through `uv tool install`, and installs vendored binaries.

## Path 3 — Docker

```bash
docker build -t vetcoders/vibecrafted:local .
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:local help
```

Build args `INSTALL_AGENT_CLIS=true` and `INSTALL_FOUNDATIONS=true` produce a full image with agent CLIs and foundation binaries baked in. See the Docker workflow in the source repository's `docs/DOCKER.md`.

## Verify

```bash
vibecrafted doctor        # health check — should report ok / 0 failures
vibecrafted version       # must match the installed VERSION stamp
cat ~/.local/share/vibecrafted/tools/vibecrafted-current/VERSION
```

If `vibecrafted` is not found, open a new terminal, or source the cross-shell helper:

```bash
source "${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders/vc-skills.sh"
```

## The install is not your checkout

The daily `vibecrafted` CLI runs from an installed runtime generation under `~/.local/share/vibecrafted`, not from a floating git checkout. After you pull runtime changes into a local tree, re-run `make install` so the staged runtime and its `VERSION` stamp (`X.Y.Z+g<shortsha>`) match the intended HEAD. See [Update and rollback](/docs/update/) for how generations work.

## Next

- [Quick start](/docs/quick-start/) — first five minutes.
- [Doctor](/docs/doctor/) — reading the health gate.
- [Configuration](/docs/configuration/) — where everything lives on disk.
