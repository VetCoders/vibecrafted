# Taksonomia `vc-partner`

`vc-partner` żyje w dwóch warstwach.

## Skill interaktywny

```yaml
vc-partner:
  kind: interactive_posture
  scope: current_interactive_session
  meaning: proactive shared steering, original shape custody, partner journal, read/write cadence
  autonomy: collaborative
```

W sesji interaktywnej `$vc-partner` znaczy, że bieżący agent przyjmuje postawę
wspólnego sterowania. Nie uruchamia automatycznie nowego procesu runtime'u.

Postawa partner odpowiada za:

- definiowanie problemu z operatorem
- zachowanie `original_shape`
- budowanie planu z `vc-scaffold`
- wybór właściwego lane'u wykonania
- egzekwowanie kadencji write -> read
- osądzanie wierności kształtu po implementacji
- utrzymywanie dziennika partnera na bieżąco

## Workflow runtime'u

```yaml
vibecrafted_partner_runtime:
  entrypoints:
    - vibecrafted partner <agent> --file <shape-or-plan>
    - vibecrafted partner <agent> --prompt <intent>
    - vc-partner <agent> --prompt <intent>
  creates:
    - run_id
    - partner/journal.md
    - reports
    - transcript.log
    - meta.json
```

Runtime istnieje dopiero po jawnym uruchomieniu przez framework.

## Postawy sąsiadujące

| Skill          | Rodzaj                 | Różnica względem partnera                                   |
| -------------- | ---------------------- | ----------------------------------------------------------- |
| `vc-ownership` | postawa autonomiczna   | bierze ster i prowadzi end-to-end                           |
| `vc-operator`  | postawa orkiestracyjna | dyryguje falami i zespołami polowymi, gdy plan już istnieje |
| `vc-init`      | narzędzie orientacji   | otwiera prawdę o repo/runtimie/intencji; to nie postawa     |

## Reguła

Partner może uruchamiać lane'y zapisu, ale nie może uznać pracy za zrobioną,
dopóki kadencja tylko-do-odczytu nie sprawdzi prawdy implementacji, wierności
kształtu, twierdzeń o ukończeniu oraz Definition of Undone.
