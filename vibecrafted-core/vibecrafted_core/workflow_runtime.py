from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from .package_resources import package_root
from .spawn import _stdin_command
from .supervisor_async import AsyncRunHandle, AsyncSupervisor

SUPPORTED_RESEARCH_AGENTS = ("claude", "codex", "gemini", "agy", "junie", "grok")
DEFAULT_RESEARCH_AGENTS = ("claude", "codex", "gemini")


@dataclass(frozen=True)
class ChildResult:
    label: str
    agent: str
    run_id: str
    agent_session_id: str
    agent_model: str
    report: Path
    transcript: Path
    exit_code: int | None
    artifact_ok: bool
    artifact_errors: tuple[str, ...]
    tokens_input: int = 0
    tokens_cached_input: int = 0
    tokens_output: int = 0
    cost_usd: float | None = None
    resume_command: str = ""
    completed_at: str = ""


@dataclass(frozen=True)
class ResearchAgentSelection:
    agents: tuple[str, ...]
    source: str
    ignored: tuple[str, ...] = ()


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


def _safe_label(label: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in label).strip("-")


def _slug(value: str, fallback: str) -> str:
    raw = re.sub(r"[^A-Za-z0-9._-]+", "-", value.lower()).strip("-")
    raw = raw[:64].strip("-")
    return raw or fallback


def _artifact_ts() -> str:
    return os.environ.get("VIBECRAFTED_ARTIFACT_TS") or datetime.now().strftime(
        "%Y-%m-%d"
    )


def _artifact_slug(prompt: str) -> str:
    return os.environ.get("VIBECRAFTED_ARTIFACT_SLUG") or _slug(
        prompt, _parent_run_id()
    )


def _artifact_suffix() -> str:
    return os.environ.get("VIBECRAFTED_ARTIFACT_SUFFIX", "")


def _research_artifact_agent(label: str, agent: str) -> str:
    if label == "research-synthesis":
        return "synthesis"
    if agent:
        return agent
    if label.startswith("research-"):
        return label.removeprefix("research-")
    return _safe_label(label) or "research"


def _canonical_research_dir() -> Path | None:
    raw = os.environ.get("VIBECRAFTED_CANONICAL_REPORT_DIR", "").strip()
    if not raw:
        return None
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _research_artifact_paths(
    *, label: str, agent: str, prompt: str
) -> tuple[Path, Path, Path]:
    base = _canonical_research_dir()
    if base is None:
        child_base = _child_dir()
        safe_label = _safe_label(label)
        return (
            child_base / f"{safe_label}.md",
            child_base / f"{safe_label}.transcript.log",
            child_base / f"{safe_label}.meta.json",
        )
    stem = (
        f"{_artifact_ts()}_"
        f"{_slug(_research_artifact_agent(label, agent), 'agent')}_"
        f"{_artifact_slug(prompt)}_report"
        f"{_artifact_suffix()}"
    )
    return (
        base / f"{stem}.md",
        base / f"{stem}.transcript.log",
        base / f"{stem}.meta.json",
    )


def _child_artifact_paths(
    *, kind: str, label: str, agent: str, prompt: str
) -> tuple[Path, Path, Path, Path]:
    safe_label = _safe_label(label)
    if kind == "research":
        report, transcript, meta = _research_artifact_paths(
            label=label, agent=agent, prompt=prompt
        )
        prompt_file = _child_dir() / f"{safe_label}.prompt.md"
        return report, transcript, meta, prompt_file
    base = _child_dir()
    return (
        base / f"{safe_label}.md",
        base / f"{safe_label}.transcript.log",
        base / f"{safe_label}.meta.json",
        base / f"{safe_label}.prompt.md",
    )


