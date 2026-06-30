# vc-operator — DISPATCH_TEMPLATE: Iter-3 Placeholder Body

Operator mode active — W2-B DISPATCH_TEMPLATE

Use this file to build worker-facing Iter-3 dispatch bodies by mechanical
substitution. Fill the YAML frontmatter first, then sections 1-12 in order.
Replace every `{{UPPER_SNAKE_CASE}}` placeholder with concrete text. Leave the
verbatim blocks unchanged unless the block itself names a placeholder. Do not
use this template for operator-side tracker, journal, close-out, or stop-point
artifacts.

Frontmatter shape demo:

```text
---
prompt_id: {{PROMPT_ID}}
agent: {{AGENT}}
skill: {{SKILL}}
wave: {{WAVE}}
slot: {{SLOT}}
baseline_branch: {{BASELINE_BRANCH}}
authored_by: {{AUTHORED_BY}}
target_repo: {{TARGET_REPO}}
---
```

---

## The twelve sections

### 1. YAML frontmatter

```text
---
prompt_id: {{PROMPT_ID}}
agent: {{AGENT}}
skill: {{SKILL}}
wave: {{WAVE}}
slot: {{SLOT}}
baseline_branch: {{BASELINE_BRANCH}}
parallel_with: {{PARALLEL_WITH}}
authored_by: {{AUTHORED_BY}}
target_repo: {{TARGET_REPO}}
report_path: {{REPORT_PATH}}
---
```

`prompt_id` is the retrieval key. `wave` + `slot` locate the worker in the
operator atlas. `agent` and `skill` name the launch target. `baseline_branch`
pins the starting truth. `parallel_with` keeps the wave dependency graph
visible. `report_path` is mandatory.

### 2. Mission

{{MISSION_PARAGRAPH}}

Open with `You're tasked with...` or `Your job is to...`. State what lands when
this prompt succeeds and what later wave or user-facing surface becomes
unblocked.

### 3. Context

Read before editing:

{{CONTEXT_BULLETS}}

Use paths, commit ids, plan/report references, and test names. Do not paste file
contents here; the worker reads source files directly.

### 4. Files to create / edit

```text
Create:
{{FILES_TO_CREATE}}

Modify:
{{FILES_TO_MODIFY}}

Do not edit:
{{FILES_NOT_TO_EDIT}}
```

For shared files, add APPEND-ONLY notes next to the file and name the exports or
sections the worker must preserve.

### 5. Acceptance

The worker flips `[ ]` to `[x]` as items complete and pastes final state into
the report.

{{ACCEPTANCE_BULLETS}}

Acceptance bullets must be atomic, testable, and observable from the repo or
runtime surface.

### 6. Gates

Run these before committing:

```bash
{{GATE_COMMANDS}}
```

All green is the gate. Paste the final relevant output lines into the report.

**Gates green is necessary, not sufficient — walk around the truck before you report "done":**

```text
Walk-around verification (see skills/VERIFICATION_RULE.md):
- Run the REAL artifact the user runs — launch the app/binary, mount the DMG
  and otool/launch the app inside, hit the runtime path. Not just `--version`.
- Signed / notarized / spctl-accepted / green tests != works. Re-verify runtime.
- Never trust an upstream agent's or pipeline's verification as proof. Re-run it.
- Check your own check actually detects failure (a command that cannot fail lies).
```

### 7. Out of scope

Do not touch:

{{OUT_OF_SCOPE_BULLETS}}

Two concrete anti-scope-creep bullets is the minimum. More is fine when the
neighboring surface is tempting or concurrently edited.

### 8. Living Tree etiquette

**Verbatim**, no paraphrase:

```text
Living Tree etiquette (NON-NEGOTIABLE):
- Re-read every file in `Files to modify` IMMEDIATELY before editing it.
  Another agent in a sibling wave or this wave's prior step may have
  pushed between your dispatch start and your first edit.
- Before handing off, capture a pre-handoff baseline: branch, HEAD SHA,
  `git status --short`, changed files, gates run, known failures, unverified
  surfaces, current intent, scope fence, and exact next instruction/report path.
- If you are receiving from another worker, compare that baseline with the live
  tree before editing. Drift is handled by re-reading and adapting, not by
  pretending the old prompt is still the whole truth.
- For files marked APPEND-ONLY, never delete or rename existing exports.
  Append new signals / methods at the end of the export block.
- For shared CSS files, add new rules in a dedicated section with a
  comment block stating which prompt added them.
- If you detect that another agent's work is incompatible with your
  acceptance, halt and write a "substrate failure" report instead of
  attempting a merge. The operator-agent decides next move.
```

