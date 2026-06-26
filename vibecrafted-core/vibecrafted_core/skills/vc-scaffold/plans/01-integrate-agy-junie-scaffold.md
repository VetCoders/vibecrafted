---
title: Integrate agy and junie into vc-scaffold
description: Plan for adapting the installation manifests, diagnostic utilities, and founder-first scaffold planning configs to include agy and junie
type: implementation_plan
project: VetCoders/vibecrafted
created: 2026-05-23
parent_branch: release/v2.0.0
---

# Plan: `vc-scaffold` — `agy` & `junie` Bootstrap and Planning Integration

This plan details the steps required to configure the installer, diagnostic sweeps, and founder-first scaffold planning layers to fully support `antigravity-cli` (`agy`) and `junie`.

---

## 1) Goal and Rationale

To make the transition to `agy` and `junie` seamless for founders and operators alike, the `vibecrafted` bootstrap process must configure the toolchain paths, symlinks, and diagnostics out of the box. Additionally, the plan authoring system (`vc-scaffold`) must be equipped with configurations for both agents.

---

## 2) Detailed Changes

### Component: Framework Bootstrapping

#### [MODIFY] [scripts/install-foundations.sh](file:///Users/polyversai/Libraxis/vc-runtime/vibecrafted/scripts/install-foundations.sh)

- Update `AGENT_PACKAGES` to replace Gemini with `agy`:
  ```diff
  -  "gemini:@google/gemini-cli"
  +  "agy:@google/antigravity-cli"
  ```
- Add the Junie CLI installer reference:
  ```bash
  # Check and register junie npm or binary download channel
  "junie:junie-cli"
  ```

#### [MODIFY] [install.toml](file:///Users/polyversai/Libraxis/vc-runtime/vibecrafted/install.toml)

- Update intro/reason descriptions to cite `antigravity-cli (agy)` and `junie` instead of `gemini-cli`.
- In `[diagnostics.commands]`, replace `gemini` with `agy` and add `junie`:
  ```toml
  agents = ["claude", "codex", "agy", "junie"]
  ```
- In `[diagnostics.paths]`, update target symlinks:
  ```toml
  symlinks = ["$HOME/.agents", "$HOME/.claude", "$HOME/.codex", "$HOME/.agy", "$HOME/.junie"]
  ```

---

### Component: Diagnostics and Installer Scripts

#### [MODIFY] [scripts/vetcoders_install.py](file:///Users/polyversai/Libraxis/vc-runtime/vibecrafted/scripts/vetcoders_install.py)

- Update core metadata list:
  ```python
  AGENT_RUNTIMES = ["codex", "claude", "agy", "junie"]
  SYMLINK_TARGET_CHOICES = ["agents", "claude", "codex", "agy", "junie"]
  ```
- Register version and help-command mappings to identify active executables on path:
  ```python
  "agy": [["--version"], ["help"]],
  "junie": [["--version"], ["-h"]]
  ```
- In shell wrapper code generation blocks, map the `agy-` and `junie-` command variations cleanly.

---

### Component: `skills/vc-scaffold/`

#### [MODIFY] [SKILL.md](file:///Users/polyversai/Libraxis/vc-runtime/vibecrafted/skills/vc-scaffold/SKILL.md)

- Register `agy` and `junie` in the valid agent runtime targets for architecture planning.
- Update model definitions to include JetBrains Junie and Antigravity Gemini configurations.

#### [NEW] [agy.yaml](file:///Users/polyversai/Libraxis/vc-runtime/vibecrafted/skills/vc-scaffold/agents/agy.yaml)

Create the scaffold agent config mapping for `agy`:

```yaml
agent:
  name: agy
  short_description: "Antigravity Gemini CLI - sandboxed, stream-filtered, and highly robust."
  default_prompt: "Use /vc-scaffold to output robust structural plans while leveraging agy sandbox parameters."
```

#### [NEW] [junie.yaml](file:///Users/polyversai/Libraxis/vc-runtime/vibecrafted/skills/vc-scaffold/agents/junie.yaml)

Create the scaffold agent config mapping for `junie`:

```yaml
agent:
  name: junie
  short_description: "JetBrains Junie CLI - standard IDE-centric code generator."
  default_prompt: "Use /vc-scaffold to map clean multi-file plans optimized for Junie's workspace-wide parser."
```

---

## 3) Verification Plan

- Run diagnostic check command:
  ```bash
  python3 scripts/vetcoders_install.py doctor
  ```
- Dry-run install foundations script:
  ```bash
  bash scripts/install-foundations.sh --check
  ```
- Validate scaffold parser loader:
  ```bash
  pytest tests/tui/test_frontier_resolution.py
  ```
