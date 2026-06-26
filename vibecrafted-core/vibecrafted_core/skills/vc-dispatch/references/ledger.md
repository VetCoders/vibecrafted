# Ledger — tracker, journal, baton (single-writer bookkeeping)

The dispatcher is the SINGLE WRITER of the line's ledger. Workers write code
and reports; only the dispatcher flips states and appends the journal. This
is what makes evidence trustworthy when the audit skills arrive.

## Tracker (`plans/<line>/tracker.md`)

Header: repo, baseline branch + SHA, atlas/journal pointers, agent roster.

Table: `| Cut | Wave | Agent | Brief | State | Evidence |`

States:

- `[ ]` planned — brief exists, not dispatched
- `[~]` in flight — dispatched; evidence = run_id + dispatch notes (BATON
  highlights, EXTRA hardening)
- `[?]` delivered but operator-verify pending — used for manual/runtime
  acceptance items that a headless worker cannot exercise
- `[!]` failed / stalled / substrate failure — evidence = diagnosis trail
- `[x]` settled — flipped ONLY by the dispatcher, only with evidence

Evidence for `[x]` ALWAYS contains: commit SHA(s) + worker-reported gate
results + who verified + which acceptance items remain `[?]` for the
operator. A report is a claim; the commit (it passed the hooks) + a diff that
matches the brief + the report's gate section together are the proof. The
dispatcher does NOT re-run lints/tests — duplicate gates are cost without
information; final truth belongs to vc-followup / vc-audit / vc-dou.

Wave planning lives in the tracker too: list hard file overlaps explicitly
("C1→C2: messages.rs; C5b↔C7: settings/") — everything else is a candidate
for PARALLEL dispatch, and maximizing that parallelism is an obligation, not
an option.

## Journal (`JOURNAL.md`, append-only)

Open it in the line's first minute — it is the flight recorder if the
dispatcher's context dies mid-line. NEVER rewrite or reorder; append dated
sections. Every entry records one transition or event:

- dispatch (run_id, prompt size, placeholder check result)
- delivery + flip (SHA, diff essence, gates from report, what stays `[?]`)
- stall + recovery (full evidence: elapsed vs CPU, frozen session file,
  orphan check, what the new run inherits)
- in-flight corrections (operator decision verbatim-spirit + the correction
  brief it spawned)
- doctrine corrections from the operator (these also belong in persistent
  memory — the journal is per-line, memory is forever)
- post-line findings → backtracker entries with code-truth anchors

## Baton

The baton is not a file — it is the BATON layer of the next prompt plus the
tracker's evidence column. When composing it, answer the next worker's three
questions: what landed before me (SHAs + touched files), what may move while
I work (operator testing live, parallel workers and their fenced areas), and
what comes after me (so I fence my scope).

## Backtracker (`99_BACKTRACKER.md`)

Post-line findings from operator smoke / audit: one section per finding,
operator's words verbatim-spirit + code anchors from structural tools (file:
line + one-line why). Findings become backlog cuts (`C<n>` rows in the
tracker, state `[ ]`) and are dispatched on the operator's button — possibly
all in one run with per-item commits and an execution order in EXTRA
(small regressions first, big features last).

## Own-work rule

The dispatcher's own repo edits (hotfixes assigned by the operator, line
bookkeeping inside the repo) follow marbles: one unit = one commit,
hook-formed message, REAL session id in trailers (from the harness, never
uuidgen), committed immediately — hoarding uncommitted work on a Living Tree
is the failure mode, not the safe choice. Version bumps and pushes stay on
the operator's buttons.