### 9. Loctree first

Canonical orientation gate:

```text
Loctree first (perception over memory):
1. `mcp__loctree-mcp__context` on project root before any edit
2. `mcp__loctree-mcp__slice` on each file in `Files to modify` before editing
3. `mcp__loctree-mcp__impact` on files in `Files to modify` if your change
   could affect importers
4. `mcp__loctree-mcp__find name={{SHARED_SYMBOL_OR_CONTRACT}} mode=where-symbol`
   to confirm where shared types live

Grep fallback (only if loctree fails):
- Acceptable only after loctree fails for the specific structural question.
- Log a hook entry to `~/.vibecrafted/loctree/loctree-fail.md` describing
  why loctree was insufficient, so the loctree team can improve it.

Literal vs semantic (first move on any structural question = semantic, not grep):
- Semantic (AST/importer/dispatch graphs): who-imports, where-symbol, slice,
  impact, follow dead|cycles|twins, health, suppressions, env-truth.
- Literal (exact text/identifier): `loct find --literal`, `loct occurrences`,
  `loct body`; MCP `find mode=literal`. occurrence_kind tags each hit.
- Reflex: "AST/importer graph, or literal text?" First semantic, then literal,
  grep only as a post-loct magnifier.
```

### 10. Recovery hint

```text
Recovery hint (if your dispatch stalls):
- Substrate stall (Living Tree poisoned, prior wave's commit doesn't
  exist on baseline_branch): halt, write `substrate-failure.md`, exit
  non-zero. Operator-agent dispatches a fix.
- Scope stall (acceptance #N is wider than 1 commit can satisfy): write
  a `scope-overflow.md` listing what landed + what didn't, exit 0 with
  partial commit. Operator-agent narrows the next dispatch.
- Implementation stall (you took the wrong cut, gates fail at >30 min):
  revert only your own changes, write `wrong-cut.md` describing what you
  tried, exit 1. Operator-agent dispatches a focused integration agent
  with hints.
```

Task-specific recovery hint:

{{RECOVERY_HINT}}

### 11. Branch + commit convention

```text
Branch + commit:
- Branch: {{BRANCH_INSTRUCTION}}
- Cadence: ONE commit per round (marbles — one round = one commit); a dispatch that delivers multiple rounds/units is EXPECTED to produce multiple commits, each committed locally as its round completes. Never leave delivered work uncommitted.
- Commit subject: {{COMMIT_TITLE}}
- Commit body: explain the change, then include the full runtime footer:
  `Authored-By: {{AUTHORED_BY}}`, `session_id: <uuid>`,
  `time: YYYY-MM-DDTHH:MM:SS±HH:MM`, and `runtime: <runtime>`.
- Do not use `Co-Authored-By:`, vendor noreply addresses, or personal signatures.
- DO NOT `git push`. Operator publishes after wave green.
- DO NOT create PR. Operator does that operator-side.
```

### 12. Report path + Call to Action + Closing rail

Required for worker-facing dispatch bodies. Operator-side artifacts (tracker,
journal, close-out, stop-point handoff) are exempt and must not carry this rail
unless the operator explicitly asks.

```text
Report path (mandatory):
{{REPORT_PATH}}

Report sections:
- Frontmatter (mirror this prompt's YAML, set `status: completed | failed`)
- Current state, Proposal, Execution, Open risks, Next move
- Gate results (paste the final relevant output lines of each gate command)
- Files changed (paste `git diff --stat HEAD~1` when a commit was made)
- Acceptance verification (paste the Section 5 checkbox state, flipped)
- Pre-handoff baseline (branch, HEAD, `git status --short`, changed files,
  verification result, known failures, unverified surfaces, next instruction)
```

Call to Action: {{CALL_TO_ACTION}}

```text
=======================
{{ANTI_DEBT_ONE_LINER}} {{RAIL_KAOMOJI}}
=======================

Suchar: {{SUCHAR_PUNCHLINE}} {{SUCHAR_KAOMOJI}}
```

---

Filled example reference:
`$HOME/.vibecrafted/artifacts/Vetcoders/vibecrafted/2026_0521/operator-reform-2.0.0/briefs/W1-A_runner.md`

```text
=======================
Twelve sections. One template. Operator-agent fills, does not
compose. Mission, acceptance, gates, rail — placeholders take the
weight. The voice stays, the typing leaves.
ᕦ(ò_óˇ)ᕤ
=======================

Suchar: Why does the template never write itself?
Because it already showed where the variables live. (._.)
```

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
