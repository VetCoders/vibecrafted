---
title: "Install"
description: "Install the complete Vibecrafted desktop product from one signed and notarized DMG."
section: getting-started
order: 20
---

# Install

Vibecrafted ships as one macOS product. `Vibecrafted.app` owns installation,
updates, the terminal host, the session interior and the runtime generation.

## Requirements

- macOS 14 or newer
- Apple Silicon (`arm64`)
- authenticated agent CLIs for the agents you choose to use

## Download

Open the [latest release](https://github.com/vetcoders/vibecrafted/releases/latest),
download `Vibecrafted_<version>-<YYYYMMDD>-<sha8>.dmg`, verify it with the
adjacent `.dmg.sha256`, and open the DMG.

Drag `Vibecrafted.app` to Applications and launch it. The app always enters a
new or restored workspace through its bundled `vc-start` and durable
`workspace_id` contract.

## Hermetic boundary

The app carries matching builds of `vc-terminal`, `vc-frame` and the complete
Vibecrafted runtime. It sources its own XDG/runtime environment at startup and
does not overwrite user-managed terminal, shell, Zellij or vc-frame config.
`vc-terminal` and `vc-frame` do not have independent app, DMG, installer or
update channels.

## Verify

```bash
vibecrafted doctor
vibecrafted version
```

The GitHub Release report publishes the artifact SHA-256, source revisions,
security gates, notarization proof and cold install smoke from the downloaded
DMG.

## Maintainer source path

The repository still contains source bootstrap and `make install` targets for
development, Linux/WSL control-plane work and test fixtures. Those paths stage
the Vibecrafted-owned runtime; they are not an alternative desktop product or
a per-repository installer.
