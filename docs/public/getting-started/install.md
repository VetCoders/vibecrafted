---
title: "Install"
description: "Install Vibecrafted on macOS, Linux or Windows through WSL2, and verify the result with doctor."
section: getting-started
order: 20
---

# Install

Vibecrafted runs on macOS, Linux, and Windows through WSL2. Pick the channel
that matches your platform, then verify the result with `vibecrafted doctor`.

## Channels

| Channel                      | Platform             | What you get                                           | Status                                   |
| ---------------------------- | -------------------- | ------------------------------------------------------ | ---------------------------------------- |
| Signed `Vibecrafted.app` DMG | macOS 14+, arm64     | Full desktop product: terminal, frame, runtime, server | Build path complete; publication pending |
| Bootstrap `install.sh`       | macOS, Linux, WSL2   | Command deck, runtime, control plane, skills           | Published; CI-gated                      |
| Source checkout              | macOS, Linux, WSL2   | Everything above plus build, test and release targets  | Published                                |
| Container                    | anywhere Docker runs | Isolated operator runtime                              | Published                                |

On macOS and Linux, use the bootstrap today. On Windows, install WSL2 first and
then use the same bootstrap inside it.

## macOS and Linux

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
```

The installer detects your platform and Linux distribution family first, reports
every missing prerequisite in one pass instead of failing one tool at a time,
and stages a versioned runtime generation under
`~/.local/share/vibecrafted/tools/`.

To read the script before running it:

```bash
curl -fsSL https://vibecrafted.io/install.sh -o install.sh
less install.sh
bash install.sh
```

### Linux is a first-class runtime

The Linux install path is gated on every push and pull request. Two jobs run:
Ubuntu on a hosted runner, which exercises real `/etc/os-release` detection and
the apt-family prerequisite hints, and `debian:bookworm-slim` in a container,
which exercises the bare-minimum case with no pre-baked tooling. Both assert
that `vibecrafted doctor` reports green afterwards.

The macOS-only surfaces are the desktop app, notarization, and the `locterm`
runtime. The command deck, control plane, dispatch, skills, and settlement
ledger all run on Linux.

## Windows

Vibecrafted has no native Windows build. The installer is POSIX shell and the
runtime assumes a POSIX process model, so on Windows you install WSL2 once and
use the Linux path inside it.

Install WSL2 from an elevated PowerShell prompt:

```powershell
wsl --install
```

Reboot when prompted, then confirm:

```powershell
wsl --status
```

Install Vibecrafted inside your default distribution:

```powershell
wsl bash -c 'curl -fsSL https://vibecrafted.io/install.sh | bash'
```

`install.sh` detects WSL explicitly by reading `/proc/sys/kernel/osrelease` and
`/proc/version` for a `microsoft` or `wsl` marker, and treats it as Linux for
runtime purposes. WSL changes the reported platform line, not the install
layout.

The repository also ships `install.ps1`, a Windows entry point that checks for
PowerShell 5.1 or newer, probes whether WSL is installed and healthy, and either
prints the exact bootstrap one-liner for your default distribution or prints the
WSL2 install path and exits non-zero. It never silently succeeds. Run it from a
checkout with `.\install.ps1`.

## macOS desktop app

The intended shape of the end-user product is one Developer ID signed and
notarized artifact carrying matching builds of `vc-terminal`, `vc-frame`,
`vc-start` and the complete Vibecrafted runtime. No companion repository
installer is required.

When a release carries a DMG, open the
[latest release](https://github.com/vetcoders/vibecrafted/releases/latest),
download `Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg` and its adjacent
`.dmg.sha256`, verify the bytes, then open it:

```bash
shasum -a 256 -c Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg.sha256
```

Drag `Vibecrafted.app` to Applications and launch it.

Check what a given release actually carries:

```bash
gh release view --json assets -q '.assets[].name'
```

No published release carries a DMG yet, so use the bootstrap channel above. The
build path exists end to end and its shape is gated by contract tests, but it
has not been exercised since the runtime layout changed — treat it as unproven
rather than ready.

### Runtime boundary

Every new or restored workspace has a durable `workspace_id` and enters through
the bundled `vc-start`. The app sources an app-owned XDG/runtime environment and
does not overwrite your terminal, shell, Zellij or vc-frame configuration.
`vc-terminal` and `vc-frame` do not have independent app, DMG, installer or
update channels.

The server endpoint is read from Vibecrafted settings and may be any host:port,
for example `http://127.0.0.1:3024`. It is never baked into the app.

## Container

```bash
docker build -t vetcoders/vibecrafted:local .
docker run --rm -it -v "$PWD:/workspace" vetcoders/vibecrafted:local version
```

## Verify

```bash
vibecrafted doctor
vibecrafted version
```

`doctor` distinguishes what is broken from what is merely absent. On a plain
install, externally managed foundations you have not installed are reported as
warnings rather than failures. Anything reported red is genuinely wrong.

## Next

- [First run](/docs/first-run/) — what happens on your first command, and what
  to do when an agent CLI is missing.
- [Build from source](/docs/build-from-source/) — the checkout path, the target
  surface, and building your own artifact.
- [Quick start](/docs/quick-start/) — your first workflow.
- [Update and rollback](/docs/update/) — runtime generations and pointer
  rollback.
