---
title: Runtime Feedback Ledger
kind: doctrine_feedback
version: 1.0.0
description: "Per-command correction ledger: every faulty execution becomes an actionable feedback message with the correct usage and on-disk evidence."
scope: framework
status: active
---

# 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. Runtime Feedback Ledger

> Every incorrect execution is a data point. This ledger turns friction into
> per-command correction prompts so no agent repeats a mistake the fleet has
> already paid for. Read it the way you read the
> [Delegation Matrix](DELEGATION_MATRIX.md): as doctrine, not as history.

## Feedback message model

Each entry is keyed by the **command or action** that was executed incorrectly
and carries exactly three fields:

- **❌ Observed** — what actually happened (context + outcome).
- **✅ Correct** — the correct command usage or behavior, copy-pasteable.
- **Evidence** — date, run_id/commit, artifact path. No evidence, no entry.

Lifecycle: incident → entry here (same day) → when a pattern recurs or the fix
belongs in code, promote it to a runtime fix, a hook, or a skill clause and
link the promotion. An entry without a promotion path after 3 recurrences is a
process failure. Entries are appended, never silently rewritten; superseded
entries get a `Promoted:` line, not deletion.

---

## Ledger

### `vibecrafted <launcher> <agent>` (re-dispatch after a dead run)

- **❌ Observed:** After a worker died mid-run, a fresh `workflow` dispatch was
  issued (twice). Cold context: the successor re-reads the repo, re-derives the
  plan, and can die on the same cold start. One successor died within ~2 min.
- **✅ Correct:** First move is `vibecrafted resume <agent> --session
<agent_session_id> --prompt "<what happened + tree delta + what to finish>"`.
  The dead session holds the full working context. Fresh dispatch only when the
  session is unrecoverable.
- **Evidence:** 2026-07-25, aicx repo: cold recoveries `work-260725-115446-86000`
  (died ~2 min) vs resumed session `019f9894…` → commit `3b7d670` delivered.

### `vibecrafted resume <agent> --session <id>` (session identity)

- **❌ Observed:** `session_id` was taken from the control-plane record
  (`~/.vibecrafted/control_plane/runs/<run_id>.json`). That is the
  **vibecrafted** session id, not the agent's — resume answered
  `404 Not Found, restoring from remote` and died at 283 bytes of stream.
- **✅ Correct:** Use the agent-native id: grok → `ls -t
~/.grok/sessions/<url-encoded-cwd>/` (uuidv7 dirs; match mtime to the death
  time), claude → `~/.claude/projects/<encoded-cwd>/<uuid>.jsonl`; for
  completed runs the id is in the report frontmatter. Verify format per agent
  before launching.
- **Evidence:** 2026-07-25 11:57 stream `resume/grok-20260725-115749.stream.jsonl`
  (404) vs 11:59 resume of `019f9894-c578-7800-8c5a-dd76f004dc8c` (worked).

### `vibecrafted <agent> await --run-id …` (trusting the green)

- **❌ Observed:** Await returned `completed / rc=0 / report_delivered` on an
  **untouched launcher template** — the launcher pre-seeds the report file at
  spawn, and `_report_file_written` accepted any non-empty file. Silent false
  green on dead workers.
- **✅ Correct:** Never treat `await_rc=0` alone as delivery. Verify the report
  frontmatter: `head -8 <report> | grep 'finalized: true'` plus a non-empty
  `claim`. Fixed in runtime by `068428bc` (template ≠ delivery, `finalized`
  attests terminal); the supervisor-side frontmatter check stays as
  belt-and-braces.
- **Evidence:** 2026-07-25 run `work-260725-112151-88000`
  (`await_outcome: completed` on a template); fix `068428bc`, 52/52
  `test_control_plane.py`.

### Declaring a run dead (recovery trigger)

- **❌ Observed:** `launcher_pid` dead + silent vibecrafted transcript was read
  as "worker dead". Three same-day counterexamples: workers survived their
  launchers, kept working blind to the control plane, and one delivered a full
  commit _after_ its run was declared stopped.
- **✅ Correct:** Before recovery, check **all three**: (1) `worker_pid` via
  `kill -0`, (2) mtime of the **agent-native** session file (not the launcher
  pipe), (3) uncommitted diff progression in the target repo. Launcher death
  with a live worker means _watch, don't redispatch_ — a second worker on the
  same tree is a Living-Tree collision.
- **Evidence:** 2026-07-25: claude worker 59360 alive → commit `068428bc` after
  launcher 58811 died; "stopped" run's worker delivered `3b7d670`.

### Supervisor watch scripts (monitors around runs)

- **❌ Observed:** Two false "FINALIZED" notifications from sloppy watch
  one-liners: `ls | head -1` (alphabetical, wrong file) and `grep -q
'finalized: true'` matching a **quote in the report body** instead of the
  frontmatter.
