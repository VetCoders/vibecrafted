# vc-review — FINDINGS: Phase 2 Analysis Procedure

> Reading order, mandatory pattern scans, adversarial pass, minimum
> coverage requirements, and full output template. Phase 2 of
> vc-review.

Read alongside [`SKILL.md`](SKILL.md) and [`PRVIEW.md`](PRVIEW.md).

---

## Philosophy

Tryb: **Findings-max**. Nie kończ na "kilku punktach". Jeśli widać
25 osobnych problemów, wypisz 25. Lepiej 20 celnych findingów niż 5
ogólników.

Każdy finding MUSI mieć:

- **Evidence grade** (STRONG / MEDIUM / WEAK / NONE) — see SKILL.md
- **Positive evidence** — artefakt + ścieżka (1–2 linie z patcha/logu)
- **Negative check** — "old path removed at …" lub "WEAK — not confirmed"
- **Test evidence** — `<test-path>::<name>` lub "WEAK — no targeted test"
- **Comment** — dlaczego to ważne (1 zdanie) + co grozi
- **Recommendation** — co zrobić / jak zweryfikować

Zasady:

- Jeden punkt = jeden problem (nie łącz tematów).
- Czego nie da się potwierdzić z artefaktów: oznacz **[VERIFY]**.
- Rozdzielaj **problem w kodzie** vs **problem narzędzia [TOOLING]**.

---

## Reading Order (Obowiązkowy)

1. **`AI_INDEX.md`** (if exists) — verify it points to real paths.
   Lying index → P3 [TOOLING].
2. **`report.json`** (default) — `meta`, `gate.allow_merge` +
   `policy_mode` + reasons, `checks[]` (status / log_path / command),
   `diff.stats` + `diff.files[]` (scale / churn / hotspots),
   `quality` (breaking / coverage / sarif / heuristics).
3. **`00_summary/MERGE_GATE.json` + `SANITY.json`** — cross-check
   with `report.json`. Inconsistency → P2 [TOOLING]. "All checks
   passed" with WARN / INLINE_FINDINGS = misleading.
4. **`00_summary/pr-metadata.txt` + `file-status.txt` +
   `commit-list.txt`** — scope, A/M/D categories, commit progression.
   Look for branch drift (infra files outside PR scope).
5. **`30_context/INLINE_FINDINGS.sarif`** — every SARIF result =
   ready-made finding. Transfer all to findings list.
6. **`20_quality/*`** — PASS gates: extract warnings from logs (cargo
   warns, tsc non-errors). WARN / ERROR / FAIL: root cause +
   recommendation. `checks-errors.log` for high-signal filtered errors.
   `BREAKING_CHANGES.md`: assess real weight (P?).
   `coverage-delta.txt`: flag critical "NO_TEST_CHANGE" entries.
7. **`30_context/changed-tests.txt`** — cross-reference with source
   changes. Untested source files → finding.
8. **Diffs (selective)** — `10_diff/per-file-diffs/00-INDEX.txt` for
   top churn. Per-file patches for hotspots. `10_diff/per-commit-diffs/
00-SUMMARY.md` for highest-impact commits.

---

## Mandatory Pattern Scans

Scan per-file patches and `full.patch` for:

**Rust** — `.unwrap()`, `.expect(`, `panic!`, `todo!`, `unsafe`,
`dbg!`, `println!`, `#[allow(`

**TypeScript / JavaScript** — `any`, `as unknown as` (double cast),
`@ts-ignore`, `@ts-expect-error`, `eslint-disable`,
`// TODO|FIXME|HACK`, empty `catch {}` without log/rethrow, non-null
assertion `!` on uncertain values, `console.log|warn|error` (should
use secureLogger in Vista)

**Security / PII** — logging tokens / emails / passwords / personal
IDs, new telemetry without privacy review, new endpoints / command
handlers without auth checks, hardcoded URLs / keys / secrets

**Data / Performance** — query in loop (N+1), missing batching for
bulk ops, large payloads without pagination, unnecessary I/O in hot
paths

Each "hit" in the diff = potential finding with evidence.

---

## Adversarial Pass

