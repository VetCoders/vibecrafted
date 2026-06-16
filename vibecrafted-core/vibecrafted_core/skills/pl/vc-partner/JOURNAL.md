# Dziennik `vc-partner`

Dziennik partnera to dziennik misji „tylko do dopisywania (append-only)".

Istnieje, bo `vc-partner` odpowiada za zachowanie pierwotnego kształtu
przez compaction, delegację, review, audyt i dowiezienie.

## Ścieżka

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/partner/journal.md
```

Jeśli nie istnieje jeszcze korzeń artefaktów runtime'u, trzymaj tę samą strukturę
wewnątrz raportu interaktywnego albo utwórz korzeń artefaktów przed pierwszym
zdelegowanym runem.

## Reguły

- Tylko do dopisywania.
- Pierwszy wpis uchwyca `original_shape`.
- Nigdy nie przepisuj wcześniejszych wpisów, by narracja wyglądała czyściej.
- Korekty są nowymi wpisami.
- Każdy zdelegowany run, compaction, finding, domknięcie luki i dryf kształtu
  dostaje wpis.
- Raport końcowy podsumowuje dziennik; nie zastępuje go.

## Pierwszy wpis

````md
## <timestamp> - original shape

```yaml
original_shape:
  problem: ""
  promise: ""
  target_user_or_operator: ""
  invariants: []
  non_goals: []
  success_contract: []
  accepted_drift_policy: "only with explicit journal entry"
```

- Evidence: source prompt, operator clarification, repo/runtime context
- Next: first bounded move
````

## Zwykły wpis

```md
## <timestamp> - <phase>

- State: what is true now
- Shape check: faithful | drifting | intentionally changed
- Evidence: commands, reports, runtime observations, links
- Decision: what changed in the plan or contract
- Next: the next bounded move
```

## Wpis dryfu

```md
## <timestamp> - shape drift decision

- Previous model:
- New model:
- Why this is not a mylik:
- Evidence:
- Operator approval: yes | no | not needed because runtime proof is decisive
- Updated invariants:
- Next:
```

## Wpis handoffu

```md
## <timestamp> - handoff to <runtime>

- Runtime:
- Reason:
- Original shape excerpt:
- Worker must preserve:
- Worker must not:
- Expected artifact:
- Await/recovery path:
```

## Wpis wznowienia

```md
## <timestamp> - resume after compaction

- Original shape:
- Last known state:
- Open gaps:
- Drift decisions so far:
- Next bounded move:
```
