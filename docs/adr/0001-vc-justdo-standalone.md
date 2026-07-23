# ADR-0001 — `vc-justdo`: od aliasu `vc-implement` do samodzielnego skilla+launchera „Just Do"

- **Status:** Accepted (operator-decided 2026-06-04; runtime+matrix cut 2026-07-23).
  `justdo` is its own skill id in registry/cli/help; matrix v3.2 places it under
  Additional launchers; `implement` is ship WRITE only.
- **Deprecates:** obecne stanowisko „`justdo` = compatibility alias `vc-implement`; implement is the public face"
  (`docs/runtime/CONTRACT_v1.5.0.md:534`, `docs/SKILLS.md:60-61`).
- **Kontekst pierwszy:** to nie jest pierwszy ADR projektu jako konwencji — w repo nie istniał katalog
  ADR; ten plik go zakłada (`docs/adr/`). Numeracja sekwencyjna od `0001`.

## Kontekst

`vc-justdo` jest dziś **aliasem** `vc-implement`. Wpięcie aliasu (zweryfikowane loctree-first, literal):

- **Run-id / shell mapping:** `runtime/scripts/lib/session.sh:38` i `runtime/helpers/vetcoders-runtime-core.sh:402`
  (`justdo) printf 'just\n' ;;` — justdo zwija się do `just`/implement).
- **Installer registry:** `scripts/vetcoders_install.py:1677` (`"justdo"`).
- **Tabela aliasów / public face:** `docs/SKILLS.md:60-61`, `docs/runtime/CONTRACT_v1.5.0.md:525,527,534`.
- **Docs user-facing:** `README.md:151`, `docs/FAQ.md:49,51`, `docs/FAQ-ANSWERED.md:100,183,186`,
  `docs/QUICK_START.md:75`, `docs/WORKFLOWS.md:88`, `docs/DOCKER.md:67`, `docs/installer/DESIGN.md:74,94,164`.
- **Historia:** `CHANGELOG.md:188,192,232,456,474` (`vc-justdo 2.0.0`) — historia, NIE przepisujemy.

Problem: alias **konflatuje** dwie różne rzeczy — ustrukturyzowany workflow `vc-implement` (fazy, ceremonia)
oraz **postawę** „Just Do". Alias zdeprecjonował pierwotną wartość skilla. `vc-justdo` był wstępnie i
pierwotnie planowany jako **daily rescue zmęczonego foundera**: bierzesz zadanie i robisz, bez stawiania
się w tryb deliberacji „best offer / best-of-n", bez pytań — bo o 4:00 nikt nie odpowie.

## Decyzja

1. **`vc-justdo` przestaje być aliasem `vc-implement`.** Staje się samodzielnym **skillem ORAZ launcherem**.
2. **Zrywamy alias i wzajemne cross-refery** między `vc-justdo` a `vc-implement` (lista w „Konsekwencje").
3. **Tożsamość „Just Do" (postawa):** _no question — take the task — just do it._ Niezależnie od typu zadania
   (implement, code-read, review, fix, recon, cokolwiek). **BEZ trybu best-offer / best-of-n deliberation.**
   Minimum ceremonii, maksimum dowiezienia.
4. **Wartość w hierarchii:** `vc-justdo` = **daily rescue zmęczonego foundera**. To jego jedyne i naczelne miejsce.
5. **Miejsce w VC-ship: NON-pipeline skill** — w przeciwieństwie do `vc-implement` (które JEST fazą WRITE
   read/write cadence), `vc-justdo` stoi **obok** pipeline'u, **nie jest jego fazą**. Postawa niesiona:
   **`vc-ownership`**. Ale „just do" ≠ „nie weryfikuj": delivery wciąż podlega measure-core — kończy się
   `[x]` przez verifier (Definition of Undone pass), **nie** `[~]` na słowo.

6. **Tryby (z FAQ-ANSWERED, operator 2026-06-04):** non-interactive — typ zadania w prompcie, launcher
   traktuje go jako „nie pole do pytań"; interactive (`/vc-justdo`) — zero dalszych pytań, proaktywna
   eksploracja gdy kontekstu za mało. Typ zadania (implement/review/audit/research/cokolwiek) definiuje
   **prompt**, nie skill.

## Konsekwencje

**Trzeba (osobny cut migracyjny — vc-implement/vc-justdo):**

- Odpiąć run-id mapping: `session.sh:38` i `vetcoders-runtime-core.sh:402` — `justdo` dostaje **własny** run-id,
  nie zwija się do `just`/implement.
- `scripts/vetcoders_install.py:1677` + doctor/registry: `vc-justdo` i `vc-implement` jako **dwa odrębne** skille
  (dziś doctor listuje oba, ale justdo jako alias — rozdzielić semantycznie).
- Przepisać `docs/SKILLS.md:60-61` (usunąć z tabeli aliasów), `docs/runtime/CONTRACT_v1.5.0.md:534`
  („implement is the public face" → „justdo to samodzielna postawa, nie alias"), oraz user-facing docs
  (README/FAQ/QUICK_START/WORKFLOWS/installer-DESIGN) — przestają mówić „alias of vc-implement".
- Napisać/zaostrzyć `skills/vc-justdo/SKILL.md`: postawa „no question, no best-offer, just do", dowolny typ
  zadania, daily-rescue framing.

**Ryzyko / kompatybilność:**

- Agenci i shell-e wired do `justdo` **w znaczeniu „implement-pipeline"** dostaną zmienioną semantykę:
  `justdo` nadal odpala, ale **robi postawę, nie pełny implement-workflow**. To świadoma, komunikowana zmiana
  (nie cichy drift) — odnotować w CHANGELOG przy cutcie migracyjnym.
- `CHANGELOG.md` (historia) zostaje nietknięty; zmiana zachowania opisana jako nowy wpis, nie edycja przeszłości.

## Acceptance ADR-a

Decyzja zapisana, cross-refy zmapowane z file:line, migracja wyodrębniona jako osobny cut z verifierem
(doctor pokazuje `vc-justdo` i `vc-implement` jako odrębne; `justdo` nie mapuje na implement run-id;
SKILL.md niesie postawę). Push/merge — operator.
