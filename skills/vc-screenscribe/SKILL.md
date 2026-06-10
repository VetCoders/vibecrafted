---
name: vc-screenscribe
version: 1.2.1
description: >
  ScreenScribe workflow skill for analyzing screencast recordings and for
  working inside the ScreenScribe repo itself. Use this whenever the user
  mentions ScreenScribe, screencast review, app review videos, bug demo
  recordings, HTML Pro reports, transcript-first artifact extraction,
  extracting actionable findings from narrated videos, batch video analysis,
  or wants to debug/build/improve the ScreenScribe project or the default
  https://github.com/VetCoders/Screenscribe repository. Prefer this skill even
  if the user does not explicitly ask for "ScreenScribe" but clearly wants a
  spoken screen recording turned into structured engineering findings.
loctree_value: "primary repo map for structural/literal repository work"
aicx_value: "intent, session, and decision-context retrieval"
dogfooding: "required for repo-impacting work"
---

<!-- fleet-imperative: v1 -->

> **Invoking `/vc-screenscribe` means you are DISPATCHING THE 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍 FLEET** — real,
> out-of-process agents launched through `vibecrafted <workflow> <agent>`. This invocation
> is an **imperative to act**, **not a no-op**, and **not** native in-process subagents.
> If you loaded this skill and find yourself reaching for an in-thread tool (e.g. native
> `Workflow`), STOP and dispatch through the launcher. The **sole** exception is
> `vc-delegate` (native in-process subagents) — every other `/vc-*` is the fleet.

<!-- /fleet-imperative -->

# Vibecrafted. ScreenScribe

Use this skill for two related jobs:

1. Run ScreenScribe on real recordings and turn them into actionable outputs.
2. Work on the ScreenScribe codebase without guessing its CLI, gates, or report model.

## Canonical Orientation Gate

For ScreenScribe repo work, run or consume the `vc-init` procedure before
editing, planning, or release judgement. `Loctree:loctree` is the default
structural perception skill for that pass and must produce or refresh the
Code-Derived Application Map.

If fresh `vc-init` evidence is absent, perform the init pass first and treat
ScreenScribe repo work as blocked until repo truth exists.

For pure video-analysis runs, state the no-repo exception and use the installed
ScreenScribe CLI directly.

## Repository Work Doctrine

For repository work, start with Loctree as the map: use `loct context`,
`loct occurrences`, `loct body`, and `loct find --literal` before broad manual
search. Use AICX for intent and session context. Use rg/grep as fallback or
local magnifier, not as a replacement for structural mapping. If Loctree fails
or misses a surface, append feedback to `~/.vibecrafted/loctree/loctree-fail.md`.

## What ScreenScribe Is

ScreenScribe is a screencast pipeline, not a vague "video AI thing."

Its strongest value is artifact production:

- extracts audio from videos
- transcribes commentary with timestamps
- detects bugs, change requests, and UI issues
- captures screenshots at relevant moments
- generates transcript, JSON, Markdown, and optional HTML Pro outputs

Primary commands exposed by the project:

- `review`
- `analyze`
- `transcribe`
- `preprocess`
- `config`
- `version`

## When To Use

Use this skill when the user wants to:

- analyze a screen recording of an app review
- turn spoken bug commentary into structured findings
- process one or many `.mov` / `.mp4` files
- generate HTML Pro reports, screenshots, transcripts, or transcript-first bundles
- run ScreenScribe in dry-run, estimate, resume, or batch mode
- extract artifacts first and let an agent/model analyze them later
- debug ScreenScribe output, prompts, providers, or report generation
- modify the ScreenScribe repo and keep its quality gates honest

## Default Mindset

Do not treat ScreenScribe like a model endpoint.
Treat it like a concrete pipeline with real stages, real artifacts, and real failure points.

Default to the shortest working path.
If the user hands you a video and wants review findings, the first move is usually just:

```bash
screenscribe review /absolute/path/to/video.mov
```

Do not start by circling around `uv run`, repo internals, or `--help` unless:

- the user explicitly wants repo/debug work
- the `screenscribe` command is missing
- the first real run failed and you are diagnosing why

Always establish:

- what the input video set is
- whether the goal is `review`, `preprocess`, `analyze`, or `transcribe`
- whether the user wants speed, depth, interactivity, or artifact extraction
- whether provider config and FFmpeg are available

## Fast Decision Table

Use this mapping:

- User wants full actionable review from one or more narrated videos:
  - use `screenscribe review ...`
- User wants transcript-first artifact bundle for downstream model/agent work:
  - use `screenscribe preprocess ...`
- User wants transcript only:
  - use `screenscribe transcribe ...`
- User wants interactive/reversed flow server:
  - use `screenscribe analyze ...` or repo `make analyze`
- User wants to change the tool itself:
  - work in repo and run repo quality gates

## Fast Path First

For normal user-facing video analysis, prefer the installed CLI directly:

```bash
screenscribe review /absolute/path/to/video.mov
```

Batch:

```bash
screenscribe review /path/video1.mov /path/video2.mov -o /absolute/output/dir
```

