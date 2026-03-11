---
name: vetcoders-screenscribe
version: 1.0.0
description: >
  ScreenScribe workflow skill for analyzing screencast recordings and for
  working inside the ScreenScribe repo itself. Use this whenever the user
  mentions ScreenScribe, screencast review, app review videos, bug demo
  recordings, HTML Pro reports, extracting actionable findings from narrated
  videos, batch video analysis, or wants to debug/build/improve the
  /Users/maciejgad/hosted/VetCoders/ScreenScribe project. Prefer this skill
  even if the user does not explicitly ask for "ScreenScribe" but clearly wants
  a spoken screen recording turned into structured engineering findings.
---

# VetCoders ScreenScribe

Use this skill for two related jobs:

1. Run ScreenScribe on real recordings and turn them into actionable outputs.
2. Work on the ScreenScribe codebase without guessing its CLI, gates, or report model.

## What ScreenScribe Is

ScreenScribe is an AI-powered screencast analysis tool that:

- extracts audio from videos
- transcribes commentary with timestamps
- detects bugs, change requests, and UI issues
- captures screenshots at relevant moments
- generates JSON, Markdown, and optional HTML Pro reports

Primary commands exposed by the project:

- `review`
- `analyze`
- `transcribe`
- `config`
- `version`

## When To Use

Use this skill when the user wants to:

- analyze a screen recording of an app review
- turn spoken bug commentary into structured findings
- process one or many `.mov` / `.mp4` files
- generate HTML Pro reports, screenshots, or transcripts
- run ScreenScribe in dry-run, estimate, resume, or batch mode
- debug ScreenScribe output, prompts, providers, or report generation
- modify the ScreenScribe repo and keep its quality gates honest

## Default Mindset

Do not treat ScreenScribe like a vague "video AI thing."
It is a concrete pipeline with real steps, real artifacts, and real failure points.

Always establish:

- what the input video set is
- whether the goal is `review`, `analyze`, or `transcribe`
- whether the user wants speed, depth, or interactivity
- whether provider config and FFmpeg are available

## Fast Decision Table

Use this mapping:

- User wants full actionable review from one or more narrated videos:
  - use `review`
- User wants transcript only:
  - use `transcribe`
- User wants interactive/reversed flow server:
  - use `analyze`
- User wants to change the tool itself:
  - work in repo and run repo quality gates

## Canonical Run Paths

Prefer running from the repo for reproducibility:

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
uv run python -m screenscribe --help
```

### Review

Single video:

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
uv run python -m screenscribe review /absolute/path/to/video.mov
```

Batch:

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
uv run python -m screenscribe review /path/video1.mov /path/video2.mov -o /absolute/output/dir
```

Useful flags:

- `--keywords-only`
- `--estimate`
- `--dry-run`
- `--no-vision`
- `--resume`
- `--lang en`
- `-o /path/output`

### Transcribe

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
uv run python -m screenscribe transcribe /absolute/path/to/video.mov -o /absolute/path/to/transcript.txt
```

### Interactive Analyze Server

Preferred:

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
make analyze VIDEO=/absolute/path/to/video.mov PORT=8766
```

## Output Expectations

For a normal review run, expect an output directory like:

```text
{video}_review/
  {video}_transcript.txt
  {video}_report.json
  {video}_report.md
  {video}_report.html
  screenshots/
```

When reporting results back to the user, always include:

- input video(s)
- exact command run
- output directory path
- whether run was full, dry-run, keywords-only, or no-vision
- important blockers or warnings

## Config and Dependencies

Important runtime dependencies:

- Python 3.11+
- `uv`
- FFmpeg
- configured provider credentials / endpoints

Primary config file:

- `~/.config/screenscribe/config.env`

If a run fails, check these first:

1. FFmpeg installed and visible in PATH
2. API keys configured
3. endpoint/model alignment
4. output path permissions
5. whether user wanted `review` but actually needed `transcribe` or `analyze`

Do not invent config values or fake API success.

## Repo Workflows

When editing or debugging ScreenScribe itself, use the repo-native gates:

```bash
cd /Users/maciejgad/hosted/VetCoders/ScreenScribe
make lint
make typecheck
make test
```

Useful extras:

```bash
make security
make test-integration
make test-all
make format
```

If integration tests need external API access and keys are missing, say so clearly and run unit tests plus static gates.

## Investigation Order For Failures

When ScreenScribe behavior looks wrong, debug in this order:

1. command shape
2. input file validity
3. FFmpeg/audio extraction
4. transcription output
5. detection mode choice
6. screenshot extraction
7. semantic / unified analysis
8. report generation
9. HTML Pro rendering/opening

Do not jump straight to model blame before checking pipeline stage boundaries.

## Output Format For ScreenScribe Tasks

Use this response structure when helpful:

```markdown
Current state: what the input is and what ScreenScribe path we are using.
Proposal: which command/workflow best fits and why.
Migration plan: concrete steps or fixes if repo work is involved.
Quick win: the smallest useful run or fix right now.
```

If the task is simple, compress this into a short paragraph.

## Examples

**Example 1**
Input: "Przelec mi ten review.mov i wypluj JSON + markdown z bugami."
Action: run `review` from repo, return output dir and key findings.

**Example 2**
Input: "Mam 3 nagrania sprint review, chcemy kontekst między nimi."
Action: run batch `review` with all files in one command so shared context can matter.

**Example 3**
Input: "Czemu HTML Pro report się nie otwiera po wygenerowaniu?"
Action: inspect report generation, served assets, and `analyze`/report open flow before changing templates.

**Example 4**
Input: "Zmień coś w ScreenScribe i upewnij się, że repo jest zdrowe."
Action: edit repo, then run `make lint`, `make typecheck`, and `make test`.

## Anti-Patterns

Do not:

- treat ScreenScribe as a generic summarizer
- run random repo commands when `make` already defines the quality path
- skip reporting the output directory
- ignore whether the user wants `review` vs `transcribe` vs `analyze`
- claim a run is valid if FFmpeg or provider config is missing
- assume HTML report exists unless the run actually produced it

## Definition of Done

A ScreenScribe task is done when:

- the right command was chosen
- the run or code change actually completed
- output artifacts are named and located
- blockers are concrete if the run could not finish
- repo changes, if any, pass the closest real quality gates
