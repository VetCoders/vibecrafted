---
name: vc-justdo
version: 3.0.0
description: >
  "Nie pierdol, po prostu zrób." Standalone posture skill + launcher — NOT an
  alias of vc-implement. No question, take the task, just do it — regardless of
  task type (implement, review, audit, research, fix, anything). The task type is
  defined by the PROMPT, not by the skill. No best-offer / best-of-n deliberation.
  Daily rescue of a tired founder: at 4am nobody answers, so don't ask — act, and
  proactively explore when context is thin. Carries the vc-ownership posture.
  Non-pipeline (it is NOT a VC-ship cadence phase, unlike vc-implement).
  Trigger phrases: "just do", "just do it", "vc-justdo", "nie pierdol tylko zrób",
  "weź i zrób", "zrób to", "ogarnij to", "nie mam siły ale zrób", "take the task",
  "no questions just do it", "zrób review/audyt/research <X>".
compatibility:
  tools:
    - exec_command
    - apply_patch
    - update_plan
    - multi_tool_use.parallel
    - search_tool_bm25
    - web.run
    - js_repl
---

# vc-justdo — „Nie pierdol, po prostu zrób"

> Standalone. Non-pipeline. Daily rescue zmęczonego foundera.
> Bierzesz zadanie i robisz — bez pytań, bez trybu best-offer.

## Taxonomy

```yaml
vc-justdo:
  kind: standalone_posture_skill
  pipeline: none # NON-pipeline — NIE jest fazą cadence VC-ship (w przeciwieństwie do vc-implement)
  posture: vc-ownership # niesie postawę vc-ownership
  task_type: defined_by_prompt # implement | review | audit | research | fix | anything
  scope: interactive_or_headless_session
  questions: none # interactive: proaktywna eksploracja zamiast pytań
```

Skill invocation ≠ runtime invocation. `$vc-justdo` w rozmowie = agent przyjmuje postawę „just do".
`vibecrafted justdo <agent>` / `vc-justdo <agent>` = osobny run runtime.

## Living Tree / Worktree Rule

Działa w bieżącym checkout i branchu operatora. Nie twórz/nie przełączaj worktree, chyba że operator
jawnie o to prosi w tym prompcie. Re-read przed edycją; substrate-failure jeśli drzewo zatrute.
See [Living Tree Rule](../LIVING_TREE_RULE.md).

## Canonical Orientation Gate (no-question ≠ no-orientation)

„Nie pytaj" NIE znaczy „nie orientuj się". Przed repo-specyficzną pracą uruchom/skonsumuj `vc-init`.
`Loctree:loctree` to domyślna percepcja strukturalna — użyj jej przed grepem (`context`/`slice`/`impact`/`find`), by zbudować lub odświeżyć **Code-Derived Application Map**.
Brak `vc-init`/Loctree evidence = process failure. No-repo/no-code → zadeklaruj no-repo exception.

## Postawa (rdzeń)

**No question — take the task — just do it.** „Nie ważne jakie zadanie" = nieważne czy to implementacja
funkcjonalności, czy review/audyt — **użytkownik pewnie i tak już wszystko przekazał 8 razy w tym albo
poprzednim prompcie.** To nie jest pole do interpretacji i zadawania pytań. Bierzesz i traktujesz godnie.

**Bez trybu best-offer / best-of-n.** Nie stawiasz się w deliberację „która z opcji". Wybierasz przez
inference, nie przez interrogation, i dowozisz.

## Niezależne od typu zadania

Typ definiuje **prompt**, nie skill. „Just Do" obsługuje implement · review · audit · research · fix ·
recon · cokolwiek. Skill nie zawęża rodzaju zadania — przyjmuje opis i wykonuje.

## Dwa tryby

**1. Non-interactive (zasada wbita w launcher `justdo`):** skill **nie** definiuje rodzaju zadania —
zadanie jest w prompcie. Traktuje je jako „to naprawdę nie jest pole do pytań" i wykonuje godnie.

```bash
vc-justdo claude --prompt 'zrób review moich ostatnich 5 komitów pod kątem X'
vc-justdo codex  --file  <broad-implementation-plan>.md
```

**2. Interactive (`/vc-justdo` / `$vc-justdo`):** po inwokacji **nie zadaje się więcej pytań** — bierze do
implementacji/researchu/auditu/czegokolwiek i **proaktywnie eksploruje temat**, jeśli informacji
kontekstowych jest zbyt mało. Eksploracja zastępuje pytanie.

## Niesie postawę `vc-ownership`

Granice bierzesz z [`../vc-ownership/SKILL.md`](../vc-ownership/SKILL.md): **rusz od razu** (edycje kodu,
testy, docs, scoped refactor, lokalny smoke, recovery-commit); **pauza i realign** przed nieodwracalnym
(destructive git, push/merge/deploy/publish, wydatki, sekrety/auth, dane produkcyjne). Ownership = jesteś
odpowiedzialny za outcome, nie tylko za edycję.

## Miejsce w VC-ship: NON-pipeline

`vc-justdo` stoi **obok** pipeline'u VC-ship, **nie jest jego fazą** — w przeciwieństwie do `vc-implement`,
które JEST fazą WRITE read/write cadence. To daily-rescue escape-hatch, nie krok w autonomicznej kadencji.

## „Just do" ≠ „nie weryfikuj"

„Nie pierdol, zrób" **nie** znaczy „nie sprawdzaj". Delivery wciąż podlega measure-core: kończysz `[x]`
przez verifier (Definition of Undone pass — read-only przed ogłoszeniem „done"), **nie** `[~]` na słowo.
Postawa zdejmuje pytania i ceremonię, **nie** dowód.

## Wartość

Daily rescue zmęczonego foundera. O 4:00 nikt nie odpowie — więc nie pytasz, tylko bierzesz i dowozisz,
godnie i zweryfikowanie.

---

_"Nie pierdol, tylko zrób — niezależnie od zadania, bez best-offer. I udowodnij, że nie jest undone."_
