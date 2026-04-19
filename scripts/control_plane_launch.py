from __future__ import annotations

import json
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

try:
    from control_plane_state import control_plane_home, sync_state
except ModuleNotFoundError:  # pragma: no cover - import path depends on entrypoint
    from scripts.control_plane_state import control_plane_home, sync_state


SUPPORTED_WORKFLOWS = {"workflow", "research", "review", "marbles"}
SUPPORTED_AGENTS = {"claude", "codex", "gemini", "swarm"}
SUPPORTED_RUNTIMES = {"headless", "terminal", "visible"}


@dataclass(frozen=True)
class WorkflowLaunchSpec:
    agent: str
    mode: str
    skill: str
    prompt: str
    file: str
    runtime: str
    root: str

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def vibecrafted_launcher(source_dir: str | Path) -> Path:
    return Path(source_dir).resolve() / "scripts" / "vibecrafted"


def _normalized_runtime(raw: str) -> str:
    return raw if raw in SUPPORTED_RUNTIMES else "headless"


def normalize_launch_spec(
    payload: dict[str, Any], source_dir: str | Path
) -> WorkflowLaunchSpec:
    skill = str(payload.get("skill") or "workflow").strip()
    if skill not in SUPPORTED_WORKFLOWS:
        raise ValueError(f"Unsupported workflow: {skill}")

    default_agent = "swarm" if skill == "research" else "claude"
    agent = str(payload.get("agent") or default_agent).strip()
    if skill == "research":
        agent = "swarm"
    if agent not in SUPPORTED_AGENTS:
        raise ValueError(f"Unsupported agent: {agent}")

    prompt = str(payload.get("prompt") or "").strip()
    file_path = str(payload.get("file") or "").strip()
    root = str(payload.get("root") or Path(source_dir).resolve()).strip()
    runtime = _normalized_runtime(str(payload.get("runtime") or "headless").strip())
    mode = str(payload.get("mode") or skill).strip() or skill

    if skill != "marbles" and not prompt and not file_path:
        raise ValueError("Launch requires either prompt text or a file path.")

    return WorkflowLaunchSpec(
        agent=agent,
        mode=mode,
        skill=skill,
        prompt=prompt,
        file=file_path,
        runtime=runtime,
        root=root,
    )


def build_launch_command(spec: WorkflowLaunchSpec, source_dir: str | Path) -> list[str]:
    launcher = vibecrafted_launcher(source_dir)
    if not launcher.exists():
        raise FileNotFoundError(f"Command deck not found at {launcher}")

    command = ["bash", str(launcher), spec.skill]
    if spec.skill != "research":
        command.append(spec.agent)

    command.extend(["--runtime", spec.runtime])
    if spec.root:
        command.extend(["--root", spec.root])
    if spec.file:
        command.extend(["--file", spec.file])
    elif spec.prompt:
        command.extend(["--prompt", spec.prompt])
    elif spec.skill == "marbles":
        command.extend(["--depth", "3"])

    return command


def launch_workflow(
    spec: WorkflowLaunchSpec,
    source_dir: str | Path,
    *,
    env: dict[str, str] | None = None,
) -> dict[str, Any]:
    command = build_launch_command(spec, source_dir)
    launch_dir = control_plane_home() / "launches"
    launch_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    launch_log = launch_dir / f"{stamp}_{spec.skill}.log"
    with launch_log.open("a", encoding="utf-8") as handle:
        handle.write(
            json.dumps({"ts": stamp, "spec": spec.to_payload(), "command": command})
            + "\n"
        )
        subprocess.Popen(
            command,
            cwd=Path(source_dir).resolve(),
            env=env,
            stdout=handle,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            text=True,
        )

    snapshot = sync_state()
    return {
        "accepted": True,
        "message": f"Launched {spec.skill} via the existing command deck.",
        "command": command,
        "launch_log": str(launch_log),
        "spec": spec.to_payload(),
        "control_plane": snapshot,
    }
