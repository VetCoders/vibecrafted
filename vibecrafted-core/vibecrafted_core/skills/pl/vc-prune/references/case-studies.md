# vc-prune Fala 5 — Studia przypadków

Realne przebiegi prune pokazujące wzorzec silencer-strip w różnych językach i toolchainach.

## Vista 0.67.3 (Rust + TypeScript), 2026-04-28

Późnowieczorny przebieg zdjął:

- 12 `#[allow(...)]`
- 7 `// nosemgrep`
- 10 `eslint-disable`
- 24 adnotacje `@ts-(ignore|nocheck|expect-error)`

Po zdjęciu `cargo test --all` poległo na 13 testach e2e z `panic!("Test requires API credentials")`. Ale ta panika była _nowym szumem tylko dlatego, że_ sąsiednie testy w tym samym suicie już po cichu skipowały się na tym samym warunku wstępnym. **Dwa sprzeczne zachowania „missing credentials" współistniejące obok siebie.** Zdjęcie nie wprowadziło niespójności; wydobyło ją na powierzchnię.

Większa lekcja: żaden z tych 13 testów e2e nigdy realnie nie uruchomił się bez ręcznego wstrzyknięcia env. 13 panikujących testów to był teatr CI; 5 po cichu skipujących testów to był równie dobrze teatr. Dwie odmiany tego samego kłamstwa.

Followup — realny loader `dotenvy::from_path("src-tauri/.env")` — był **nagrodą** za uruchomienie Fali 5.

## Hipotetyczny odpowiednik w Pythonie (vista-portal, billing service)

Przebieg po `# type: ignore` i `@pytest.mark.skipif(not stripe_keys_present(), reason="...")` ujawnia:

- 11 `# type: ignore[attr-defined]` na obiekcie `stripe.Customer` — każdy dodany przed tym, jak upgrade `stripe-python` 11.x wprowadził porządne typy w 2025-Q1. Żaden już niepotrzebny.
- 3 dekoratory `@pytest.mark.skipif` na testach idempotencji webhooków, które **zawsze skipowały się w CI**, bo nikt nie podpiął testowych kluczy Stripe'a do sekretów GitHub Actions.

Ten sam wzorzec co w Vista, inny ekosystem: silencery przeżywające buga, który ukrywały, plus testy, które nigdy nie uruchomiły.

Zapomniana perełka w tym samym przebiegu: 380-liniowy `app/billing/archived_invoice_export.py` z `# noqa: F401` na każdym imporcie — okazało się, że to kompletny eksporter faktur do CSV, który ktoś zbudował dla klienta, który odszedł (churned), nigdy niepodpięty do komendy CLI, a testowe pokrycie wynosiło 87%. Zgłoszone do operatora: revive jako CLI `vc-export-invoices` albo archive w `docs/archive/billing-archive.md` i delete.

## Wzorzec

Języki i toolchainy się różnią; dyscyplina jest identyczna.

- Silencery przeżywają buga, który ukrywały (upgrade'y frameworków, naprawy typów, refactory).
- Testy, które „zawsze się skipują" albo „zawsze panikują", nie istnieją jako bramki — kosztują uwagę recenzenta, nie produkując sygnału.
- Zapomniana perełka w tym samym przebiegu jest często wartościowsza niż samo sprzątanie silencerów.

## Katalog zaskakujących findingów

Wypatruj zwłaszcza:

- testów, które zawsze się skipują
- testów, które zawsze panikują
- allow `dead_code` na funkcjach, których jedyny caller usunięto trzy release'y temu
- `@ts-ignore` na typach poprawnych od roku
- `eslint-disable jsx-a11y/...` na prawdziwych naruszeniach a11y, które framework rzekomo wymuszał (gdy framework został zaktualizowany w 2025)
- `nosemgrep: react-dangerouslysetinnerhtml` na HTML-u, który **nie** jest sanityzowany
- `# type: ignore[arg-type]` na funkcji, której sygnaturę naprawiono dwa refactory temu

Każdy z nich to prawdziwy bug albo prawdziwe kłamstwo, które silencer ukrywał. Strip-and-listen je znajduje. O to chodzi.

## Raport Zapomnianych Perełek — pełny szablon

Zapisz do `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_forgotten-gems.md`.

```markdown
# Forgotten Gems — <repo> <date>

## Summary

Stripped: N silencers. Real bugs (X), false positives (Y), constraints (Z),
gems (G), test theater (T), truly dead (D). Operator decisions needed: G + T.

## Gems

### #1 src/archive/clinic_export_v2.rs (412 LOC, last touch 2025-09-04)

- What: 2nd-gen export pipeline, clean trait split, full SOAP→PDF, never wired
- Why valuable: better-structured than current export, tests included, no dep drift
- Why parked: PR #341 merged the trait shape; wiring step deferred and forgotten
- Recommendation: revive, retire current path. Operator decision (customer-facing).
- Alt: archive in docs/archive/ + delete from runtime if direction superseded.
```

## Raport teatru testów (osobny)

Teatr testów to dług, nie perełka. Zapisz do `<timestamp>_test-theater.md`:

```markdown
## src-tauri/tests/e2e/rust/document_tests.rs:120

Was: `panic!("Test requires API credentials")`
Reality: never ran in any CI; required manual `LIBRAXIS_API_KEY` export
Real fix: `tests/common/credentials.rs` loading `src-tauri/.env` via dotenvy
before `has_vision_credentials()`
Owner: <to be assigned>
```

Teatr testów zawsze dostaje plan followupu. Nigdy przywrócenia silencera.
