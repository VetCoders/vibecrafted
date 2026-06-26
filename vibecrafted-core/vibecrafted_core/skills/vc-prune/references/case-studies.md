# vc-prune Wave 5 — Case Studies

Real prune sweeps showing the silencer-strip pattern across languages and toolchains.

## Vista 0.67.3 (Rust + TypeScript), 2026-04-28

A late-evening sweep stripped:

- 12 `#[allow(...)]`
- 7 `// nosemgrep`
- 10 `eslint-disable`
- 24 `@ts-(ignore|nocheck|expect-error)` annotations

After the strip, `cargo test --all` failed on 13 e2e tests with `panic!("Test requires API credentials")`. But the panic was _new noise only because_ adjacent tests in the same suite already silently skipped on the same precondition. **Two contradictory "missing credentials" behaviours co-existing.** Stripping did not introduce the inconsistency; it surfaced it.

The bigger lesson: none of those 13 e2e tests had ever actually run without manual env injection. The 13 panicking tests were CI theater; the 5 quietly skipping tests were equally theater. Two flavours of the same lie.

The follow-up — a real `dotenvy::from_path("src-tauri/.env")` loader — was the **prize** of running Wave 5.

## Hypothetical Python equivalent (vista-portal billing service)

A sweep of `# type: ignore` and `@pytest.mark.skipif(not stripe_keys_present(), reason="...")` reveals:

- 11 `# type: ignore[attr-defined]` on the `stripe.Customer` object — every one was added before the `stripe-python` 11.x upgrade landed proper types in 2025-Q1. None still needed.
- 3 `@pytest.mark.skipif` decorators on webhook idempotency tests that **always skipped in CI** because nobody had wired Stripe test keys into GitHub Actions secrets.

Same pattern as Vista, different ecosystem: silencers outliving the bug they hid, plus tests that never ran.

The forgotten gem in the same sweep: a 380-line `app/billing/archived_invoice_export.py` with `# noqa: F401` on every import — turns out it was a complete invoice CSV exporter someone built for a customer who churned, never wired into a CLI command, and tested coverage was 87%. Reported up to operator: revive as `vc-export-invoices` CLI, or archive in `docs/archive/billing-archive.md` and delete.

## Pattern

Languages and toolchains differ; the discipline is identical.

- Silencers outlive the bug they hid (framework upgrades, type fixes, refactors).
- Tests that "always skip" or "always panic" do not exist as gates — they cost reviewer attention without producing signal.
- The forgotten gem in the same sweep is often more valuable than the silencer cleanup.

## Surprise findings catalog

Watch specifically for:

- tests that always skip
- tests that always panic
- `dead_code` allow on functions whose only caller was deleted three releases ago
- `@ts-ignore` on types that have been correct for a year
- `eslint-disable jsx-a11y/...` on real a11y violations the framework allegedly forced (when the framework was upgraded in 2025)
- `nosemgrep: react-dangerouslysetinnerhtml` on HTML that is **not** sanitized
- `# type: ignore[arg-type]` on a function whose signature was fixed two refactors ago

Each is a real bug or a real lie the silencer was hiding. Strip-and-listen finds them. That is the point.

## Forgotten Gems Report — full template

Save to `$VIBECRAFTED_HOME/artifacts/<org>/<repo>/<YYYY_MMDD>/reports/<timestamp>_forgotten-gems.md`.

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

## Test theater report (separate)

Test theater is debt, not gem. Save to `<timestamp>_test-theater.md`:

```markdown
## src-tauri/tests/e2e/rust/document_tests.rs:120

Was: `panic!("Test requires API credentials")`
Reality: never ran in any CI; required manual `LIBRAXIS_API_KEY` export
Real fix: `tests/common/credentials.rs` loading `src-tauri/.env` via dotenvy
before `has_vision_credentials()`
Owner: <to be assigned>
```

Test theater always gets a follow-up plan. Never a silencer reinstatement.
