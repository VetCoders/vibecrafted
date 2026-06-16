# Runtime `vc-operator`

`vc-operator` jako skill interaktywny nie uruchamia runtime'u automatycznie.

Runtime zaczyna się dopiero, gdy operator wybierze żywy pas supervisora lub workflow:

```bash
vibecrafted dispatch plan.dispatch.toml --doctor
vibecrafted dispatch plan.dispatch.toml --dry-run --json
vibecrafted dispatch run --run-id <id> --root . --report report.md --transcript trace.log -- <worker>
vibecrafted workflow claude --file /path/to/plan.md
vibecrafted implement codex --prompt '<bounded slice>'
```

## Obowiązki runtime'u

Postawa operatora tworzy lub konsumuje trwały stan dla orkiestracji floty:

- metadane runu
- transkrypt
- tracker fal
- dziennik tylko do dopisywania (append-only)
- briefy workerów
- karty uruchomienia i run ID
- zamknięcia per fala
- finalny handoff w punkcie stopu
- wpisy mutacji planu i guardraili bezpieczeństwa w dzienniku operatora

## Układ artefaktów

```text
$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/
  plans/
  reports/
  tmp/
  dispatch-result.json or run-specific result files
  <timestamp>_<slug>.transcript.log
  <timestamp>_<slug>.meta.json
```

Sesja w trybie operatora może też trzymać `tracker.md`, `journal.md` oraz `briefs/`
dla wielofalowego planu, ale te artefakty to dyscyplina postawy, a nie dowód, że
istnieje publiczna komenda `vibecrafted operator`.

## Pasy runtime'u

| Potrzeba                      | Pas runtime'u                      |
| ----------------------------- | ---------------------------------- |
| Plan jest mglisty             | `vibecrafted scaffold <agent>`     |
| Jeden slice workera           | `vibecrafted implement <agent>`    |
| Ścisły slice ERi              | `vibecrafted workflow <agent>`     |
| Zbieżność na dryfie prawdy    | `vibecrafted marbles <agent>`      |
| Dowiezienie slice'a od A do Z | `vibecrafted ownership <agent>`    |
| Pauza na wspólną strategię    | `vibecrafted partner <agent>`      |
| Niezależna weryfikacja        | `vibecrafted audit <agent>`        |
| Deterministyczny supervisor   | `vibecrafted dispatch <file.toml>` |
| Dowiezienie na zewnątrz       | `vibecrafted release <agent>`      |

## Stany terminalne

```yaml
terminal_state:
  stopped_at_operator_button:
    requires:
      - wave tracker updated
      - journal updated
      - reports and SHAs named
      - remaining unpermitted human action named
  completed_with_plan_permission:
    requires:
      - permission source named
      - tracker updated
      - journal updated
      - reports and SHAs named
  blocked_with_evidence:
    requires:
      - blocker classification
      - attempted recovery
      - nearest safe next action
  escalated:
    requires:
      - target skill
      - reason
      - handoff state
```

## Nie-cele

- Nie używaj runtime'u do ukrywania decyzji przed operatorem.
- Nie uruchamiaj nieobserwowalnego dispatchu.
- Nie obchodź telemetrii uruchomień.
- Nie zamieniaj handoffu w punkcie stopu w push/merge/deploy, chyba że spisany plan
  lub bieżąca sesja jawnie dopuściły to działanie.
