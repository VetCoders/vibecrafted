# Living Tree Rule

VetCoders work in one shared repository checkout.

Vibecrafted workflows do **not** create, switch to, or move work into git
worktrees by default. Worktrees are not a harmless implementation detail here:
they split runtime truth, hide concurrent edits, multiply merge surfaces, and
turn fast Vibecraftsmanship into branch archaeology.

## Hard Rule

- Work in the current checkout and current branch.
- Do not run `git worktree add`, create a side checkout, or relocate execution
  into another lane.
- Do not switch branches during active workflow execution.
- Do not create branches unless the operator explicitly asks for that git move.
- Re-read files before editing when time has passed or concurrent agents may be
  active.
- Treat local changes as shared work. Never stash, discard, reset, or overwrite
  changes you did not make.

## Only Exception

A worktree is allowed only when the operator explicitly says to use a worktree.
Generic requests like "isolate this", "work in parallel", "make a clean branch",
or "avoid conflicts" are not enough.

If the current substrate is too poisoned to continue safely, stop and report the
substrate failure. Do not solve substrate invalidity by escaping into a worktree.

## Why

Vibecrafting optimizes for rapid convergence on runtime truth. The pace is the
point. We do not move that fast so that a stale side tree can later force the
team into rebase drift, duplicate conflict repair, or backwards motion.

Training-data defaults about worktrees are subordinate to this repository
doctrine.

## Race-protection helper (added 2026-05-12, Plan 07)

Living Tree disciplines parallel work but does not by itself make
`git commit --only path1 path2` atomic against another agent's
simultaneous commit on the same branch. Kronika 2026-04-16/17 captured the
exact failure mode: under concurrent activity, one agent's commit message
can land under another agent's tree envelope.

Plan 07 ships a reusable primitive that detects this race after the fact
and refuses to silently accept the unsafe commit.

**Operator-facing entry point**:

```
make commit-safe MSG="<commit message>" FILES="path1 path2 ..."
```

**Direct shell invocation**:

```
scripts/lib/living-tree-commit.sh "<commit message>" -- path1 path2 ...
```

The helper captures pre-flight `HEAD`, stages only the named files, snapshots
the staged tree, then commits. After the commit it cross-checks three
invariants:

1. The new commit's parent equals the pre-flight `HEAD` (no concurrent
   commit slipped in via ref update).
2. The new commit's tree matches the staged-tree fingerprint (no foreign
   index mutation rode in on the commit).
3. The set of files changed by the commit matches the staged-files
   snapshot exactly (no foreign files in the envelope).

On race the helper prints both commit SHAs plus the foreign-file list,
offers two operator-driven recovery options, and exits nonzero. It does
**not** auto-amend, auto-reset, or auto-rebase. Recovery is intentionally
operator-driven, consistent with the rest of this rule.

The helper enforces the existing safety rule against wildcard staging:
arguments like `.`, `-A`, `--all`, `-a` are rejected. Name the files.

Verification:

```
make test-race-protection
```

The test suite at `tests/race_protection_test.sh` exercises both the
clean-commit path and two synthetic race injections (concurrent ref update
and foreign-index mutation).

## Plan 07-b helper limitations closure (2026-05-12)

Plan 07's first cut shipped the race detector with two known limitations
that were confirmed across four follow-up marble rounds. Plan 07-b closes
both. Cross-references: marble reports for Plan 04 (Cut D), Plan 03
(Cut F), and Plan 06 (Cut H) document the false-positives that prompted
this work; the Plan 07-b report at
`.vibecrafted/reports/marbles/2026_0512/plan-07b-helper-limitations-fix.md`
captures the closure evidence.

### Limitation #1 — pre-commit hook false-positive (3 confirmations)

The repo's `scripts/hooks/pre-commit` runs `prettier --write` followed by
`git add` on `.md`/`.yaml` files. That happens AFTER the helper's
`git write-tree` snapshot but BEFORE the commit's final tree is sealed.
The original tree-hash detector tripped on the cosmetic content change
and reported a race even though the commit was correct. Operators saw
exit code 3 + "RACE DETECTED" diagnostics on perfectly legitimate
commits.

**Fix**: tree-hash mismatch alone is no longer a race signal. The race
detector now treats the three primitives asymmetrically:

- **HEAD shift** — hard race signal (another commit landed via ref update).
- **Foreign files** — hard race signal (extra files in the commit envelope).
- **Tree-hash mismatch** — informational. Only contributes to a race
  diagnostic when one of the hard signals also fires. With clean HEAD
  and matching file set, the helper now emits `notice — pre-commit hooks
rewrote content; not a race` and exits 0.

**Trade-off**: a hypothetical race that mutates ONLY the content of staged
files (without adding/removing files and without shifting HEAD) would
now slip through. We accept this — no such race has been observed in
four plan rounds, and the original kronika 2026-04-16/17 incident is
caught by the foreign-file detector (which remains strict).

### Limitation #2 — multi-line MSG quoting (1 confirmation in Plan 06)

`make commit-safe MSG="..."` failed on multi-line message bodies due to
Makefile `$$` escaping vs. shell expansion. Plan 06 worked around by
calling `scripts/lib/living-tree-commit.sh` directly with a heredoc.

**Fix**: the helper now accepts `--message-file <path>` as an alternative
to the positional message argument. The Makefile target gains a
`MSG_FILE=<path>` parameter that maps to it. Both invocation modes work;
they are mutually exclusive per invocation.

**Multi-line usage**:

```
cat >/tmp/commit.msg <<'EOF'
plan-XX subject line

Body paragraph one with "quotes" and $shell-style references intact.

- bullet one
- bullet two
EOF

make commit-safe MSG_FILE=/tmp/commit.msg FILES="path1 path2"
```

**Direct shell**:

```
scripts/lib/living-tree-commit.sh --message-file /tmp/commit.msg -- path1 path2
```

Single-line `MSG="..."` continues to work unchanged. Plans 04/03/06
fallback paths that called the helper directly are not affected.

### Verification

The expanded `tests/race_protection_test.sh` adds two positive cases:

- `[positive-C]` simulates a pre-commit hook that prettier-style rewrites
  staged `.md` content. Helper must exit 0 and emit the hook-modified
  notice.
- `[positive-D]` exercises `--message-file` with a body containing
  embedded newlines, single/double quotes, `$shell` references, and
  backticks. All preserved verbatim in the committed body.

Existing 10 assertions (clean-commit + 2 race injections) preserved.
