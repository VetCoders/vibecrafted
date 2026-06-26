# Taksonomia `vc-ownership`

`vc-ownership` żyje w dwóch warstwach.

## Skill interaktywny lub headless

```yaml
vc-ownership:
  kind: autonomous_posture
  scope: interactive_or_headless_session
  meaning: take responsibility end-to-end, minimize questions, drive to green
  autonomy: full
```

W sesji interaktywnej `$vc-ownership` oznacza, że bieżący agent przyjmuje
odpowiedzialność za autonomiczne dostarczanie. W sesji headless ta sama postawa
oznacza mniej pytań, mocniejsze założenia i pełną weryfikację end-to-end
wewnątrz przydzielonego mandatu.

Nie uruchamia automatycznie oddzielnego procesu runtime'u.

## Workflow runtime'u

```yaml
vibecrafted_ownership_runtime:
  entrypoints:
    - vibecrafted ownership <agent> --file <task>
    - vibecrafted ownership <agent> --prompt <mandate>
    - vc-ownership <agent> --prompt <mandate>
  creates:
    - run_id
    - reports
    - transcript.log
    - meta.json
```

Runtime istnieje dopiero po jawnym uruchomieniu przez framework.

## Sąsiednie postawy

| Skill         | Rodzaj               | Różnica względem ownershipu                               |
| ------------- | -------------------- | --------------------------------------------------------- |
| `vc-partner`  | postawa interaktywna | utrzymuje współdzielone sterowanie strategiczne           |
| `vc-operator` | postawa orkiestracji | dyryguje falami, zamiast być właścicielem jednego slice'a |
| `vc-init`     | narzędzie orientacji | otwiera prawdę repo/runtime/intencji; nie jest postawą    |

## Reguła

Ownership prowadzi slice, ale wciąż kończy się percepcją read-only:
`vc-review`, `vc-followup`, `vc-audit` i `vc-dou`.
