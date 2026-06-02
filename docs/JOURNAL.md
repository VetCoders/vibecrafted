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

## 2026-06-02 - Checkpoint: Sight, Insight, Ship, Frame

Tags: `VC-CHECKPOINT SAVE`, `VC-PRODUCT`, `VC-FRAME`, `vc-skillaunch`, `loctree`, `aicx`, `vc-ship`

### Trigger

After the shell runtime split and async dispatcher checkpoint, the operator
started distilling the session through `vc-skillaunch` into the next Loctree and
`vc-ship` contracts.

This checkpoint records the product shape before any SKILL.md rewrite.

### Decisions

Loctree and AICX are not optional tools.

```text
Loctree = sight
AICX    = insight
```

Together they form an independent two-body perception system and the nucleus of
every workflow. They are the hub and bearing; the workflows are spokes coming
out of that center.

Loctree is not an obligation imposed on agents. Loctree is a need: the work
needs sight before it can move honestly. If Loctree is unavailable, that is a
framework failure, not a normal fallback mode.

AICX is the complementary insight layer: intent, memory, prior decisions, and
why the code got this shape.

### Workflow Shape

Current "skills" are already splitting into a larger runtime anatomy:

```text
skill     = formal interactive instruction
workflow  = goal procedure and gates
launcher  = non-interactive runtime entrypoint
telemetry = fuel for read-write cadence and control plane
```

Every repo-dependent workflow starts with `vc-init` and a Loctree context
snapshot. That start is not ceremony; it prevents 20-minute rediscovery loops
and token burn.

There is no "minimal telemetry." Telemetry is runtime fuel for the read-write
cadence: observation, decisions, stop reasons, resumption, report synthesis, and
next work.

### Shipping Shape

If sight and insight are the hub and bearing, `vc-ship` is not just a final
command. It is the riding surface and steering surface:

```text
vc-ship = tire + handlebar + saddle
```

- Tire: contact with reality, release, bundles, distribution, customer surface.
- Handlebar: direction, stop/go decisions, pipeline selection.
- Saddle: operator ergonomics for sustained work.

The old runtime shape at or below 3.0.0 may disappear as a form. The intended
frame is:

```text
vibecrafted-core   = mechanics / drive
vibecrafted-mcp    = lever and peephole for agents
vibecrafted-server = observability and protocol brain
vibecrafted-app    = cockpit for humans
vibecrafted-vm     = isolated factory runtime
```

### Distribution Correction

Bundle-first is the standard product path.

Vibecrafted should normally deliver required Loctree/AICX binaries with the
bundle. `curl` is fallback, not the primary product path.

This corrects any earlier wording that made `curl -fsSL https://loct.io/install.sh | sh`
sound like the main foundation delivery model.

### Stop Conditions

These stop the pipeline:

- Loctree unavailable or unable to produce the needed context snapshot.
- Missing `vc-init` for repo-dependent work.
- Missing telemetry/report fuel for read-write cadence.
- Missing product-decision journal entry when shape changed.
- Red gates.
- Dirty-tree ownership that cannot be explained.
- Overclaim in a report or final answer.

### Source Of Truth

Skill/workflow authoring happens in the repo.

Installed copies under `.codex`, `.agents`, or `.vibecrafted` are distribution
outputs, not manual authoring targets.

## 2026-06-02 - Product Shape Established

`[VC-PRODUCT SHAPE] ESTABLISHED 2026-06-02`

The Runtime 3.0 product shape is established as a factory runtime, not an
ideology surface. Vibecrafted consumes the methodology internally and exposes a
durable product contract externally.

Implementation direction:

- Build the runtime around `vibecrafted-{core,mcp,vm,server,app}`.
- Hard-deprecate `./skills/vc-agents/**` as the source of truth for implement
  spawning.
- Prefer the shared lifecycle dispatcher surface, with `vibecrafted-tui` as the
  operator dispatcher/cockpit and `vibecrafted-core` as the lifecycle engine.
- Use `vc-polarize` WRITE followed by automatic `vc-audit` READ as the first
  factory cadence slice.
- Treat `vc-ship` as a meta-plan and trigger graph, not another loose script.
- Keep factory internals private: expose trade names, product contracts,
  status, quality proof, and operator buttons, not the internal recipe.

The target trigger graph is:

```text
vc-scaffold bu⪮mp vc-implement bu⪮mp vc-review bu⪮mp vc-workflow
bu⪮mp vc-followup bu⪮mp vc-marbles bu⪮mp vc-audit bu⪮mp vc-polarize
bu⪮mp vc-dou bu⪮mp vc-hydrate bu⪮mp vc-release
```

Success condition: one prompt travels this full graph automatically, with
durable lifecycle events, reports, telemetry, gates, parent-child trigger
evidence, and operator-button stops only at real trust boundaries.
