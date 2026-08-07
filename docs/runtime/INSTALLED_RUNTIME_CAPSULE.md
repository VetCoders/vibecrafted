# Installed runtime capsule

The repository is a workshop. The installed generation is the runtime.

`~/.local/bin/vibecrafted` and its `vc-*` aliases enter only the command deck
under:

```text
~/.local/share/vibecrafted/tools/vibecrafted-current/
```

`vibecrafted-current` is an atomic symlink to one immutable
`vibecrafted-generation-*` directory. The installer refuses to use a uv tool
shim or repository checkout as the public launcher target.

## Generation manifest

Every published generation contains `runtime-manifest.json` with schema
`vibecrafted.runtime-generation.v1`. It binds:

- the installed version;
- the canonical command-deck entrypoint;
- a one-way fingerprint of the source root, never the checkout path itself;
- SHA-256 digests for `VERSION`, the command deck, and generated vc-frame
  configuration.

The manifest and active runtime files are created and audited before the
single pointer swap. A failed audit leaves the previous generation live and
rollbackable.

## Checkout-free gate

Publication fails when:

- any installed symlink is broken or resolves outside its generation;
- active config, KDL, helper, or command-deck content references the source
  checkout;
- the runtime manifest cannot be created from its required inputs.

`vibecrafted doctor` repeats the audit against the installed artifact. It also
fails when the public launcher resolves outside
`~/.local/share/vibecrafted`, when the manifest is invalid, or when a
manifest-bound file has drifted.

## Host shell boundary

The default installer does not source Vibecrafted helpers into the host shell.
It may add only the guarded `~/.local/bin` path entry after explicit consent.
The full helper profile belongs to the explicit `vc-start` environment.