def _child_env(
    agent: str, report: Path, transcript: Path, meta: Path
) -> dict[str, str]:
    env = os.environ.copy()
    env["VIBECRAFTED_AGENT"] = agent
    env["VIBECRAFTED_REPORT_PATH"] = str(report)
    env["VIBECRAFTED_TRANSCRIPT_PATH"] = str(transcript)
    env["VIBECRAFTED_META_PATH"] = str(meta)
    return env


def _tee_enabled() -> bool:
    return os.environ.get("VIBECRAFTED_TEE_OUTPUT") == "1"


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


def _repo_root() -> Path:
    return package_root()


def _user_config_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home.expanduser() / "vibecrafted" / "config.toml"


def _manifest_config_paths() -> tuple[Path, ...]:
    roots = [
        Path(os.environ["VIBECRAFTED_ROOT"]).expanduser()
        if os.environ.get("VIBECRAFTED_ROOT")
        else None,
        _repo_root(),
        (
            Path(os.environ["VIBECRAFTED_TOOLS_HOME"]).expanduser()
            / "vibecrafted-current"
            if os.environ.get("VIBECRAFTED_TOOLS_HOME")
            else None
        ),
    ]
    paths: list[Path] = []
    for root in roots:
        if root is None:
            continue
        path = root / "install.toml"
        if path not in paths:
            paths.append(path)
    return tuple(paths)


