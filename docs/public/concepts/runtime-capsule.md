---
title: "Runtime capsule"
description: "Installed runtime generations: immutable directories, an atomic current pointer, a hash-bound manifest, and safe rollback."
section: concepts
order: 40
---

# Runtime capsule

The repository is a workshop; the installed generation is the runtime. The
`vibecrafted` command you run daily never executes out of a git checkout —
it enters an immutable, audited install called a runtime generation. This
page explains how generations are built, verified, switched, and rolled
back.

## Layout

The public launcher at `~/.local/bin/vibecrafted` (and its `vc-*` aliases)
enters only the command deck under:

```text
~/.local/share/vibecrafted/tools/vibecrafted-current/
```

`vibecrafted-current` is an atomic symlink pointing at exactly one
immutable generation directory:

```text
~/.local/share/vibecrafted/tools/
  vibecrafted-current -> vibecrafted-generation-<version>-<token>/
  vibecrafted-generation-<version>-<token>/
    runtime-manifest.json
    ...command deck, helpers, generated configuration...
```

The installer refuses to point the public launcher at a package-manager
shim or a repository checkout.

## The generation manifest

Every published generation contains `runtime-manifest.json` with schema
`vibecrafted.runtime-generation.v2`. It binds:

| Field              | What it pins                                                                                                                     |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------------- |
| Installed version  | The exact version this generation ships                                                                                          |
| Entrypoint         | The canonical command-deck entrypoint                                                                                            |
| Source fingerprint | A one-way fingerprint of the source root — never the checkout path itself                                                        |
| Source payload     | The v2 distribution-tree digest and entry count carried from the verified source archive                                         |
| SHA-256 hash set   | Digests for `VERSION`, launcher/deck, generated vc-frame configuration, and the verifier engine/runner/schema/policy/key closure |

The manifest and the active runtime files are created and audited **before**
the single pointer swap. If the audit fails, the previous generation stays
live and remains rollbackable — a half-copied tree is never published as an
install.

The packaged `verify-vibecrafted-walkaround` launcher repeats this closed-file
audit before it executes the verifier runner. A drifted, symlinked, or
hardlinked verifier asset therefore fails before candidate verifier code can
run; `doctor` is not the only enforcement point.

## Source carrier

Release and custom bootstrap archives carry a closed v2
`source-provenance.json` record. It names the owner repository and exact
40-character commit, and binds the complete distribution tree by a canonical
SHA-256 digest plus entry count. Paths, file types, executable modes, file
bytes, symlink targets, and empty directories all participate. The carrier is
the only excluded entry, which avoids hashing the digest into itself.

The archive writer refuses to claim a Git commit while any included payload
entry differs from that commit. Bootstrap independently recomputes the same
tree identity before extraction, after extraction, and after candidate staging;
it does this before running Python supplied by the archive. Missing, legacy,
contradictory, or byte-mismatched carriers fail closed.

That byte-to-commit proof happens while the canonical writer still has the Git
object database. After extraction, the carrier transports the proven identity
and detects conflicting claims; it cannot independently reconstruct Git history.
This v2 carrier proves internal consistency, not who produced it: an attacker
could rewrite a payload and its carrier together. Official release authenticity
therefore still comes from W4's fail-closed signed archive/channel binding, not
from the carrier alone.

## Checkout freedom

Installed artifacts must never resolve back into a development checkout.
Publication fails when:

- any installed symlink is broken or resolves outside its generation;
- active configuration, KDL layouts, helpers, or command-deck content
  reference the source checkout;
- the runtime manifest cannot be created from its required inputs.

This guarantee is what makes `git pull` in your checkout harmless to the
running product: push does not equal install. Your daily CLI keeps running
the staged generation until you deliberately install a new one.

## Verifying the installed runtime

`vibecrafted doctor` repeats the publication audit against the installed
artifact. It fails when:

- the public launcher resolves outside `~/.local/share/vibecrafted`;
- the manifest is invalid;
- any manifest-bound file has drifted from its recorded SHA-256.

```bash
vibecrafted doctor
vibecrafted --version    # shows <version>+g<sha> build provenance
```

The version string carries a `+g<sha>` suffix identifying the exact source
commit the generation was built from — see
[Versioning](/docs/versioning/).

## Rollback

Because generations are immutable and the pointer swap is atomic, rollback
is a pointer move, not a rebuild. A failed install audit never advances the
pointer in the first place, and the previously live generation remains on
disk until superseded. The installer also owns a conservative, ledgered
layout-transfer surface for migrating between store layouts, refusing to
overwrite differing files without an explicit force flag.

## Host shell boundary

The default installer does not source Vibecrafted helpers into your host
shell. It may add only a guarded `~/.local/bin` PATH entry, after explicit
consent. The full helper profile belongs to the explicit `vc-start`
environment — your everyday shell stays yours.

## Why a capsule at all

AI-developed software changes fast, and a fleet of agents commits to the
checkout continuously. Binding the daily runtime to hashed, immutable
generations means:

- agents can churn the workshop without destabilizing the tool you run;
- every installed byte is attributable to a version and a commit;
- drift between "what I run" and "what I built" is detectable
  (`doctor`, the delivery receipt) instead of silent.
