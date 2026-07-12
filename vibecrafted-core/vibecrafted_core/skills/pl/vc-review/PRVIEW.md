# vc-review — PRVIEW: Faza 1 — Generowanie artefaktów

> Referencja dla wywołania `prview-rs`, układu artifact packa oraz
> tooling-special-cases. Faza 1 z vc-review.

Czytaj wraz z [`SKILL.md`](SKILL.md) i [`FINDINGS.md`](FINDINGS.md).

- Binarka: `prview` (rozwiąż przez `command -v prview`; nie zakładaj ścieżki cargo)
- Źródło: `https://github.com/vetcoders/prview-rs`
- Autorka: Monika (@m-szymanska) — Vetcoders

---

## Tabela dispatchu

| Tryb | Komenda | Kiedy używać |
| -------------------------------- | ----------------------------------------------- | ---------------------------------------------------- | --------------------- |
| Local branch vs develop/main | `prview --pr <NUMBER>` | Domyślnie dla aktywnych PR-ów na lokalnym checkoucie |
| Remote branch (no checkout) | `prview -R --remote-only <branch> <base>` | Review gałęzi kontrybutora na origin |
| GitHub PR by number | `prview --pr <NUMBER> --with-tests --with-lint` | Domyślnie dla gruntownego review PR-a |
| All gates | `prview --deep` | Merge gate / PR wysokiego ryzyka |
| Fast triage | `prview --quick` | Tylko jawny szybki triage — NIE domyślnie |
| Refresh after amend / force-push | `prview --update` | Unikanie zduplikowanych zestawów artefaktów |
| Ambiguous origin | dodaj `--gh-repo owner/repo` | Gdy working tree ma wiele remote'ów |
| JSON-only mode | `prview --json --quiet                          | jq ...` | Integracja pipeline'u |

Domyślnie dla vc-review: **nie używaj `--quick`**. Używaj `--with-tests
--with-lint` jako bazy. Zachowaj `--deep` na merge gate / wysokie ryzyko.

---

## Układ artifact packa

Wyjście: `$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/<timestamp>/`
(najnowszy = domyślny; symlink `latest`).

Struktura najwyższego poziomu:

- `report.json` — **domyślny ustrukturyzowany raport** (parsuj najpierw)
- `dashboard.html` — interaktywny HTML
- `AI_INDEX.md` — mapa artefaktów + kolejność czytania
- `00_summary/` — `MERGE_GATE.json`, `RUN`, `MANIFEST`, `SANITY.json`,
  `pr-metadata.txt`, `file-status.txt`, `commit-list.txt`
- `10_diff/` — `full.patch`, `per-commit-diffs/`, `per-file-diffs/`
- `20_quality/` — logi/wyniki per-bramka, `checks-errors.log`,
  `coverage-delta.txt`, `BREAKING_CHANGES.md`
- `30_context/` — `INLINE_FINDINGS.sarif`, `changed-tests.txt`,
  wyjście toolingu
- `artifacts.zip` — wszystko spakowane

Pusty / brakujący najnowszy katalog → finding **P0**.

---

## Pipeline JSON

```bash
prview --json --quiet | jq '.checks[] | select(.status == "Failed")'
```

Pod integrację z agentem parsuj:

- `meta` — podsumowanie RUN
- `gate.allow_merge` + `policy_mode` + `reasons` — verdict bramki
- `checks[]` — status / log_path / command per-bramka
- `diff.stats` + `diff.files[]` — skala / churn / hotspoty
- `quality` — breaking / coverage / sarif / heurystyki

---

## Kontekst delegacji do subagenta

Dispatchując subagenta do analizy, osadź:

```
- prview artifacts at: $VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest/
- Parse report.json first (default)
- Read 00_summary/MERGE_GATE.json for quick verdict
- Read 20_quality/checks-errors.log for error details
- Read 10_diff/per-file-diffs/ for hotspot patches
```

---

## Integracja pipeline'u z `vc-followup`

```bash
prview --pr $PR_NUMBER --with-tests --with-lint
ARTIFACTS="$VIBECRAFTED_ROOT/.prview/pr-artifacts/<branch>/latest"
```

Potem dispatchuj `vc-followup` przeciw `$ARTIFACTS` do oceny na poziomie
trajektorii po review.

---

_𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI_
