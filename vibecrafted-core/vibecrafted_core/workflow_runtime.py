from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from .spawn import _stdin_command
from .supervisor_async import AsyncRunHandle, AsyncSupervisor

RESEARCH_AGENTS = ("claude", "codex", "gemini")


@dataclass(frozen=True)
class ChildResult:
    label: str
    agent: str
    run_id: str
    report: Path
    transcript: Path
    exit_code: int | None
    artifact_ok: bool
    artifact_errors: tuple[str, ...]


def _parent_run_id() -> str:
    return os.environ.get("VIBECRAFTED_RUN_ID", "workflow-runtime")


def _parent_report_path() -> Path:
    return Path(os.environ["VIBECRAFTED_REPORT_PATH"]).expanduser()


def _parent_meta_path() -> Path:
    return Path(os.environ["VIBECRAFTED_META_PATH"]).expanduser()


def _child_dir() -> Path:
    base = _parent_report_path().parent / f"{_parent_run_id()}-children"
    base.mkdir(parents=True, exist_ok=True)
    return base


def _child_env(
    agent: str, report: Path, transcript: Path, meta: Path
) -> dict[str, str]:
    env = os.environ.copy()
    env["VIBECRAFTED_AGENT"] = agent
    env["VIBECRAFTED_REPORT_PATH"] = str(report)
    env["VIBECRAFTED_TRANSCRIPT_PATH"] = str(transcript)
    env["VIBECRAFTED_META_PATH"] = str(meta)
    return env


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _read_prompt_file(path: str) -> str:
    if not path:
        return ""
    try:
        return Path(path).expanduser().read_text(encoding="utf-8", errors="replace")
    except OSError:
        return f"Read the requested prompt file yourself: {path}"


def _child_prompt(kind: str, label: str, root: str, prompt: str) -> str:
    marbles_blindness = ""
    if kind == "marbles":
        marbles_blindness = (
            "- You are intentionally blind to prior marbles runs.\n"
            "- Do not read sibling child reports/transcripts unless the operator "
            "prompt explicitly names them.\n"
        )
    return f"""You are running as a supervised Vibecrafted {kind} worker.

Contract:
- Work in repository root: {root}
- Track: {label}
- Do not launch external agent fleets.
- Write your durable report to VIBECRAFTED_REPORT_PATH.
- Let stdout/stderr form VIBECRAFTED_TRANSCRIPT_PATH.
{marbles_blindness}
Operator prompt:
{prompt}
"""


async def _run_child(
    *,
    kind: str,
    label: str,
    agent: str,
    root: str,
    prompt: str,
) -> ChildResult:
    safe_label = "".join(ch if ch.isalnum() else "-" for ch in label).strip("-")
    run_id = f"{_parent_run_id()}-{safe_label}"
    base = _child_dir()
    report = base / f"{safe_label}.md"
    transcript = base / f"{safe_label}.transcript.log"
    meta = base / f"{safe_label}.meta.json"
    prompt_file = base / f"{safe_label}.prompt.md"
    prompt_file.write_text(_child_prompt(kind, label, root, prompt), encoding="utf-8")
    command = _stdin_command(agent)
    handle: AsyncRunHandle = await AsyncSupervisor().run(
        run_id=run_id,
        command=command,
        root=root,
        env=_child_env(agent, report, transcript, meta),
        meta_path=meta,
        report_path=report,
        transcript_path=transcript,
        prompt_file_path=prompt_file,
        require_report=True,
        require_transcript_output=False,
    )
    validation = handle.artifact_validation
    return ChildResult(
        label=label,
        agent=agent,
        run_id=run_id,
        report=report,
        transcript=transcript,
        exit_code=handle.exit_code,
        artifact_ok=bool(validation.ok if validation is not None else False),
        artifact_errors=tuple(validation.errors if validation is not None else ()),
    )


