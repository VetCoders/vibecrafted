# Kontrakt `vc-operator`

Ten dokument to wiążący kontrakt stojący za czytelnym flow operatora.

## Kontrakt warstw

```yaml
interactive_skill:
  name: vc-operator
  kind: orchestration_posture
  activates_when:
    - user names "$vc-operator"
    - user asks to conduct a plan or fleet
    - user asks for multi-wave dispatch
  does_not_automatically:
    - launch "vibecrafted dispatch"
    - create a run_id
    - create transcript/meta artifacts
    - fire workers

runtime_supervisor:
  name: vibecrafted dispatch
  kind: runtime_supervisor
  activates_when:
    - operator launches "vibecrafted dispatch <file.toml>"
    - operator launches "vibecrafted dispatch run ..."
    - framework dispatches a supervisor run explicitly
  creates:
    - run_id
    - dispatch tracker/result artifacts
    - reports
    - briefs
    - transcript.log
    - meta.json
```

## Kontrakt postawy

```yaml
vc-operator:
  owns:
    - plan_intake
    - wave_atlas
    - agent_selection
    - dispatch_briefs
    - await_and_recovery
    - tracker
    - journal
    - wave_close_outs
    - stop_point_handoff
  may_launch_runtime:
    - vc-scaffold
    - vc-implement
    - vc-workflow
    - vc-marbles
    - vc-audit
    - vc-review
    - vc-followup
    - vc-release
    - vc-ownership
    - vc-partner
  must_not:
    - silently become a worker
    - dispatch without vc-init evidence
    - dispatch without a wave atlas
    - use native subagents as substitutes for fleet dispatch
    - blind-restart stalled workers
    - push_merge_deploy_or_publish_without_plan_or_session_permission
```

## Artefakty wiążące

```yaml
operator_run:
  plan_name: ""
  artifact_root: ""
  framing_shift: ""
  init_evidence: ""
wave_atlas:
  waves: []
  dependencies: []
  parallel_groups: []
dispatches:
  briefs: []
  run_ids: []
  agents: []
verification:
  reports: []
  gates: []
  branches: []
  shas: []
recovery:
  stalls: []
  recovery_dispatches: []
plan_mutations:
  skipped: []
  added: []
  reordered: []
  cherry_picks: []
security_guardrails:
  prompt_scans: []
  commit_scans: []
close_out:
  tracker: ""
  journal: ""
  stop_point_handoff: ""
```

## Polityka operator button

Tryb operatora zatrzymuje się przed każdym niedozwolonym:

- push
- force-push
- merge
- deploy
- komunikatem publicznym
- akcją płatną
- nieodwracalną zmianą stanu
- akcją na granicy zaufania

Działanie jest dozwolone tylko wtedy, gdy jest jawnie dopuszczone w spisanym planie
albo zadeklarowane i udokumentowane w bieżącej sesji. Jeśli zezwolenie jest
niejednoznaczne, zatrzymaj się i przekaż operator button w handoffie.

Finalny handoff powinien czynić pozostały przycisk oczywistym.

## Polityka mutacji planu

Operator może zmienić kształt dispatchu bez nowego przycisku, jeśli finalny cel
się nie zmienia:

- przegrupować fale
- pominąć, dodać lub przestawić prompty
- cherry-pickować między aktywnymi gałęziami fal

Każdą mutację trzeba dopisać do `journal.md` wraz z tym, co się zmieniło, dlaczego
i jaki niezmiennik celu pozostaje nienaruszony.

## Polityka guardraili bezpieczeństwa

Przed każdą falą przeskanuj briefy workerów pod kątem niebezpiecznych komend i
triggerów hard-stop. Po każdym commicie workera przeskanuj scommitowane zmiany pod
kątem sekretów, danych osobowych, ścieżek lokalnych, lokalnej topologii sieci,
adresów IP i dokumentów wewnętrznych. W razie wykrycia zrewertuj wadliwy commit,
oczyść powierzchnię, scommituj ponownie i odnotuj incydent w `journal.md`.

## Polityka odzyskiwania

Zacięcie nie oznacza restartu.

Dozwolone odzyskiwanie wymaga:

1. przeczytania raportu/transkryptu/meta zaciętego workera, jeśli są
2. sklasyfikowania awarii
3. wydania celowanego dispatchu odzyskiwania lub eskalacji do marbles/ownership
4. dopisania decyzji o odzyskiwaniu do `journal.md`

Ślepe ponowne odpalenie to porażka procesu.
