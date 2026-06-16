# vc-audit — PHASES: Eight-Phase Audit Procedure

> Every audit traverses these eight phases sequentially. No phase may
> be skipped. Each phase produces a numbered section in
> `audit_report.md` and a corresponding line in `audit_trace.log`.

Read alongside [`SKILL.md`](SKILL.md) and [`DISPATCH.md`](DISPATCH.md).

---

## Phase 1 — Context Receipt

Read the Loctree Context Pack first. Produce a Context Processing
Receipt with:

- repo root, branch, commit, snapshot id
- `dirty_worktree`: true / false
- `snapshot_health`, `stale_snapshot`
- hotspots / high fan-in files relevant to this plan
- verification gates suggested by context
- authority caveats (`RepoVerified` vs `LoctreeDerived` vs
  `SemanticGuess` vs `AicxAgent` / `AicxOperator` / `AicxFailure`)

If `dirty_worktree` is true:

- record it explicitly
- run `git status` / `git diff` before judging final state
- do not treat the checkout as clean

Authority rule:

- `RepoVerified` may be treated as repo-grounded structural evidence
- `LoctreeDerived` may be treated as derived evidence requiring caution
- `SemanticGuess` must be treated as hypothesis, not hard truth
- `AICX*` labels must not be treated as repo facts unless independently
  verified

If an authority label is not formally defined in the context/task
schema, mark your interpretation as inferred-not-verified.

Trace line: `READ_CONTEXT_PACK`.

---

## Phase 2 — Task Ingestion Receipt

Read every task / plan file in full. For each, produce a Task
Processing Record:

- `task_id`, `task_name`, source file
- frontmatter status (as **claim**, not truth)
- stated dependencies
- stated goal
- acceptance criteria count
- expected files to modify / create
- tests required
- non-goals (negative requirements)
- exit contract
- risk notes
- stage notes (if any)
- `task_read_status`: `FULL_READ` / `PARTIAL` / `BLOCKED`

If any task is not full-read, the audit cannot conclude PASS. State
this explicitly in the executive verdict.

Emit a `Tasks Loaded` table in the report:

```
| Task ID | File | Full read | Acceptance criteria | Depends on | Stage notes |
```

Trace line per task: `READ_TASK task_id_NN`.

### Layered Reading Discipline

