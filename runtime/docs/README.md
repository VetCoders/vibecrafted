# Runtime Boundary Notes (Phase 1)

Phase 1 keeps the launcher contract stable while extracting a focused helper
surface into `runtime/helpers`.

- Source path for commands: `skills/vc-agents/shell/vetcoders.sh`
- Canonical helper source: `runtime/helpers/vetcoders-runtime-core.sh`
- Responsibility: helper runtime + path/repo/store/session/research primitives
- Responsibility retained in skill shim: command wrappers, user-facing aliases, and
  command registration for backward compatibility.

The next migration phase can move spawn orchestration helpers and runtime scripts
in the same way, but only after command and tests stay green in this phase.
