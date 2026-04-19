---
run_id: rsch-183346
prompt_id: 20260416_1833_perform-the-vc-research-skill-on-this-reposito_20260416
agent: codex
skill: rsch
model: unknown
status: completed
---

# Research: Vibecrafted Repository Ground Truth

## Problem

We needed an implementation-ready read of what `vibecrafted` actually is today, not just what the marketing surface says it is. The repo mixes a shell bootstrap, Python installer/control-plane code, and skill-driven workflow orchestration, so the real question was where runtime truth currently lives, where drift is accumulating, and what the next architectural convergence move should be. This research focused on repo truth, current verification behavior, and a small set of official external references for installation and distribution practices. Out of scope: implementing the fixes or redesigning the public site.

## Findings

### Q1: What is the real end-to-end operator architecture of this repository from bootstrap install through command-deck usage and workflow execution?

**Answer**: The live operator flow is a staged control-plane bootstrap followed by a split installer stack and then a bash command deck for runtime operations. `install.sh` downloads or unpacks a versioned snapshot into `~/.vibecrafted/tools`, refreshes `vibecrafted-current`, verifies checksums/signatures when available, and then selects one of three front doors: browser-guided UI, compact non-interactive install, or the local terminal wizard. Those paths all converge on the same mutation backend in `scripts/vetcoders_install.py`, with the vendored `vetcoders-installer` runner and `install.toml` acting as the orchestration contract. After install, operators use `scripts/vibecrafted` plus the `vc-*` helper layer in `skills/vc-agents/shell/vetcoders.sh` to launch workflows and multi-agent sessions, typically through Zellij-backed operator sessions.

**Confidence**: high

**Sources**: [install.sh](/Users/polyversai/Libraxis/vibecrafted/install.sh:6), [install.sh](/Users/polyversai/Libraxis/vibecrafted/install.sh:234), [install.sh](/Users/polyversai/Libraxis/vibecrafted/install.sh:331), [Makefile](/Users/polyversai/Libraxis/vibecrafted/Makefile:50), [Makefile](/Users/polyversai/Libraxis/vibecrafted/Makefile:63), [install.toml](/Users/polyversai/Libraxis/vibecrafted/install.toml:22), [scripts/installer/README.md](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/README.md:1), [scripts/installer/pyproject.toml](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/pyproject.toml:17), [scripts/vibecrafted](/Users/polyversai/Libraxis/vibecrafted/scripts/vibecrafted:14), [skills/vc-agents/shell/vetcoders.sh](/Users/polyversai/Libraxis/vibecrafted/skills/vc-agents/shell/vetcoders.sh:959)

**Dissent**: No material disagreement across the three completed passes. The skeptical pass simply made the layering sharper: today’s runtime works, but it is still a federation of Bash, Python, and Zellij surfaces rather than one boringly unified control plane.

### Q2: Which structural risks or duplicated surfaces in the current implementation are most likely to create maintenance drag, operator confusion, or product drift?

**Answer**: The main architectural drag is duplicated installer truth. The repo currently spreads install behavior and installer-adjacent UX across `install.sh`, `Makefile`, `scripts/installer_gui.py`, `scripts/installer_tui.py`, the vendored `scripts/installer/vetcoders_installer` runner, `scripts/vetcoders_install.py`, and `scripts/install-foundations.sh`. Loctree already flags duplicate helper functions across GUI and TUI surfaces, and the vendored Textual/Rich installer has its own diagnostics/summarization logic again. That duplication is amplified by copy drift in the docs: the README says to prefer the guided browser path for onboarding, Quick Start presents the terminal-native path as the human kickoff, and `docs/installer/DESIGN.md` says the public shipping front door is browser-guided. Runtime truth is also not fully green: the repo’s intended test gate (`make test`) currently fails three `marbles` runtime tests, all around watcher/meta/report timing and failed-loop materialization.

**Confidence**: high

**Sources**: [README.md](/Users/polyversai/Libraxis/vibecrafted/README.md:95), [README.md](/Users/polyversai/Libraxis/vibecrafted/README.md:119), [docs/QUICK_START.md](/Users/polyversai/Libraxis/vibecrafted/docs/QUICK_START.md:7), [docs/QUICK_START.md](/Users/polyversai/Libraxis/vibecrafted/docs/QUICK_START.md:30), [docs/installer/DESIGN.md](/Users/polyversai/Libraxis/vibecrafted/docs/installer/DESIGN.md:3), [scripts/installer_gui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer_gui.py:48), [scripts/installer_gui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer_gui.py:60), [scripts/installer_tui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer_tui.py:85), [scripts/installer_tui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer_tui.py:123), [scripts/installer/vetcoders_installer/tui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/vetcoders_installer/tui.py:22), [scripts/installer/vetcoders_installer/tui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/vetcoders_installer/tui.py:69), [tests/tui/test_marbles_runtime.py](/Users/polyversai/Libraxis/vibecrafted/tests/tui/test_marbles_runtime.py:1018), [tests/tui/test_marbles_runtime.py](/Users/polyversai/Libraxis/vibecrafted/tests/tui/test_marbles_runtime.py:1141), [tests/tui/test_marbles_runtime.py](/Users/polyversai/Libraxis/vibecrafted/tests/tui/test_marbles_runtime.py:1237)

