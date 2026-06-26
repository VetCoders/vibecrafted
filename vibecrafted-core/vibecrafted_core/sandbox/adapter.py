from __future__ import annotations

import asyncio
import os
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from vibecrafted_core.events import append_event

from .msbserver_lifecycle import MsbserverLifecycle
from .policy import SandboxPolicy

EventCallback = Callable[[dict[str, Any]], None]


@dataclass(frozen=True)
class ExecResult:
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    sandbox: str = ""


class SandboxAdapter:
    def __init__(
        self,
        *,
        lifecycle: MsbserverLifecycle | None = None,
        policy: SandboxPolicy | None = None,
        server_url: str | None = None,
        api_key_path: str | os.PathLike[str] | None = None,
    ) -> None:
        self.lifecycle = lifecycle or MsbserverLifecycle(server_url=server_url)
        self.policy = policy or SandboxPolicy.default()
        self.server_url = server_url or self.lifecycle.server_url
        self.api_key_path = Path(api_key_path).expanduser() if api_key_path else None

    def execute_sync(
        self,
        command: Sequence[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
        timeout: int | None = None,
        run_id: str = "",
        agent: str = "",
        skill: str = "",
        mode: str = "",
        on_event: EventCallback | None = None,
    ) -> ExecResult:
        return asyncio.run(
            self.execute(
                command,
                env=env,
                cwd=cwd,
                timeout=timeout,
                run_id=run_id,
                agent=agent,
                skill=skill,
                mode=mode,
                on_event=on_event,
            )
        )

    async def execute(
        self,
        command: Sequence[str],
        *,
        env: dict[str, str] | None = None,
        cwd: str | os.PathLike[str] | None = None,
        timeout: int | None = None,
        run_id: str = "",
        agent: str = "",
        skill: str = "",
        mode: str = "",
        on_event: EventCallback | None = None,
    ) -> ExecResult:
        command_list = [str(part) for part in command]
        self._emit("launching", run_id, agent, skill, mode, command_list, on_event)
        if not self.lifecycle.ensure_running(self.api_key_path):
            raise RuntimeError(
                "msbserver is not running and could not be auto-started; "
                "install microsandbox or set MSBSERVER_EXE"
            )

        sandbox_cls = self._sandbox_class(command_list)
        api_key = self._api_key()
        sandbox_name = f"vc-{run_id or 'manual'}".replace("/", "-")[:48]
        self._emit("running", run_id, agent, skill, mode, command_list, on_event)
        sandbox = sandbox_cls(
            server_url=self.server_url,
            namespace="vibecrafted",
            name=sandbox_name,
            api_key=api_key,
        )
        sandbox._session = await _client_session()
        try:
            start_kwargs = self.policy.to_start_kwargs()
            await sandbox.start(**start_kwargs)
            execution = await sandbox.command.run(
                "sh",
                ["-lc", _shell_script(command_list, env=env, cwd=cwd)],
                timeout=timeout,
            )
            stdout = await execution.output()
            stderr = await execution.error()
            exit_code = int(getattr(execution, "exit_code", 1))
            state = "completed" if exit_code == 0 else "failed"
            self._emit(
                state,
                run_id,
                agent,
                skill,
                mode,
                command_list,
                on_event,
                {"exit_code": exit_code},
            )
            return ExecResult(
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                sandbox=sandbox_name,
            )
        finally:
            if getattr(sandbox, "_is_started", False):
                await sandbox.stop()
            session = getattr(sandbox, "_session", None)
            if session is not None:
                await session.close()
                sandbox._session = None

    def _sandbox_class(self, command: Sequence[str]) -> Any:
        _ensure_microsandbox_sdk_path()
        from microsandbox import NodeSandbox, PythonSandbox

        first = Path(command[0]).name if command else ""
        if first in {"node", "npm", "npx", "pnpm", "yarn"}:
            return NodeSandbox
        return PythonSandbox

    def _api_key(self) -> str | None:
        if os.environ.get("MSB_API_KEY"):
            return os.environ["MSB_API_KEY"]
        if self.api_key_path and self.api_key_path.is_file():
            value = self.api_key_path.read_text(encoding="utf-8").strip()
            return value if value.startswith("msb_") else None
        return None

    def _emit(
        self,
        state: str,
        run_id: str,
        agent: str,
        skill: str,
        mode: str,
        command: Sequence[str],
        on_event: EventCallback | None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "state": state,
            "agent": agent,
            "skill": skill,
            "mode": mode,
            "substrate": "microsandbox",
            "network": self.policy.network,
            "command": list(command),
        }
        if extra:
            payload.update(extra)
        event = append_event(
            "spawn-update",
            run_id,
            f"sandbox execution {state}",
            payload,
        )
        if on_event is not None:
            on_event(event)


def _shell_script(
    command: Sequence[str],
    *,
    env: dict[str, str] | None,
    cwd: str | os.PathLike[str] | None,
) -> str:
    parts: list[str] = []
    if cwd:
        parts.append(f"cd {shlex.quote(str(cwd))}")
    exports = []
    for key, value in sorted((env or {}).items()):
        if key.startswith("BASH_FUNC_"):
            continue
        exports.append(f"{key}={shlex.quote(str(value))}")
    prefix = " ".join(exports)
    exec_cmd = " ".join(shlex.quote(str(part)) for part in command)
    parts.append(f"{prefix + ' ' if prefix else ''}exec {exec_cmd}")
    return " && ".join(parts)


def _ensure_microsandbox_sdk_path() -> None:
    configured = os.environ.get("MICROSANDBOX_PYTHON_SDK")
    candidates = []
    if configured:
        candidates.append(Path(configured).expanduser())
    candidates.append(
        Path(__file__).resolve().parents[4]
        / "experimental"
        / "microsandbox"
        / "sdk"
        / "python"
    )
    for candidate in candidates:
        if (candidate / "microsandbox").is_dir():
            candidate_str = str(candidate)
            if candidate_str not in sys.path:
                sys.path.insert(0, candidate_str)
            return


async def _client_session() -> Any:
    import aiohttp

    return aiohttp.ClientSession()
