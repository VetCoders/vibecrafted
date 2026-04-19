# Vibecrafted Operator Console

This crate is the Rust TUI operator console for Vibecrafted.

It is intentionally separate from the Python installer surfaces and only reads
the shared control-plane state under `VIBECRAFTED_HOME`.

## Interface model

The operator surface is split into three tabs so the console reads like a
dispatcher station instead of a crowded single dashboard:

- `Monitor`: live runs, selected run detail, and recent events
- `Dispatch`: mission kind, agent, runtime, prompt, and launch history
- `Controls`: attach/resume/report/transcript actions for the selected run

Use `Tab` / `Shift+Tab` to switch tabs. Arrow keys stay local to the active
tab, so `Monitor` moves through runs, `Dispatch` moves through launch fields,
and `Controls` moves through deep actions.

## Expected state layout

The console reads the local control-plane contract:

```text
$VIBECRAFTED_HOME/control_plane/
  runs/*.json
  events.jsonl
```

The writer is `scripts/control_plane_state.py`. The reader is strict about
that shape: it does not follow symlinks out of the root and ignores anything
outside the control-plane directory. `config::default_state_root` falls back to
historical variants (`state/control-plane`, `state`, `control-plane`) if the
canonical `control_plane` path is missing, so older layouts keep loading.

## Launching workflows

The TUI shells out to the existing `vibecrafted` command deck when you launch a
workflow, research, review, or marbles run. Launches carry an explicit runtime
and repo root so the Rust surface stays aligned with the shared control-plane
launcher contract instead of inheriting whatever shell state happened to start
the console.

Use `v` to cycle `terminal` / `visible` / `headless` launch modes and `d` on a
selected run to enter deep controls for attach / resume / report / transcript
actions.

## Run

```bash
cargo run --manifest-path operator-tui/Cargo.toml -- --state-root "$VIBECRAFTED_HOME/control_plane"
# optional:
#   --runtime terminal
#   --root /path/to/repo
```

If you install the crate as a binary, it exposes both `vibecrafted-operator`
and the shorter `vc-operator` entrypoint.
