# Restore Contract (honest)

Product promise for **update / reinstall / detach** — what comes back, and what does not.

This document exists so installer copy, update prompts, and marketing never
outrun the engine (audit SF-6).

## Layers

| Layer                  | Identity                    | Survivability                                                                                     |
| ---------------------- | --------------------------- | ------------------------------------------------------------------------------------------------- |
| **Workspace**          | vc-frame session name       | Detach + session serialization can resurrect **layout, tabs, panes, cwd, command line to re-run** |
| **Pane**               | `PaneId` / terminal pane id | Slot in the workspace; process may need re-exec after host reboot                                 |
| **Run**                | vibecrafted `run_id`        | Control-plane ledger + report + transcript on disk                                                |
| **Agent conversation** | provider session / AICX     | Durable JSONL / catalog — **not** the same as a live pane process                                 |

## Guaranteed (when features are enabled)

With product config:

- `on_force_close "detach"`
- `session_serialization true`
- `serialize_pane_viewport true` (bounded scrollback)

Then:

1. **Close the client terminal** → sessions detach; reattach with `vc-start` / `vc-frame attach <name>`.
2. **Reinstall framework tools under lease** → launcher + skills update; **existing frame sessions are not deliberately killed** by config install alone.
3. **After binary swap of vc-frame** → resurrectable sessions may reappear via frame cache; **verify** with `vc-frame list` / doctor. Cross-version resurrection is **best-effort**, not a legal guarantee until e2e green.

## Explicitly NOT guaranteed

- Live **in-flight** LLM tool calls mid-token after host reboot.
- Agent **RAM** / open network sockets after kill -9 or power loss.
- Identity of a pane process after force-kill of the frame server.
- “Exactly the same scrollback forever” beyond `scrollback_lines_to_serialize`.

## Allowed product copy

**OK:**

> Your vc-frame session layout will be restored where the engine supports resurrection. Control-plane runs keep their `run_id`, reports, and transcripts on disk. Detach is safe; kill-session is deliberate.

**Not OK (until e2e proves otherwise):**

> All agent sessions return to exactly the same state you see now.

## Installer / update UX

- Post-install launch offers **Start here** cockpit (`vc-start`) — onboarding content, not restore magic.
- Update prompts must cite this contract or the narrower sentence above.
- Auto-update must not silent-swap binaries while claiming full agent restore.

## Verification checklist (before widening copy)

1. Two sessions (operator + agent room) → `vibecrafted update` → both listed with layout.
2. Detach client → reattach → panes present.
3. Host reboot → resurrect list non-empty OR honest “none” with next steps.
4. Kill-session → does **not** auto-return (operator intent).
