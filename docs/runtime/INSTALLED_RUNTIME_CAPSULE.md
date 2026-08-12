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
`vibecrafted.runtime-generation.v2`. It binds:

- the installed version;
- the canonical command-deck entrypoint;
- a one-way fingerprint of the source root, never the checkout path itself;
- the canonical distribution-tree digest and entry count from the verified v2
  source carrier;
- SHA-256 digests for `VERSION`, the launcher, command deck, generated vc-frame
  configuration, and the complete W0 release verifier closure: verifier engine,
  runner, public schema, release policy, and signing key.

The manifest and active runtime files are created and audited before the
single pointer swap. A failed audit leaves the previous generation live and
rollbackable.

The managed `verify-vibecrafted-walkaround` wrapper validates its own regular,
single-link identity plus the exact closed manifest and all bound file digests
before it executes any generation-owned Python. This keeps corruption
detection outside the code whose integrity is being decided.

Source archives have a separate closed v2 `source-provenance.json` carrier. A
Git checkout may claim its `HEAD` only when every included payload path, type,
mode, byte sequence, and symlink target equals that commit. The carrier records
the canonical distribution-tree SHA-256 and entry count. Bootstrap recomputes
that identity before extraction, after extraction, and after candidate staging,
before archive-owned Python may influence publication. Raw tarballs without v2
and contradictory or mismatched records fail bootstrap.

The carrier is an internal-integrity boundary, not an authenticity proof. W4
must bind the exact archive/carrier identity through the pinned release trust
root and keep bootstrap verification fail closed.

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

Generations created before this closed verifier inventory are intentionally
rejected and must be reinstalled. W4 binds this manifest into the signed release
receipt; the adjacent manifest alone is the immutable-generation corruption
boundary, not a substitute for the release signature.

## Host shell boundary

The default installer does not source Vibecrafted helpers into the host shell.
It may add only the guarded `~/.local/bin` path entry after explicit consent.
The full helper profile belongs to the explicit `vc-start` environment.
