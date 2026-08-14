# Install Vibecrafted

The public product is one signed and notarized macOS artifact:

```bash
curl -fL https://github.com/vetcoders/vibecrafted/releases/latest/download/Vibecrafted.dmg \
  -o Vibecrafted.dmg
open Vibecrafted.dmg
```

Drag `Vibecrafted.app` to Applications and launch it. The app carries matching
builds of `vc-terminal`, `vc-frame`, `vc-start` and the complete Vibecrafted
runtime. No companion repository installer is required or supported.

## Runtime boundary

Every new or restored workspace has a durable `workspace_id` and enters through
the bundled `vc-start`. The app sources an app-owned XDG/runtime environment;
it does not rewrite the user's terminal, shell, Zellij or vc-frame config.

The server endpoint is read from Vibecrafted settings and may be any host:port.
For example, an operator may configure `100.82.232.70:3025`; it is never baked
into the app or inferred from the local checkout.

## Verify

```bash
vibecrafted doctor
vibecrafted version
```

The GitHub Release report records source revisions, security gates, Apple
notarization proof, SHA-256 and a cold mounted-DMG smoke of the exact downloaded
bytes.

## Update and rollback

Install a newer `Vibecrafted.app` from the new DMG. The app/runtime binary can
be replaced while session processes continue to own their live state; restored
workspaces re-enter through the new bundled `vc-start`. Roll back by replacing
the app with the prior notarized release.

## Maintainer and non-macOS source path

The checkout retains `make install`, `make install-auto`, `install.sh` and
container targets for development, CI and headless Linux/WSL control-plane
work. These are Vibecrafted-owned source staging paths, not a second desktop
product and not an independent vc-frame/vc-terminal release channel.

Use `make help-dev` inside the checkout for that maintainer inventory.
