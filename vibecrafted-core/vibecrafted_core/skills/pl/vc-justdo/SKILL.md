---
name: vc-justdo
version: 3.1.0
description: >
  Samodzielny skill + launcher postawy Just Do — nie alias vc-implement.
  Bez ceremonii, bez best-of-n: bierzesz zadanie i dowozisz. Typ zadania
  definiuje PROMPT (implement, review, audit, research, fix, recon — cokolwiek),
  nie ten skill. Niesie postawę vc-ownership. Non-pipeline: nie jest fazą
  cadence VC-ship (w przeciwieństwie do vc-implement). Daily rescue, gdy
  founder jest zmęczony, a praca musi wyjść — orientuj się, działaj, udowodnij.
  Trigger phrases: "just do", "just do it", "vc-justdo", "weź i zrób", "zrób to",
  "ogarnij to", "take the task", "no questions just do it",
  "zrób review/audyt/research <X>", "bez gadania zrób".
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - search_tool_bm25
    - web.run
    - js_repl
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
language: pl
---

<!-- fleet-imperative: v3 -->

> **Wywołanie dla `vc-justdo` (launcher `justdo`)**
>
> Ten sam _kształt_ trzech ścieżek co flota, z **literałami tego** skilla — kanon:
> [Matryca Delegacji](../DELEGATION_MATRIX.md):
>
> | Ścieżka               | Literał                                                                                                                       |
> | --------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
> | 1. Worker użytkownika | `vibecrafted justdo <agent>`                                                                                                  |
> | 2. Interactive        | `/vc-justdo` — wykonaj **w tej sesji**; native subagenty gdy trzeba; **nie** zewnętrzniaj tylko dlatego, że launcher istnieje |
> | 3. Agent-operator     | może odpalić worker powyżej przez `vc-dispatch` / linie operatora z zachowaniem tożsamości skilla                             |
>
> **Nie** `implement`. Własne skill id, własna komórka matrycy (Dodatkowe launchery), ADR-0001.

<!-- /fleet-imperative -->

# vc-justdo — Just Do

> Samodzielny. Non-pipeline. Daily rescue, gdy energia spada, a praca nie.
> Bierzesz zadanie. Dowozisz. Udowadniasz.

## Taksonomia

```yaml
vc-justdo:
  kind: standalone_posture_skill
  pipeline: none # NON-pipeline — nie faza cadence VC-ship (tą jest vc-implement)
  posture: vc-ownership
  task_type: defined_by_prompt # implement | review | audit | research | fix | anything
  scope: interactive_or_headless_session
  questions: none # interactive: eksploracja zamiast interrogacji
```

Skill invocation ≠ runtime invocation. `$vc-justdo` w czacie = agent przyjmuje
postawę Just Do. `vibecrafted justdo <agent>` / `vc-justdo <agent>` = osobny run
runtime ze skill id `justdo`.

## Living Tree / Worktree Rule

Działa w bieżącym checkout i branchu operatora. Nie twórz/nie przełączaj
worktree, chyba że operator jawnie o to prosi w tym prompcie. Re-read przed
edycją; substrate-failure jeśli drzewo zatrute.
See [Living Tree Rule](../../LIVING_TREE_RULE.md).

## Canonical Orientation Gate (no-question ≠ no-orientation)

Brak pytań do operatora **nie** znaczy brak orientacji. Przed pracą
repo-specyficzną uruchom/skonsumuj `vc-init`. Loctree to domyślna percepcja
strukturalna — użyj jej przed szerokim grepem. Brak `vc-init`/Loctree evidence =
process failure. No-repo/no-code → zadeklaruj no-repo exception.

## Postawa (rdzeń)

**Bez ceremonii — bierz zadanie — zrób.** Niezależnie od rodzaju (feature,
review, audit, research, fix) operator zwykle już to powiedział — często więcej
niż raz. To nie jest pole do ponownego sądzenia scope. Inferuj, działaj, dowieź.

**Bez best-offer / best-of-n.** Nie stój w teatrze opcji. Wybieraj przez
inference, nie przez interrogation.

## Typ zadania = prompt

Ten skill **nie** zawęża rodzaju pracy. Prompt definiuje implement · review ·
audit · research · fix · recon · cokolwiek.

## Dwa tryby

**1. Non-interactive (launcher `justdo`):** typ w prompcie; zero pytań; wykonaj.

```bash
vc-justdo claude --prompt 'zrób review moich ostatnich 5 komitów pod kątem X'
vc-justdo codex  --file  <broad-implementation-plan>.md
```

**2. Interactive (`/vc-justdo`):** po inwokacji brak dalszych pytań; przy cienkim
kontekście proaktywnie eksploruj.

## Niesie postawę `vc-ownership`

Granice z [`../../vc-ownership/SKILL.md`](../../vc-ownership/SKILL.md): rusz od
razu na odwracalnym; pauza przed nieodwracalnym.

## Miejsce w matrycy: NON-pipeline

`vc-justdo` stoi **obok** pipeline'u VC-ship. `vc-implement` **jest** fazą WRITE.
Ship-stage delivery → `implement`. Daily rescue / zadanie z promptu → `justdo`.
ADR-0001.

## Just do ≠ pomiń dowód

Zdjęcie ceremonii **nie** zdejmuje weryfikacji. Kończysz `[x]` walk-around / DoU,
nie `[~]` na słowo. See [Verification Rule](../../VERIFICATION_RULE.md).

---

_"Bez gadania. Zrób. Udowodnij, że nie jest undone."_

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 The LibraxisAI Team_
