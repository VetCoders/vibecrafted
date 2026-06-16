# vc-research Runtime

Workflow-owned runtime for the `vc-research` triple-agent research swarm
(skill: `skills/vc-research/`).

## Layout

- `shell/research.sh` — swarm launcher (`vc-research`, `_vetcoders_research`):
  prepares per-agent launchers via the shared spawn scripts, writes the run
  summary, and hangs the research tab on the live vc_frame operator session.
- `shell/research_prompts.sh` — research worker prompt composition
  (`_vetcoders_compose_research_worker_prompt`).

Both modules are sourced by the compatibility facade
(`runtime/shell/vetcoders.sh`) through `_vetcoders_source_workflow_module
vc-research <module>` in the documented load order.

## What stays shared (do not pull in here)

- `runtime/scripts/<agent>_spawn.sh` — research spawns agents through the
  shared frontier spawners (`_vetcoders_spawn_script`), parameterized with
  `VIBECRAFTED_RESEARCH_MODE=1` and the `rsch` skill code.
- `runtime/scripts/await.sh` — `--research` mode lives in the shared awaiter;
  `vc-research-await` and last-finisher synthesis route through it.
- `runtime/scripts/lib/` — launcher/meta/telemetry library.
- `runtime/helpers/vetcoders-runtime-core.sh` — run-id, lock, store-dir and
  research run-dir helpers used both by this workflow and the degraded
  (no-lib) facade path.

Python-side entrypoints (`bin/vc-research*` →
`vibecrafted_core.wrappers.research_*`) are part of vibecrafted-core, not of
this runtime dir.