**Dissent**: Pass A emphasized duplicated installer code and path drift; Pass B emphasized “multiple public-ish entrypoints” and vendored-boundary drift; Pass C added a useful runtime nuance from `doctor`: the codebase already audits installed-vs-source drift because this problem is real in normal use, not just in theory. The only additional local finding is that raw `pytest -q` from repo root is itself a trap because the live `vibecrafted-io-link` mirror causes duplicate test discovery/import-mismatch explosions.

### Q3: Which external best practices are most relevant to the install and CLI-distribution surface here, and how well does the current repo align with them?

**Answer**: The most relevant external practices for this repo are: keep bootstrap scripts inspectable and optionally verifiable, run tools from isolated project environments, expose CLI entry points in package metadata when possible, and keep user state/config paths predictable. Vibecrafted aligns better than most `curl | bash` flows: `install.sh` stages into a user-scoped control plane, prompts before mutation, supports `--yes`, and attempts checksum/signature verification; the built-in installer runner is a proper Python project with a declared script entry point, and local execution is already `uv`-based. The main gaps are that the verification story is still bespoke rather than exposed as a standardized provenance/attestation surface, and the path model is only partially normalized: helpers use `XDG_CONFIG_HOME`, but the durable store is still a monolithic `~/.vibecrafted`.

**Confidence**: medium-high