When a task file is truncated by tool output limits, read it in
layered spans of ~1500–2000 lines using `Read` offset/limit, or in
spans of ~80,000 chars via `python3 -c 'print(open(P).read()[A:B])'`.
Explicitly state coverage in the report (e.g. "Read task-07 in 3
spans of 1800 lines, total 5400 lines, 100% coverage").

Forbidden: writing analysis based on the truncation warning text, the
first 2KB preview, or the file name alone.

---

## Phase 3 — Atomic Requirements Extraction

For each task, turn acceptance paragraphs into testable items. Each
acceptance criterion becomes at least one requirement. Also extract:

- non-goals as **negative requirements**
- dependencies as **dependency checks**
- verification commands as **verification obligations**
- exit contracts as **process / report requirements**
- staged status claims as **stage requirements**

Emit one JSON record per requirement to
`audit_requirements_matrix.jsonl`:

```json
{
  "task_id": "01-atlas-per-repo",
  "requirement_id": "01-R03",
  "requirement": "load_atlas_info no longer relies on latest/context-atlas fallback",
  "source_section": "Acceptance criteria",
  "expected_code_locations": ["loctree_rs/src/analyzer/html.rs"],
  "verification_type": "code + negative check + test"
}
```

Trace line per task: `EXTRACT_REQUIREMENTS task_id_NN count=N`.

---

## Phase 4 — Positive + Negative Code Verification

For each requirement, run both checks.

**Positive check** — verify expected code exists.

**Negative check** — verify the old fallback / old behavior /
forbidden non-goal is **not** still present.

Use Loctree before grep:

- `find(name)` mode `who-imports` for "who depends on the new symbol?"
- `slice(file)` before judging load-bearing-ness of a hub
- `impact(file)` to verify a deletion's blast radius
- `find(name)` mode `where-symbol` to confirm a deprecated path is gone

A passing positive check + a passing negative check + a passing test
= STRONG evidence. Anything less is weaker.

Trace lines per task:
`INSPECT_CODE task_id_NN files=N`,
`VERIFY_TESTS task_id_NN tests=N`,
`NEGATIVE_CHECK task_id_NN checks=N`.

---

## Phase 5 — Adversarial Pass

You are not a friendly reviewer. For every requirement, actively try
to prove the implementation is **incomplete**.

For each requirement, answer all five sub-checks:

1. **Positive evidence:** what code appears to implement this?
2. **Negative evidence:** is the old behavior still present? Is a
   deprecated fallback still wired? Is a non-goal violated? Is the
   implementation in the wrong layer? Is there a path where the
   requirement is bypassed?
3. **Test strength:** does a test exist? Does it assert the **exact**
   required behavior? Could the implementation be broken while the
   test still passes?
4. **Dependency check:** if this depends on another requirement, is
   the dependency actually implemented? Does this requirement use
   the new dependency, or an old assumption?
5. **Evidence quality:** classify as STRONG / MEDIUM / WEAK / NONE.

Trace line per task: `DEPENDENCY_CHECK task_id_NN`.

---

## Phase 6 — Stage-Aware Verdict

Many tasks are multi-stage. You MUST NOT treat frontmatter status as
truth, but you also MUST NOT mark a task FAIL just because a later
stage is queued.

For each multi-stage task, extract:

- frontmatter_status
- latest stage delta
- stages mentioned in the file
- which stage is claimed as landed
- which scope remains deferred / queued by design
- what "done" means for this task
- whether the audit should judge full-plan completion,
  landed-stage-only, or dependency-readiness for downstream tasks

Emit:

```
| Task | Stage audited | Landed scope | Deferred scope | Verdict | Evidence |
```

Stage-aware verdict values:

- `STAGE_PASS` — landed stage fully satisfied, deferred scope
  explicitly out of scope for this audit
- `STAGE_PASS_WITH_GAPS` — landed stage mostly satisfied with
  documented minor gaps
- `STAGE_PARTIAL` — landed stage has at least one key gap
- `STAGE_FAIL` — landed stage contradicts task
- `FULL_PLAN_INCOMPLETE_BY_DESIGN` — task explicitly defers later
  stages and that deferral is acceptable

Trace line per task: `STAGE_CHECK task_id_NN`.

---

## Phase 7 — Per-Task Verdict Table

Produce the main verdict table. One row per task. Each task accounted
for exactly once. Do not collapse tasks into a narrative summary.

Columns:

| Task # | Task name | Frontmatter status | Stage audited | Requirements checked | Implemented | Partial | Missing | Contradictions | Negative checks | Test coverage | Overall verdict | Severity | Evidence summary | Recommended follow-up |

Verdicts: `PASS`, `PASS_WITH_GAPS`, `PARTIAL`, `FAIL`, `UNVERIFIED`,
`STAGE_PASS`, `STAGE_PASS_WITH_GAPS`, `STAGE_PARTIAL`,
`FULL_PLAN_INCOMPLETE_BY_DESIGN`.

Severity: P0 (implementation contradicts task / breaks dependent
tasks / violates non-goal), P1 (key acceptance criterion missing),
P2 (test / report / process gap), P3 (cosmetic / documentation gap).

Trace line per task: `CLASSIFY task_id_NN verdict=<verdict>`.

---

## Phase 8 — Self-Attack Pass + Model Check

### Self-Attack

Before finalizing, review **every** PASS and PASS_WITH_GAPS verdict.
For each, answer:

- What is the strongest reason this verdict might be wrong?
- What did I not verify directly?
- Which requirement has the weakest evidence?
- What single command or test would most quickly falsify my verdict?

If any PASS has weak evidence after this attack, downgrade it to
PASS_WITH_GAPS or UNVERIFIED. Do not protect your first answer.
Attack it.

Trace line per attacked task: `SELF_ATTACK task_id_NN`.

### Model Check

Emit a Model Check section:

- assumptions made
- areas where the audit could be wrong
- tasks hardest to verify
- which report claims you refused to trust without code evidence
- which code areas require human review
- which staged tasks might be misclassified if judged against
  full-plan rather than landed-stage scope

Set:

```
model_confidence: high | medium | low
```

If confidence is not `high`, say why.

Cross-Task Findings (optional but recommended) — identify patterns
across tasks: repeated missing pattern, broken dependency chains,
stale report claims, old fallback still present, tests too weak,
non-goal violated, implementation in wrong layer, context/atlas/LSP/
API mismatch, stage/status confusion.

| Finding | Affected tasks | Evidence | Severity | Recommendation |

Trace line: `WRITE_REPORT`, then `END`.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