Transcript-first bundle:

```bash
screenscribe preprocess /absolute/path/to/video.mov
```

Transcript only:

```bash
screenscribe transcribe /absolute/path/to/video.mov -o /absolute/path/to/transcript.txt
```

This is the default path unless it fails.

## Transcript-First Lane

`preprocess` is the artifact-first lane.
Use it when the user wants the deterministic parts of the pipeline without committing to semantic/VLM analysis.

Expected bundle:

```text
{video}_preprocess/
  transcript.txt
  transcript.timestamped.txt
  transcript.segments.json
  transcript.vtt
  preprocess.json
  audio.mp3
```

This is the best handoff shape when:

- a later model/agent should choose timestamps or POIs
- the user wants transcript and timing truth first
- analysis quality is suspect and the artifact pack matters more

## Repo / Debug Path

Canonical upstream repo:

- [VetCoders/Screenscribe](https://github.com/VetCoders/Screenscribe)

When repo work is needed, prefer the current ScreenScribe checkout if the user
already opened one. Do not assume a fixed local path. If no checkout is open,
refer to the default repo above and only mention a local path once it is
actually known.

Drop into the repo only when:

- the CLI is missing or broken
- provider/config/runtime debugging is needed
- the user wants work on ScreenScribe itself

Then prefer:

```bash
cd /path/to/ScreenScribe
uv run python -m screenscribe review /absolute/path/to/video.mov
```

### Review

Single video:

```bash
cd /path/to/ScreenScribe
uv run python -m screenscribe review /absolute/path/to/video.mov
```

Batch:

```bash
cd /path/to/ScreenScribe
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

### Preprocess

```bash
cd /path/to/ScreenScribe
uv run python -m screenscribe preprocess /absolute/path/to/video.mov
```

Useful flags:

- `--no-audio`
- `--force`
- `--lang en`
- `-o /path/output`

### Transcribe

```bash
cd /path/to/ScreenScribe
uv run python -m screenscribe transcribe /absolute/path/to/video.mov -o /absolute/path/to/transcript.txt
```

### Interactive Analyze Server

Preferred:

```bash
cd /path/to/ScreenScribe
make analyze VIDEO=/absolute/path/to/video.mov PORT=8766
```

### Safe Triage Commands

Only use these if the normal `screenscribe review ...` or `screenscribe preprocess ...` path failed:

```bash
screenscribe review --help
screenscribe preprocess --help
screenscribe version
ffmpeg -version
test -f ~/.config/screenscribe/config.env && echo CONFIG_OK || echo CONFIG_MISSING
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

For preprocess, expect the transcript-first bundle described above.

When reporting results back to the user, always include:

- input video(s)
- exact command run
- output directory path
- whether run was full, preprocess-only, dry-run, keywords-only, or no-vision
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
5. whether user wanted `review` but actually needed `preprocess`, `transcribe`, or `analyze`

Do not invent config values or fake API success.

## Repo Workflows

When editing or debugging ScreenScribe itself, use the repo-native gates:

```bash
cd /path/to/ScreenScribe
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
5. detection or preprocess mode choice
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
Input: "Przeleć mi ten review.mov i wypluj JSON + markdown z bugami."
Action: run `screenscribe review /absolute/path/to/review.mov`, return output dir and key findings.

**Example 2**
Input: "Mam video, ale chcę tylko transcript, timestampy i pack dla agenta."
Action: run `screenscribe preprocess /absolute/path/to/video.mov`, return bundle dir and artifact list.

**Example 3**
Input: "W repo https://github.com/VetCoders/Screenscribe coś popsuliśmy w HTML Pro."
Action: treat this as repo work, use repo-native commands and quality gates, not a plain review run.

## Anti-Patterns

Do not:

- treat ScreenScribe as a generic summarizer
- start with repo plumbing when a plain `screenscribe review <file>` or `screenscribe preprocess <file>` would do
- probe `--help` before the first real run on a normal video-analysis request
- run random repo commands when `make` already defines the quality path
- skip reporting the output directory
- ignore whether the user wants `review` vs `preprocess` vs `transcribe` vs `analyze`
- claim a run is valid if FFmpeg or provider config is missing
- assume HTML report exists unless the run actually produced it
- trust the AI layer more than the transcript/screenshot artifacts when they disagree

## Definition of Done

A ScreenScribe task is done when:

- the right command was chosen
- the run or code change actually completed
- output artifacts are named and located
- blockers are concrete if the run could not finish
- repo changes, if any, pass the closest real quality gates

## Fleet Dispatch Terminal

This skill's flow ends in action, never in absorbed prose. The named action here
is running the actual `screenscribe` command (`review`, `preprocess`,
`transcribe`, `analyze`) on the recording. When the findings demand repo work
beyond a bounded in-session cut, dispatch a fleet worker on them:

```bash
vibecrafted workflow <agent> --file <plan-built-from-screenscribe-findings>
```

No `screenscribe` run and no dispatch fired means the invocation was a no-op —
the failure mode this terminal forbids.
