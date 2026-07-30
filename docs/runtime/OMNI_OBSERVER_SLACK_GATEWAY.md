# Omni-observer + Slack gateway

## Polarized thesis (single axis — 2026-07-30)

**control_plane is the only durable status truth; vc-server and MCP are
projections of that truth (eyes); the Slack gateway is mouth/ear only;
workers are hands.** Unit green never equals Slack product green —
live `@mention → run_id` requires operator buttons (allowlist + fresh
Socket Mode bridge), not a second status store.

Parent ownership doctrine (same axis, wider domains):
[`docs/adr/0002-unified-operator-ownership.md`](../adr/0002-unified-operator-ownership.md)
— domain `run-lifecycle` owned by `control-plane`; Slack owns `a2a-envelopes`
only, never run status. This file is the gateway-specific contract; the ADR
is not a second truth.

Plan: `vc-server-mcp-slack-gateway` (2026-07-28 scaffold · implement →
marbles fortify → polarize L1–L2 2026-07-30).

### Three surface classes (do not average)

| Class               | What it is                                                            | Authority                                     | Not                                   |
| ------------------- | --------------------------------------------------------------------- | --------------------------------------------- | ------------------------------------- |
| **Board truth**     | runs / events / warnings / settlement on disk under control_plane     | `~/.vibecrafted/control_plane` via dispatcher | Slack messages, unit logs, agent chat |
| **Eye projections** | HTTP `GET /api/control/*` and MCP `vc_board_status` / `vc_run_status` | read models of the same plane                 | independent DBs                       |
| **Gateway policy**  | allowlist, cooldown, STALE/fresh modules, progress rate-limit         | bot process config + measured process age     | board truth                           |

### Rejected alternatives (explicit)

1. **Parallel status DB inside the bot** (`slack_jobs` as board) — job index is thread↔run_id only.
2. **Byte-identical JSON across MCP and HTTP** — envelopes may differ; mission bar is **logical** parity on `active_runs` / `recent_runs` / `warnings` counts and run identity fields.
3. **Merge MCP + HTTP into one package** — W6 dual-process stands; Node bot uses HTTP; IDE keeps stdio MCP.
4. **Unit / e2e green ⇒ product complete** — `e2e-certainty.sh` exits **3** on STALE live bridge by design; empty `SLACK_ALLOW_USERS` is fail-closed.
5. **Agent-owned bridge restart or allowlist write** — operator buttons only.

### Board parity bar (measured)

Shared keys (logical board): `active_runs`, `recent_runs`, `warnings`,
`events`, `generated_at`, `settlement_counts`.

Envelope deltas (not a dual truth):

- HTTP adds `control_plane` path; MCP may expose `orphan_artifacts` /
  `stalled_runs` from direct `sync_state()`.
- `settlement_counts` field bags can differ by projection; do **not**
  invent a third store to reconcile them — re-read control_plane.

Slack `/vc status` and `vc-slack status` read the **HTTP eye** only.

## Architecture

```
Workers / ship / justdo
    │  write (vibecrafted_core dispatcher)
    ▼
~/.vibecrafted/control_plane/     ← single source of truth
    │
    ├─► vc-server (HTTP read + SSE)     omni-observer UI + API  :3024
    ├─► vibecrafted-mcp (stdio MCP)     same logical board for agents
    │
    └─► Slack gateway (Socket Mode)     human ↔ fleet connector
            │  read: GET /api/control/*   (HTTP eye — not local status)
            │  write (dispatch only): vibecrafted justdo …
            ▼
        #agents-room threads (run_id, status, report path)
```

## Measured curls (operator host)

```bash
# health (constant-time readiness)
curl -s http://127.0.0.1:3024/api/health
# → {"schema":"vibecrafted.health.v1","status":"ok"}

# board slice used by /vc status and MCP vc_board_status
curl -s http://127.0.0.1:3024/api/control/state | python3 -m json.tool | head

# one run
curl -s http://127.0.0.1:3024/api/control/runs/<run_id> | python3 -m json.tool | head

# lifecycle list
curl -s http://127.0.0.1:3024/api/control/lifecycle | python3 -c 'import sys,json;print(json.load(sys.stdin).get("count"),"lifecycle runs")'
```

Env override: `VC_SERVER_URL` (default `http://127.0.0.1:3024`).  
Home override: `$VIBECRAFTED_HOME` (default `~/.vibecrafted`).

## Bot surfaces (vibecrafted-slack-agent)

