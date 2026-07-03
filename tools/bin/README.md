# tools/bin — bundled toolchain drop-in

This directory is the **drop-in slot** for notarized foundation binaries
that ship inside the Vibecrafted release tarball. When populated, the
installer picks binaries up from here before reaching out to GitHub
releases, `cargo install`, or `npm install -g`.

## Layout

Per-architecture (preferred for multi-target releases):

```
tools/bin/
├── README.md                (this file)
├── macos-aarch64/
│   ├── aicx
│   ├── aicx-mcp
│   ├── loctree
│   ├── loctree-mcp
│   ├── loct
│   └── prview
├── macos-x86_64/
│   └── …
├── linux-x86_64/
│   └── …
└── linux-aarch64/
    └── …
```

Flat fallback (single-arch dev drops):

```
tools/bin/
├── aicx-mcp
├── loctree-mcp
└── …
```

## Recognized binaries

The installer only looks for names it knows about:

- `aicx`, `aicx-mcp`, `aicx-extract`
- `loctree`, `loctree-mcp`, `loct`
- `prview`

Anything else lands in the tarball but is not auto-installed.

## Resolution order (install-foundations.sh & installer_gui.py)

1. `$VIBECRAFTED_BUNDLED_BIN` — explicit absolute path override
2. `$SOURCE/tools/bin/<os>-<arch>` — per-arch (preferred)
3. `$SOURCE/tools/bin` — flat fallback

`<os>` is one of `macos`, `linux`, `windows`.
`<arch>` is one of `x86_64`, `aarch64`, `armv7`.

## Notarization contract (macOS)

Binaries in `macos-*` subdirectories are expected to be signed with the
Vetcoders Developer ID and notarized via `xcrun notarytool`. The
installer runs a basic `binary_runs` smoke test after copying — it does
**not** re-run `codesign --verify` or `spctl --assess` today. That gate
lives in the release pipeline, not on end-user machines.

To re-stamp locally before shipping:

```bash
codesign --force --options runtime --timestamp \
  --sign "Developer ID Application: Vetcoders" \
  tools/bin/macos-aarch64/aicx
xcrun notarytool submit tools/bin/macos-aarch64/aicx \
  --keychain-profile vetcoders-notary --wait
```

## What ships, what doesn't

- `build_marketplace_bundle.py` packs the entire `tools/bin/**` subtree
  (minus `.gitkeep` / `.DS_Store` / `.pyc`) into the `.plugin` zip.
- Empty directory = tarball is built without the bundled slot, and the
  installer falls through to GH/cargo/npm attempts. No error.
- `tools/bin/README.md` ships too — operators extracting the tarball
  can read the convention in place.