After pattern scans, before writing the final report, run an explicit
adversarial pass. For every candidate finding, answer all three:

1. **Positive evidence:** what code in the diff appears to introduce
   this concern?
2. **Negative evidence:** is the deprecated / forbidden behavior still
   present somewhere else in the diff (or elsewhere in the tree, if
   the diff claims to remove it)?
3. **Test strength:** does a test in the diff assert the **exact**
   behavior implied by the PR description? Could the code be broken
   while the test still passes?

Findings that fail the adversarial pass get downgraded:

- Negative check fails (old path still present) → upgrade severity by one P-level
- Test asserts something weaker than required → cap evidence at MEDIUM
- No test for a claimed behavior change → cap evidence at WEAK;
  severity stays

---

## Minimum Coverage Requirements

To prevent laconic reports:

- **All** entries in `INLINE_FINDINGS.sarif`
- **Top 10** files by churn — read per-file patch
- **All** files in core risk categories: auth, payments, database,
  session, security, encryption, middleware
- **All** critical "NO_TEST_CHANGE" entries from `coverage-delta.txt`
- **All** entries in `BREAKING_CHANGES.md` with assessed P-level
- **Per-commit progression** for PRs with >5 commits — identify
  phases, risky transitions

---

## Output Format (Obowiązkowy)

Three mandatory sections, in this order.

### 1) Findings (P0/P1/P2/P3 with evidence grade)

```
- **[P?][EVIDENCE: STRONG|MEDIUM|WEAK|NONE] <Title>**
  (optionally: [VERIFY], [TOOLING], [STAGE-OK-DEFERRED],
  [STAGE-PARTIAL], [STAGE-DRIFT])
  - **Positive evidence:** `<artifact-path>` + `<file:line>` + short fragment
  - **Negative check:** "old path removed at <file:line>" OR
    "WEAK — old path not confirmed removed" OR "N/A — no removal claim"
  - **Test evidence:** `<test-path>::<test-name>` + 1 line of assertion,
    or "WEAK — no targeted test for this behavior"
  - **Comment:** 1 sentence on risk / impact
  - **Recommendation:** concrete "what to do" / "how to verify"
  - **Owner:** `author` / `reviewer` / `infra` (optional)
```

Number for cross-referencing: `P1-01`, `P1-02`, `P2-01`, etc.

Evidence grade is **mandatory** on every finding. A finding without
evidence grade is itself a process gap.

### 2) Before-Merge TODO (Markdown Checkboxes)

```markdown
- [ ] **(P0)** ... (ref: P0-01)
- [ ] **(P1)** ... (ref: P1-01, P1-02)
- [ ] **(P2)** ... (ref: P2-01)
- [ ] **(P3)** ... (ref: P3-01)
```

Each TODO references finding IDs. Include verification commands in
code fences where applicable.

### 3) Self-Attack Pass + Model Check

For every finding tagged `[EVIDENCE: STRONG]` and every "ready to
merge" recommendation, answer in one line each:

- **Strongest reason this verdict could be wrong:** _<answer>_
- **What I did not verify directly:** _<answer>_
- **Quickest falsifier:** _<command or test that would catch the gap>_

If any STRONG verdict has a credible falsifier, downgrade to MEDIUM
or WEAK and re-rank the P-level. Do not protect your first answer.

Emit a one-line model check:

```
model_confidence: high | medium | low — <one-sentence why>
```

If confidence ≠ `high`, the review output cannot recommend "merge
as-is" — only "merge after operator verifies <X>".

---

## Optional Sections

Add when they provide value:

- **Executive Summary** (max 8 bullets): gate verdict, top 3 risks,
  test signal, top hotspots, scope delta
- **Architecture Context** — diagram or description of affected subsystem
- **Scope / What Changed** — based on `diff.stats` + top dirs + top files
- **Commit Progression** — phases for multi-commit PRs
- **Test Coverage Matrix** — source → test → new tests count
- **Security & Privacy Check** — PII in logs, data flows, event filtering
- **QA Plan** — 5–15 manual + automated test recommendations
- **Evidence Index** — links to key artifacts used

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by VetCoders (c)2024-2026 LibraxisAI_
