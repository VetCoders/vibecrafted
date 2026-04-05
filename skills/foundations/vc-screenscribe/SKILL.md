---
name: screenscribe
description: >
  Convert screen recordings into structured engineering findings.
  Use screenscribe CLI as the bridge between visual demos and code truth.
---

# ScreenScribe — Video to Engineering Findings

ScreenScribe captures product-surface truth by turning narrated bug demos
and screen recordings into structured, actionable engineering findings.

## Hard Rules

1. **Show, don't just tell**: use `screenscribe` when a bug is easier to demo than to explain.
2. **Product-surface truth**: consume recordings to verify the real install/onboarding path.
3. **Audit evidence**: use ScreenScribe output as empirical evidence for `vc-dou` audits.

## Standard Workflow

### 1) Capture Demo

- Record the bug or feature flow.
- Ensure audio narration is clear for the AI to extract context.

### 2) Process with ScreenScribe

- Run `screenscribe <VIDEO_FILE>` (or use internal integrations).
- Output: structured findings, segments, and technical transcript.

### 3) Review Findings

- Use the generated findings to triage bugs or verify UI polish.
- Integrate findings into `vc-followup` or `vc-dou` reports.

## CLI Reference

| Command                  | Purpose                             |
| ------------------------ | ----------------------------------- |
| `screenscribe <VIDEO>`   | Analyze video and generate findings |
| `screenscribe --version` | Verify installation                 |

## Binary Details

- Binary: `screenscribe` (resolve via `command -v screenscribe`)
- Source: `https://github.com/VetCoders/Screenscribe`
- Install: `pip install screenscribe` (install from source if not on PyPI)
