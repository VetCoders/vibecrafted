# VibeCraft ScreenScribe

Skill do pracy z `ScreenScribe`: analizą screencastów oraz samym repo narzędzia.

Kanoniczne repo:

- [VetCoders/Screenscribe](https://github.com/VetCoders/Screenscribe)

To nie jest ogólny skill od “video AI”. To workflow dla konkretnego pipeline’u,
który ma trzy główne warstwy:

- artefakty deterministyczne: audio, transcript, timestampy, bundle
- review pipeline: findings, screenshoty, raporty
- repo/debug path: naprawa i rozwój samego narzędzia

## Kiedy używać

Używaj `vc-screenscribe`, gdy użytkownik chce:

- przeanalizować nagrane demo aplikacji
- zamienić komentarz głosowy z review w uporządkowane findings
- wygenerować screenshoty, transcript, raport HTML Pro albo transcript-first bundle
- przepuścić przez pipeline jeden lub wiele plików `.mov` / `.mp4`
- debugować albo rozwijać repo `ScreenScribe`

## Jak mapować intencję

- pełny review:
  - `screenscribe review ...`
- transcript-first artifact pack:
  - `screenscribe preprocess ...`
- transcript only:
  - `screenscribe transcribe ...`
- tryb interaktywny:
  - `screenscribe analyze ...`

## Fast path

Domyślny odruch przy zwykłym review:

```bash
screenscribe review /absolute/path/to/video.mov
```

Domyślny odruch przy transcript-first handoffie:

```bash
screenscribe preprocess /absolute/path/to/video.mov
```

Repo `ScreenScribe` i `uv run python -m screenscribe ...` są ścieżką drugą, nie pierwszą.
Wchodzimy tam dopiero wtedy, gdy:

- zwykły `screenscribe` CLI jest niedostępny albo popsuty
- debugujemy provider/config/runtime
- użytkownik chce pracować nad samym repo `ScreenScribe`

Nie zakładaj stałej lokalnej ścieżki do checkoutu.
Najpierw używaj bieżącego checkoutu, jeśli user już pracuje w repo.
Jeśli checkout nie jest znany, odnoś się do repo kanonicznego na GitHubie.

## Najważniejsza zasada

Nie ufaj bezrefleksyjnie warstwie AI bardziej niż artefaktom.
W ScreenScribe transcript, timestampy, screenshoty i output dir są prawdą operacyjną.
Model ma je interpretować, nie zastępować.

## Pliki

- `SKILL.md` — canonical workflow i komendy
- `evals/evals.json` — eval harness dla skilla