| Surface                              | Backend                                      |
| ------------------------------------ | -------------------------------------------- |
| `/vc status` · `vc-slack status`     | `GET /api/health` + `GET /api/control/state` |
| `/vc run <id>` · `vc-slack run <id>` | `GET /api/control/runs/{id}`                 |

PATH install: `ln -sfn <repo>/bin/vc-slack ~/.local/bin/vc-slack` is supported.
`bin/vc-slack` **resolves symlinks** before setting `ROOT` so `status`/`run`
load package `src/cli-*.js` (not `~/.local/src/…`). Always-on proof uses the
package path or a correctly linked PATH entry — not a broken install tree.
| `@Vibecrafted justdo <root> <prompt>` | allowlist → `vibecrafted justdo <agent> --json …` → thread `run_id` → progress posts → terminal |
| `vc-slack signal` / lifecycle hook | Slack post only (does not invent control_plane state) |

Allowlist: `SLACK_ALLOW_USERS`. Default agent: `VC_DEFAULT_AGENT=grok`.

Dispatch policy (gateway, not control_plane):

- empty allowlist ⇒ fail-closed (read-only)
- per-user cooldown (`VC_DISPATCH_COOLDOWN_MS`, default 30s)
- max concurrent jobs per user (`VC_DISPATCH_MAX_CONCURRENT`, default 3)
- intermediate `*progress*` posts on state/health/liveness/report key change (first always; then `VC_PROGRESS_MIN_MS`)
- ≤5s product SLA = receipt-in-thread (`run_id`), not worker terminal
- `/vc status` (in-process) prints **measured** bridge freshness: `code_mtime`
  vs process start → `modules=STALE|fresh`
- `vc-slack status` (CLI) discovers the live `node src/index.js` for the package
  via pgrep/lsof/ps → `live_bridge_pid` + `modules=STALE|fresh` _(out-of-process)_
  so a multi-day-old bridge cannot hide behind `bridge_modules=n/a`
- `e2e-certainty.sh` **exits 3** when a live bridge is STALE (unit green ≠ Slack green)
- empty allowlist deny ≠ "user not listed" (distinct messages)
- dispatch cooldown starts only after a real `run_id` receipt (failed spawn does not burn cooldown)
- board `warnings` from control state appear on status (eye, not a second store)

Workers do **not** need Slack. Example visibility path:

1. Worker finishes → control_plane meta/report written by dispatcher
2. Operator (or bot) reads `GET /api/control/runs/{id}` or `/vc run {id}`
3. Optional human bus: `scripts/vc-slack-hook.sh` / `vc-slack signal` from hook policy

## MCP dual-run (W6 decision)

HTTP is sufficient for the Node gateway. Prefer:

- always-on: `vibecrafted server start` (or equivalent) on `:3024`
- IDE: stdio `vibecrafted-mcp` with existing tools (`vc_board_status`, `vc_launch`, …)

Do **not** merge packages unless a single MCP-HTTP binary is explicitly required. Mutating MCP tools stay permissioned; Slack gateway uses shell launch for allowlisted humans.

## Always-on

- vc-server: first-class `vibecrafted server start|status|stop`
- Slack bridge: `npm start` in `vibecrafted-slack-agent` or LaunchAgent example  
  `deploy/com.vetcoders.vibecrafted-slack-bridge.plist.example` in that repo
- Certainty script: `vibecrafted-slack-agent/scripts/e2e-certainty.sh` (full `npm test` + live board)
- **Restart the Socket Mode bridge after every pull** — Node does not hot-reload
  `dispatch.js`; a stale process can green unit tests while Slack still lacks
  intermediate `*progress*` / rate-limit behavior. Proof surfaces:
  - `/vc status` → `modules=fresh` (in-process)
  - `vc-slack status` → `live_bridge_pid=… modules=fresh` (out-of-process)
  - `./scripts/e2e-certainty.sh` fails with exit 3 while STALE
    Operator smoke: set `SLACK_ALLOW_USERS` → restart bridge → status shows
    `modules=fresh` + non-zero allowlist → `@Vibecrafted justdo …` →
    `curl /api/control/runs/{id}`

## Invariants

1. No secrets in git; tokens only `~/.keys` / `.env`.
2. Bot never claims verifier `[x]` without control_plane / report evidence.
3. Offline observer → `ObserverOffline` within a few seconds; slash still acks.
4. Empty `SLACK_ALLOW_USERS` ⇒ fail-closed dispatch (read-only gateway).

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
