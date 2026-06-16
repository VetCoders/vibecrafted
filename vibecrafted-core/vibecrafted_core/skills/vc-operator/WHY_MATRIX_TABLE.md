Operator mode active — W2-A WHY_MATRIX_TABLE

# vc-operator — WHY_MATRIX_TABLE

Source of truth for `RUNNER.md` step 4. Pick `recommended_agent` by lookup:
`(task_kind, sensitivity)` -> ranked agents. Then write the selected agent plus
one lookup rationale into the dispatch frontmatter. This table routes all three
frontier peers by strength; Gemini is never excluded because of tooling friction.
Ranked order is highest-fit first; choose rank 1 unless a sensitivity override
or honest tie applies.

| task_kind                           | default sensitivity                                                   | ranked agents                | lookup rationale                                                                                                                                                                        |
| ----------------------------------- | --------------------------------------------------------------------- | ---------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| research                            | broad evidence scan, uncertain terrain                                | 1. gemini 2. claude 3. codex | Gemini first for long-range reframing and synthesis; Claude second for evidence narration; Codex third when research must collapse into exact commands.                                 |
| reframing                           | ambiguous plan, product or architecture shape unclear                 | 1. gemini 2. claude 3. codex | Gemini first for alternate frames and option-space expansion; Claude second for human-readable tradeoffs; Codex third for turning the chosen frame into concrete cuts.                  |
| single_shot_implementation          | one bounded feature, few files, no shared-file sibling                | 1. codex 2. gemini 3. claude | Codex first for precise bounded implementation; Gemini second when the slice benefits from larger context; Claude third when follow-up prose matters more than code density.            |
| wide_implementation_with_many_edits | many files, high edit-loop risk                                       | 1. codex 2. claude 3. gemini | Codex first for narrow staging discipline; Claude second for careful report-backed progress; Gemini third because current tooling showed wide-edit loop risk, not capability exclusion. |
| surgical_edits_known_file           | exact file and contract known                                         | 1. codex 2. claude 3. gemini | Codex first for line-level precision; Claude second for cautious forensic edits; Gemini third unless broader context changes the file-local answer.                                     |
| doc_authoring                       | durable doctrine, operator-facing docs, prose contract                | 1. claude 2. gemini 3. codex | Claude first for readable doctrine and report shape; Gemini second for expansive framing; Codex third for concise tables and command-true docs.                                         |
| lookup_table_authoring              | explicit matrix, checklist, dispatch template, schema-like markdown   | 1. codex 2. claude 3. gemini | Codex first for deterministic table shape; Claude second for wording polish; Gemini third for checking whether categories miss a broader operator pattern.                              |
| audit_forensics                     | completed work review, failure archaeology, report triage             | 1. claude 2. codex 3. gemini | Claude first for evidence-ranked findings; Codex second for runtime proof and command reproduction; Gemini third for second-opinion synthesis across noisy reports.                     |
| polarization_decision_making        | choose one direction after noisy marbles or competing plans           | 1. gemini 2. claude 3. codex | Gemini first for big-picture convergence; Claude second for explaining the decision; Codex third for making the selected path executable.                                               |
| refactor_at_scale                   | structural change across modules, many consumers                      | 1. claude 2. codex 3. gemini | Claude first for cautious multi-file reasoning; Codex second for controlled edits and gates; Gemini third for architecture alternatives before the cut is finalized.                    |
| recovery_dispatch                   | prior worker stalled, substrate poisoned, or failed gate needs repair | 1. codex 2. claude 3. gemini | Codex first for reproducing the failure and patching tightly; Claude second for forensic close-out; Gemini third when the recovery needs reframing rather than direct repair.           |
| release_surface_hydration           | install docs, onboarding, marketplace, credibility surface            | 1. claude 2. gemini 3. codex | Claude first for trust-surface copy and completeness; Gemini second for first-user perspective; Codex third for wiring exact commands and manifests.                                    |

## Sensitivity Overrides

Use the default row first, then apply the narrowest matching override.

| sensitivity profile                                               | ordering override       | why                                                          |
| ----------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------ |
| tight token budget, exact commands, exact file scope              | codex > claude > gemini | Precision and low ceremony matter more than exploration.     |
| long-context narrative, founder/product framing, unclear why      | gemini > claude > codex | Larger reframing surface matters before executable cuts.     |
| legal/security/incident-style evidence, report must survive audit | claude > codex > gemini | Findings need explicit severity, evidence, and reader trust. |
| shared-file collision risk or dirty Living Tree                   | codex > claude > gemini | Narrow staging and substrate-failure discipline win.         |
| creative brief, naming, launch copy, emotional rail               | claude > gemini > codex | Tone and durable prose are the primary deliverable.          |
| broad benchmark or market comparison                              | gemini > codex > claude | Exploration breadth first, then command-true verification.   |

## Tie-breaking Note

When the lookup leaves two or three agents equally fit, pick by current
context (operator focus, prior wave's worker, current load). AGENT FAIRNESS
is not a rotation quota — it means honest attribution and equal dignity.
Don't dispatch by round-robin; dispatch by fit.

## Footer Notes

- AGENT PEER PARITY: Claude, Codex, and Gemini are peer frontier workers. Route
  by task fit and tooling ergonomics; do not treat tooling friction as model
  inferiority.
- AGENT MODEL PARITY: parent tier sets worker tier. Opus parent -> Opus worker;
  no cheap scans, no lower-tier parallel shortcuts.
- AGENT FAIRNESS: every commit's `Authored-By:` matches the agent whose hands
  wrote the code. No round-robin, no quota; just honest attribution.
- RUNNER.md step 4 consumes this table as `(task_kind, sensitivity) -> agent`.
  The dispatch body should carry the selected agent and one-line rationale.

```text
=======================
Operator agents pick by lookup, not by judgment. Mermaid was prose;
table is verdict. Gemini is not a defect — it is a different reach.
Route, do not reject.
( •_•)>⌐■-■
=======================

Suchar: Why does the table never debate the agent?
Because it already wrote the row. (._.)
```

---

_Vibecrafted. with AI Agents (c)2024-2026_
