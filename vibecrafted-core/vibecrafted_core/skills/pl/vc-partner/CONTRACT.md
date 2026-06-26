# Kontrakt `vc-partner`

Ten dokument to wiążący kontrakt stojący za czytelnym przepływem.

## Kontrakt warstwy

```yaml
interactive_skill:
  name: vc-partner
  kind: interactive_posture
  activates_when:
    - user names "$vc-partner"
    - user asks to think/define/shape together
    - user wants proactive shared steering without full takeover
  does_not_automatically:
    - launch "vibecrafted partner"
    - create a run_id
    - create transcript/meta artifacts
    - spawn workers

runtime_workflow:
  name: vibecrafted partner
  kind: runtime_workflow
  activates_when:
    - operator launches "vibecrafted partner <agent>"
    - framework dispatches a partner run explicitly
  creates:
    - run_id
    - partner/journal.md
    - reports
    - transcript.log
    - meta.json
```

## Kontrakt postawy

```yaml
vc-partner:
  owns:
    - original_shape
    - success_contract
    - partner_journal
    - decision_log
    - shape_review
  may_launch_runtime:
    - vc-implement
    - vc-workflow
    - vc-operator
    - vc-marbles
    - vc-polarize
    - vc-review
    - vc-followup
    - vc-audit
    - vc-dou
    - vc-release
  must_not:
    - silently become vc-ownership
    - outsource problem definition to workers
    - allow delegated workers to redefine original_shape
    - treat mermaid as a binding runtime trigger
    - claim_done_before_vc_dou
    - ship_before_read_cadence_or_fresh_evidence
```

## Wiążące artefakty

Dla nietrywialnej pracy `vc-partner` musi zachować te pola — albo w
metadanych runtime'u, albo w dzienniku tylko-do-dopisywania:

```yaml
problem:
  statement: ""
  scope: []
  non_goals: []
original_shape:
  promise: ""
  target_user_or_operator: ""
  invariants: []
  accepted_drift_policy: ""
success_contract:
  acceptance: []
  gates: []
  runtime_proof: []
execution:
  selected_lane: ""
  reason: ""
  delegated_runs: []
shape_review:
  faithful: null
  mismatches: []
  drift_decisions: []
audit:
  review_report: ""
  followup_report: ""
  audit_report: ""
  dou_report: ""
ship:
  commit: ""
  release_or_next_move: ""
```

## Kadencja odczyt-zapis

```yaml
write_lanes:
  - vc-implement
  - vc-workflow
  - vc-marbles
  - vc-polarize
read_lanes:
  - vc-review
  - vc-followup
  - vc-audit
  - vc-dou
completion_rule: "Do not claim finished until DoU passes or records explicit remaining gaps."
```

## Polityka dryfu

Dryf kształtu nie jest zakazany. Cichy dryf kształtu jest zakazany.

Dozwolony dryf wymaga jednego z:

- evidence z runtime'u obala pierwotne założenie
- operator jawnie wybiera nowy kształt
- audyt/followup wykrywa, że pierwotny kształt nie może spełnić obietnicy

Każda decyzja o dryfie musi zostać dopisana do dziennika partnera.

## Polityka compaction

Po compaction lub wznowieniu partner musi przedstawić ponownie:

1. pierwotny kształt
2. stan bieżący
3. znane decyzje o dryfie
4. następny bounded ruch

Jeśli nie da się ich odtworzyć, sesja jest zablokowana, dopóki dziennik,
raport lub operator ich nie przywróci.
