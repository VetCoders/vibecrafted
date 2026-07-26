from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .artifacts import validate_artifacts
from .control_plane import (
    await_run,
    control_plane_home,
    ensure_session_id,
    lookup_run,
    normalize_run_root,
    record_stop_transition,
    run_snapshot_dir,
    sync_state,
)
from .cron import parse_frontmatter
from .delivery.store import atomic_write_json
from .events import append_event
from .model_overrides import _model_override_receipt, _with_model_override
from .package_resources import deck_path as package_deck_path
from .report_contract import CLAIM_DIGEST_ENV
from .research_config import ResearchAgentSelection, resolve_research_runtime_config
from .spawn import _stdin_command
from .workflow_runtime import WORKER_SIGNAL_DISCIPLINE
from .workflows import registry as workflow_registry

SUPPORTED_WORKFLOWS = workflow_registry.SUPPORTED_WORKFLOWS
WORKFLOW_ALIASES = workflow_registry.WORKFLOW_ALIASES
SUPPORTED_AGENTS = {"claude", "codex", "agy", "junie", "grok", "swarm"}
SUPPORTED_RUNTIMES = {"headless", "terminal", "visible"}
TERMINAL_STATES = {
    "completed",
    "failed",
    "report_validated",
    "report_missing",
    "report_invalid",
    "contract_failed",
    "closed",
    "stopped",
    "timed_out",
    "ghost",
}


@dataclass(frozen=True)
class WorkflowLaunchSpec:
    agent: str
    mode: str
    skill: str
    prompt: str
    file: str
    runtime: str
    root: str
    count: int | None = None
    depth: int | None = None
    model: str = ""
    research_agents: tuple[str, ...] = ()
    research_synthesizer: str = ""
    research_synthesizer_model: str = ""
    # Push-side report-on-death (docs/runtime/AGENT_OPS.md, Class 2): when the
    # launch belongs to a lifecycle run, this carries the lifecycle state.json
    # path so the dispatcher can write the worker's terminal truth into it.
    lifecycle_state_path: str = ""
    # Machine-owned mission binding for lifecycle stage reports. The worker may
    # attest success, but it cannot choose which mission that attestation closes.
    claim_digest: str = ""
    # Adapters that must expose the execution identity before launch (ACP's
    # session/new) may reserve one through reserve_run_id(). Empty keeps the
    # historical launch-time allocation path.
    run_id: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def vibecrafted_launcher(source_dir: str | Path) -> Path:
    return package_deck_path()


def reserve_run_id(skill: str) -> str:
    """Return a safe control-plane run id without creating runtime state."""
    stamp = time.strftime("%y%m%d-%H%M%S")
    code = (skill or "run")[:4].ljust(4, "x")
    entropy = int(time.time_ns() % 100000)
    return f"{code}-{stamp}-{entropy:05d}"


def _run_id(skill: str) -> str:
    """Backward-compatible internal alias for the run-id allocator."""
    return reserve_run_id(skill)


def _artifact_org_repo(root: str | Path) -> tuple[str, str] | None:
    root_path = Path(root).expanduser()
    remote = _origin_remote_url(root_path)
    match = re.search(r"[:/]([^/]+)/([^/.]+)(?:\.git)?$", remote)
    if match:
        return match.group(1), match.group(2)
    fallback = root_path.name.strip()
    return ("local", fallback) if fallback else None


def _git_config_path(root: Path) -> Path | None:
    git_entry = root / ".git"
    if git_entry.is_dir():
        return git_entry / "config"
    if not git_entry.is_file():
        return None
    try:
        raw = git_entry.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not raw.startswith("gitdir:"):
        return None
    git_dir = Path(raw.removeprefix("gitdir:").strip()).expanduser()
    if not git_dir.is_absolute():
        git_dir = (root / git_dir).resolve()
    config = git_dir / "config"
    if config.is_file():
        return config
    common_dir_file = git_dir / "commondir"
    if common_dir_file.is_file():
        try:
            common = Path(common_dir_file.read_text(encoding="utf-8").strip())
        except OSError:
            return None
        if not common.is_absolute():
            common = (git_dir / common).resolve()
        return common / "config"
    return None


def _origin_remote_url(root: Path) -> str:
    config_path = _git_config_path(root)
    if config_path is None or not config_path.is_file():
        return ""
    try:
        lines = config_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return ""
    in_origin = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_origin = stripped == '[remote "origin"]'
            continue
        if not in_origin or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        if key.strip() == "url":
            return value.strip()
    return ""


def _run_artifact_paths(run_id: str) -> dict[str, Path]:
    run_dir = control_plane_home() / "runtime_runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    return {
        "meta": run_dir / "meta.json",
        "prompt": run_dir / "prompt.md",
        "transcript": run_dir / "transcript.log",
    }


def _canonical_report_dir(root: str | Path, skill: str) -> Path:
    org_repo = _artifact_org_repo(root)
    if org_repo is None:
        base = Path(root).expanduser() / ".vibecrafted"
    else:
        org, repo = org_repo
        base = (
            control_plane_home().parent
            / "artifacts"
            / org
            / repo
            / time.strftime("%Y_%m%d")
        )
    path = base / "reports" / skill
    path.mkdir(parents=True, exist_ok=True)
    return path


