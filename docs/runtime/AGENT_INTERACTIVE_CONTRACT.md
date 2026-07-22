# Agent interactive contract — init / resume / operator

Spec for how `vibecrafted init|resume|operator <agent>` must behave.
Applies to the **operator seat** (interactive launcher → vc-frame tab).
Fleet workers (`*_spawn.sh`, marbles baton) stay non-interactive by design.

## Modes

| Mode                | Trigger                                                                              | UI                                                       | Agent invocation                     |
| ------------------- | ------------------------------------------------------------------------------------ | -------------------------------------------------------- | ------------------------------------ |
| **interactive**     | bare `init` / `resume` / `operator`; or `resume --session` without operator job text | Operator tab in vc-frame (or tty)                        | TUI stays open; human can continue   |
| **non-interactive** | explicit `--prompt` / `--file` on resume (job continue); fleet spawn                 | May still _host_ in a tab, but agent **exits** when done | One-shot / print / exec / `--single` |

Codex exception (already implemented): internal AICX continuity pack as a
file is **transport**, not operator job text — bare resume stays interactive.

## Lifecycle (clean install)

1. `vc-start` / `vibecrafted start` → operator layout (`vibecrafted` / `operator.kdl`).
2. Tab **Start here** = Guide / onboarding (map + picker when productized).
3. **Start 1st Operator session** → pick agent + root → `vibecrafted init <agent>`
   → new tab on the **human seat** with `/vc-init` seed, **interactive**.
4. Workers land in `… workers` sessions (G7); not in the human seat.
5. When a supervised worker finishes, runtime triage may move its tab into a
   bucket session (`Finalized runs` / `Failed runs` / `Needs attention`). Board
   `f · x · n` counts those bucket tabs — not control-plane completed rows.
   See [`TRIAGE_AND_SESSIONS.md`](./TRIAGE_AND_SESSIONS.md).

## Per-command

### `vibecrafted init <agent>`

- Always **interactive-only** (`terminal` / `visible`).
- Seed prompt: `/vc-init` (+ optional operator text).
- Grok: positional PROMPT, **no** `--single`, **no** `streaming-json`.

### `vibecrafted resume <agent>`

| Args                              | Mode                                                                                  |
| --------------------------------- | ------------------------------------------------------------------------------------- |
| bare                              | AICX 48h pack → native resume if same-agent session, else **new interactive** session |
| `--session <id>`                  | **interactive** resume of that session                                                |
| `--session` + `--prompt`/`--file` | **non-interactive** continue (job)                                                    |
| bare + `--prompt`/`--file`        | **non-interactive** (job; for codex, explicit input only)                             |

### `vibecrafted operator <agent>`

Same interactive contract as init; seed `/vc-operator`.

## Grok CLI flags (ground truth)

From `grok --help`:

- `[PROMPT]` — interactive session seed (TUI stays open).
- `-p, --single <PROMPT>` — **single-turn, print + exit** (headless only).
- `-r, --resume [SESSION_ID]` — resume session.
- Never use `--restore-code` on resume (clobbers working tree).

## Anti-patterns

- Using `--single` on init / operator / bare interactive resume.
- Treating AICX continuity file as “operator prompt” for mode selection
  (codex rule; other agents should converge on the same intent model).
- Dumping worker tabs into the operator interactive session (G7).

## Ownership

Each agent lane owns its flag matrix. A broken interactive path for one
agent is fixed on that agent only (no cross-agent “make everyone the same
wrong”).
