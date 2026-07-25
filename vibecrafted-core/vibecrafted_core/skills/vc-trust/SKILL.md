---
name: vc-trust
version: 1.0.0
description: >
  Post-hoc falsification of commit claims on a Living Tree. Produces
  pass, pass-with-gaps, or block verdicts, appends evidence to the trust
  journal, and projects explicit verdicts onto the canonical f/x/n settlement
  axis. Trust observes and judges; it never blocks dispatch or mutates code.
loctree_value: "commit scope, consumers, blast radius, and runtime paths"
aicx_value: "why the commit exists and which prior attempts shaped it"
dogfooding: "required"
---

# vc-trust — the judge after the fact

`vc-trust` is a calm, post-hoc judge for commits made on the shared Living
Tree. Commit messages are hypotheses. Trust falsifies their claims against the
diff, consumers, tests, runtime, and historical intent before issuing:

- `pass` — every material claim survived falsification.
- `pass-with-gaps` — the core claim survived, but named evidence or coverage
  gaps remain.
- `block` — a material claim is false, contradicted, unsafe, or cannot meet its
  required evidence bar.

The settlement mapping is closed and canonical:

| Trust verdict    | Settlement      | TUI |
| ---------------- | --------------- | --- |
| `pass`           | Finalized       | `f` |
| `pass-with-gaps` | Needs attention | `n` |
| `block`          | Failed          | `x` |

## Invocation

- Worker: `vibecrafted trust <claude|codex|agy|junie|grok> --prompt ...`
- Interactive: `/vc-trust`
- Operator line: `vibecrafted trust <agent> --file <brief.md>`

The structured helper is:

```bash
python -m vibecrafted_core.trust --help
```

## Hard boundary

Trust is READ-only with respect to the repository. It may write only:

- the append-only trust journal;
- an explicit trust settlement on an existing run;
- the scoped control-plane projection for that same run;
- its report and transcript.

Trust never edits code, amends or reverts commits, blocks a dispatch, pushes,
or merges. Enforcement belongs to the separately planned `vc-guard`, which is
PARKED until vc-trust Cuts 1–3 are proven. Do not implement guard behavior here.

For pause, stop, operator buttons, and autonomy boundaries, follow
[`vc-operator/AUTONOMY.md`](../vc-operator/AUTONOMY.md); do not fork that
contract.

## Protocol

### 1. Orient and bound the stream

Run the `vc-init` gate. Read the complete Loctree atlas and AICX intent history.
Capture branch, HEAD, dirty state, and the exact commit range. On a Living Tree,
never attribute a dirty file or concurrent commit from timing alone.

List unjudged candidates:

```bash
python -m vibecrafted_core.trust enumerate <author> --since <sha-or-ISO-time>
```

### 2. Turn prose into falsifiable claims

For each commit, extract every material claim from its subject/body and changed
surface. Rewrite vague prose into checks such as:

- named test or gate exists and fails when the behavior is broken;
- runtime path reaches the changed code;
- claimed fail-closed behavior has no bypass or silencer;
- docs and launcher surface describe the behavior that actually ships;
- diff scope matches the message and contains no unclaimed foreign files.

Absence of a claim in the message does not hide a material regression in the
diff.

### 3. Grade evidence per claim

- `strong` — direct runtime reproduction, adversarial test, exact artifact
  inspection, or an independently failing-then-passing gate.
- `medium` — focused unit/integration test plus structural consumer proof.
- `weak` — static prose, inferred intent, happy-path-only evidence, or an
  upstream report not re-run by the judge.

A `pass` requires every material claim to have sufficient direct evidence.
Weak evidence can support context, never a material pass by itself.

### 4. Falsify, do not replay ceremony

Use Loctree `slice` for changed files, `impact` for high-blast-radius changes,
literal find/body for exact claims, and `follow` for relevant dead/cycle/twin
signals. Read the commit diff and its parents. Run the nearest tests and the
real user path. Check that the verification command itself can fail.

`vc-review` and `vc-audit` remain different:

- `vc-review` judges bounded diff/PR quality.
- `vc-audit` falsifies a completed plan or multi-task implementation.
- `vc-trust` judges a commit stream on the live shared tree and records a
  durable per-commit verdict.

### 5. Record exactly one explicit verdict

Each `--claim` must have one matching `--grade` and `--evidence`:

```bash
python -m vibecrafted_core.trust note <sha> pass \
  --claim "the blocking lane rejects insecure code" \
  --grade strong \
  --evidence "negative fixture failed before the fix and passed after it"
```

When judging the commit(s) produced by a run, add `--run-id <id>`. Only this
explicit `note` writes the canonical settlement. Exit code, report presence,
or await completion never imply a trust pass.

The journal defaults to
`$VIBECRAFTED_HOME/trust/journal.jsonl` and uses
`vibecrafted.trust-journal.v1`. Override it with
`VIBECRAFTED_TRUST_JOURNAL` or `--journal`.

### 6. Await at the run boundary

The primary lifecycle mode is named `await-primary`, not `guard=await`:

```bash
python -m vibecrafted_core.trust await-primary <run-id> \
  --author <agent-author> \
  --since <baseline-sha>
```

It waits synchronously through the canonical control plane, then lists
unjudged candidate commits. It does not auto-pass, auto-note, poll in the
background, or act as a persistent monitor. Persistent monitoring is only an
interactive convenience and is not a durable wake mechanism.

### 7. Roll up

```bash
python -m vibecrafted_core.trust triage [--run-id <id>]
```

Triage uses the latest append-only record per repo+commit and reports canonical
`f/x/n` counts. It does not recompute settlement from Git or exit codes.

## Report contract

The final report must include:

- baseline branch/HEAD and reviewed commit range;
- claim matrix with evidence grade and exact commands/artifacts;
- one verdict per commit and the run-level roll-up;
- journal path and settlement write result;
- verification performed and not performed;
- residual gaps and the next safe move.

Never say “trusted” without showing which claim was attacked and what survived.
