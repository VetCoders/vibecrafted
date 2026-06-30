# vc-intents audit — 2026-04-29

Bounded intent-to-runtime audit of `vc-operator` (Vibecrafted Operator Console).

**Worker:** claude (vc-agents native, Opus 4.7)
**Scope:** intentions extracted from `NEXT_STEPS.md`, `NEXT_STEPS_AGNOSTIC.md`, and the operator video review at `Screen_Recording_2026-04-25_at_06.54.04_report.md`, verified against runtime code in `src/` and `tests/`.
**Full report:** see the artifacts path below.

## Verdict in one sentence

The TUI's self-tests pass for the launch-string contract, but the operator-facing surface still lies on three intertwined fronts: the panel says "Live queue" while the loader returns every `runs/*.json` ever written (including 25-day-old completed runs), there is no operator-side eviction primitive so the dashboard can only grow, and the prompt editor that the dispatch flow funnels every operator into is a single-line `String` with no modal.

## Coverage

| Status       | Count  |
| ------------ | ------ |
| `done`       | 4      |
| `partial`    | 5      |
| `superseded` | 2      |
| `missing`    | 9      |
| **Total**    | **20** |

`done`-rate against deduped intent surface: **20%**.

## Highest-leverage next moves

1. **Eviction + freshness for the live queue (V#1 + V#2).** Add `Char('x')` archive action + a real time slice for "Live"; closes three video items at once.
2. **Subprocess error pipeline → status_line + ErrorOverlay (A#3 + A#10 + B#7).** Capture child stderr, surface in status_line, add `LaunchFocus::Error(String)` overlay. Fixes silent-fail UX after `q`-exits.
3. **Multiline prompt modal (V#7 + V#8 + V#9).** Promote the prompt editor to a Ratatui overlay with `\n` support and a save toast.

## Full report

`/Users/tester/.vibecrafted/artifacts/Vetcoders/vc-operator/2026_0429/reports/20260429_215131_20260429_2151_perform-the-vc-intents-skill-on-this-repositor_claude.md`

(Also reachable via the local symlink: `.vibecrafted/reports/20260429_215131_…_claude.md`.)

## What was inspected

| Surface                                             | Path                      | LOC |
| --------------------------------------------------- | ------------------------- | --- |
| Library entry, key handler, suspend_and_run         | `src/lib.rs`              | 423 |
| App state, deep actions, dispatch state machine     | `src/app.rs`              | 663 |
| Ratatui draw functions, three tabs, help overlay    | `src/ui.rs`               | 675 |
| Control-plane state loader, classification, age     | `src/state.rs`            | 412 |
| Launch command builder, vc_frame layout, env join   | `src/launch.rs`           | 269 |
| Config + CLI parser                                 | `src/config.rs`           | 189 |
| Integration tests (state contract + launch builder) | `tests/state_contract.rs` | 499 |

## Key shape findings

### Done (and why it matters)

1. **In-place vc_frame multiplexer hand-off** is real. `build_terminal_launch_command` (`src/launch.rs:181-202`) emits `vc_frame options --config-dir … --layout-string …` with the deck `exec` quoted into a bash pane. `tests/state_contract.rs:148-189` pins the exact layout string. This was the most architecturally consequential intent — and it landed cleanly.
2. **TTY hygiene around subprocess launch** is real. `suspend_and_run` (`src/lib.rs:248-266`) restores raw mode + alternate screen even when the launched child fails — `leave_result?` and `raw_result?` run before `launch_result?`.

### Superseded (be honest about which plan died)

The Ghostty-first plan in `NEXT_STEPS.md` is dead. Items A#1 (Ghostty env), A#2 (Ghostty-vc-frame chain), A#4 (`terminal_binary`), A#6 ("new Ghostty window" for reports) all replaced by the terminal-agnostic shape from `NEXT_STEPS_AGNOSTIC.md`. Documenting this so the next worker doesn't re-implement Ghostty wrappers.

### The unresolved 9 (ranked by user-visible impact)

- The `Live queue` panel keeps growing forever (no GC, no time slice, no eviction).
- No `delete`/`archive`/`dismiss` action — operator audit V#2.
- Subprocess errors silently take down the TUI — A#3 + A#10 + B#7.
- Prompt editor is a single-line `String` with no save feedback — V#7-V#9.
- No `notify` async watcher; UI refreshes on a 250ms poll only — B#5.
- No `arboard` clipboard — B#8.
- No `/` fuzzy search — B#9.
- No native Ratatui pager — A#8 + B#6.
- No tooling autodetection (Zoxide/Starship/Atuin) — B#4.

See the full report for evidence per item.