def _split_agent_tokens(raw: object) -> list[str]:
    if isinstance(raw, str):
        return [item.strip() for item in raw.replace(",", " ").split() if item.strip()]
    if isinstance(raw, (list, tuple)):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _select_supported_agents(
    tokens: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    agents: list[str] = []
    ignored: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        agent = token.strip()
        if not agent:
            continue
        if agent not in SUPPORTED_RESEARCH_AGENTS:
            ignored.append(agent)
            continue
        if agent in seen:
            continue
        seen.add(agent)
        agents.append(agent)
    return tuple(agents), tuple(ignored)


def _read_research_agents_from_toml(path: Path) -> tuple[str, ...]:
    if not path.is_file():
        return ()
    try:
        with path.open("rb") as handle:
            data = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        print(f"Failed to read research agent config: {path}: {exc}", file=sys.stderr)
        return ()
    raw = (
        data.get("runtime", {})
        .get("picking", {})
        .get("research", {})
        .get("default_agents", [])
    )
    return tuple(_split_agent_tokens(raw))


def research_agent_selection() -> ResearchAgentSelection:
    env_agents = os.environ.get("VIBECRAFTED_RESEARCH_AGENTS", "").strip()
    if env_agents:
        agents, ignored = _select_supported_agents(_split_agent_tokens(env_agents))
        return ResearchAgentSelection(
            agents, "env:VIBECRAFTED_RESEARCH_AGENTS", ignored
        )

    user_config = _user_config_path()
    tokens = _read_research_agents_from_toml(user_config)
    if tokens:
        agents, ignored = _select_supported_agents(tokens)
        return ResearchAgentSelection(agents, str(user_config), ignored)

    for manifest in _manifest_config_paths():
        tokens = _read_research_agents_from_toml(manifest)
        if not tokens:
            continue
        agents, ignored = _select_supported_agents(tokens)
        return ResearchAgentSelection(agents, str(manifest), ignored)

    return ResearchAgentSelection(DEFAULT_RESEARCH_AGENTS, "builtin-default")


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
- Skill: vc-{kind}
- Track: {label}
- Do not launch external agent fleets.
- Write your durable report to VIBECRAFTED_REPORT_PATH.
- Let stdout/stderr form VIBECRAFTED_TRANSCRIPT_PATH.
{marbles_blindness}
Operator prompt:
{prompt}
"""


def _loop_prompt(kind: str, prompt: str, index: int, count: int, depth: int) -> str:
    if kind == "polarize":
        instruction = (
            f"Polarize loop: L{index}/{count}. Depth target: {depth}. "
            "Start fresh against the current workspace state, strip back marbles "
            "excess, reject competing axes, and choose one runtime truth."
        )
    else:
        instruction = (
            f"Marbles loop: L{index}/{count}. Depth target: {depth}. "
            "Start fresh against the current workspace state, find what is still wrong, "
            "over-correct deliberately, and report the next truth."
        )
    return f"{prompt}\n\n{instruction}"


def _research_synthesis_prompt(
    root: str, prompt: str, results: Sequence[ChildResult]
) -> str:
    reports = "\n".join(
        f"- {result.agent}: {result.report}" for result in results if result.report
    )
    return f"""You are resuming the last completed vc-research lane to produce the objective synthesis.

Contract:
- Work in repository root: {root}
- This is not new research; synthesize only from the completed research reports.
- Read every source report fully before citing it.
- Write the synthesis report to VIBECRAFTED_REPORT_PATH.
- Use concise file:path citations to source reports; do not inline full reports.
- Surface convergent findings, single-agent signals, disagreements, and the operator-ready recommendation.

Original operator prompt:
{prompt}

Research reports:
{reports}
"""


def _resume_stdin_command(agent: str, session_id: str) -> list[str]:
    if agent == "claude":
        return [
            "claude",
            "--resume",
            session_id,
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
    if agent == "codex":
        return [
            "codex",
            "resume",
            session_id,
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "-",
        ]
    if agent == "gemini":
        return [
            "gemini",
            "--resume",
            session_id,
            "-p",
            "",
            "--approval-mode",
            "yolo",
            "-o",
            "stream-json",
        ]
    if agent == "agy":
        return [
            "agy",
            "--conversation",
            session_id,
            "--print",
            "--dangerously-skip-permissions",
            "--add-dir",
            ".",
            "--print-timeout",
            "30m",
            "",
        ]
    if agent == "junie":
        return [
            "junie",
            "--resume",
            "--session-id",
            session_id,
            "--project",
            ".",
            "--skip-update-check",
            "--input-format",
            "text",
            "--output-format",
            "json-stream",
        ]
    if agent == "grok":
        return [
            "grok",
            "--resume",
            session_id,
            "--cwd",
            ".",
            "--permission-mode",
            "bypassPermissions",
            "--no-alt-screen",
            "--output-format",
            "streaming-json",
            "--prompt-file",
            "/dev/stdin",
        ]
    return _stdin_command(agent)


async def _run_child(
    *,
    kind: str,
    label: str,
    agent: str,
    root: str,
    prompt: str,
    command: Sequence[str] | None = None,
    prompt_body: str | None = None,
) -> ChildResult:
    safe_label = _safe_label(label)
    run_id = f"{_parent_run_id()}-{safe_label}"
    report, transcript, meta, prompt_file = _child_artifact_paths(
        kind=kind,
        label=label,
        agent=agent,
        prompt=prompt,
    )
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(
        prompt_body or _child_prompt(kind, label, root, prompt), encoding="utf-8"
    )
    child_command = list(command) if command is not None else _stdin_command(agent)
    if _tee_enabled():
        print(f"\n===== {kind}:{label}:{agent} =====", flush=True)
    handle: AsyncRunHandle = await AsyncSupervisor().run(
        run_id=run_id,
        command=child_command,
        root=root,
        env=_child_env(agent, report, transcript, meta),
        meta_path=meta,
        report_path=report,
        transcript_path=transcript,
        prompt_file_path=prompt_file,
        require_report=True,
        require_transcript_output=False,
        tee_output=_tee_enabled(),
    )
    validation = handle.artifact_validation
    return ChildResult(
        label=label,
        agent=agent,
        run_id=run_id,
        agent_session_id=handle.agent_session_id,
        agent_model=handle.agent_model,
        report=report,
        transcript=transcript,
        exit_code=handle.exit_code,
        artifact_ok=bool(validation.ok if validation is not None else False),
        artifact_errors=tuple(validation.errors if validation is not None else ()),
        tokens_input=handle.tokens_input,
        tokens_cached_input=handle.tokens_cached_input,
        tokens_output=handle.tokens_output,
        cost_usd=handle.cost_usd,
        resume_command=handle.resume_command,
        completed_at=handle.completed_at.isoformat() if handle.completed_at else "",
    )


def _child_result_from_meta(label: str, meta_path: Path) -> ChildResult | None:
    try:
        payload = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    report = Path(str(payload.get("report") or meta_path.with_suffix(".md")))
    transcript = Path(
        str(payload.get("transcript") or meta_path.with_suffix(".transcript.log"))
    )
    exit_code_raw = payload.get("exit_code")
    exit_code: int | None
    try:
        exit_code = int(exit_code_raw) if exit_code_raw is not None else None
    except (TypeError, ValueError):
        exit_code = None
    errors = payload.get("artifact_errors") or []
    artifact_errors = (
        tuple(str(item) for item in errors)
        if isinstance(errors, list)
        else (str(errors),)
    )
    if exit_code is None and not artifact_errors and _non_empty_file(report):
        exit_code = 0
    return ChildResult(
        label=label,
        agent=str(payload.get("agent") or ""),
        run_id=str(payload.get("run_id") or ""),
        agent_session_id=str(
            payload.get("agent_session_id") or payload.get("session_id") or ""
        ),
        agent_model=str(payload.get("agent_model") or payload.get("model") or ""),
        report=report,
        transcript=transcript,
        exit_code=exit_code,
        artifact_ok=not artifact_errors and exit_code == 0 and report.is_file(),
        artifact_errors=artifact_errors,
        tokens_input=int(payload.get("tokens_input") or 0),
        tokens_cached_input=int(payload.get("tokens_cached_input") or 0),
        tokens_output=int(payload.get("tokens_output") or 0),
        cost_usd=payload.get("cost_usd")
        if isinstance(payload.get("cost_usd"), float)
        else None,
        resume_command=str(payload.get("resume_command") or ""),
        completed_at=str(
            payload.get("completed_at") or payload.get("updated_at") or ""
        ),
    )


def _non_empty_file(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _lane_meta_path(agent: str) -> Path:
    return _research_artifact_paths(
        label=f"research-{agent}",
        agent=agent,
        prompt="",
    )[2]


def _research_quorum(total: int) -> int:
    """Survivors needed for a research swarm to still count as a success.

    Majority of the configured lanes (``floor(N/2) + 1``): 2-of-3, 3-of-5.
    A 2-lane swarm needs both — there is no majority below the full set.
    """

    if total <= 0:
        return 0
    return total // 2 + 1


def _research_survivors(results: Sequence[ChildResult]) -> list[ChildResult]:
    return [r for r in results if r.exit_code == 0 and r.artifact_ok]


def _research_run_status(
    results: Sequence[ChildResult],
    synthesis: ChildResult | None,
    *,
    kind: str,
) -> str:
    """Three-way outcome for a supervised swarm run.

    Research degrades gracefully: a majority of surviving lanes plus a valid
    synthesis is ``partial_success`` (a green run, not a failure) instead of
    collapsing the whole swarm to ``failed`` on a single dead lane. Non-research
    kinds (marbles/polarize) keep the strict all-or-nothing contract.
    """

    total = len(results)
    if total == 0:
        return "failed"
    survivors = _research_survivors(results)
    all_ok = len(survivors) == total
    if kind != "research":
        return "completed" if all_ok else "failed"
    synthesis_ok = (
        synthesis is not None and synthesis.exit_code == 0 and synthesis.artifact_ok
    )
    if not synthesis_ok:
        return "failed"
    if all_ok:
        return "completed"
    if len(survivors) >= _research_quorum(total):
        return "partial_success"
    return "failed"


async def _wait_for_research_lanes(
    agents: Sequence[str],
    *,
    timeout_seconds: float = 86400,
    interval_seconds: float = 5,
) -> list[ChildResult]:
    quorum = _research_quorum(len(agents))
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while True:
        results: list[ChildResult] = []
        pending: list[str] = []
        failed = 0
        for agent in agents:
            result = _child_result_from_meta(
                f"research-{agent}", _lane_meta_path(agent)
            )
            if result is None or result.exit_code is None:
                pending.append(agent)
            elif result.agent:
                results.append(result)
                if result.exit_code != 0 or not result.artifact_ok:
                    failed += 1
        # Stop waiting only when the majority can no longer be reached, even if
        # every still-pending lane were to succeed. A single dead lane no longer
        # short-circuits the survivors — we keep waiting so synthesis can run on
        # the quorum (the orchestration-robustness fix).
        if failed > len(agents) - quorum:
            return results
        if not pending:
            return results
        if asyncio.get_running_loop().time() >= deadline:
            if len(results) - failed >= quorum:
                print(
                    "research lanes timed out; proceeding with quorum "
                    f"{len(results) - failed}/{len(agents)} (pending: "
                    f"{', '.join(pending)})",
                    file=sys.stderr,
                    flush=True,
                )
                return results
            missing = ", ".join(pending)
            raise TimeoutError(f"timed out waiting for research lanes: {missing}")
        print(f"waiting for research lanes: {', '.join(pending)}", flush=True)
        await asyncio.sleep(interval_seconds)


def _failed_synthesis_result(last: ChildResult, reason: str) -> ChildResult:
    report, transcript, _meta, _prompt_file = _child_artifact_paths(
        kind="research",
        label="research-synthesis",
        agent=last.agent,
        prompt="",
    )
    now = datetime.now(timezone.utc).isoformat()
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "---\nstatus: failed\n---\n\n"
        f"# vc-research synthesis failed\n\nReason: {reason}\n",
        encoding="utf-8",
    )
    transcript.write_text(reason + "\n", encoding="utf-8")
    return ChildResult(
        label="research-synthesis",
        agent=last.agent,
        run_id=f"{_parent_run_id()}-research-synthesis",
        agent_session_id=last.agent_session_id,
        agent_model=last.agent_model,
        report=report,
        transcript=transcript,
        exit_code=1,
        artifact_ok=False,
        artifact_errors=(reason,),
        resume_command=last.resume_command,
        completed_at=now,
    )


async def _run_research_synthesis(
    root: str, prompt: str, results: Sequence[ChildResult]
) -> ChildResult | None:
    survivors = _research_survivors(results)
    if not survivors or len(survivors) < _research_quorum(len(results)):
        return None
    last = max(survivors, key=lambda item: item.completed_at or "")
    if not last.agent_session_id:
        return _failed_synthesis_result(last, "missing_agent_session_id_for_resume")
    return await _run_child(
        kind="research",
        label="research-synthesis",
        agent=last.agent,
        root=root,
        prompt=prompt,
        command=_resume_stdin_command(last.agent, last.agent_session_id),
        prompt_body=_research_synthesis_prompt(root, prompt, survivors),
    )


def _write_parent_report(
    kind: str,
    root: str,
    prompt: str,
    results: Sequence[ChildResult],
    *,
    synthesis: ChildResult | None = None,
    research_selection: ResearchAgentSelection | None = None,
) -> None:
    status = _research_run_status(results, synthesis, kind=kind)
    report = _parent_report_path()
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        f"status: {status}",
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
        "Child reports are supervised artifacts for the parent runtime. Research synthesis resumes the last-finishing lane so the reducer can use native agent context/cache.",
        "",
    ]
    if research_selection is not None:
        lines.extend(
            [
                "## Research Lane Selection",
                "",
                f"- source: {research_selection.source}",
                f"- agents: {', '.join(research_selection.agents) or 'none'}",
                f"- ignored: {', '.join(research_selection.ignored) or 'none'}",
                "",
            ]
        )
    if synthesis is not None:
        lines.extend(
            [
                "## Synthesis",
                "",
                f"- {synthesis.label} ({synthesis.agent})",
                f"  - run_id: {synthesis.run_id}",
                f"  - agent_session_id: {synthesis.agent_session_id or 'unknown'}",
                f"  - agent_model: {synthesis.agent_model or 'unknown'}",
                f"  - exit_code: {synthesis.exit_code}",
                f"  - artifact_ok: {str(synthesis.artifact_ok).lower()}",
                f"  - resume: {synthesis.resume_command}",
                f"  - report: {synthesis.report}",
                f"  - transcript: {synthesis.transcript}",
                "",
            ]
        )
    elif kind == "research":
        lines.extend(["## Synthesis", "", "- skipped: child run failure", ""])
    lines.extend(["## Child Runs", ""])
    for result in results:
        errors = ", ".join(result.artifact_errors) if result.artifact_errors else "none"
        lines.extend(
            [
                f"- {result.label} ({result.agent})",
                f"  - run_id: {result.run_id}",
                f"  - agent_session_id: {result.agent_session_id or 'unknown'}",
                f"  - agent_model: {result.agent_model or 'unknown'}",
                f"  - exit_code: {result.exit_code}",
                f"  - artifact_ok: {str(result.artifact_ok).lower()}",
                f"  - artifact_errors: {errors}",
                f"  - tokens: {result.tokens_input} in ({result.tokens_cached_input} cached) / {result.tokens_output} out",
                f"  - cost_usd: {result.cost_usd if result.cost_usd is not None else 'unknown'}",
                f"  - resume: {result.resume_command}",
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
            "status": status,
            "report": str(report),
            "research_agent_source": research_selection.source
            if research_selection is not None
            else "",
            "research_agents": list(research_selection.agents)
            if research_selection is not None
            else [],
            "research_ignored_agents": list(research_selection.ignored)
            if research_selection is not None
            else [],
            "synthesis": {
                "label": synthesis.label,
                "agent": synthesis.agent,
                "run_id": synthesis.run_id,
                "agent_session_id": synthesis.agent_session_id,
                "agent_model": synthesis.agent_model,
                "report": str(synthesis.report),
                "transcript": str(synthesis.transcript),
                "exit_code": synthesis.exit_code,
                "artifact_ok": synthesis.artifact_ok,
                "artifact_errors": list(synthesis.artifact_errors),
                "resume_command": synthesis.resume_command,
            }
            if synthesis is not None
            else {},
            "children": [
                {
                    "label": result.label,
                    "agent": result.agent,
                    "run_id": result.run_id,
                    "agent_session_id": result.agent_session_id,
                    "agent_model": result.agent_model,
                    "report": str(result.report),
                    "transcript": str(result.transcript),
                    "exit_code": result.exit_code,
                    "artifact_ok": result.artifact_ok,
                    "artifact_errors": list(result.artifact_errors),
                    "tokens_input": result.tokens_input,
                    "tokens_cached_input": result.tokens_cached_input,
                    "tokens_output": result.tokens_output,
                    "tokens_total": result.tokens_input + result.tokens_output,
                    "cost_usd": result.cost_usd
                    if result.cost_usd is not None
                    else "unknown",
                    "resume_command": result.resume_command,
                    "completed_at": result.completed_at,
                }
                for result in results
            ],
        },
    )


async def run_research(root: str, prompt: str) -> int:
    selection = research_agent_selection()
    for agent in selection.ignored:
        print(
            f"Ignoring unsupported research agent from runtime picking config: {agent}",
            file=sys.stderr,
        )
    if not selection.agents:
        print("vc-research: no supported research agents configured.", file=sys.stderr)
        return 1
    tasks = [
        _run_child(
            kind="research",
            label=f"research-{agent}",
            agent=agent,
            root=root,
            prompt=prompt,
        )
        for agent in selection.agents
    ]
    results = await asyncio.gather(*tasks)
    synthesis = await _run_research_synthesis(root, prompt, results)
    _write_parent_report(
        "research",
        root,
        prompt,
        results,
        synthesis=synthesis,
        research_selection=selection,
    )
    return (
        0
        if _research_run_status(results, synthesis, kind="research")
        in {"completed", "partial_success"}
        else 1
    )


async def run_research_lane(root: str, prompt: str, agent: str) -> int:
    if agent not in SUPPORTED_RESEARCH_AGENTS:
        print(f"vc-research: unsupported research agent: {agent}", file=sys.stderr)
        return 1
    result = await _run_child(
        kind="research",
        label=f"research-{agent}",
        agent=agent,
        root=root,
        prompt=prompt,
    )
    return 0 if result.exit_code == 0 and result.artifact_ok else 1


async def run_research_synthesis(root: str, prompt: str) -> int:
    selection = research_agent_selection()
    for agent in selection.ignored:
        print(
            f"Ignoring unsupported research agent from runtime picking config: {agent}",
            file=sys.stderr,
        )
    if not selection.agents:
        print("vc-research: no supported research agents configured.", file=sys.stderr)
        return 1
    timeout = float(os.environ.get("VIBECRAFTED_RESEARCH_SYNTHESIS_TIMEOUT", "86400"))
    try:
        results = await _wait_for_research_lanes(
            selection.agents, timeout_seconds=timeout
        )
    except TimeoutError as exc:
        print(str(exc), file=sys.stderr)
        _write_parent_report(
            "research",
            root,
            prompt,
            [],
            research_selection=selection,
        )
        return 1
    synthesis = await _run_research_synthesis(root, prompt, results)
    _write_parent_report(
        "research",
        root,
        prompt,
        results,
        synthesis=synthesis,
        research_selection=selection,
    )
    return (
        0
        if _research_run_status(results, synthesis, kind="research")
        in {"completed", "partial_success"}
        else 1
    )


async def run_marbles(
    root: str,
    agent: str,
    prompt: str,
    count: int,
    depth: int,
    workflow: str = "marbles",
) -> int:
    kind = _safe_label(workflow) or "marbles"
    results: list[ChildResult] = []
    for index in range(1, max(count, 1) + 1):
        loop_prompt = _loop_prompt(kind, prompt, index, count, depth)
        result = await _run_child(
            kind=kind,
            label=f"{kind}-L{index}",
            agent=agent,
            root=root,
            prompt=loop_prompt,
        )
        results.append(result)
        if result.exit_code != 0 or not result.artifact_ok:
            break
    _write_parent_report(kind, root, prompt, results)
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
    research_lane = sub.add_parser("research-lane")
    research_lane.add_argument("--agent", required=True)
    research_lane.add_argument("--root", required=True)
    research_lane.add_argument("--prompt", default="")
    research_lane.add_argument("--prompt-file", default="")
    research_synthesis = sub.add_parser("research-synthesis")
    research_synthesis.add_argument("--root", required=True)
    research_synthesis.add_argument("--prompt", default="")
    research_synthesis.add_argument("--prompt-file", default="")
    marbles = sub.add_parser("marbles")
    marbles.add_argument("--workflow", default="marbles")
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
    if ns.command == "research-lane":
        prompt = ns.prompt or _read_prompt_file(ns.prompt_file)
        return asyncio.run(run_research_lane(ns.root, prompt, ns.agent))
    if ns.command == "research-synthesis":
        prompt = ns.prompt or _read_prompt_file(ns.prompt_file)
        return asyncio.run(run_research_synthesis(ns.root, prompt))
    if ns.command == "marbles":
        prompt = ns.prompt or _read_prompt_file(ns.prompt_file)
        return asyncio.run(
            run_marbles(ns.root, ns.agent, prompt, ns.count, ns.depth, ns.workflow)
        )
    return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
