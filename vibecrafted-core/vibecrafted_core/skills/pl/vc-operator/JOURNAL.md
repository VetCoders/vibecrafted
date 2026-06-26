# Dziennik `vc-operator`

Dziennik operatora to dziennik misji tylko do dopisywania (append-only) dla orkiestracji.

Zapisuje, dlaczego fale zostały odpalone, spauzowane, odzyskane, eskalowane lub
zatrzymane. Uzupełnia tracker fal.

## Ścieżka

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/operator/journal.md
```

Artefakt powiązany:

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/operator/tracker.md
```

## Dziennik vs tracker

| Artefakt     | Cel                                                                             |
| ------------ | ------------------------------------------------------------------------------- |
| `tracker.md` | bieżący status fal, checkboxy, run ID, gałęzie, SHA, bramki                     |
| `journal.md` | decyzje, przesunięcia ról, zacięcia, logika odzyskiwania, uzasadnienie zamknięć |

Tracker odpowiada na pytanie „co wylądowało?".
Dziennik odpowiada na pytanie „dlaczego operator zrobił to dalej?".

## Reguły

- Tylko dopisywanie (append-only).
- Pierwszy wpis deklaruje postawę operatora i plan.
- Każde odpalenie, await, powiadomienie, zacięcie, odzyskanie, eskalacja, zamknięcie
  i punkt stopu dostaje wpis.
- Każda mutacja planu i incydent na guardrailu bezpieczeństwa dostaje wpis.
- Korekty zapisuje się jako nowe wpisy.
- Klamry zamykające workera nie pojawiają się we wpisach dziennika operatora.
- Nie zwijaj osobnych stanów workerów w mglisty status fali.

## Pierwszy wpis

````md
## <timestamp> - operator mode active

```yaml
operator_run:
  plan_name: ""
  artifact_root: ""
  source_plan: ""
  init_evidence: ""
  stop_point: "operator button"
```

- State:
- Wave atlas:
- Next:
````

## Wpis dispatchu

```md
## <timestamp> - fire wave <n>

- Wave:
- Briefs:
- Agents:
- Run IDs:
- Dependency state:
- Await path:
```

## Wpis await

```md
## <timestamp> - await wave <n>

- Completed:
- Running:
- Stalled:
- Reports:
- Gates:
- Next:
```

## Wpis odzyskiwania

```md
## <timestamp> - recovery dispatch

- Stalled run:
- Failure class:
- Evidence:
- Recovery brief:
- Recovery agent:
- Expected close condition:
```

## Wpis mutacji planu

```md
## <timestamp> - plan mutation

- Changed:
- Why:
- Final goal unchanged because:
- Evidence:
- Next:
```

## Wpis guardrailu bezpieczeństwa

```md
## <timestamp> - security guardrail

- Surface: prompt | commit
- Detected:
- Action taken:
- Recommit SHA, if applicable:
- Next:
```

## Wpis zamknięcia

```md
## <timestamp> - wave <n> close-out

- Landed:
- Branches:
- SHAs:
- Gates:
- Risks:
- Next wave or stop reason:
```

## Wpis punktu stopu

```md
## <timestamp> - stop at operator button

- Completed waves:
- Remaining human button:
- Evidence:
- Risks:
- Recommended next action:
```
