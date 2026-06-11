# Runtime Boundary Notes

The launcher contract is stable enough to document as live runtime. Historical
phase language belongs in roadmap notes, not in this directory index.

- Source path for commands: `../../runtime/shell/vetcoders.sh`
- Canonical helper source: `runtime/helpers/vetcoders-runtime-core.sh`
- Responsibility: helper runtime + path/repo/store/session/research primitives
- Responsibility retained in shell facade: command wrappers, user-facing
  aliases, and command registration for backward compatibility.

`runtime/scripts/` is active. `runtime/vc-*` directories show the extraction
pattern for workflow-specific runtime.
