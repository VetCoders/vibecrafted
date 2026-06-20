# Installing 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍.

> **One-line install (POSIX):**
>
> ```bash
> curl -fsSL https://vibecrafted.io/install.sh | bash
> ```
>
> This page documents what that command does on each supported platform, the
> prerequisites you need in place first, and known platform-specific
> limitations.

The current release line ships a native install path for **macOS**, **Linux**
(Debian/Ubuntu/Arch/Fedora), and **WSL2**. Native Windows still routes through
WSL; see [Windows](#windows-native-use-wsl) below for the honest bridge.

The installer is **idempotent** on every platform: re-running it never breaks
an existing install. It uses `$HOME/.vibecrafted/` as its staging root unless
you override `VIBECRAFTED_HOME`.

---

## macOS

### Supported versions

- macOS 13 (Ventura) or later
- Apple Silicon (arm64) and Intel (x86_64)
- Tested on macOS 14 (Sonoma) and macOS 15 (Sequoia)

### Prerequisites

The installer expects these to be present and on `PATH`:

| Tool       | Why                                          | Install                                          |
| ---------- | -------------------------------------------- | ------------------------------------------------ |
| `bash` 5.x | Installer + skill helpers                    | `brew install bash` (system bash 3.2 also works) |
| `tar`      | Archive extraction                           | Built-in                                         |
| `make`     | Workflow runner                              | `xcode-select --install` (Command Line Tools)    |
| `python3`  | Compact installer + GUI                      | `brew install python` (3.11+)                    |
| `curl`     | Download path                                | Built-in                                         |
| `git`      | Channel resolution, hooks                    | `xcode-select --install`                         |
| `uv`       | Runs the staged installer in an isolated env | Auto-bootstrapped by `install.sh`                |

If you already have Homebrew, the one-liner Just Works. If not, install
Homebrew first ([brew.sh](https://brew.sh)) — every subsequent step in this
guide assumes brew is available.

### Install

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
```

Or from a local checkout:

```bash
git clone https://github.com/VetCoders/vibecrafted.git
cd vibecrafted
make install              # interactive wizard
# or
make install-auto         # non-interactive (CI-friendly)
```

### Verify

```bash
vibecrafted doctor        # health check — should report 100+ ok / 0 failures
vc-help                   # cross-shell skill discovery
```

### macOS-specific surfaces

- **iTerm2 dynamic profiles + Hammerspoon URL handlers** —
  `make iterm-plugin` installs Vibecrafted's iTerm2 integration. Requires
  iTerm2 ≥ 3.5. Hammerspoon is an opt-in extra (`brew install --cask
hammerspoon`).
- **vibecrafted iTerm2 / locterm AutoLaunch plugin** —
  surfaces live spawn activity in the iTerm2 status bar, writes an
  additive `Vibecrafted` DynamicProfile with managed trigger rows, and
  posts native notifications on terminal spawn lifecycle transitions.
  Separate-process IPC over the documented iTerm2 Python API (clean GPL v2
  boundary — no static linking against locterm).

  ```bash
  pip install -e ./plugins/iterm2
  python -m vibecrafted_iterm2.install_autolaunch
  # then: iTerm2 → Preferences → General → Magic → Enable Python API
  ```

  `scripts/install-foundations.sh` will prompt automatically when run
  interactively on macOS and iTerm2 / locterm is detected at
  `/Applications/iTerm.app` or `/Applications/locterm.app`.
  See `plugins/iterm2/README.md` for
  the operator runbook and uninstall steps.

- **Codesigned binaries** — foundation binaries (loctree, aicx) ship signed
  with Maciej Gad's Apple Developer ID (`MW223P3NPX`). The installer
  verifies the signature on every download — see `verify_signature()` in
  `install.sh`.
- **AppleScript / Vibecrafted shell-agent .app** — `operator/shell-agent/`
  ships a native macOS bridge. Built only on macOS.

---

## Linux

Linux is a first-class target. The installer auto-detects your
distribution via `/etc/os-release` and emits copy-pasteable `apt`, `dnf`,
or `pacman` hints if anything is missing.

### Supported distributions

| Distro                                      | Status                   | Package manager |
| ------------------------------------------- | ------------------------ | --------------- |
| Debian 12 (Bookworm)                        | Tested, CI-gated         | `apt`           |
| Ubuntu 22.04 LTS                            | Tested                   | `apt`           |
| Ubuntu 24.04 LTS                            | Tested, CI-gated         | `apt`           |
| Linux Mint, Pop!\_OS, Raspbian              | Best-effort (apt-family) | `apt`           |
| Fedora 39+                                  | Tested                   | `dnf`           |
| Rocky Linux 9, AlmaLinux 9, CentOS Stream 9 | Best-effort (dnf-family) | `dnf`           |
| Arch, Manjaro, EndeavourOS                  | Tested                   | `pacman`        |
| Other / generic Linux                       | Best-effort              | (manual)        |

If your distro isn't listed, the installer still runs — it just won't emit
distro-specific package-manager hints when something is missing. File an
issue with your `cat /etc/os-release` output and we'll add it.

### Prerequisites

| Tool                 | Debian/Ubuntu                                  | Fedora                                           | Arch                                 |
| -------------------- | ---------------------------------------------- | ------------------------------------------------ | ------------------------------------ |
| `bash`               | built-in                                       | built-in                                         | built-in                             |
| `tar`                | built-in                                       | built-in                                         | built-in                             |
| `make`               | `sudo apt-get install -y make`                 | `sudo dnf install -y make`                       | `sudo pacman -S --noconfirm make`    |
| `python3` (3.11+)    | `sudo apt-get install -y python3 python3-venv` | `sudo dnf install -y python3 python3-virtualenv` | `sudo pacman -S --noconfirm python`  |
| `curl`               | `sudo apt-get install -y curl ca-certificates` | usually built-in                                 | `sudo pacman -S --noconfirm curl`    |
| `git`                | `sudo apt-get install -y git`                  | usually built-in                                 | `sudo pacman -S --noconfirm git`     |
| `ripgrep` (optional) | `sudo apt-get install -y ripgrep`              | `sudo dnf install -y ripgrep`                    | `sudo pacman -S --noconfirm ripgrep` |
| `uv`                 | auto-bootstrapped by `install.sh`              | same                                             | same                                 |

`uv` is downloaded by the installer if missing. Foundation binaries
(`loctree`, `aicx`) come from GitHub releases — `cargo` is only needed if
you want to build them from source.

### Install (one-shot)

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
```

If a prerequisite is missing, the installer prints the exact `sudo` command
to copy-paste, scoped to your detected package manager. Re-run after.

### Install (from source)

```bash
git clone https://github.com/VetCoders/vibecrafted.git
cd vibecrafted
make install               # interactive wizard
```

### Verify

```bash
vibecrafted doctor         # should report 100+ ok / 0 failures
vc-help                    # cross-shell skill discovery
```

### Linux-specific limitations

- **iTerm2 dynamic profiles** — macOS only. Linux terminals (Kitty, Wezterm,
  Alacritty) get baseline `vc-help` + shell helpers but no profile injection
  from this repo today.
- **Hammerspoon URL handlers** — macOS only. Linux terminal-level URL
  dispatch is planned, not shipped.
- **Shell-agent .app** — macOS only. The Rust core under
  `operator/shell-agent/ffi/` is cross-platform, but the Swift/AppKit wrapper
  is not.
- **codesigned foundation binaries** — Linux releases are signed with a
  detached GPG signature (or SHA256SUMS), not Apple Developer ID. The
  installer's `verify_signature()` falls back to SHA256-only on Linux.

---

## WSL (Windows Subsystem for Linux)

WSL2 is a fully-supported install target — it's identical to a native Linux
install from the framework's perspective. The installer auto-detects WSL via
`/proc/version` and prints "Platform: WSL / <distro>" so you know you're
running the Linux path.

### Supported configurations

- **WSL2 with Ubuntu 22.04 LTS or 24.04 LTS** — tested, recommended
- **WSL2 with Debian** — tested
- **WSL2 with Fedora / Arch** — best-effort (apt/dnf/pacman hints work)
- **WSL1** — best-effort; some foundation binaries may behave oddly under
  WSL1's Linux syscall translation. Upgrade to WSL2.

### Install

From inside your WSL distro:

```bash
curl -fsSL https://vibecrafted.io/install.sh | bash
```

From a Windows PowerShell or Command Prompt (one-shot wrapper):

```powershell
wsl -- bash -c 'curl -fsSL https://vibecrafted.io/install.sh | bash'
```

### Verify

```bash
vibecrafted doctor
vc-help
```

### WSL-specific notes

- **Filesystem placement** — install into your WSL home (`/home/<user>`),
  not into `/mnt/c/` (Windows filesystem). Cross-filesystem performance is
  drastically worse and `git` operations break in subtle ways.
- **Clock skew** — WSL2 occasionally drifts after Windows sleep. If you see
  TLS errors during the install, run `sudo hwclock -s` and retry.
- **Path mapping** — Windows `%PATH%` leaks into WSL by default and can
  shadow Linux binaries. The installer is robust to this; if you hit
  surprises, set `WSLENV` or disable path interop per WSL docs.

---

## Windows (native: use WSL)

Native Windows install is not supported today. Use WSL.

The `install.ps1` PowerShell entry point is operator-honest about this:

```powershell
# From PowerShell 5.1+ or PowerShell 7
iwr -useb https://vibecrafted.io/install.ps1 | iex
```

If WSL is installed and operational, it prints the exact one-liner to run:

```
wsl -- bash -c 'curl -fsSL https://vibecrafted.io/install.sh | bash'
```

If WSL is not installed, it prints the WSL2 install command
(`wsl --install`) and a link to the Microsoft docs. **It never silently
succeeds** — both branches exit with non-zero so any wrapping CI or
automation knows the install did not happen yet.

### Native Windows roadmap

Native Windows install remains a planned surface and should land as:

- Signed PowerShell module (`Install-Vibecrafted`)
- Native Windows binaries for foundation tools (loctree, aicx, prview)
- Optional MSI installer for the operator-facing CLI
- Windows Terminal profile injection (analogous to iTerm2 dynamic profiles
  on macOS)

Track progress through the issue tracker and release notes. Do not treat an old
plan filename as the current roadmap unless it exists in this checkout.

---

## Docker

The repository ships a `Dockerfile` for containerized smoke tests and
isolated agent workspaces.

```bash
docker build -t vibecrafted:local .
docker run --rm -it vibecrafted:local help
```

Build args:

| Arg                   | Default | Effect                                                                       |
| --------------------- | ------- | ---------------------------------------------------------------------------- |
| `INSTALL_AGENT_CLIS`  | `false` | Install claude / codex / gemini CLIs via npm                                 |
| `INSTALL_FOUNDATIONS` | `false` | Install foundation binaries (loctree, aicx, prview, etc.)                    |
| `INSTALL_RUST`        | `false` | Install rustup + stable toolchain (only if building foundations from source) |

See [`docs/DOCKER.md`](DOCKER.md) for the full container workflow.

---

## Maintenance — reclaim disk from old install snapshots

Each install stages the runtime under `<tools>/vibecrafted-<ref>` and repoints the
`vibecrafted-current` symlink at it. Switching refs (or migrating the tools base
dir) leaves the previous `vibecrafted-<ref>` tree behind: `vibecrafted-current` no
longer points at it, but nothing reclaims it.

`vibecrafted doctor` reports these as `snapshot-orphan` warnings — health stays
green (they waste disk, they don't break the runtime). `vibecrafted gc` reclaims
them through a recoverable, trash-like two-stage flow:

```bash
vibecrafted gc            # list de-pointed snapshots + total size (read-only)
vibecrafted gc --prune    # move them into a recoverable quarantine (no disk freed yet)
vibecrafted gc --purge    # hard-remove the quarantine — frees disk (irreversible)
```

| Flag        | Effect                                                       |
| ----------- | ------------------------------------------------------------ |
| _(none)_    | List orphaned snapshots and their sizes; change nothing      |
| `--prune`   | Move orphans into `<tools>/.orphan-snapshots/` (recoverable) |
| `--purge`   | Delete the quarantine to reclaim disk (asks to confirm)      |
| `--dry-run` | Show what any mode would do, touching nothing                |
| `--yes`     | Skip the `--purge` confirmation prompt                       |
| `--json`    | Emit a machine-readable summary                              |

The active `vibecrafted-current` snapshot is never touched. `--prune` is an atomic
same-filesystem move (nothing is copied), and the quarantine stays recoverable
until `--purge`.

---

## Uninstall

```bash
make uninstall              # remove skills + shell helpers
make restore                # undo last install/uninstall step
rm -rf "$HOME/.vibecrafted" # nuclear option (removes EVERYTHING)
```

The installer leaves a transaction log at `~/.vibecrafted/install.log`.

---

## Troubleshooting

### `vibecrafted: command not found` after install

The installer adds `~/.vibecrafted/bin` to your shell's `PATH` via the
cross-shell helper at `~/.config/vetcoders/vc-skills.sh`. If your shell
doesn't source it, add this to your `~/.bashrc` or `~/.zshrc`:

```bash
[ -f "$HOME/.config/vetcoders/vc-skills.sh" ] && source "$HOME/.config/vetcoders/vc-skills.sh"
```

Then `exec $SHELL -l` (or open a new terminal).

### `make: command not found`

Install your distro's build-essentials package — the install.sh pre-flight
prints the exact command for your platform.

### `python3: command not found`

Same — pre-flight will print the exact `apt`/`dnf`/`pacman`/`brew` command.

### Behind a corporate proxy

Set `HTTPS_PROXY` / `HTTP_PROXY` before running `install.sh`. The curl
download path honors these; `uv` honors them via env-var passthrough.

### Permission errors on `~/.vibecrafted/`

The installer never uses `sudo`. If you see permission errors, check that
`$HOME/.vibecrafted/` is writable by your user (or set `VIBECRAFTED_HOME`
to a path you own).

---

## CI smoke-testing the installer

The repo ships these CI workflows that exercise this install matrix:

- `.github/workflows/portable.yml` — shell-check + installer test on
  ubuntu-latest + macos-latest.
- `.github/workflows/install-linux.yml` — Linux install matrix
  (ubuntu-latest, debian-12 container).
- `.github/workflows/skill-loader.yml` — skill-loader smoke on
  ubuntu-latest + macos-latest.

Run the same smokes locally:

```bash
make check        # shellcheck on installer + helpers
make test         # pytest gate for installer + marketplace
make test-skills  # skill-loader smoke
make doctor       # health check
```

---

_Plan source: [`docs/plans/META_22_SCAFFOLD_TO_RELEASE.md`](plans/META_22_SCAFFOLD_TO_RELEASE.md) — Plan 03._

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