def _artifact_slug(text: str, fallback: str) -> str:
    frontmatter = re.match(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", text, re.DOTALL)
    if frontmatter:
        for key in ("slug", "title"):
            match = re.search(
                rf"(?im)^\s*{key}\s*:\s*[\"']?(.+?)[\"']?\s*$",
                frontmatter.group(1),
            )
            if match:
                words = _slug_words(match.group(1))
                if words:
                    return "-".join(words[:3])
    words = _slug_words(text)
    return "-".join(words[:3]) if words else fallback


def _slug_words(text: str) -> list[str]:
    boilerplate = {
        "a",
        "an",
        "and",
        "for",
        "on",
        "perform",
        "please",
        "research",
        "run",
        "skill",
        "task",
        "the",
        "this",
        "workflow",
    }
    return [
        word
        for word in re.findall(r"[A-Za-z0-9]+", text.lower())
        if word not in boilerplate
    ]


def _artifact_report_suffix(
    canonical_report_dir: Path | None,
    artifact_ts: str,
    artifact_slug: str,
) -> str:
    if canonical_report_dir is None:
        return ""
    for index in range(1, 100):
        suffix = "" if index == 1 else f"-{index}"
        pattern = f"{artifact_ts}_*_{artifact_slug}_report{suffix}.*"
        if not any(canonical_report_dir.glob(pattern)):
            return suffix
    return "-99"


def _canonical_report_path(
    *,
    canonical_report_dir: Path,
    artifact_ts: str,
    agent: str,
    artifact_slug: str,
    artifact_suffix: str,
) -> Path:
    safe_agent = "-".join(_slug_words(agent)) or "agent"
    return (
        canonical_report_dir
        / f"{artifact_ts}_{safe_agent}_{artifact_slug}_report{artifact_suffix}.md"
    )


def _core_package_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _prepend_pythonpath(env: dict[str, str], path: Path) -> None:
    existing = env.get("PYTHONPATH", "")
    entries = [str(path)]
    entries.extend(item for item in existing.split(os.pathsep) if item)
    env["PYTHONPATH"] = os.pathsep.join(dict.fromkeys(entries))


def _dispatcher_command(
    *,
    run_id: str,
    root: str,
    meta_path: Path,
    prompt_path: Path | None = None,
    report_path: Path,
    transcript_path: Path,
    worker_command: list[str],
    tee_output: bool = False,
    emit_json: bool = True,
    quiet: bool = False,
    lifecycle_state_path: str = "",
) -> list[str]:
    command = [
        sys.executable,
        "-m",
        "vibecrafted_core.dispatcher",
        "run",
        "--run-id",
        run_id,
        "--root",
        root,
        "--meta",
        str(meta_path),
        "--report",
        str(report_path),
        "--transcript",
        str(transcript_path),
    ]
    if prompt_path is not None:
        command.extend(
            [
                "--prompt-file",
                str(prompt_path),
            ]
        )
    if lifecycle_state_path:
        command.extend(["--lifecycle-state", lifecycle_state_path])
    if tee_output:
        command.append("--tee-output")
    if quiet:
        command.append("--quiet")
    if emit_json:
        command.append("--json")
    command.append("--")
    command.extend(worker_command)
    return command


def _write_command_script(
    path: Path, command: list[str], exports: dict[str, str] | None = None
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    export_lines = "".join(
        f"export {key}={shlex.quote(value)}\n" for key, value in (exports or {}).items()
    )
    path.write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        f"{export_lines}"
        f"exec {shlex.join(command)}\n",
        encoding="utf-8",
    )
    path.chmod(0o755)
    return path


def _runtime_script_exports(
    *,
    run_id: str,
    prompt_path: Path,
    report_path: Path,
    transcript_path: Path,
    meta_path: Path,
    agent: str,
    skill: str,
    runtime: str,
    canonical_report_dir: Path | None = None,
    artifact_slug: str = "",
    artifact_ts: str = "",
    artifact_suffix: str = "",
    claim_digest: str = "",
    worker_session: str = "",
) -> dict[str, str]:
    pythonpath = os.pathsep.join(
        dict.fromkeys(
            [str(_core_package_root())]
            + [
                item
                for item in os.environ.get("PYTHONPATH", "").split(os.pathsep)
                if item
            ]
        )
    )
    exports = {
        "VIBECRAFTED_RUN_ID": run_id,
        "VIBECRAFTED_REPORT_PATH": str(report_path),
        "VIBECRAFTED_TRANSCRIPT_PATH": str(transcript_path),
        "VIBECRAFTED_META_PATH": str(meta_path),
        "VIBECRAFTED_PROMPT_PATH": str(prompt_path),
        "VIBECRAFTED_AGENT": agent,
        "VIBECRAFTED_SKILL": skill,
        "VIBECRAFTED_RUNTIME": runtime,
        # vc-frame starts this script from its long-lived server environment,
        # not from launch_workflow's Popen(env=...). Keep the generated
        # dispatcher self-contained and keep installed payloads bytecode-clean.
        "PYTHONPATH": pythonpath,
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if canonical_report_dir is not None:
        exports["VIBECRAFTED_CANONICAL_REPORT_DIR"] = str(canonical_report_dir)
    if artifact_slug:
        exports["VIBECRAFTED_ARTIFACT_SLUG"] = artifact_slug
    if artifact_ts:
        exports["VIBECRAFTED_ARTIFACT_TS"] = artifact_ts
    if artifact_suffix:
        exports["VIBECRAFTED_ARTIFACT_SUFFIX"] = artifact_suffix
    if claim_digest:
        exports[CLAIM_DIGEST_ENV] = claim_digest
    if worker_session:
        # vc-frame launches this script from the host server's long-lived
        # environment. That environment can still describe the human
        # dispatcher seat, so pin the actual worker host for durable triage.
        exports["VIBECRAFTED_WORKER_SESSION"] = worker_session
        exports["VIBECRAFTED_OPERATOR_SESSION"] = worker_session
    if runtime in {"terminal", "visible"}:
        exports["VIBECRAFTED_TEE_OUTPUT"] = "1"
    return exports


def _kdl_string(value: str | Path) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _write_research_lane_scripts(
    *,
    launch_dir: Path,
    run_id: str,
    root: str,
    prompt_path: Path,
    report_path: Path,
    transcript_path: Path,
    meta_path: Path,
    canonical_report_dir: Path,
    artifact_slug: str,
    artifact_ts: str,
    artifact_suffix: str,
    research_selection: ResearchAgentSelection,
    model_requested: str = "",
    claim_digest: str = "",
    worker_session: str = "",
) -> dict[str, Path]:
    scripts: dict[str, Path] = {}
    for agent in research_selection.agents:
        path = launch_dir / f"{run_id}-research-{agent}.sh"
        command = [
            sys.executable,
            "-m",
            "vibecrafted_core.workflow_runtime",
            "research-lane",
            "--agent",
            agent,
            "--root",
            root,
            "--prompt-file",
            str(prompt_path),
        ]
        lane_model = research_selection.lane_model(agent, model_requested)
        if lane_model:
            command.extend(["--model", lane_model])
        exports = _runtime_script_exports(
            run_id=run_id,
            prompt_path=prompt_path,
            report_path=report_path,
            transcript_path=transcript_path,
            meta_path=meta_path,
            agent=agent,
            skill="research",
            runtime="terminal",
            canonical_report_dir=canonical_report_dir,
            artifact_slug=artifact_slug,
            artifact_ts=artifact_ts,
            artifact_suffix=artifact_suffix,
            claim_digest=claim_digest,
            worker_session=worker_session,
        )
        export_lines = "".join(
            f"export {key}={shlex.quote(value)}\n" for key, value in exports.items()
        )
        path.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            f"{export_lines}"
            f"exec {shlex.join(command)}\n",
            encoding="utf-8",
        )
        path.chmod(0o755)
        scripts[agent] = path
    return scripts


def _write_research_layout(
    *,
    path: Path,
    synthesis_script: Path,
    lane_scripts: dict[str, Path],
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lane_panes = []
    for agent, script in lane_scripts.items():
        lane_panes.append(
            f"""                pane name={_kdl_string(agent)} command="bash" {{
                    args {_kdl_string(script)}
                }}"""
        )
    lane_panes_text = "\n".join(lane_panes)
    path.write_text(
        f"""layout {{
    default_tab_template {{
        pane size=1 borderless=true {{
            plugin location="compact-bar"
        }}
        children
        pane size=1 borderless=true {{
            plugin location="status-bar"
        }}
    }}

    tab name="Vibecrafted Research" {{
        pane split_direction="vertical" {{
            pane name="synthesis" size="55%" focus=true command="bash" {{
                args {_kdl_string(synthesis_script)}
            }}
            pane split_direction="horizontal" size="45%" {{
{lane_panes_text}
            }}
        }}
    }}
}}
""",
        encoding="utf-8",
    )
    return path


_ANSI_SGR = re.compile(r"\x1b\[[0-9;]*m")
_SESSION_NOT_FOUND_RE = re.compile(
    r"Session ['\"][^'\"]+['\"] not found|There is no active session!",
    re.IGNORECASE,
)


def _vc_frame_stderr_is_session_not_found(text: str) -> bool:
    """True when stderr carries vc-frame's missing-host-session diagnostic.

    Some builds exit 0 while still printing this message — exit code alone is
    not sufficient (G3 recon, 2026-07-21).
    """
    return bool(_SESSION_NOT_FOUND_RE.search(text or ""))


def _vc_frame_session_active(vc_frame: str, session: str) -> bool:
    """True only if `session` is a live (non-EXITED) vc-frame session.

    A terminal-runtime launch opens a new tab in an existing operator session
    (`vc-frame --session <name> action new-tab`). If that session does not
    exist, vc-frame prints "Session '<name>' not found" and the tab — and the
    dispatcher inside it — never runs. EXITED sessions are not spawn targets
    (parity with bash ``spawn_session_is_live``).
    """
    if not session:
        return False
    try:
        result = subprocess.run(
            [vc_frame, "list-sessions"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    for line in result.stdout.splitlines():
        clean = _ANSI_SGR.sub("", line).strip()
        if not clean:
            continue
        if "EXITED" in clean.upper():
            continue
        # Strip trailing status tags so multi-word hosts (G7: "<repo> workers") match.
        name = re.sub(r"\s+\[.*$", "", clean)
        name = re.sub(r"\s+\([^)]*\)$", "", name).rstrip()
        if name == session:
            return True
    return False


def _vc_frame_create_background(vc_frame: str, session: str) -> tuple[bool, str]:
    """One-shot ``attach --create-background`` for a missing host session."""
    try:
        result = subprocess.run(
            [vc_frame, "attach", "--create-background", session],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    combined = "\n".join(
        part for part in (result.stderr or "", result.stdout or "") if part
    ).strip()
    if _vc_frame_session_active(vc_frame, session):
        return True, combined
    if result.returncode == 0:
        # Some builds report success before the session is listable; accept
        # zero exit when the message is not a hard failure.
        return True, combined
    return False, combined or f"attach --create-background exit {result.returncode}"


@dataclass(frozen=True)
class _HostActionResult:
    ok: bool
    pid: int | None
    error: str
    stderr: str
    resurrected: bool = False


def _vc_frame_run_host_action(
    command: list[str],
    *,
    operator_session: str,
    timeout: float = 30.0,
) -> _HostActionResult:
    """Run a vc-frame host action with one create-background retry on not-found.

    Treats "Session 'X' not found" as failure even when the binary exits 0.
    """
    if not command:
        return _HostActionResult(False, None, "empty vc-frame command", "", False)

    resurrected = False

    def _run_once() -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            command, capture_output=True, text=True, timeout=timeout, check=False
        )

    # CompletedProcess has no .pid; host actions are short-lived, so pid is
    # informational only. Use os.getpid() of the parent as a stable handle for
    # receipt fields that require an int.
    action_pid = os.getpid()

    try:
        result = _run_once()
    except (OSError, subprocess.SubprocessError) as exc:
        return _HostActionResult(False, None, f"{type(exc).__name__}: {exc}", "", False)

    combined = "\n".join(
        part for part in (result.stderr or "", result.stdout or "") if part
    ).strip()

    if _vc_frame_stderr_is_session_not_found(combined):
        if not operator_session:
            return _HostActionResult(False, action_pid, combined, combined, False)
        ok_create, create_err = _vc_frame_create_background(
            command[0], operator_session
        )
        resurrected = True
        if not ok_create:
            err = "\n".join(
                part
                for part in (combined, create_err, "attach --create-background failed")
                if part
            )
            return _HostActionResult(False, action_pid, err, err, True)
        try:
            result = _run_once()
        except (OSError, subprocess.SubprocessError) as exc:
            return _HostActionResult(
                False, None, f"{type(exc).__name__}: {exc}", "", True
            )
        combined = "\n".join(
            part for part in (result.stderr or "", result.stdout or "") if part
        ).strip()
        if _vc_frame_stderr_is_session_not_found(combined) or result.returncode != 0:
            err = (
                combined
                or f"vc-frame action failed after host resurrect (exit {result.returncode})"
            )
            return _HostActionResult(False, action_pid, err, err, True)

    elif result.returncode != 0:
        err = combined or f"vc-frame action exit {result.returncode}"
        return _HostActionResult(False, action_pid, err, err, False)

    return _HostActionResult(True, action_pid, "", combined, resurrected)


def _launch_transport_command(
    *,
    spec: WorkflowLaunchSpec,
    run_id: str,
    operator_session: str,
    dispatch_command: list[str],
    launch_dir: Path,
    prompt_path: Path,
    report_path: Path,
    transcript_path: Path,
    meta_path: Path,
    canonical_report_dir: Path | None,
    artifact_slug: str,
    artifact_ts: str,
    artifact_suffix: str,
    research_selection: ResearchAgentSelection | None = None,
) -> tuple[list[str], str, Path | None]:
    if spec.runtime not in {"terminal", "visible"}:
        return dispatch_command, "headless", None

    vc_frame = shutil.which("vc-frame") or ""
    if not vc_frame:
        return dispatch_command, "headless", None

    # G3: missing host sessions are handled at launch time via one-shot
    # `attach --create-background` + action retry (`_vc_frame_run_host_action`).
    # Do not silently degrade to headless here — that path left runs in
    # process_spawned→stalled with no last_error. Always emit the vc-frame
    # transport when the binary exists; the spawn step fails loud on double-fail.

    command_script = _write_command_script(
        launch_dir / f"{run_id}-dispatcher.sh",
        dispatch_command,
        exports=_runtime_script_exports(
            run_id=run_id,
            prompt_path=prompt_path,
            report_path=report_path,
            transcript_path=transcript_path,
            meta_path=meta_path,
            agent=spec.agent,
            skill=spec.skill,
            runtime=spec.runtime,
            canonical_report_dir=canonical_report_dir,
            artifact_slug=artifact_slug,
            artifact_ts=artifact_ts,
            artifact_suffix=artifact_suffix,
            claim_digest=spec.claim_digest,
            worker_session=operator_session,
        ),
    )
    definition = workflow_registry.workflow_definition(spec.skill)
    if spec.skill == "research":
        selection = research_selection or resolve_research_runtime_config(
            override_agents=spec.research_agents,
            synthesizer=spec.research_synthesizer,
            synthesizer_model=spec.research_synthesizer_model,
        )
        lane_scripts = _write_research_lane_scripts(
            launch_dir=launch_dir,
            run_id=run_id,
            root=spec.root,
            prompt_path=prompt_path,
            report_path=report_path,
            transcript_path=transcript_path,
            meta_path=meta_path,
            canonical_report_dir=canonical_report_dir
            or _canonical_report_dir(spec.root, spec.skill),
            artifact_slug=artifact_slug,
            artifact_ts=artifact_ts,
            artifact_suffix=artifact_suffix,
            research_selection=selection,
            model_requested=spec.model,
            claim_digest=spec.claim_digest,
            worker_session=operator_session,
        )
        layout_file = _write_research_layout(
            path=launch_dir / f"{run_id}-research.kdl",
            synthesis_script=command_script,
            lane_scripts=lane_scripts,
        )
        return (
            [
                vc_frame,
                "--session",
                operator_session,
                "action",
                "new-tab",
                "--layout",
                str(layout_file),
                "--name",
                run_id,
                "--cwd",
                spec.root,
            ],
            "vc-frame",
            command_script,
        )

    terminal_command = [
        vc_frame,
        "--session",
        operator_session,
        "action",
        "new-tab",
    ]
    if definition is not None and definition.terminal_layout:
        terminal_command.extend(["--layout", definition.terminal_layout])
    terminal_command.extend(
        [
            "--name",
            run_id,
            "--cwd",
            spec.root,
            "--",
            str(command_script),
        ]
    )
    return (
        terminal_command,
        "vc-frame",
        command_script,
    )


def _effective_operator_session(*, root: str, run_id: str, env: dict[str, str]) -> str:
    """Resolve the vc-frame session that hosts worker tabs (G7).

    Python mirror of bash ``spawn_effective_operator_session``
    (``runtime/scripts/lib/vc_frame.sh``). The launch-log field
    ``operator_session`` records this host (truthful worker target), not the
    human operator's interactive seat.

    Rules (exact order):

    1. ``VIBECRAFTED_WORKER_SESSION`` if set — explicit override wins.
    2. ``basename(root)`` — per-project host session for workers.
    3. If that equals the dispatcher seat (``VC_FRAME_SESSION_NAME`` /
       ``ZELLIJ_SESSION_NAME``), use ``"<repo> workers"`` so the operator
       session never receives a worker tab — even when repo name == seat name.

    Missing hosts are resurrected by G3 (``attach --create-background``). The
    ``run_id`` argument is retained for call-site compatibility only.
    """
    _ = run_id  # call-site compatibility; not part of G7 host rules
    override = str(env.get("VIBECRAFTED_WORKER_SESSION") or "").strip()
    if override:
        return override

    host = Path(root or ".").name or "vibecrafted"
    dispatcher = (
        str(env.get("VC_FRAME_SESSION_NAME") or "").strip()
        or str(env.get("ZELLIJ_SESSION_NAME") or "").strip()
    )
    if dispatcher and host == dispatcher:
        return f"{host} workers"
    return host


def _run_is_terminal(run: dict[str, Any]) -> bool:
    if str(run.get("state") or "") in TERMINAL_STATES:
        return True
    if str(run.get("liveness") or "") == "terminal":
        return True
    return run.get("exit_code") is not None


def _path_exists(path: str) -> bool:
    if not path:
        return False
    try:
        return Path(path).is_file()
    except OSError:
        return False


def _report_frontmatter_value(report_path: str, key: str) -> str:
    if not _path_exists(report_path):
        return ""
    values = parse_frontmatter(Path(report_path))
    return str(values.get(key) or "").strip()


def _report_requested_next_stage(report_path: str) -> str:
    """Worker-requested lifecycle steering read from report frontmatter.

    A stage worker may steer the lifecycle runner (umbrella forward/backward)
    by writing ``next_stage: <stage-id>`` in its report frontmatter. Unknown
    stage ids are ignored downstream by the runner's manifest validation.
    """
    return _report_frontmatter_value(report_path, "next_stage")


def _report_requested_next_agent(report_path: str) -> str:
    """Worker-requested baton handoff read from report frontmatter.

    A stage worker may hand the lifecycle baton to another agent by writing
    ``next_agent: <agent-id>`` in its report frontmatter. Unknown agents are
    ignored downstream by the runner's SUPPORTED_AGENTS validation.
    """
    return _report_frontmatter_value(report_path, "next_agent")


def report_dou_index(report_path: str) -> int | None:
    """Worker-reported DoU index read from report frontmatter.

    A DoU stage worker measures the launch gap by writing
    ``dou_index: <int>`` — the count of open Definition-of-Undone findings —
    in its report frontmatter; 0 is the launch-ready target (ZERO DoU index).
    Absent or invalid values read as ``None``, never as a fake zero.

    Public (unlike the ``next_stage``/``next_agent`` readers) because the
    lifecycle status surface also reads it live in no-await mode.
    """
    raw = _report_frontmatter_value(report_path, "dou_index")
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    return value if value >= 0 else None


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _terminal_meta_payload(
    *,
    run_id: str,
    run: dict[str, Any],
    report_path: str,
    transcript_path: str,
    meta_path: str,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "state": str(run.get("state") or ""),
        "liveness": str(run.get("liveness") or ""),
        "operator_state": str(run.get("operator_state") or ""),
        "terminal": _run_is_terminal(run),
        "exit_code": run.get("exit_code"),
        "session_id": str(run.get("session_id") or ""),
        "root": str(run.get("root") or ""),
        "agent": str(run.get("agent") or ""),
        "skill": str(run.get("skill") or ""),
        "mode": str(run.get("mode") or ""),
        "report": report_path,
        "transcript": transcript_path,
        "meta": meta_path,
        "artifact_ok": bool(run.get("artifact_ok")),
        "artifact_errors": list(run.get("artifact_errors") or []),
        "updated_at": str(run.get("updated_at") or ""),
        "completed_at": str(run.get("completed_at") or ""),
    }


def _write_terminal_meta(
    *,
    run_id: str,
    run: dict[str, Any],
    report_path: str,
    transcript_path: str,
    meta_path: str,
) -> dict[str, Any]:
    if not meta_path:
        return {}
    path = Path(meta_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = _read_json_object(path)
    payload = {
        **existing,
        **_terminal_meta_payload(
            run_id=run_id,
            run=run,
            report_path=report_path,
            transcript_path=transcript_path,
            meta_path=meta_path,
        ),
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def await_launch_truth(
    launch: dict[str, Any] | str,
    *,
    timeout_seconds: float = 300,
    interval_seconds: float = 5,
    hard_cap_seconds: float | None = None,
    require_report: bool = True,
    require_transcript_output: bool = False,
) -> dict[str, Any]:
    """Await a launched workflow and verify its announced artifact paths.

    This is intentionally separate from :func:`launch_workflow` so callers can
    keep launch acceptance asynchronous while dispatch engines can later prove
    terminal run truth for returned run ids. ``timeout_seconds`` is forwarded as
    :func:`await_run`'s liveness-aware idle deadline (resets on real activity);
    ``hard_cap_seconds`` is the optional absolute ceiling for a live-but-wedged
    worker.
    """
    launch_payload: dict[str, Any]
    if isinstance(launch, dict):
        launch_payload = dict(launch)
        run_id = str(launch_payload.get("run_id") or "").strip()
    else:
        launch_payload = {}
        run_id = str(launch or "").strip()
    if not run_id:
        raise ValueError("run_id is required")

    awaited = await_run(
        run_id,
        timeout_seconds=timeout_seconds,
        interval_seconds=interval_seconds,
        hard_cap_seconds=hard_cap_seconds,
    )
    run = dict(awaited.get("run") or {})
    await_reason = str(awaited.get("reason") or "")
    worker_alive = bool(awaited.get("worker_alive"))
    report_path = str(launch_payload.get("report") or run.get("latest_report") or "")
    transcript_path = str(
        launch_payload.get("transcript") or run.get("latest_transcript") or ""
    )
    meta_path = str(launch_payload.get("meta") or run.get("meta") or "")
    terminal = (
        bool(awaited.get("completed")) and _run_is_terminal(run) and not worker_alive
    )
    terminal_evidence = terminal or (
        bool(awaited.get("completed"))
        and await_reason == "report_delivered"
        and not worker_alive
    )

    meta_payload: dict[str, Any] = {}
    if terminal:
        meta_payload = _write_terminal_meta(
            run_id=run_id,
            run=run,
            report_path=report_path,
            transcript_path=transcript_path,
            meta_path=meta_path,
        )

    validation = validate_artifacts(
        meta_path=meta_path or None,
        report_path=report_path or None,
        transcript_path=transcript_path or None,
        require_report=require_report,
        require_transcript_output=require_transcript_output,
    )
    paths_exist = {
        "report": _path_exists(report_path),
        "transcript": _path_exists(transcript_path),
        "meta": _path_exists(meta_path),
    }
    path_errors = [
        f"{name}_missing" for name, exists in paths_exist.items() if not exists
    ]

    return {
        "run_id": run_id,
        "found": bool(awaited.get("found")),
        "completed": bool(awaited.get("completed")),
        "timed_out": bool(awaited.get("timed_out")),
        "terminal": terminal,
        "terminal_evidence": terminal_evidence,
        "await_reason": await_reason,
        "worker_alive": worker_alive,
        "attempts": awaited.get("attempts"),
        "run": run,
        "report": report_path,
        "transcript": transcript_path,
        "meta": meta_path,
        "paths_exist": paths_exist,
        "artifact_ok": validation.ok and not path_errors,
        "artifact_errors": list(validation.errors) + path_errors,
        "artifact_warnings": list(validation.warnings),
        "meta_payload": meta_payload or validation.meta_payload,
        "next_stage": _report_requested_next_stage(report_path),
        "next_agent": _report_requested_next_agent(report_path),
        "dou_index": report_dou_index(report_path),
    }


def _stop_signal_target(run: dict[str, Any]) -> tuple[str, int] | None:
    for key in ("launcher_pid", "worker_pgid", "worker_pid"):
        raw = run.get(key)
        if isinstance(raw, int) and raw > 0:
            return key, raw
        if isinstance(raw, str) and raw.strip().isdigit():
            return key, int(raw.strip())
    return None


def _pid_is_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _wait_for_pid_exit(pid: int, grace_seconds: float) -> bool:
    deadline = time.monotonic() + max(float(grace_seconds), 0.0)
    while time.monotonic() < deadline:
        if not _pid_is_alive(pid):
            return False
        time.sleep(min(0.05, max(deadline - time.monotonic(), 0.0)))
    return _pid_is_alive(pid)


def _normalized_runtime(raw: str) -> str:
    return raw if raw in SUPPORTED_RUNTIMES else "headless"


def _coerce_positive_int(value: Any, default: int | None = None) -> int | None:
    if value in (None, ""):
        return default
    try:
        result = int(str(value))
    except ValueError:
        return default
    return result if result > 0 else default


def _workflow_metadata(skill: str) -> dict[str, Any]:
    definition = workflow_registry.workflow_definition(skill)
    if definition is None:
        return {}
    return {
        "id": definition.id,
        "phase": definition.cadence,
        "can_modify_code": definition.can_modify_code,
        "runtime_kind": definition.runtime_kind,
        "tooling": list(definition.tooling),
        "lifecycle_order": definition.lifecycle_order,
    }


def normalize_launch_spec(
    payload: dict[str, Any], source_dir: str | Path
) -> WorkflowLaunchSpec:
    requested_skill = str(payload.get("skill") or "workflow").strip()
    skill = WORKFLOW_ALIASES.get(requested_skill, requested_skill)
    definition = workflow_registry.workflow_definition(skill)
    if definition is None:
        raise ValueError(f"Unsupported workflow: {skill}")

    raw_agent = payload.get("agent")
    raw_research_agents = payload.get("research_agents") or ()
    if isinstance(raw_agent, (list, tuple)):
        positional_agents = tuple(
            str(item).strip() for item in raw_agent if str(item).strip()
        )
        agent = positional_agents[0] if positional_agents else definition.default_agent
    else:
        positional_agents = ()
        agent = str(raw_agent or definition.default_agent).strip()
    if definition.runtime_kind == "supervised_research":
        if not positional_agents and raw_research_agents:
            positional_agents = tuple(
                str(item).strip() for item in raw_research_agents if str(item).strip()
            )
        unsupported = [
            item for item in positional_agents if item not in SUPPORTED_AGENTS
        ]
        if unsupported:
            raise ValueError(f"Unsupported research agent: {unsupported[0]}")
        agent = "swarm"
    if agent not in SUPPORTED_AGENTS:
        raise ValueError(f"Unsupported agent: {agent}")

    prompt = str(payload.get("prompt") or "").strip()
    file_path = str(payload.get("file") or "").strip()
    if not prompt and not file_path:
        prompt = workflow_registry.workflow_default_prompt(skill)
    root = normalize_run_root(payload.get("root"), source_dir)
    runtime = _normalized_runtime(str(payload.get("runtime") or "headless").strip())
    mode = str(payload.get("mode") or skill).strip() or skill
    count = _coerce_positive_int(
        payload.get("count"), 3 if definition.supports_count else None
    )
    depth = _coerce_positive_int(
        payload.get("depth"), 3 if definition.supports_depth else None
    )
    model = str(payload.get("model") or payload.get("model_requested") or "").strip()
    if not model and file_path:
        # Brief frontmatter is the plan's voice: `model: <id>` pins the worker
        # tier without an explicit --model flag. Flag always wins over brief.
        model = parse_frontmatter(Path(file_path).expanduser()).get("model", "").strip()
    research_agents: tuple[str, ...] = ()
    research_synthesizer = ""
    research_synthesizer_model = str(
        payload.get("synthesizer_model")
        or payload.get("research_synthesizer_model")
        or ""
    ).strip()
    if definition.runtime_kind == "supervised_research":
        explicit_synthesizer = str(
            payload.get("synthesizer") or payload.get("research_synthesizer") or ""
        ).strip()
        if len(positional_agents) > 1:
            research_agents = positional_agents
            research_synthesizer = explicit_synthesizer or positional_agents[0]
        elif positional_agents:
            research_synthesizer = explicit_synthesizer or positional_agents[0]
        elif explicit_synthesizer:
            research_synthesizer = explicit_synthesizer
        if research_synthesizer and research_synthesizer not in SUPPORTED_AGENTS:
            raise ValueError(
                f"Unsupported research synthesizer: {research_synthesizer}"
            )

    if definition.requires_input and not prompt and not file_path:
        raise ValueError("Launch requires either --prompt text or --file path.")

    return WorkflowLaunchSpec(
        agent=agent,
        mode=mode,
        skill=skill,
        prompt=prompt,
        file=file_path,
        runtime=runtime,
        root=root,
        count=count,
        depth=depth,
        model=model,
        research_agents=research_agents,
        research_synthesizer=research_synthesizer,
        research_synthesizer_model=research_synthesizer_model,
        run_id=str(payload.get("run_id") or "").strip(),
    )


def _source_prompt(spec: WorkflowLaunchSpec) -> str:
    if spec.file:
        try:
            return (
                Path(spec.file)
                .expanduser()
                .read_text(encoding="utf-8", errors="replace")
            )
        except OSError:
            return f"Read the requested prompt file yourself: {spec.file}"
    return spec.prompt


def _runtime_prompt(spec: WorkflowLaunchSpec) -> str:
    report_hint = "${VIBECRAFTED_REPORT_PATH}"
    transcript_hint = "${VIBECRAFTED_TRANSCRIPT_PATH}"
    source_prompt = _source_prompt(spec)
    return f"""You are running under Vibecrafted core runtime.

Contract:
- Work in repository root: {spec.root}
- Skill: vc-{spec.skill}
- Agent request: {spec.agent}
- Mode: {spec.mode}
- Runtime request: {spec.runtime}
- Count: {spec.count or ""}
- Depth: {spec.depth or ""}
- Do not launch or delegate to external agent fleets.
- Do not call legacy Vibecrafted skill launchers or runtime/scripts launchers.
- Write your final report to the path in VIBECRAFTED_REPORT_PATH ({report_hint}).
- The launcher pre-seeds that report's YAML frontmatter with machine-owned
  `run_id` and `session_id`; preserve those values and never copy or guess identity.
- Edit the existing frontmatter, keeping `finalized: false` until you deliberately
  attest success with `finalized: true` plus a non-empty `claim`.
- Keep non-empty `agent`, `skill`, and `status` keys.
- Preserve an honest blocked/partial/failed status.
- Let stdout/stderr form the transcript captured at VIBECRAFTED_TRANSCRIPT_PATH ({transcript_hint}).
- Do not create, overwrite, or summarize run metadata yourself. The runtime owns VIBECRAFTED_META_PATH.
{WORKER_SIGNAL_DISCIPLINE.rstrip()}

Step 0 — orient before you touch (the vc-init pass).
The operator prompt below is one framing — a hypothesis, not the ground truth. Reading a
couple of files and feeling oriented is the trap: you'd cut from a partial, self-picked slice,
and that is where silent drift gets in. So before any skill-specific work, run the vc-init
due-diligence right here in this thread, because it is what makes every later move land:
- Map: materialize the Loctree context atlas for {spec.root} and read it to the END
  (entrypoints, blast radius, twins, dead surfaces, the real shape).
- Intent: recover the AICX history — why the code became this, what was already tried.
- Ground truth + risk: git/security sanity, then grade the blast radius before changing behavior.
Your skill (vc-{spec.skill}) carries its own orientation gate — this is it. Not a rule barked at
you: it is simply the move that separates a real cut from a confident guess, and it pays for
itself in the very next step.

Operator prompt:
{source_prompt}
"""


def _write_prompt_file(path: Path, body: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def build_launch_command(
    spec: WorkflowLaunchSpec,
    _source_dir: str | Path,
    *,
    prompt_file: str | Path | None = None,
) -> list[str]:
    prompt_path = str(prompt_file or spec.file or "")
    runtime_kind = workflow_registry.workflow_runtime_kind(spec.skill)
    if runtime_kind == "supervised_research":
        command = (
            "research-synthesis"
            if spec.runtime in {"terminal", "visible"}
            else "research"
        )
        launch_command = [
            sys.executable,
            "-m",
            "vibecrafted_core.workflow_runtime",
            command,
            "--root",
            spec.root,
            "--prompt-file",
            prompt_path,
        ]
        if spec.model:
            launch_command.extend(["--model", spec.model])
        if spec.research_synthesizer:
            launch_command.extend(["--synthesizer", spec.research_synthesizer])
        if spec.research_synthesizer_model:
            launch_command.extend(
                ["--synthesizer-model", spec.research_synthesizer_model]
            )
        return launch_command
    if runtime_kind == "supervised_marbles":
        launch_command = [
            sys.executable,
            "-m",
            "vibecrafted_core.workflow_runtime",
            "marbles",
            "--workflow",
            spec.skill,
            "--agent",
            spec.agent if spec.agent != "swarm" else "codex",
            "--root",
            spec.root,
            "--prompt-file",
            prompt_path,
            "--count",
            str(spec.count or 3),
            "--depth",
            str(spec.depth or 3),
        ]
        if spec.model:
            launch_command.extend(["--model", spec.model])
        return launch_command

    worker_agent = spec.agent
    return _with_model_override(worker_agent, _stdin_command(worker_agent), spec.model)


def _sweep_stale_runs() -> None:
    """Reap survivors of terminal runs. Never raises, never blocks a launch."""
    try:
        from .run_reaper import sweep_quietly

        sweep_quietly()
    except Exception as _sweep_exc:  # noqa: BLE001
        _ = _sweep_exc  # best-effort reaper sweep


def launch_workflow(
    spec: WorkflowLaunchSpec,
    source_dir: str | Path,
    *,
    env: dict[str, str] | None = None,
    retry_of: str = "",
) -> dict[str, Any]:
    # Opportunistic pre-flight: before adding a run to the machine, take the dead
    # ones' survivors off it. Every spawn is the natural sweep point — it needs no
    # daemon, and it is exactly when the residue starts costing the new run cores.
    # Silent and best-effort; a reaper problem must never block a launch.
    _sweep_stale_runs()

    # vc-guard proof path: refuse continuation when trust has block on HEAD.
    # Guard never invents settlement; only consumes trust journal. Opt-out via
    # VIBECRAFTED_GUARD=0 for hermetic tests that are not about enforcement.
    if str(os.environ.get("VIBECRAFTED_GUARD", "1")).strip() not in {
        "0",
        "false",
        "off",
        "no",
    }:
        try:
            from . import guard as guard_mod

            root = Path(spec.root or source_dir or Path.cwd())
            decision = guard_mod.enforce_continuation(
                repo=root,
                skill=str(spec.skill or ""),
            )
            if not decision.allowed:
                raise ValueError(decision.remedium or "vc-guard refused continuation")
        except ImportError:
            pass
        except (ValueError, OSError) as exc:
            # Non-git fixtures, sandbox roots, and hermetic tests that stub
            # subprocess: do not hard-fail launch unless the error is an
            # explicit guard refusal (remedium text).
            message = str(exc)
            if (
                "vc-guard" in message
                or "Remedium" in message
                or "trust recorded block" in message
            ):
                raise
            # not a git repository / stubbed subprocess / unreadable context → allow

    run_id = spec.run_id or reserve_run_id(spec.skill)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", run_id):
        raise ValueError("run_id must be a safe 1-128 character identifier")
    artifacts = _run_artifact_paths(run_id)
    runtime_kind = workflow_registry.workflow_runtime_kind(spec.skill)
    research_selection = (
        resolve_research_runtime_config(
            override_agents=spec.research_agents,
            synthesizer=spec.research_synthesizer,
            synthesizer_model=spec.research_synthesizer_model,
        )
        if runtime_kind == "supervised_research"
        else None
    )
    source_prompt = _source_prompt(spec)
    prompt_body = (
        source_prompt
        if runtime_kind in {"supervised_research", "supervised_marbles"}
        else _runtime_prompt(spec)
    )
    canonical_report_dir = _canonical_report_dir(spec.root, spec.skill)
    artifact_ts = time.strftime("%Y-%m-%d")
    artifact_slug = _artifact_slug(source_prompt, run_id)
    artifact_suffix = _artifact_report_suffix(
        canonical_report_dir,
        artifact_ts,
        artifact_slug,
    )
    report_path = _canonical_report_path(
        canonical_report_dir=canonical_report_dir,
        artifact_ts=artifact_ts,
        agent=spec.agent,
        artifact_slug=artifact_slug,
        artifact_suffix=artifact_suffix,
    )
    prompt_path = _write_prompt_file(artifacts["prompt"], prompt_body)
    claim_digest = str(spec.claim_digest or "").strip()
    if claim_digest:
        atomic_write_json(
            artifacts["meta"],
            {
                "run_id": run_id,
                "claim_digest": claim_digest,
            },
        )
    safe_spec = {**spec.to_payload(), "prompt": "", "file": str(prompt_path)}
    worker_command = build_launch_command(spec, source_dir, prompt_file=prompt_path)
    model_receipt = _model_override_receipt(spec.agent, spec.model)
    if spec.model and runtime_kind == "supervised_research":
        model_receipt = {"model_requested": spec.model}
    dispatch_command = _dispatcher_command(
        run_id=run_id,
        root=spec.root,
        meta_path=artifacts["meta"],
        prompt_path=prompt_path,
        report_path=report_path,
        transcript_path=artifacts["transcript"],
        worker_command=worker_command,
        tee_output=spec.runtime in {"terminal", "visible"},
        emit_json=spec.runtime not in {"terminal", "visible"},
        quiet=spec.runtime in {"terminal", "visible"},
        lifecycle_state_path=spec.lifecycle_state_path,
    )
    launch_dir = control_plane_home() / "launches"
    launch_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    launch_log = launch_dir / f"{stamp}_{spec.skill}.log"
    merged_env = dict(os.environ)
    if env:
        merged_env.update(env)
    merged_env.pop(CLAIM_DIGEST_ENV, None)
    _prepend_pythonpath(merged_env, _core_package_root())
    session_id = ensure_session_id(merged_env.get("VIBECRAFTED_SESSION_ID"))
    merged_env["VIBECRAFTED_RUN_ID"] = run_id
    merged_env["VIBECRAFTED_SESSION_ID"] = session_id
    merged_env["VIBECRAFTED_REPORT_PATH"] = str(report_path)
    merged_env["VIBECRAFTED_TRANSCRIPT_PATH"] = str(artifacts["transcript"])
    merged_env["VIBECRAFTED_META_PATH"] = str(artifacts["meta"])
    merged_env["VIBECRAFTED_PROMPT_PATH"] = str(prompt_path)
    merged_env["VIBECRAFTED_AGENT"] = spec.agent
    merged_env["VIBECRAFTED_SKILL"] = spec.skill
    merged_env["VIBECRAFTED_RUNTIME"] = spec.runtime
    if claim_digest:
        merged_env[CLAIM_DIGEST_ENV] = claim_digest
    if spec.model:
        merged_env["VIBECRAFTED_MODEL_REQUESTED"] = spec.model
    if research_selection is not None:
        if spec.research_agents:
            merged_env["VIBECRAFTED_RESEARCH_AGENTS"] = ",".join(
                research_selection.agents
            )
        if research_selection.synthesizer:
            merged_env["VIBECRAFTED_RESEARCH_SYNTHESIZER"] = (
                research_selection.synthesizer
            )
        if research_selection.synthesizer_model:
            merged_env["VIBECRAFTED_RESEARCH_SYNTHESIZER_MODEL"] = (
                research_selection.synthesizer_model
            )
    if "model_override_supported" in model_receipt:
        merged_env["VIBECRAFTED_MODEL_OVERRIDE_SUPPORTED"] = str(
            bool(model_receipt["model_override_supported"])
        ).lower()
    if "model_override_skipped" in model_receipt:
        merged_env["VIBECRAFTED_MODEL_OVERRIDE_SKIPPED"] = str(
            bool(model_receipt["model_override_skipped"])
        ).lower()
    if model_receipt.get("model_override_skip_reason"):
        merged_env["VIBECRAFTED_MODEL_OVERRIDE_SKIP_REASON"] = str(
            model_receipt["model_override_skip_reason"]
        )
    merged_env["VIBECRAFTED_CANONICAL_REPORT_DIR"] = str(canonical_report_dir)
    merged_env["VIBECRAFTED_ARTIFACT_SLUG"] = artifact_slug
    merged_env["VIBECRAFTED_ARTIFACT_TS"] = artifact_ts
    if artifact_suffix:
        merged_env["VIBECRAFTED_ARTIFACT_SUFFIX"] = artifact_suffix
    operator_session = _effective_operator_session(
        root=spec.root,
        run_id=run_id,
        env=merged_env,
    )
    command, transport, command_script = _launch_transport_command(
        spec=spec,
        run_id=run_id,
        operator_session=operator_session,
        dispatch_command=dispatch_command,
        launch_dir=launch_dir,
        prompt_path=prompt_path,
        report_path=report_path,
        transcript_path=artifacts["transcript"],
        meta_path=artifacts["meta"],
        canonical_report_dir=canonical_report_dir,
        artifact_slug=artifact_slug,
        artifact_ts=artifact_ts,
        artifact_suffix=artifact_suffix,
        research_selection=research_selection,
    )
    merged_env["VIBECRAFTED_OPERATOR_SESSION"] = operator_session

    append_event(
        kind="launch",
        run_id=run_id,
        message=f"launch accepted for {spec.skill}",
        payload={
            "state": "created",
            "agent": spec.agent,
            "skill": spec.skill,
            "mode": spec.mode,
            "runtime": spec.runtime,
            "root": spec.root,
            "operator_session": operator_session,
            "session_id": session_id,
            "identity_required": True,
            "source_dir": str(Path(source_dir).resolve()),
            "prompt": "",
            "file": str(prompt_path),
            "prompt_file": str(prompt_path),
            "report": str(report_path),
            "transcript": str(artifacts["transcript"]),
            "meta": str(artifacts["meta"]),
            **({"claim_digest": claim_digest} if claim_digest else {}),
            "workflow": _workflow_metadata(spec.skill),
            **(
                {
                    "research_agents": list(research_selection.agents),
                    "research_agent_source": research_selection.source,
                    "research_synthesizer": research_selection.synthesizer,
                    "research_synthesizer_model": research_selection.synthesizer_model,
                    "research_synthesizer_source": research_selection.synthesizer_source,
                    "research_ignored_agents": list(research_selection.ignored),
                }
                if research_selection is not None
                else {}
            ),
            **model_receipt,
            "worker_command": worker_command,
            "dispatch_command": dispatch_command,
            "command": command,
            "transport": transport,
            "command_script": str(command_script or ""),
            "retry_of": retry_of,
        },
    )
    with launch_log.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                {
                    "ts": stamp,
                    "run_id": run_id,
                    "spec": safe_spec,
                    "workflow": _workflow_metadata(spec.skill),
                    **model_receipt,
                    "worker_command": worker_command,
                    "dispatch_command": dispatch_command,
                    "command": command,
                    "transport": transport,
                    "command_script": str(command_script or ""),
                    "retry_of": retry_of,
                    "session_id": session_id,
                    "operator_session": operator_session,
                    **model_receipt,
                }
            )
            + "\n"
        )
        launcher_pid: int | None = None
        try:
            if transport == "vc-frame":
                # G3: run action synchronously so "Session not found" cannot
                # leave a silent process_spawned receipt. One create-background
                # retry lives inside _vc_frame_run_host_action.
                host = _vc_frame_run_host_action(
                    command, operator_session=operator_session
                )
                handle.write(
                    json.dumps(
                        {
                            "ts": stamp,
                            "event": "vc_frame_host_action",
                            "ok": host.ok,
                            "resurrected": host.resurrected,
                            "error": host.error,
                            "stderr": host.stderr[:2000] if host.stderr else "",
                        }
                    )
                    + "\n"
                )
                if not host.ok:
                    append_event(
                        kind="launch",
                        run_id=run_id,
                        message=f"vc-frame host session launch failed: {host.error}",
                        payload={
                            "state": "failed",
                            "agent": spec.agent,
                            "skill": spec.skill,
                            "mode": spec.mode,
                            "runtime": spec.runtime,
                            "root": spec.root,
                            "operator_session": operator_session,
                            "session_id": session_id,
                            "error": host.error,
                            "last_error": host.error,
                            "retry_of": retry_of,
                            **model_receipt,
                        },
                    )
                    return {
                        "accepted": False,
                        "message": f"Failed to launch {spec.skill}: {host.error}",
                        "command": command,
                        "worker_command": worker_command,
                        "dispatch_command": dispatch_command,
                        "transport": transport,
                        "command_script": str(command_script or ""),
                        "launch_log": str(launch_log),
                        "spec": safe_spec,
                        "error": host.error,
                        "last_error": host.error,
                        "run_id": run_id,
                        "operator_session": operator_session,
                        "retry_of": retry_of,
                        **model_receipt,
                        "control_plane": sync_state(),
                    }
                launcher_pid = host.pid
            else:
                proc = subprocess.Popen(
                    command,
                    cwd=Path(source_dir).resolve(),
                    env=merged_env,
                    stdout=handle,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    text=True,
                )
                launcher_pid = proc.pid
                # The launch is intentionally asynchronous, but dropping the
                # Popen object without waiting leaves a completed launcher as a
                # zombie.  ``kill(pid, 0)`` then reports it alive and canonical
                # await cannot distinguish finalization from stale OS state.
                wait_for_launcher = getattr(proc, "wait", None)
                if callable(wait_for_launcher):
                    threading.Thread(
                        target=wait_for_launcher,
                        name=f"vibecrafted-reap-{run_id}",
                        daemon=True,
                    ).start()
        except OSError as exc:
            handle.write(
                json.dumps(
                    {
                        "ts": stamp,
                        "event": "spawn_error",
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                )
                + "\n"
            )
            # The "launch accepted" event above already recorded state="created".
            # Without a terminal event here, the run is stranded as "created"
            # forever — sync_state() shows a phantom active run that never
            # progressed. Record the failure so reconciliation marks it failed.
            append_event(
                kind="launch",
                run_id=run_id,
                message=f"dispatcher spawn failed: {type(exc).__name__}: {exc}",
                payload={
                    "state": "failed",
                    "agent": spec.agent,
                    "skill": spec.skill,
                    "mode": spec.mode,
                    "runtime": spec.runtime,
                    "root": spec.root,
                    "operator_session": operator_session,
                    "session_id": session_id,
                    "error": f"{type(exc).__name__}: {exc}",
                    "last_error": f"{type(exc).__name__}: {exc}",
                    "retry_of": retry_of,
                    **model_receipt,
                },
            )
            return {
                "accepted": False,
                "message": f"Failed to launch {spec.skill}: {exc}",
                "command": command,
                "worker_command": worker_command,
                "dispatch_command": dispatch_command,
                "transport": transport,
                "command_script": str(command_script or ""),
                "launch_log": str(launch_log),
                "spec": safe_spec,
                "error": f"{type(exc).__name__}: {exc}",
                "run_id": run_id,
                "retry_of": retry_of,
                **model_receipt,
                "control_plane": sync_state(),
            }
        append_event(
            kind="launch",
            run_id=run_id,
            message="dispatcher process spawned",
            payload={
                "state": "process_spawned",
                "launcher_pid": launcher_pid,
                "agent": spec.agent,
                "skill": spec.skill,
                "mode": spec.mode,
                "runtime": spec.runtime,
                "root": spec.root,
                "operator_session": operator_session,
                "session_id": session_id,
                "identity_required": True,
                "source_dir": str(Path(source_dir).resolve()),
                "prompt": "",
                "file": str(prompt_path),
                "prompt_file": str(prompt_path),
                "report": str(report_path),
                "transcript": str(artifacts["transcript"]),
                "meta": str(artifacts["meta"]),
                "workflow": _workflow_metadata(spec.skill),
                **model_receipt,
                "worker_command": worker_command,
                "dispatch_command": dispatch_command,
                "command": command,
                "transport": transport,
                "command_script": str(command_script or ""),
                "retry_of": retry_of,
            },
        )
        handle.write(
            json.dumps({"ts": stamp, "event": "spawned", "pid": launcher_pid}) + "\n"
        )

    return {
        "accepted": True,
        "message": f"Launched {spec.skill} via Vibecrafted core runtime.",
        "command": command,
        "dispatch_command": dispatch_command,
        "worker_command": worker_command,
        "transport": transport,
        "command_script": str(command_script or ""),
        "pid": launcher_pid,
        "run_id": run_id,
        "agent": spec.agent,
        "skill": spec.skill,
        "root": spec.root,
        "dispatch": 0,
        "status": "launching",
        "control": str(run_snapshot_dir() / f"{run_id}.json"),
        "report": str(report_path),
        "transcript": str(artifacts["transcript"]),
        "meta": str(artifacts["meta"]),
        "prompt_file": str(prompt_path),
        "session_id": session_id,
        "operator_session": operator_session,
        "control_plane_identity": {
            "run_id": run_id,
            "session_id": session_id,
            "operator_session": operator_session,
        },
        "workflow": _workflow_metadata(spec.skill),
        **model_receipt,
        "retry_of": retry_of,
        "launch_log": str(launch_log),
        "spec": safe_spec,
        # Launch acceptance is already durable in the event stream, run meta,
        # and dispatcher process. A global board reconciliation here can block
        # on an unrelated run and turn a successful launch into a traceback.
        # Reconciliation belongs to observe/await/board readers, never the
        # launch acknowledgement path.
        "control_plane": {"sync": "deferred", "run_id": run_id},
    }


def stop_run(
    run_id: str,
    *,
    reason: str = "operator stop request",
    grace_seconds: float = 2.0,
) -> dict[str, Any]:
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run = lookup_run(target)
    if run is None:
        record_stop_transition(
            target,
            accepted=False,
            reason="run_not_found",
        )
        return {"accepted": False, "run_id": target, "reason": "run_not_found"}

    if _run_is_terminal(run):
        record_stop_transition(
            target,
            run=run,
            accepted=False,
            reason="run_terminal",
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "run_terminal",
            "run": run,
        }

    signal_target = _stop_signal_target(run)
    if signal_target is None:
        record_stop_transition(
            target,
            run=run,
            accepted=False,
            reason="missing_signal_target",
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "missing_signal_target",
            "run": run,
        }

    target_kind, target_pid = signal_target
    target_pgid: int | None = None
    signal_sent = False
    already_dead = False
    alive_after_grace: bool | None = None
    stop_reason = reason
    stop_error = ""
    try:
        if target_kind == "launcher_pid":
            target_pgid = os.getpgid(target_pid)
            os.killpg(target_pgid, signal.SIGTERM)
        elif target_kind == "worker_pgid":
            target_pgid = target_pid
            os.killpg(target_pgid, signal.SIGTERM)
        else:
            os.kill(target_pid, signal.SIGTERM)
        signal_sent = True
    except ProcessLookupError:
        already_dead = True
        stop_reason = "pid_gone_before_stop"
    except OSError as exc:
        stop_error = f"{type(exc).__name__}: {exc}"

    accepted = not stop_error
    if signal_sent:
        alive_after_grace = _wait_for_pid_exit(target_pid, grace_seconds)
    elif already_dead:
        alive_after_grace = False

    record_stop_transition(
        target,
        run=run,
        accepted=accepted,
        reason=stop_reason if accepted else "signal_failed",
        signal_name="SIGTERM",
        target=target_kind,
        target_pid=target_pid,
        target_pgid=target_pgid,
        signal_sent=signal_sent,
        already_dead=already_dead,
        alive_after_grace=alive_after_grace,
        grace_seconds=grace_seconds,
        exit_code=143 if signal_sent else None,
        error=stop_error,
    )
    return {
        "accepted": accepted,
        "run_id": target,
        "target": target_kind,
        "target_pid": target_pid,
        "target_pgid": target_pgid,
        "signal_sent": signal_sent,
        "already_dead": already_dead,
        "alive_after_grace": alive_after_grace,
        "reason": stop_reason if accepted else "signal_failed",
        "error": stop_error,
        "run": lookup_run(target),
    }


def retry_run(
    run_id: str,
    source_dir: str | Path = ".",
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run = lookup_run(target)
    if run is None:
        append_event(
            kind="audit:retry",
            run_id=target,
            message="retry rejected: run not found",
            payload={"accepted": False, "reason": "run_not_found"},
        )
        return {"accepted": False, "run_id": target, "reason": "run_not_found"}

    if not _run_is_terminal(run):
        append_event(
            kind="audit:retry",
            run_id=target,
            message="retry rejected: run not terminal",
            payload={
                "accepted": False,
                "reason": "run_not_terminal",
                "state": run.get("state"),
            },
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "run_not_terminal",
            "run": run,
        }

    payload: dict[str, Any] = {
        "skill": str(run.get("skill") or "workflow"),
        "agent": str(run.get("agent") or "claude"),
        "prompt": str(run.get("prompt") or ""),
        "file": str(run.get("file") or ""),
        "runtime": str(run.get("runtime") or "headless"),
        "root": str(run.get("root") or Path(source_dir).resolve()),
    }
    mode = str(run.get("mode") or "").strip()
    if mode:
        payload["mode"] = mode
    model_requested = str(run.get("model_requested") or "").strip()
    if model_requested:
        payload["model_requested"] = model_requested

    try:
        spec = normalize_launch_spec(payload, source_dir)
    except ValueError as exc:
        append_event(
            kind="audit:retry",
            run_id=target,
            message="retry rejected: launch spec invalid",
            payload={
                "accepted": False,
                "reason": "invalid_retry_spec",
                "error": str(exc),
            },
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "invalid_retry_spec",
            "error": str(exc),
            "run": run,
        }

    launched = launch_workflow(spec, source_dir, env=env, retry_of=target)
    append_event(
        kind="audit:retry",
        run_id=target,
        message="retry dispatched" if launched.get("accepted") else "retry failed",
        payload={
            "accepted": bool(launched.get("accepted")),
            "new_run_id": launched.get("run_id"),
            "error": launched.get("error", ""),
        },
    )
    return {
        "accepted": bool(launched.get("accepted")),
        "run_id": target,
        "retry_run_id": str(launched.get("run_id") or ""),
        "launch": launched,
    }


def block_run(
    run_id: str,
    *,
    reason: str = "operator block request",
    note: str = "",
) -> dict[str, Any]:
    """Mark an in-flight run as ``blocked`` with an audited lifecycle event.

    Blocking is an operator lever, not a signal: it records that the run needs
    human intervention and pins it to the terminal ``blocked`` state so the
    control plane stops treating it as active. A blocked run can later be
    resumed through :func:`retry_run` (which requires a terminal state).
    """
    target = str(run_id or "").strip()
    if not target:
        raise ValueError("run_id is required")

    run = lookup_run(target)
    if run is None:
        append_event(
            kind="audit:block",
            run_id=target,
            message="block rejected: run not found",
            payload={"accepted": False, "reason": "run_not_found"},
        )
        return {"accepted": False, "run_id": target, "reason": "run_not_found"}

    if _run_is_terminal(run):
        append_event(
            kind="audit:block",
            run_id=target,
            message="block rejected: run already terminal",
            payload={
                "accepted": False,
                "reason": "run_terminal",
                "state": run.get("state"),
            },
        )
        return {
            "accepted": False,
            "run_id": target,
            "reason": "run_terminal",
            "run": run,
        }

    append_event(
        kind="audit:block",
        run_id=target,
        message="run marked blocked",
        payload={
            "accepted": True,
            "reason": reason,
            "note": note,
            "state": "blocked",
        },
    )
    return {
        "accepted": True,
        "run_id": target,
        "reason": reason,
        "note": note,
        "run": lookup_run(target),
    }