- **✅ Correct:** Anchor frontmatter checks to `head -8`; pick newest files with
  `ls -t`; watch the agent-native transcript/session file, not the launcher
  stream; cover every terminal state (success _and_ death), not just the happy
  path.
- **Evidence:** 2026-07-25 monitors `bgilttlr3`/`byb31gua4` (false) vs
  `b1dyhpsyk` (correct pattern).

### Dispatch root (`--file`/`--prompt` from the wrong directory)

- **❌ Observed:** A fix dispatch was aimed at an empty stub checkout
  (`vetcoders/loctree-suite`) instead of the live repo
  (`loctree/loctree-suite`); the worker had to be redirected mid-run.
- **✅ Correct:** Before dispatch: `git -C <root> log --oneline -3` (does the
  history match the work you're citing?) and launch from the repo root the
  evidence came from. The launch receipt echoes `root:` — read it before
  arming await.
- **Evidence:** 2026-07-25 morning, loctree-suite mis-dispatch (pre-compaction).

### Building in a live dispatched repo

- **❌ Observed:** Supervisor started `cargo build` in a repo where a worker was
  mid-run: shared `target/` lock + mixed tree states race the worker.
- **✅ Correct:** Never build/test in a tree a worker is actively mutating.
  Verify on an isolated clone, or wait for the worker's terminal state. After a
  worker dies mid-build, its `target/` is warm — tell the successor to keep it.
- **Evidence:** 2026-07-25, racing build vs `work-260725-103320-02000`, killed;
  isolated clone used instead.

### Provider failure at launch (5xx from an agent line)

- **❌ Observed:** Codex line returned 503 (`circuit_open`) at spawn.
- **✅ Correct:** That is a service failure, not a prompt failure: re-dispatch
  the same brief to another line immediately; the commit signature becomes the
  **executing** agent's (`Authored-By: <actual-agent>`), per the matrix.
- **Evidence:** 2026-07-25 codex 503 → claude took the stall-detector cut →
  `068428bc`.

### Recovery brief content (spec addendum)

- **❌ Observed:** (near-miss) A successor could have discarded 563 uncommitted
  lines its predecessor wrote before dying, or committed a parallel agent's
  release work.
- **✅ Correct:** Every recovery brief carries a **tree-state addendum**: what
  the predecessor left uncommitted (_adopt, don't discard_), which dirty files
  belong to other agents (_avoid_), which gates were not yet run. First
  successor move is `git diff` of the named files.
- **Evidence:** 2026-07-25 ADDENDUM 2 in `specs/loctree-literal-boost.md` →
  successor adopted the diff → `cf9d7b62` with clean gates.

### `aicx intents` at scale (supervisor context budget)

- **❌ Observed:** A raw `intents` pull (133 KB / 1000+ lines) landed in the
  supervisor's own context during an audit.
- **✅ Correct:** For audit-scale retrieval, delegate reduction to a subagent
  reading the persisted result file; the supervisor consumes the bounded
  candidate list. Use `--slim --collapse-session` and exact project identity
  first.
- **Evidence:** 2026-07-25 vc-intents audit of codescribe (two-subagent sweep).

### `grep`/`rg` on working repos (zero-fallback)

- **❌ Observed:** Reflexive grep on repos where loctree has a snapshot; when
  loctree genuinely missed a surface, the gap went unrecorded.
- **✅ Correct:** `loct find --literal` / loctree-mcp `find` for anything
  identifier-shaped; grep only for non-AST literal text. When loctree can't
  answer, **append the hak** to `~/.vibecrafted/loctree/loctree-fail.md` and
  fall back loudly — the backlog is the feedback channel.
- **Evidence:** 2026-07-25 zero-fallback audit: 8/9 greps were agent reflex,
  2 real loctree defects → both fixed same day (`eed8b22b`, `cf9d7b62`).

---

## Session-start surfacing

This ledger is referenced from the [Delegation Matrix](DELEGATION_MATRIX.md)
(always loaded with fleet skills) and surfaced at session start by the
operator's AICX living-tree hook. Workers receive it whenever a brief cites a
command listed here — cite the entry, not the whole file.

## Canonical references

- [Delegation Matrix](DELEGATION_MATRIX.md) — invocation & delegation authority
- [Living Tree Rule](LIVING_TREE_RULE.md) — shared-tree discipline behind the
  recovery and build entries
- [`vc-dispatch`](vc-dispatch/SKILL.md) — external fleet lines, await/observe
- [`vc-operator`](vc-operator/SKILL.md) — multi-wave supervision posture
- Loctree hak backlog: `~/.vibecrafted/loctree/loctree-fail.md` (operator-side,
  append-only)

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI
