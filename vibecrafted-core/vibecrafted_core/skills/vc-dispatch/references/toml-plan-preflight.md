# Authoring & pre-flighting a `.dispatch.toml` plan (field-learned)

Evidence base: sessions-rail-live-buckets line, 2026-08-09 (3-cut sequential
line, claude workers, deployed CLI 3.7.0). Every rule below was hit live.

## Schema authority

- The reference is `docs/public/dispatch/dispatch-schema.md` + `--doctor`.
  The parser fails closed; do not author fields from memory. Validate with
  `vibecrafted dispatch <plan> --doctor` BEFORE anything else.
- `--doctor` emits **informational warnings** for model pins ("pin will be
  forwarded; provider/account availability is not validated") — warnings are
  not errors; pin per cut class anyway (mechanical → cheap tier, surgical /
  decision-bearing → strong tier).

## Renderer truth (braces)

`_format_known` (`dispatch/schema.py`) substitutes **only known** `{name}`
placeholders (`{repo}` `{id}` `{agent}` `{workflow}` `{resolved_workflow}`
`{reports_dir}` `{tracker}` `{baton}` — prompts only for baton). Unknown
braces pass through untouched. Consequences:

- `env=dict()`-style Python in verify `run` commands is safe; so is `{}`.
- **`{baton}` renders as JSON — rendered prompts legitimately contain
  braces.** A naive `grep -c '{'` unrendered-placeholder gate false-positives
  on every prompt that carries a baton. The correct gate greps for the
  _known placeholder tokens_ still present after rendering:

  ```bash
  grep -nE '\{(repo|id|agent|workflow|resolved_workflow|reports_dir|tracker|baton)\}' \
    <reports_dir>/dry-run/prompts/*.md   # expect: no output
  ```

## Verify gates: two techniques that make them non-trivial

1. **Prove `-k` selections are non-empty** before the line moves — a gate
   matching 0 tests is trivially green:

   ```bash
   uv run pytest <file> -k '<expr>' --collect-only -q   # expect ≥1 collected
   ```

2. **Semantic probe verifiers**: a deterministic `python -c` probe that
   returns the OLD value today and MUST return the NEW value after the cut.
   Pre-flight it live: today's output proves the command is syntactically
   valid AND that the gate cannot pass without the work landing. Example
   pair from the sessions-rail line:

   ```toml
   [[cuts.verify]]
   run = '''cd {repo} && uv run python -c "from vibecrafted_core.workflow import _effective_operator_session as f; print(f(root='/x/demo', run_id='r', env=dict()))"'''
   expect = { equals = "demo workers", exit_code = 0 }   # today prints "demo"
   ```

   For env-sensitive probes, force non-TTY with `</dev/null` and inject env
   inline (`env KEY=val …`) so the probe is hermetic.

## TOML escaping

- Verify `run` commands mixing single and double quotes: use multi-line
  literal strings `'''…'''` (fine on one line) — zero escaping.
- Keep **prompts** brace-free except real placeholders; put brace-bearing
  code only in `run` commands (renderer passes them through).

## Dry-run layout

`--dry-run` writes under `reports_dir/dry-run/`: `prompts/<cut-id>.md`,
`tracker.md`, `validated-dispatch.toml`, `dispatch-result.json`. Inspect the
rendered prompts (placeholder gate above) before the real launch.

## Deployed CLI vs checkout (push ≠ install, line edition)

The supervisor and its workers run from the **deployed tools home**
(`vibecrafted --version` → `X.Y.Z+g<sha>`), not from the checkout the cuts
edit. A line whose cuts change runtime/dispatch behavior does NOT change the
behavior of the very line executing it — expect the old behavior for the
whole flight, and leave `make install` as the operator's post-line button.
Corollary: a cut can demonstrably _reproduce_ the bug it fixes while flying.

## Living Tree concurrency clause

When other sessions edit the same checkout during the line, say so in
`[common]` explicitly: name the concurrent work, require re-reading each
file's current state before editing, and state that `git add -A` sweeps are
commitment, not destruction. Workers must not "protect" themselves with
worktrees or branch switches.

## Launch shape

```bash
bash -c 'ulimit -f unlimited; exec vibecrafted dispatch <plan> --json'   # detached/background
```

Receipt = supervisor-written `tracker.md` (single writer, baseline branch +
head) plus the first worker's run_id in the control plane. Then spanko:
await through artifacts and the task/await notification — no pane staring,
no hedge pollers.

## Substrate contract pair + recovery (field-learned, flights 2–4)

`require_commit` WRITE cuts sit between **two symmetric gates**
(`dispatch/supervisor.py::_run_cut`): the cut refuses to START from a dirty
worktree, and refuses to END with uncommitted changes. A worker that edits,
passes verification, then dies before committing (gate-nap: waiting on a
Monitor/wakeup instead of committing — Class 3, `AGENT_OPS.md`) therefore
deadlocks the line: the orphan delivery blocks every refire.

- **Dispatcher recovery**: review the orphan diff against the brief (the
  orphan often delivers), commit it yourself with the cut id in the subject
  and the orphan run's provenance in the body, THEN resume. Never discard.
- **`repair_rounds` does not fire** on `CellContractError` — repair covers
  red verifiers, not substrate contract breaks.
- **A failed resume clobbers the tracker**: every dispatch run rewrites
  `tracker.md` at start, so a resume that dies on a substrate gate erases
  prior `[x]` states and the NEXT resume restarts from the first cut. Keep
  the delivered commit SHAs in the journal/notes — you will need them.
- **Idempotent settle needs explicit proof**
  (`supervisor.py::_existing_delivery_commit`): a worker that finds the work
  already landed must put a standalone line `commit: <sha>` in its report;
  the supervisor accepts it only if the sha resolves, is an ancestor of
  HEAD, and the commit message identifies the cut (keep `[<cut-id>]` in
  delivery commit subjects). Bake this clause into `[common]` from the
  start — "nothing to do" without the proof line is a contract failure, and
  a full-line idempotent resume is also the clean way to re-settle a
  clobbered tracker.
