# Quick Start

## 1. Install the one product

Open the [latest release](https://github.com/vetcoders/vibecrafted/releases/latest),
download `Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg`, verify it with the
adjacent `.dmg.sha256`, and open the DMG.

Drag `Vibecrafted.app` to Applications, then launch it. The DMG is Developer ID
signed, notarized and carries the exact matching `vc-terminal`, `vc-frame` and
Vibecrafted runtime. There are no per-repository installers to run.

The app creates or restores a durable `workspace_id`, starts through its
bundled `vc-start`, and sources an app-owned XDG/runtime environment. Your
terminal, shell and vc-frame configuration files are not replaced.

## 2. Verify

```bash
vibecrafted doctor
vibecrafted --version
```

The release report on GitHub records the exact source tuple, DMG SHA-256,
notarization status and cold mounted-DMG smoke.

## 3. Orient your agent

From any repository:

```bash
vibecrafted init codex
```

This recovers intentions through AICX, maps the living tree through Loctree and
checks runtime truth before work begins.

## 4. Build something

```bash
vibecrafted implement codex --prompt "Add user authentication with JWT"
```

Use `vibecrafted help` for the full operator surface.

## Developer checkout path

`make install`, `make install-auto` and the legacy curl bootstrap remain
maintainer/control-plane staging tools for non-app development. They are not a
second end-user product, DMG, terminal installer or vc-frame update channel.
