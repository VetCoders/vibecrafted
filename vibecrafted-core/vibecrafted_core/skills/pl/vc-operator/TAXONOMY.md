# `vc-operator` Taksonomia

`vc-operator` żyje w dwóch warstwach.

## Skill interaktywny

```yaml
vc-operator:
  kind: orchestration_posture
  scope: interactive_session
  meaning: dispatch, await, synthesize, recover, close waves
  autonomy: orchestration
```

W sesji interaktywnej `$vc-operator` oznacza, że bieżący agent przyjmuje rolę
dyrygenta. Nie uruchamia to automatycznie nowego procesu runtime'u.

Postawa operatora jest odpowiedzialna za:

- zadeklarowanie przesunięcia framingu
- przeczytanie planu
- zbudowanie wave atlas
- dobór agentów
- odpalanie fal przez launchery frameworka
- czekanie na trwałe artefakty
- wydawanie dispatchów odzyskiwania
- prowadzenie trackera i dziennika
- doprowadzenie dozwolonej pracy do celu
- zatrzymywanie się przy niedozwolonych operator buttonach

## Workflow runtime'u

```yaml
operator_runtime_lanes:
  entrypoints:
    - vibecrafted dispatch <file.toml>
    - vibecrafted dispatch run ...
    - vibecrafted workflow <agent> --file <plan>
    - vibecrafted implement <agent> --prompt <slice>
  creates:
    - run_id
    - dispatch/result artifacts
    - tracker or journal when the posture maintains them
    - briefs
    - reports
    - transcript.log
    - meta.json
```

Runtime istnieje dopiero po jawnym uruchomieniu przez framework.

## Postawy sąsiadujące

| Skill          | Rodzaj                    | Różnica względem operatora                                                           |
| -------------- | ------------------------- | ------------------------------------------------------------------------------------ |
| `vc-partner`   | postawa interaktywna      | wspólne sterowanie i piecza nad pierwotnym kształtem przed strategią / w jej trakcie |
| `vc-ownership` | postawa autonomiczna      | jeden slice prowadzony end-to-end do zweryfikowanego handoffu                        |
| `vc-init`      | narzędzie orientacji      | otwiera prawdę repo/runtime'u/intencji; nie jest postawą                             |
| `vc-agents`    | warstwa floty zewnętrznej | uruchamia workerów; sama nie jest właścicielem historii orkiestracji                 |

## Reguła

Jeśli zadanie jest wielofalowe, wieloagentowe i ma kształt planu, użyj postawy operatora.

Jeśli zadanie to jeden feature lub jeden slice, użyj zamiast tego ownership lub implement.