**Sources**: [install.sh](/Users/polyversai/Libraxis/vibecrafted/install.sh:77), [install.sh](/Users/polyversai/Libraxis/vibecrafted/install.sh:234), [scripts/installer/pyproject.toml](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/pyproject.toml:1), [scripts/installer/pyproject.toml](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/pyproject.toml:17), [scripts/runtime_paths.py](/Users/polyversai/Libraxis/vibecrafted/scripts/runtime_paths.py:21), [scripts/runtime_paths.py](/Users/polyversai/Libraxis/vibecrafted/scripts/runtime_paths.py:25), [.github/workflows/release.yml](/Users/polyversai/Libraxis/vibecrafted/.github/workflows/release.yml:68), [.github/workflows/release.yml](/Users/polyversai/Libraxis/vibecrafted/.github/workflows/release.yml:77), [uv Installation](https://docs.astral.sh/uv/getting-started/installation/), [pipx](https://pipx.pypa.io/stable/), [XDG Base Directory Specification](https://specifications.freedesktop.org/basedir/latest/)

**Dissent**: Pass A stayed close to the current Python packaging/uv shape; Pass B pushed harder on supply-chain standardization and package-manager distribution; Pass C made the strongest critique, which is that the packaged artifact is still `vetcoders-installer`, not `vibecrafted` itself. I think the repo evidence supports the shared conclusion: the current baseline is good, but the verification and distribution story is not yet boringly standard.

### Q4: Based on repo truth plus external guidance, what target architecture should the next implementation cycle converge toward?

**Answer**: The strongest next target is one install graph, one path model, and thin front doors. `install.toml` plus the vendored `vetcoders-installer` runner should remain the single orchestration contract, and `scripts/vetcoders_install.py` should remain the only mutation backend until the install graph is fully stable. The next implementation cycle should extract shared path/diagnostic/install-step helpers so that `installer_gui.py`, `installer_tui.py`, and the vendored runner stop re-implementing the same logic, then normalize docs and manifests onto the actual `VIBECRAFTED_HOME` and `XDG_CONFIG_HOME` truth. After that, the team can decide whether the bash command deck remains the right long-term operator surface or whether it should be packaged as a more formally distributed CLI, and whether to add a mainstream distribution channel like Homebrew once the release artifact contract settles.

**Confidence**: medium-high

**Sources**: [scripts/installer/README.md](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/README.md:1), [docs/installer/REFERENCE.md](/Users/polyversai/Libraxis/vibecrafted/docs/installer/REFERENCE.md:1), [install.toml](/Users/polyversai/Libraxis/vibecrafted/install.toml:1), [scripts/runtime_paths.py](/Users/polyversai/Libraxis/vibecrafted/scripts/runtime_paths.py:21), [docs/REPO_GROUND_TRUTH_2026_04_13.md](/Users/polyversai/Libraxis/vibecrafted/docs/REPO_GROUND_TRUTH_2026_04_13.md:107), [scripts/installer/pyproject.toml](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/pyproject.toml:17), [Zellij Layouts With Config](https://zellij.dev/documentation/layouts-with-config.html)

**Dissent**: Pass B specifically recommended adding a mainstream package-manager channel and a more explicit verification UX; Pass C went further and argued that `vibecrafted` itself should become the packaged CLI sooner rather than later. I agree with the ordering compromise: converge the internal contract first, then decide whether the packaged public CLI should be `vibecrafted` rather than just the installer subpackage.

## Architecture Decision

- **Chosen approach**: Converge on `install.toml` + `vetcoders-installer` as the sole install graph, keep `scripts/vetcoders_install.py` as the sole mutator for now, and treat every other install surface as a thin selector or presentation wrapper.
- **Why**: That preserves what already works, matches the strongest repo-local truth, and directly attacks the biggest remaining source of drift: duplicated installer-adjacent code and copy.
- **Alternatives rejected**: Keeping the current split longer invites more drift. Rewriting the mutation engine immediately is premature while the public install contract is still mixed. Turning the whole command deck into a new packaged CLI before the install graph stabilizes would add another parallel truth instead of removing one.

## Implementation Notes

- Extract shared installer helpers first: source-dir resolution, path model, diagnostics summarization, and install command construction are currently duplicated across [scripts/installer_gui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer_gui.py:48), [scripts/installer_tui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer_tui.py:85), and [scripts/installer/vetcoders_installer/tui.py](/Users/polyversai/Libraxis/vibecrafted/scripts/installer/vetcoders_installer/tui.py:69).
- Normalize every human-facing install reference to one truth. Right now the repo mixes “browser-guided public front door” and “terminal-native default human kickoff” across [README.md](/Users/polyversai/Libraxis/vibecrafted/README.md:99), [docs/QUICK_START.md](/Users/polyversai/Libraxis/vibecrafted/docs/QUICK_START.md:7), [install.toml](/Users/polyversai/Libraxis/vibecrafted/install.toml:4), and [docs/installer/REFERENCE.md](/Users/polyversai/Libraxis/vibecrafted/docs/installer/REFERENCE.md:11).
- Normalize the path language. The runtime code already resolves `VIBECRAFTED_HOME` and `XDG_CONFIG_HOME`, but [install.toml](/Users/polyversai/Libraxis/vibecrafted/install.toml:62) and older docs still talk about `$VIBECRAFTED_ROOT/.vibecrafted/...`.
- Keep the current signature/checksum path, but make verification more operator-visible. The release pipeline already emits `SHA256SUMS`, a detached signature, and a public key, and [install.sh](/Users/polyversai/Libraxis/vibecrafted/install.sh:234) already verifies them.
- Treat `marbles` watcher/meta/report timing as the highest-priority runtime fix before advertising the broader workflow surface as fully stable. The three failing assertions in [tests/tui/test_marbles_runtime.py](/Users/polyversai/Libraxis/vibecrafted/tests/tui/test_marbles_runtime.py:1018) all point at that same seam.

## Verification Snapshot

- `pytest -q` from repo root is not a valid repo-wide truth command here: it explodes with import-file mismatch errors because the live `vibecrafted-io-link` mirror duplicates test module names inside the tree.
- `bash scripts/vibecrafted help` worked locally and surfaced the expected command-deck contract.
- `bash scripts/vibecrafted doctor` reported `93 ok`, `3 warnings`, `0 failures`; the warnings were installed-vs-source skill drift, stale installed files, and a missing local `claude` CLI on `PATH`.
- `pytest tests/tui/test_vibecrafted_launcher.py -q` passed with `21 passed`.
- `make check` passed cleanly.
- `make semgrep` exited cleanly.
- `make test` finished with `3 failed, 210 passed, 2 skipped` after 219 seconds. All three failures are in `tests/tui/test_marbles_runtime.py` and concern loop-state transitions around failed launch or delayed metadata/report completion.
- A narrower installer/launcher slice from one independent pass reported `14 passed`, which fits the broader picture: installer truth is relatively healthy, but the `marbles` runtime is not fully green.

## Remaining Gaps

- All three independent passes completed, but only two were needed for core consensus; the third mainly sharpened the packaging and drift critique rather than changing the answer.
- I did not inspect the downstream `vibecrafted-io` mirror repo itself beyond observing that its symlinked presence changes test-discovery behavior in this workspace.
- The next unresolved product decision is not technical debt but distribution strategy: once the install contract is unified, does Vibecrafted stay source-bootstrap-first, or does it also ship a first-class package-manager channel?