def _write_parent_report(
    kind: str, root: str, prompt: str, results: Sequence[ChildResult]
) -> None:
    ok = all(result.exit_code == 0 and result.artifact_ok for result in results)
    report = _parent_report_path()
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"status: {'completed' if ok else 'failed'}",
        f"skill: vc-{kind}",
        f"run_id: {_parent_run_id()}",
        f"root: {root}",
        "---",
        "",
        f"# vc-{kind} supervised run",
        "",
        "## Operator Prompt",
        "",
        prompt or "(empty)",
        "",
        "## Reception Ledger",
        "",
        "Child reports are supervised artifacts for the parent runtime; they are not automatically injected into later workers.",
        "",
        "## Child Runs",
        "",
    ]
    for result in results:
        errors = ", ".join(result.artifact_errors) if result.artifact_errors else "none"
        lines.extend(
            [
                f"- {result.label} ({result.agent})",
                f"  - run_id: {result.run_id}",
                f"  - exit_code: {result.exit_code}",
                f"  - artifact_ok: {str(result.artifact_ok).lower()}",
                f"  - artifact_errors: {errors}",
                f"  - report: {result.report}",
                f"  - transcript: {result.transcript}",
            ]
        )
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_json(
        _parent_meta_path(),
        {
            "run_id": _parent_run_id(),
            "skill": kind,
            "status": "completed" if ok else "failed",
            "report": str(report),
            "children": [
                {
                    "label": result.label,
                    "agent": result.agent,
                    "run_id": result.run_id,
                    "report": str(result.report),
                    "transcript": str(result.transcript),
                    "exit_code": result.exit_code,
                    "artifact_ok": result.artifact_ok,
                    "artifact_errors": list(result.artifact_errors),
                }
                for result in results
            ],
        },
    )


async def run_research(root: str, prompt: str) -> int:
    tasks = [
        _run_child(
            kind="research",
            label=f"research-{agent}",
            agent=agent,
            root=root,
            prompt=prompt,
        )
        for agent in RESEARCH_AGENTS
    ]
    results = await asyncio.gather(*tasks)
    _write_parent_report("research", root, prompt, results)
    return (
        0
        if all(result.exit_code == 0 and result.artifact_ok for result in results)
        else 1
    )


async def run_marbles(
    root: str, agent: str, prompt: str, count: int, depth: int
) -> int:
    results: list[ChildResult] = []
    for index in range(1, max(count, 1) + 1):
        loop_prompt = (
            f"{prompt}\n\nMarbles loop: L{index}/{count}. Depth target: {depth}. "
            "Start fresh against the current workspace state, find what is still wrong, "
            "over-correct deliberately, and report the next truth."
        )
        result = await _run_child(
            kind="marbles",
            label=f"marbles-L{index}",
            agent=agent,
            root=root,
            prompt=loop_prompt,
        )
        results.append(result)
        if result.exit_code != 0 or not result.artifact_ok:
            break
    _write_parent_report("marbles", root, prompt, results)
    return (
        0
        if len(results) == count
        and all(result.exit_code == 0 and result.artifact_ok for result in results)
        else 1
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Vibecrafted supervised workflow runtimes."
    )
    sub = parser.add_subparsers(dest="command", required=True)
    research = sub.add_parser("research")
    research.add_argument("--root", required=True)
    research.add_argument("--prompt", default="")
    research.add_argument("--prompt-file", default="")
    marbles = sub.add_parser("marbles")
    marbles.add_argument("--agent", default="codex")
    marbles.add_argument("--root", required=True)
    marbles.add_argument("--prompt", default="")
    marbles.add_argument("--prompt-file", default="")
    marbles.add_argument("--count", type=int, default=3)
    marbles.add_argument("--depth", type=int, default=3)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    ns = _parser().parse_args(argv)
    if ns.command == "research":
        prompt = ns.prompt or _read_prompt_file(ns.prompt_file)
        return asyncio.run(run_research(ns.root, prompt))
    if ns.command == "marbles":
        prompt = ns.prompt or _read_prompt_file(ns.prompt_file)
        return asyncio.run(run_marbles(ns.root, ns.agent, prompt, ns.count, ns.depth))
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
