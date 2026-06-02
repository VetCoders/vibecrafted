# Vibecrafted Journal

Living record of product/runtime decisions that must survive context loss.

## 2026-06-02 - Foundations Are Fuel, Not Guessable Dependencies

Tags: `VC-RUNTIME RECORD`, `VC-PRODUCT RECORD`, `installer`, `foundations`, `loctree`, `aicx`

### Trigger

The session began with the runtime question:

> Na czym opiera sie marbles runtime?

The investigation quickly exposed that the runtime depends on Loctree and AICX as
foundations, but the installer shape was still capable of treating them like
ordinary package-manager dependencies. That is the wrong product shape.

### Decision

There is no honest Vibecrafted without Loctree and AICX.

But Vibecrafted must not:

- guess where Loctree or AICX should come from;
- install historical crates/npm packages because they happen to exist;
- silently shadow user-owned binaries;
- rewrite or reorder the user's shell world;
- write to `.zshrc`, `.zprofile`, `.bashrc`, or equivalent shell config without explicit consent;
- assume foundations are broken just because they live in a non-default `$PATH` location.

### Product Contract

Installer behavior must be:

```text
detect -> validate -> explain -> offer canonical action
```

It must not be:

```text
detect missing -> guess crates/npm/local checkout -> mutate shell config or PATH
```

If `loct`, `loctree`, `loctree-mcp`, `aicx`, and `aicx-mcp` are present on the
user's effective `$PATH` and pass version/health validation, Vibecrafted accepts
them and reports where they were found.

If they are missing or unhealthy, Vibecrafted must show the canonical foundation
installer action and fail honestly when that canonical action is unavailable.

Current local patch CTA:

```sh
curl -fsSL https://loct.io/install.sh | sh
```

Do not replace this with crates.io, npm, GitHub guessing, sibling checkout
guessing, or `$HOME/.cargo/bin` hardcoding. The exact canonical endpoint should
still be treated as a release-time product contract, but this patch no longer
executes guessed foundation installs.

This does not ban a bootstrap process from temporarily adding existing
user-local bin directories to its own process `PATH` so it can detect tools.
The banned shape is product-foundation ownership by hardcoded install roots or
shell configuration mutation.

### Shape Debugging Note

This was not merely a code bug. The deeper bug was an intent/shape bug:

`foundation` had been treated as a generic dependency.

The correct shape is:

`foundation = runtime fuel from an explicit canonical source of truth`

That shape must drive setup, doctor, docs, and tests.

### Current Patch Boundary

At the time this journal entry was written, there were uncommitted installer
edits in:

- `install.toml`
- `scripts/install-foundations.sh`
- `scripts/vetcoders_install.py`

Those edits must be reviewed against this record before commit. In particular,
any source-root guessing, cargo/npm Loctree/AICX installation path, or shell
config mutation is suspect unless explicitly requested by the operator.

### 2026-06-02 Addendum - AICX Intent Noise Is A Product Hook

During the ownership pass, `aicx intents -p vibecrafted --emit json` returned
high-noise top results for a very specific runtime/installer/foundations
question, including older version bump and Rust toolchain items. It also emitted
a candidate-cap warning.

Treat this like a Loctree fail hook, not like harmless background noise:

- intent-debugging queries need high precision around the current operator
  shape;
- stale adjacent plans must not outrank the active runtime/product decision;
- cap/drop warnings should become visible retrieval-health evidence;
- future `vc-intents` should record when AICX is useful, noisy, or misleading.

The current installer diff before compaction is Codex-owned and must be cleaned
against this journal, not attributed to another worker.
