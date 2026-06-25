from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shlex
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

from .agent_dispatch import extract_session_id, sandbox_supported
from .control_plane import ensure_session_id, normalize_run_root
from .events import append_event

EventCallback = Callable[[dict[str, Any]], None]

ANSI_PATTERN = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")
SESSION_PATTERNS = (
    re.compile(
        r"(?:^|\[[0-9]{2}:[0-9]{2}:[0-9]{2}\]\s+)session:\s*([A-Za-z0-9][A-Za-z0-9._:-]*)",
        re.MULTILINE,
    ),
    re.compile(
        r"\b(?:thread|conversation|session)[_-]?id['\"]?\s*[:=]\s*['\"]?([A-Za-z0-9][A-Za-z0-9._:-]*)",
        re.IGNORECASE,
    ),
)
TOKEN_PATTERN = re.compile(
    r"tokens:\s*([0-9]+)\s+in(?:\s*\(([0-9]+)\s+cached\))?\s*/\s*([0-9]+)\s+out",
    re.IGNORECASE,
)
# Authoritative per-run totals emitted by the run-closure footer
# (supervisor_async writes these for EVERY agent). Preferred over the
# per-event `tokens: N in / N out` lines, which only some provider
# formatters render and which would otherwise sum partial streaming usage.
FOOTER_TOKEN_PATTERNS = {
    "input": re.compile(r"^tokens_input:\s*([0-9]+)", re.IGNORECASE | re.MULTILINE),
    "cached_input": re.compile(
        r"^tokens_cached_input:\s*([0-9]+)", re.IGNORECASE | re.MULTILINE
    ),
    "output": re.compile(r"^tokens_output:\s*([0-9]+)", re.IGNORECASE | re.MULTILINE),
}
COST_PATTERNS = (
    re.compile(r"cost(?:_usd)?\s*[:=]\s*\$?([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE),
    re.compile(r"\$([0-9]+\.[0-9]+)\s*(?:usd)?", re.IGNORECASE),
)
MODEL_ENV_VARS = (
    "VIBECRAFTED_PARENT_MODEL",
    "CLAUDE_MODEL",
    "CODEX_MODEL",
    "GEMINI_MODEL",
    "GROK_MODEL",
)
MODEL_PLACEHOLDERS = {"", "none", "null", "unknown", "pending"}


@dataclass
class SpawnHandle:
    run_id: str
    agent: str
    skill: str
    mode: str
    root: Path
    process: Any
    pgid: int | None
    started_at: str
    command: list[str]
    meta_path: Path | None = None
    transcript_path: Path | None = None
    exit_code: int | None = None
    completed_at: str = ""
    session_id: str = ""
    _done: threading.Event = field(default_factory=threading.Event, repr=False)
    _thread: threading.Thread | None = field(default=None, repr=False)

    @property
    def pid(self) -> int:
        return self.process.pid

    def wait(self, timeout: float | None = None) -> int:
        if not self._done.wait(timeout):
            raise TimeoutError(f"spawn {self.run_id} still running")
        return int(self.exit_code if self.exit_code is not None else 1)


class _SandboxProcess:
    def __init__(self) -> None:
        self.pid = os.getpid()

    def wait(self) -> int:
        return 0


def _now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _set_child_pgid() -> None:
    try:
        os.setpgid(0, 0)
    except OSError:
        pass


def _default_command(agent: str, prompt: str) -> list[str]:
    if agent == "claude":
        return [
            "claude",
            "--print",
            "--verbose",
            "--dangerously-skip-permissions",
            prompt,
        ]
    if agent == "codex":
        return ["codex", "exec", "--dangerously-bypass-approvals-and-sandbox", prompt]
    if agent == "gemini":
        return ["gemini", "--yolo", "--prompt", prompt]
    if agent == "agy":
        return [
            "bash",
            "-lc",
            "agy --print --dangerously-skip-permissions --add-dir . --print-timeout 30m '' <<< \"$1\"",
            "agy",
            prompt,
        ]
    if agent == "junie":
        return ["junie", "--task", prompt, "--project", ".", "--skip-update-check"]
    if agent == "grok":
        return [
            "grok",
            "--cwd",
            ".",
            "--permission-mode",
            "bypassPermissions",
            "--no-alt-screen",
            "--single",
            prompt,
        ]
    raise ValueError(f"unsupported agent: {agent}")


def _stdin_command(agent: str) -> list[str]:
    """Build an agent command that receives the full prompt on stdin.

    The command argv must carry flags and paths only; large prompt bodies belong
    on stdin so they do not leak through ps(1) or hit ARG_MAX.
    """

    if agent == "claude":
        return [
            "claude",
            "-p",
            "--output-format",
            "stream-json",
            "--verbose",
            "--dangerously-skip-permissions",
        ]
    if agent == "codex":
        return [
            "codex",
            "exec",
            "--json",
            "--dangerously-bypass-approvals-and-sandbox",
            "-",
        ]
    if agent == "gemini":
        return ["gemini", "-p", "", "--approval-mode", "yolo", "-o", "stream-json"]
    if agent == "agy":
        return [
            "agy",
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
    raise ValueError(f"unsupported agent: {agent}")


def _parse_launcher_assignment(path: Path, key: str) -> str:
    if not path.is_file():
        return ""
    prefix = f"{key}="
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith(prefix):
            continue
        raw = line.split("=", 1)[1].strip()
        try:
            parts = shlex.split(raw)
        except ValueError:
            return raw.strip("'\"")
        return parts[0] if parts else ""
    return ""


def _read_meta(path: Path | None) -> dict[str, Any]:
    if path is None or not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def _write_meta(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _clean_text(text: str) -> str:
    return ANSI_PATTERN.sub("", text)


def _extract_session(text: str) -> str:
    clean = _clean_text(text)
    for pattern in SESSION_PATTERNS:
        matches = pattern.findall(clean)
        if matches:
            return str(matches[-1])
    return ""


def _extract_tokens(text: str) -> dict[str, int]:
    clean = _clean_text(text)
    # Prefer the authoritative run-closure footer totals when present: they are
    # written for every agent and carry the final per-run usage, so they work
    # uniformly across providers and never sum partial streaming deltas.
    footer_in = FOOTER_TOKEN_PATTERNS["input"].findall(clean)
    footer_out = FOOTER_TOKEN_PATTERNS["output"].findall(clean)
    if footer_in or footer_out:
        footer_cached = FOOTER_TOKEN_PATTERNS["cached_input"].findall(clean)
        input_tokens = int(footer_in[-1]) if footer_in else 0
        cached_tokens = int(footer_cached[-1]) if footer_cached else 0
        output_tokens = int(footer_out[-1]) if footer_out else 0
        return {
            "input": input_tokens,
            "cached_input": cached_tokens,
            "output": output_tokens,
            "total": input_tokens + output_tokens,
        }
    found = TOKEN_PATTERN.findall(clean)
    if not found:
        return {"input": 0, "cached_input": 0, "output": 0, "total": 0}
    input_tokens = cached_tokens = output_tokens = 0
    for raw_in, raw_cached, raw_out in found:
        input_tokens += int(raw_in)
        cached_tokens += int(raw_cached or 0)
        output_tokens += int(raw_out)
    return {
        "input": input_tokens,
        "cached_input": cached_tokens,
        "output": output_tokens,
        "total": input_tokens + output_tokens,
    }


def _extract_cost(text: str) -> float | None:
    clean = _clean_text(text)
    for pattern in COST_PATTERNS:
        matches = pattern.findall(clean)
        if not matches:
            continue
        try:
            return round(float(matches[-1]), 6)
        except ValueError:
            pass
    return None


def _clean_model(value: object) -> str:
    raw = str(value or "").strip()
    return "" if raw.lower() in MODEL_PLACEHOLDERS else raw


def _fallback_model(agent: object) -> str:
    agent_name = str(agent or "agent").strip() or "agent"
    if agent_name == "agy":
        return "gemini-cli-default"
    return f"{agent_name}-cli-default"


def _extract_model_from_text(text: str) -> str:
    clean = _clean_text(text)
    for match in reversed(re.findall(r"^model:\s*(.+?)\s*$", clean, re.MULTILINE)):
        model = _clean_model(match)
        if model:
            return model
    return ""


def _resolve_model(payload: dict[str, Any], combined_text: str) -> str:
    model = _clean_model(payload.get("model"))
    if model:
        return model
    for env_name in MODEL_ENV_VARS:
        model = _clean_model(os.environ.get(env_name))
        if model:
            return model
    model = _extract_model_from_text(combined_text)
    if model:
        return model
    return _fallback_model(payload.get("agent"))


def _parse_dt(value: object) -> dt.datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def _resolve_duration(
    payload: dict[str, Any], completed_at_iso: str
) -> float | int | None:
    current = payload.get("duration_s")
    if isinstance(current, (int, float)):
        return current
    if (
        isinstance(current, str)
        and current.strip()
        and current.lower()
        not in {
            "none",
            "null",
        }
    ):
        try:
            return round(float(current), 3)
        except ValueError:
            pass
    completed_dt = _parse_dt(completed_at_iso)
    started_dt = _parse_dt(payload.get("created_at") or payload.get("updated_at"))
    if completed_dt is None or started_dt is None:
        return None
    return round((completed_dt - started_dt).total_seconds(), 3)


def write_meta(
    meta_path: str | os.PathLike[str],
    status: str,
    agent: str,
    mode: str,
    root: str | os.PathLike[str],
    input_ref: str,
    report: str,
    transcript: str,
    launcher: str,
    model: str = "",
    prompt_id: str = "",
    run_id: str = "",
    loop_nr: str | int = 0,
    skill_code: str = "",
    framework_version: str = "",
) -> Path:
    """Write initial launcher meta.json."""
    meta = Path(meta_path)
    meta.parent.mkdir(parents=True, exist_ok=True)

    loop_nr_value: str | int
    try:
        loop_nr_value = int(loop_nr)
    except (ValueError, TypeError):
        loop_nr_value = loop_nr

    now_iso = dt.datetime.now(dt.timezone.utc).isoformat()
    payload: dict[str, Any] = {
        "created_at": now_iso,
        "updated_at": now_iso,
        "status": status,
        "agent": agent,
        "mode": mode,
        "root": str(root),
        "input": input_ref,
        "report": report,
        "transcript": transcript,
        "launcher": launcher,
        "prompt_id": prompt_id,
        "run_id": run_id,
        "loop_nr": loop_nr_value,
        "skill_code": skill_code,
        "framework_version": framework_version,
        "exit_code": None,
        "launcher_pid": None,
        "liveness": "pid_pending",
        "model": model,
    }

    _write_meta(meta, payload)
    return meta


def finish_meta(
    meta_path: str | os.PathLike[str],
    status: str,
    exit_code: int | str = 0,
) -> Path | None:
    """Mark a launcher meta.json terminal and persist completion telemetry."""
    meta = Path(meta_path)
    if not meta.is_file():
        return None

    try:
        payload = json.loads(_read_text(meta))
    except json.JSONDecodeError:
        return None

    completed_at = dt.datetime.now(dt.timezone.utc)
    started_dt = _parse_dt(payload.get("created_at") or payload.get("updated_at"))
    duration_s = (
        round((completed_at - started_dt).total_seconds(), 3)
        if started_dt is not None
        else None
    )

    payload["updated_at"] = completed_at.isoformat()
    payload["completed_at"] = completed_at.isoformat()
    payload["duration_s"] = duration_s
    payload["status"] = status
    payload["exit_code"] = int(exit_code)
    payload["liveness"] = "terminal"

    transcript_raw = str(payload.get("transcript") or "")
    transcript_text = (
        _read_text(Path(transcript_raw))[: 64 * 1024] if transcript_raw else ""
    )
    session_id = _extract_session(transcript_text)
    if session_id:
        payload["session_id"] = session_id

    _write_meta(meta, payload)
    return meta


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = None
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end = index
            break
    if end is None:
        return {}, text
    data: dict[str, str] = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        data[key.strip()] = value.strip()
    body = "\n".join(lines[end + 1 :]).lstrip("\n")
    return data, body


def _render_frontmatter(data: dict[str, object]) -> str:
    order = [
        "run_id",
        "prompt_id",
        "agent",
        "skill",
        "model",
        "status",
        "date",
        "session_id",
        "artifact_stem",
        "artifact_kind",
        "repo_path",
        "tokens_input",
        "tokens_output",
        "tokens_total",
        "cost_usd",
    ]
    lines = ["---"]
    emitted = set()
    for key in order:
        if key in data:
            value = data.get(key)
            lines.append(f"{key}: {value if value not in (None, '') else 'unknown'}")
            emitted.add(key)
    for key in sorted(k for k in data if k not in emitted):
        value = data.get(key)
        lines.append(f"{key}: {value if value not in (None, '') else 'unknown'}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _slug_component(value: object, fallback: str) -> str:
    raw = str(value or fallback)
    raw = re.sub(r"[^A-Za-z0-9._-]+", "-", raw).strip("-")
    return raw or fallback


def _same_file(left: Path, right: Path) -> bool:
    try:
        return left.samefile(right)
    except OSError:
        return left == right


def _infer_artifact_store(meta: Path) -> dict[str, object] | None:
    reports_dir = meta.parent
    if reports_dir.name != "reports":
        return None
    day_dir = reports_dir.parent
    if not re.fullmatch(r"[0-9]{4}_[0-9]{4}", day_dir.name):
        return None
    repo_dir = day_dir.parent
    org_dir = repo_dir.parent
    if not org_dir.name or not repo_dir.name:
        return None
    yyyy, mmdd = day_dir.name.split("_", 1)
    return {
        "reports_dir": reports_dir,
        "day": f"{yyyy}-{mmdd[:2]}-{mmdd[2:]}",
        "org": org_dir.name,
        "repo": repo_dir.name,
    }


def _unique_stem(
    reports_dir: Path, stem: str, sources: list[Path], disambiguator: str
) -> str:
    candidates = [stem]
    if disambiguator:
        candidates.append(f"{stem}-{_slug_component(disambiguator, 'run')}")
    for index in range(2, 100):
        candidates.append(f"{stem}-{index}")

    suffixes = [".md", ".transcript.log", ".meta.json"]
    for candidate in candidates:
        blocked = False
        for suffix in suffixes:
            target = reports_dir / f"{candidate}{suffix}"
            if not target.exists():
                continue
            if any(
                source and source.exists() and _same_file(target, source)
                for source in sources
            ):
                continue
            blocked = True
            break
        if not blocked:
            return candidate
    return candidates[-1]


def _move_artifact(source: Path, target: Path) -> Path:
    if not str(source) or not source.is_file() or _same_file(source, target):
        return source
    target.parent.mkdir(parents=True, exist_ok=True)
    source.rename(target)
    return target


def _leave_compat_link(announced: Path, final: Path) -> None:
    if not str(announced) or not final.is_file():
        return
    if announced == final or _same_file(announced, final):
        return
    if announced.is_symlink() or announced.exists():
        return
    try:
        announced.parent.mkdir(parents=True, exist_ok=True)
        link_target: str | Path = (
            final.name if announced.parent == final.parent else final
        )
        announced.symlink_to(link_target)
    except OSError:
        pass


def _footer(marker: str, payload: dict[str, object]) -> str:
    return "\n".join(
        [
            "",
            f"<!-- vibecrafted-artifact-footer:{marker} -->",
            "---",
            "run_closure:",
            f"  run_id: {payload.get('run_id', 'unknown')}",
            f"  session_id: {payload.get('session_id') or 'unknown'}",
            f"  tokens_input: {payload.get('tokens_input', 0)}",
            f"  tokens_output: {payload.get('tokens_output', 0)}",
            f"  tokens_total: {payload.get('tokens_total', 0)}",
            f"  cost_usd: {payload.get('cost_usd') if payload.get('cost_usd') is not None else 'unknown'}",
            f"  status: {payload.get('status', 'unknown')}",
            f"  completed_at: {payload.get('completed_at', 'unknown')}",
            f'  resume_hint: "{payload.get("resume_hint", "")}"',
            "---",
            "",
        ]
    )


def _normalize_markdown_artifact(
    path: Path, payload: dict[str, object], *, fallback_body: str = ""
) -> None:
    text = _read_text(path)
    if not text and fallback_body:
        text = fallback_body
    if not text:
        return
    fm, body = _parse_frontmatter(text)
    frontmatter: dict[str, object] = dict(fm)
    frontmatter.update(
        {
            "run_id": payload.get("run_id", "unknown"),
            "prompt_id": payload.get("prompt_id", "unknown"),
            "agent": payload.get("agent", "unknown"),
            "skill": payload.get("skill_code") or payload.get("skill") or "unknown",
            "model": payload.get("model", "unknown"),
            "status": payload.get("status", "unknown"),
            "date": payload.get("date", "unknown"),
            "session_id": payload.get("session_id") or "unknown",
            "artifact_stem": payload.get("artifact_stem", "unknown"),
            "artifact_kind": payload.get("artifact_kind", "unknown"),
            "repo_path": payload.get("root", "unknown"),
            "tokens_input": payload.get("tokens_input", 0),
            "tokens_output": payload.get("tokens_output", 0),
            "tokens_total": payload.get("tokens_total", 0),
            "cost_usd": payload.get("cost_usd")
            if payload.get("cost_usd") is not None
            else "unknown",
        }
    )
    marker = str(payload.get("run_id") or "unknown")
    new_text = _render_frontmatter(frontmatter) + body.rstrip() + "\n"
    if f"vibecrafted-artifact-footer:{marker}" not in new_text:
        new_text += _footer(marker, payload)
    _write_text(path, new_text)


def finalize_artifacts(
    meta_path: str | os.PathLike[str],
    report_path: str | os.PathLike[str] | None = None,
    transcript_path: str | os.PathLike[str] | None = None,
) -> Path | None:
    """Finalize a launcher run's report/transcript/meta artifact contract."""
    meta = Path(meta_path)
    if not meta.is_file():
        return None

    try:
        payload = json.loads(_read_text(meta))
    except json.JSONDecodeError:
        return None

    report = Path(str(report_path or payload.get("report", "")))
    transcript = Path(str(transcript_path or payload.get("transcript", "")))
    announced_report = report
    announced_transcript = transcript
    transcript_text = _read_text(transcript) if str(transcript) else ""
    report_text = _read_text(report) if str(report) else ""
    combined_text = "\n".join([transcript_text, report_text])

    session_id = payload.get("session_id") or _extract_session(combined_text)
    tokens = _extract_tokens(combined_text)
    cost = _extract_cost(combined_text)
    completed_at = (
        payload.get("completed_at") or dt.datetime.now(dt.timezone.utc).isoformat()
    )
    artifact_time = dt.datetime.now().astimezone().isoformat(timespec="seconds")
    root = payload.get("root") or os.getcwd()
    resume_hint = (
        f"Use `cd {root} && vc-resume --session {session_id}` to continue work with this Agent."
        if session_id
        else f"Use `cd {root} && vc-resume --session <session_id>` to continue work with this Agent."
    )

    payload["session_id"] = session_id or payload.get("session_id") or ""
    payload["model"] = _resolve_model(payload, combined_text)
    payload["duration_s"] = _resolve_duration(payload, str(completed_at))
    payload["tokens_input"] = tokens["input"]
    payload["tokens_cached_input"] = tokens["cached_input"]
    payload["tokens_output"] = tokens["output"]
    payload["tokens_total"] = tokens["total"]
    payload["token_usage"] = tokens
    payload["cost_usd"] = cost
    payload["resume_hint"] = resume_hint
    payload["artifact_contract"] = "vibecrafted.agent-artifact.v1"
    payload["date"] = payload.get("date") or artifact_time

    store = _infer_artifact_store(meta)
    if store:
        reports_dir = Path(str(store["reports_dir"]))
        session_for_name = (
            session_id
            or payload.get("session_id")
            or payload.get("run_id")
            or "unknown-session"
        )
        stem = (
            f"{store['day']}_"
            f"{_slug_component(store['org'], 'org')}_"
            f"{_slug_component(store['repo'], 'repo')}_"
            f"{_slug_component(session_for_name, 'session')}-report"
        )
        stem = _unique_stem(
            reports_dir,
            stem,
            [report, transcript, meta],
            str(payload.get("run_id") or ""),
        )
        final_report = reports_dir / f"{stem}.md"
        final_transcript = reports_dir / f"{stem}.transcript.log"
        final_meta = reports_dir / f"{stem}.meta.json"

        report = _move_artifact(report, final_report)
        transcript = _move_artifact(transcript, final_transcript)
        _leave_compat_link(announced_report, report)
        _leave_compat_link(announced_transcript, transcript)
        payload["report"] = str(report)
        payload["transcript"] = str(transcript)
        payload["meta"] = str(final_meta)
        payload["artifact_stem"] = stem
        payload["artifact_kind"] = "report"

    payload["artifact_footer"] = {
        "run_id": payload.get("run_id", "unknown"),
        "session_id": payload.get("session_id") or "",
        "tokens_total": tokens["total"],
        "cost_usd": cost,
        "resume_hint": resume_hint,
    }
    payload.setdefault("completed_at", completed_at)
    payload["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()

    target_meta = Path(str(payload.get("meta") or meta))
    target_meta.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if not _same_file(meta, target_meta) and meta.exists():
        meta.unlink()
        _leave_compat_link(meta, target_meta)
    meta = target_meta

    footer_payload = {
        **payload,
        "tokens_input": tokens["input"],
        "tokens_output": tokens["output"],
        "tokens_total": tokens["total"],
        "cost_usd": cost,
    }

    if str(transcript):
        _normalize_markdown_artifact(transcript, footer_payload)
    if (
        str(report)
        and report.exists()
        and report.suffix.lower() in {".md", ".markdown"}
    ):
        _normalize_markdown_artifact(report, footer_payload)
    return meta


def _maybe_extract_session_id(handle: SpawnHandle) -> str:
    meta = _read_meta(handle.meta_path)
    if meta.get("session_id"):
        return str(meta["session_id"])

    transcript = handle.transcript_path
    if transcript is None and meta.get("transcript"):
        transcript = Path(str(meta["transcript"]))
    if transcript is None or not transcript.is_file():
        return ""

    text = transcript.read_text(encoding="utf-8", errors="replace")
    session_id = extract_session_id(handle.agent, text) or ""
    if session_id and handle.meta_path is not None and handle.meta_path.is_file():
        meta["session_id"] = session_id
        _write_meta(handle.meta_path, meta)
    return session_id


class Supervisor:
    """Small UNIX process supervisor for Vibecrafted agent launchers."""

    def spawn(
        self,
        agent: str,
        prompt: str,
        *,
        skill: str,
        mode: str,
        root: str | os.PathLike[str],
        on_event: EventCallback | None = None,
        command: Sequence[str] | None = None,
        env: dict[str, str] | None = None,
        run_id: str | None = None,
        meta_path: str | os.PathLike[str] | None = None,
        transcript_path: str | os.PathLike[str] | None = None,
        sandbox: bool = False,
        sandbox_policy: str | os.PathLike[str] | None = None,
        sandbox_config: dict[str, Any] | None = None,
    ) -> SpawnHandle:
        root_path = Path(normalize_run_root(os.fspath(root)))
        command_list = (
            list(command) if command is not None else _default_command(agent, prompt)
        )
        effective_run_id = (
            run_id or os.environ.get("VIBECRAFTED_RUN_ID") or f"{skill}-manual"
        )

        launcher = Path(command_list[-1]).expanduser() if command_list else Path()
        inferred_meta = Path(meta_path).expanduser() if meta_path is not None else None
        inferred_transcript = (
            Path(transcript_path).expanduser() if transcript_path is not None else None
        )
        if inferred_meta is None and launcher.suffix == ".sh":
            parsed = _parse_launcher_assignment(launcher, "meta")
            inferred_meta = Path(parsed).expanduser() if parsed else None
        if inferred_transcript is None and launcher.suffix == ".sh":
            parsed = _parse_launcher_assignment(launcher, "transcript")
            inferred_transcript = Path(parsed).expanduser() if parsed else None

        child_env = os.environ.copy()
        if env:
            child_env.update(env)
        session_id = ensure_session_id(child_env.get("VIBECRAFTED_SESSION_ID"))
        child_env.setdefault("VIBECRAFTED_RUN_ID", effective_run_id)
        child_env["VIBECRAFTED_SESSION_ID"] = session_id

        if sandbox:
            if not sandbox_supported(agent):
                raise ValueError(f"agent does not support sandbox dispatch: {agent}")
            sandbox_process = _SandboxProcess()
            handle = SpawnHandle(
                run_id=effective_run_id,
                agent=agent,
                skill=skill,
                mode=mode,
                root=root_path,
                process=sandbox_process,
                pgid=None,
                started_at=_now_iso(),
                command=command_list,
                meta_path=inferred_meta,
                transcript_path=inferred_transcript,
                session_id=session_id,
            )
            self._emit(
                "spawn-started",
                handle,
                "supervisor spawned sandbox child",
                {"pid": sandbox_process.pid, "pgid": None, "command": command_list},
                on_event,
            )
            thread = threading.Thread(
                target=self._run_sandbox,
                args=(
                    handle,
                    child_env,
                    sandbox_policy,
                    sandbox_config or {},
                    on_event,
                ),
                daemon=True,
            )
            handle._thread = thread
            thread.start()
            return handle

        process = subprocess.Popen(
            command_list,
            cwd=str(root_path),
            env=child_env,
            text=True,
            preexec_fn=_set_child_pgid if hasattr(os, "setpgid") else None,
        )
        try:
            pgid = os.getpgid(process.pid)
        except OSError:
            pgid = None

        handle = SpawnHandle(
            run_id=effective_run_id,
            agent=agent,
            skill=skill,
            mode=mode,
            root=root_path,
            process=process,
            pgid=pgid,
            started_at=_now_iso(),
            command=command_list,
            meta_path=inferred_meta,
            transcript_path=inferred_transcript,
            session_id=session_id,
        )
        self._emit(
            "spawn-started",
            handle,
            "supervisor spawned child",
            {"pid": process.pid, "pgid": pgid, "command": command_list},
            on_event,
        )
        thread = threading.Thread(
            target=self._wait_owner, args=(handle, on_event), daemon=True
        )
        handle._thread = thread
        thread.start()
        return handle

    def _run_sandbox(
        self,
        handle: SpawnHandle,
        env: dict[str, str],
        sandbox_policy: str | os.PathLike[str] | None,
        sandbox_config: dict[str, Any],
        on_event: EventCallback | None,
    ) -> None:
        try:
            from .sandbox import SandboxAdapter, SandboxPolicy

            policy = SandboxPolicy.load(sandbox_policy, root=handle.root)
            adapter = SandboxAdapter(
                policy=policy,
                server_url=sandbox_config.get("server_url"),
                api_key_path=sandbox_config.get("api_key_path"),
            )
            result = adapter.execute_sync(
                handle.command,
                env=env,
                cwd=handle.root,
                timeout=sandbox_config.get("timeout"),
                run_id=handle.run_id,
                agent=handle.agent,
                skill=handle.skill,
                mode=handle.mode,
                on_event=on_event,
            )
            handle.exit_code = result.exit_code
        except Exception as exc:  # pragma: no cover - defensive event path
            handle.exit_code = 1
            self._emit(
                "spawn-failed",
                handle,
                f"sandbox execution failed: {exc}",
                {"pid": handle.pid, "pgid": handle.pgid, "exit_code": 1},
                on_event,
            )
            handle._done.set()
            return

        handle.completed_at = _now_iso()
        extracted_session_id = _maybe_extract_session_id(handle)
        if extracted_session_id:
            handle.session_id = extracted_session_id
        kind = "spawn-completed" if handle.exit_code == 0 else "spawn-failed"
        self._emit(
            kind,
            handle,
            f"sandbox child exited with {handle.exit_code}",
            {
                "pid": handle.pid,
                "pgid": handle.pgid,
                "exit_code": handle.exit_code,
                "session_id": handle.session_id,
                "meta": str(handle.meta_path or ""),
                "transcript": str(handle.transcript_path or ""),
                "substrate": "microsandbox",
            },
            on_event,
        )
        handle._done.set()

    def _wait_owner(self, handle: SpawnHandle, on_event: EventCallback | None) -> None:
        exit_code = handle.process.wait()
        handle.exit_code = exit_code
        handle.completed_at = _now_iso()
        extracted_session_id = _maybe_extract_session_id(handle)
        if extracted_session_id:
            handle.session_id = extracted_session_id
        kind = "spawn-completed" if exit_code == 0 else "spawn-failed"
        self._emit(
            kind,
            handle,
            f"supervisor child exited with {exit_code}",
            {
                "pid": handle.pid,
                "pgid": handle.pgid,
                "exit_code": exit_code,
                "session_id": handle.session_id,
                "meta": str(handle.meta_path or ""),
                "transcript": str(handle.transcript_path or ""),
            },
            on_event,
        )
        if handle.transcript_path and not handle.session_id:
            self._emit(
                "session_id_extraction_failed",
                handle,
                "could not extract agent session_id from transcript",
                {"agent": handle.agent, "transcript": str(handle.transcript_path)},
                on_event,
            )
        handle._done.set()

    def _emit(
        self,
        kind: str,
        handle: SpawnHandle,
        message: str,
        payload: dict[str, Any],
        on_event: EventCallback | None,
    ) -> None:
        event = append_event(
            kind,
            handle.run_id,
            message,
            {
                "agent": handle.agent,
                "skill": handle.skill,
                "mode": handle.mode,
                "root": str(handle.root),
                "session_id": handle.session_id,
                "identity_required": True,
                **payload,
            },
        )
        if on_event is not None:
            on_event(event)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Vibecrafted launcher helpers.")
    sub = parser.add_subparsers(dest="command", required=True)
    write = sub.add_parser(
        "write-meta",
        help="Write initial launcher meta.json.",
    )
    write.add_argument("meta")
    write.add_argument("status")
    write.add_argument("agent")
    write.add_argument("mode")
    write.add_argument("root")
    write.add_argument("input")
    write.add_argument("report")
    write.add_argument("transcript")
    write.add_argument("launcher")
    write.add_argument("--model", default="")
    write.add_argument("--prompt-id", default="")
    write.add_argument("--run-id", default="")
    write.add_argument("--loop-nr", default="0")
    write.add_argument("--skill-code", default="")
    write.add_argument("--framework-version", default="")

    finalize = sub.add_parser(
        "finalize-artifacts",
        help="Finalize launcher meta/report/transcript artifacts.",
    )
    finalize.add_argument("meta")
    finalize.add_argument("report", nargs="?")
    finalize.add_argument("transcript", nargs="?")
    finish = sub.add_parser(
        "finish-meta",
        help="Mark launcher meta terminal and persist completion telemetry.",
    )
    finish.add_argument("meta")
    finish.add_argument("status")
    finish.add_argument("exit_code", nargs="?", default="0")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.command == "write-meta":
        write_meta(
            args.meta,
            args.status,
            args.agent,
            args.mode,
            args.root,
            args.input,
            args.report,
            args.transcript,
            args.launcher,
            model=args.model,
            prompt_id=args.prompt_id,
            run_id=args.run_id,
            loop_nr=args.loop_nr,
            skill_code=args.skill_code,
            framework_version=args.framework_version,
        )
        return 0
    if args.command == "finish-meta":
        finish_meta(args.meta, args.status, args.exit_code)
        return 0
    if args.command == "finalize-artifacts":
        finalize_artifacts(args.meta, args.report, args.transcript)
        return 0
    return 2


if __name__ == "__main__":  # pragma: no cover - CLI entry point.
    raise SystemExit(main())
