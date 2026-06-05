---
status: draft
owner: codex
date: 2026-06-05
vector: stabilize
---

# Workflow Runtime Extraction

## Current State

Workflow runtime truth is split across:

- `skills/<workflow>/SKILL.md`, `FLOW.md`, references, templates, and agent YAML.
- `skills/vc-agents/shell/lib/*.sh` public shell functions and compatibility wrappers.
- `agents/scripts/*.sh` spawn helpers, watchers, telemetry, filters, and marbles control.
- `vibecrafted-core/vibecrafted_core/workflow*.py` supervised core runtime.
- `agents/vc-marbles/orchestrator/` slash-command and hook substrate.
- Installer surfaces in `scripts/vetcoders_install.py`, `~/.config/vetcoders/vc-skills.sh`, and managed `~/.local/bin/vc-*` wrappers.

This violates the intended boundary: skills should describe operator/worker doctrine, not host launchers. Runtime code needs a first-class home per workflow.

## Target Shape

Each workflow gets one runtime package boundary:

```text
runtime/workflows/<workflow>/
  README.md
  runtime.sh|runtime.py
  telemetry.md
  watchers/
  commands/
  agents/
  templates/
```

The skill directory remains doctrine and references only:

```text
skills/<workflow>/
  SKILL.md
  FLOW.md
  references/
  assets/
```

The command deck (`scripts/vibecrafted`) and core Python runtime call `runtime/workflows/<workflow>/...`; they do not call `skills/.../scripts`.

## Migration Cuts

| State | Vector    | Cut                        | Intent                                                                            | Baseline                                                                 | Delivery Verifier                                                                                                      |
| ----- | --------- | -------------------------- | --------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | ---------------------------------------------------------------------------------------------------------------------- | ------ | --------- | ------------------------------------------------------- |
| [~]   | stabilize | `resume` routing           | `vc-resume codex --runtime terminal --session X` opens a Zellij tab               | direct `codex resume` in current shell                                   | fake-zellij test proves `action new-tab --name resume-codex`, fake codex not called                                    |
| [~]   | stabilize | launcher install repair    | broken managed `~/.local/bin/vibecrafted` symlink gets replaced                   | symlink points at missing `~/.vibecrafted/bin/vibecrafted`               | installer unit test replaces broken symlink with real executable                                                       |
| [ ]   | implement | runtime manifest           | inventory every workflow runtime surface                                          | scattered skills/shell/agents/core                                       | generated manifest lists skill docs, helpers, watchers, telemetry, commands, ACP agents                                |
| [ ]   | implement | `marbles` runtime package  | move marbles launch/watch/control out of `skills/vc-agents`                       | public function resolves `marbles_spawn.sh` through skill store fallback | `vc-marbles codex --count 1 --depth 1 --runtime headless --dry-run` or resolver smoke hits `runtime/workflows/marbles` |
| [ ]   | implement | `research` runtime package | preserve triple-agent async supervision                                           | old shell `vc-research` and new core runtime overlap                     | fake-agent test proves three child tracks plus parent synthesis report                                                 |
| [ ]   | implement | slash commands             | install `/marbles`, `/cancel-marbles`, `/codex-marbles-loop` from runtime package | command payloads embedded in installer                                   | doctor reports commands ok and managed markers installed                                                               |
| [ ]   | implement | ACP agents                 | workflow-specific ACP agents live beside runtime package                          | only `skills/*/agents/openai.yaml`                                       | installer copies runtime ACP agents and doctor detects drift                                                           |
| [ ]   | prune     | skill launcher purge       | no launcher scripts under `skills/`                                               | shell libs still source from `skills/vc-agents`                          | `rg 'spawn                                                                                                             | zellij | osascript | marbles_spawn' skills` returns doctrine-only references |

## Immediate Rule

Until the extraction lands, bugfixes may touch the compatibility shell layer only when they are:

- covered by a regression test,
- described as a bridge,
- not presented as the final architecture.

The final architecture is runtime-first: `runtime/workflows/*` owns execution; `skills/*` owns doctrine.
