# vc-operator — DISPATCH_TEMPLATE: Ciało z placeholderami Iter-3

Operator mode active — W2-B DISPATCH_TEMPLATE

Użyj tego pliku, aby budować ciała dispatchów Iter-3 skierowane do workera przez
mechaniczne podstawianie. Wypełnij najpierw frontmatter YAML, potem sekcje 1-12 po kolei.
Zastąp każdy placeholder `{{UPPER_SNAKE_CASE}}` konkretnym tekstem. Zostaw
bloki verbatim bez zmian, chyba że sam blok nazywa placeholder. Nie
używaj tego szablonu do operatorskich artefaktów: trackera, dziennika, zamknięcia ani
punktu stopu.

Demo kształtu frontmattera:

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

## Dwanaście sekcji

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

`prompt_id` to klucz retrievalu. `wave` + `slot` lokalizują workera w
atlasie operatora. `agent` i `skill` nazywają cel uruchomienia. `baseline_branch`
przypina prawdę startową. `parallel_with` utrzymuje graf zależności fali
widocznym. `report_path` jest obowiązkowy.

### 2. Mission

{{MISSION_PARAGRAPH}}

Otwórz przez `You're tasked with...` lub `Your job is to...`. Podaj, co ląduje, gdy
ten prompt się powiedzie i jaka późniejsza fala lub powierzchnia skierowana do
użytkownika zostaje odblokowana.

### 3. Context

Przeczytaj przed edycją:

{{CONTEXT_BULLETS}}

Użyj ścieżek, id commitów, referencji do planu/raportu oraz nazw testów. Nie wklejaj tu
treści plików; worker czyta pliki źródłowe bezpośrednio.

### 4. Files to create / edit

```text
Create:
{{FILES_TO_CREATE}}

Modify:
{{FILES_TO_MODIFY}}

Do not edit:
{{FILES_NOT_TO_EDIT}}
```

Dla plików współdzielonych dodaj noty APPEND-ONLY obok pliku i nazwij eksporty lub
sekcje, które worker musi zachować.

### 5. Acceptance

Worker przerzuca `[ ]` na `[x]` w miarę ukańczania pozycji i wkleja finalny stan do
raportu.

{{ACCEPTANCE_BULLETS}}

Bullety acceptance muszą być atomowe, testowalne i obserwowalne z repo lub
powierzchni runtime'u.

### 6. Gates

Uruchom je przed commitem:

```bash
{{GATE_COMMANDS}}
```

Wszystko zielone to bramka. Wklej finalne istotne linie wyjścia do raportu.

### 7. Out of scope

Nie dotykaj:

{{OUT_OF_SCOPE_BULLETS}}

Dwa konkretne bullety anti-scope-creep to minimum. Więcej jest w porządku, gdy
sąsiednia powierzchnia kusi lub jest edytowana równolegle.

### 8. Living Tree etiquette

**Verbatim**, bez parafrazy:

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

Checkpoint orientacji:

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

Podpowiedź odzyskiwania specyficzna dla zadania:

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

Wymagane dla ciał dispatchów skierowanych do workera. Artefakty operatorskie (tracker,
dziennik, zamknięcie, handoff punktu stopu) są zwolnione i nie mogą nieść tego railu,
chyba że operator jawnie o to poprosi.

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

Referencja wypełnionego przykładu:
`$HOME/.vibecrafted/artifacts/vetcoders/vibecrafted/2026_0521/operator-reform-2.0.0/briefs/W1-A_runner.md`

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
