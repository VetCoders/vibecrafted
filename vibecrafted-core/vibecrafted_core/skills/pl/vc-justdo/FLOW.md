# `vc-justdo` Flow — postawa, runtime kompatybilności

> Postawa jest standalone. Runtime pozostaje wpięty kompatybilnościowo w `vc-implement`
> aż wejdzie migracja de-alias z `docs/adr/0001-vc-justdo-standalone.md`.
> „Nie pierdol, po prostu zrób proszę" — bierzesz zadanie i robisz, niezależnie od typu zadania.

## Flow

```mermaid
flowchart TD
    A[Operator: vibecrafted justdo claude --prompt '<task>'  ·  $vc-justdo in chat] --> G[Canonical Orientation Gate: vc-init + loctree — no-question ≠ no-orientation]
    G --> T{Task type — defined by PROMPT, not by the skill}
    T --> X[Take the task — no questions, no best-of-n]
    X --> Ex[Proactively explore if context is thin — exploration replaces questioning]
    Ex --> D[Deliver — carry the vc-ownership posture]
    D --> V[Verify: measure-core — finish [x] via verifier, never [~] on word]
```

## Postawa (nie faza pipeline'u)

vc-justdo stoi **obok** read/write cadence VC-ship — **nie** jest fazą WRITE (tą jest
`vc-implement`). To daily-rescue escape-hatch: bez pytań, bierzesz zadanie i po prostu robisz. Typ
zadania (implement / review / audit / research / fix / cokolwiek) bierze się z promptu, nie ze skilla.

## Trasy

| Wejście                                     | Argumenty               | Produkuje                                          | Wyjście            |
| ------------------------------------------- | ----------------------- | -------------------------------------------------- | ------------------ |
| `vibecrafted implement <agent>`             | `--prompt` lub `--file` | kanoniczny autonomiczny runtime implementacji      | `0` przy dispatchu |
| `vibecrafted justdo <agent>`                | tak samo                | alias kompatybilności aż wejdzie migracja de-alias | `0` przy dispatchu |
| `vc-justdo <agent>`                         | tak samo                | skrót shellowy / alias kompatybilności             | `0` przy dispatchu |
| `$vc-justdo` / `/vc-justdo` (interaktywnie) | —                       | agent przyjmuje postawę „just do" w sesji          | —                  |

### Granice (przeniesione z `../vc-ownership/SKILL.md`)

- Rusz od razu: edycje, testy, docs, scoped refactor, lokalny smoke, recovery-commit.
- Pauza + realign przed nieodwracalnym: destructive git, push/merge/deploy/publish, wydatki, sekrety/auth, dane produkcyjne.

### Status migracji runtime (uczciwie)

**Postawa/skill** jest standalone (ten plik + `SKILL.md` v3.0.0 są zgodne). **De-alias runtime'u** —
rozdzielenie prefiksu run-id (`just-`) oraz installera/registry tak, by `justdo` przestało zwijać się na
`implement` — to oczekująca migracja zaplanowana w `../../docs/adr/0001-vc-justdo-standalone.md` (status:
Proposed). Dopóki nie zostanie ratyfikowana, launcher może wciąż współdzielić wiring run-id z `implement`.

### Artefakty sesji

- Korzeń artefaktów: `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/`
- Lock: `$VIBECRAFTED_HOME/locks/<org>/<repo>/<run_id>.lock`
- Outputy: `reports/<timestamp>_<slug>_<agent>.md` z dopasowanym `.transcript.log` i `.meta.json`
