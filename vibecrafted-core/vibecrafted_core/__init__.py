from __future__ import annotations

from typing import Any

from .control_plane import (
    Event,
    RunStatus,
    await_run,
    control_plane_home,
    event_stream_path,
    lookup_run,
    read_event_tail,
    run_snapshot_dir,
    subscribe_events,
    sync_state,
)
from .events import append_event
from .capabilities import (
    ToolCapability,
    foundation_capabilities,
    probe_tool,
)
from .perception import (
    DEFAULT_MCP_TRANSPORT,
    WatchOutcome,
    ensure_watch,
    loctree_mcp_config_entry,
    mcp_endpoint,
    mcp_servers_config,
    port_for_root,
    watcher_running,
)
from .doctor import doctor_run, doctor_summary
from .git import repo_full, repo_full_summary
from .artifacts import ArtifactValidation, validate_artifacts
from .lifecycle import (
    EventKind,
    RunState,
    is_final_state,
    is_negative_state,
    transition_allowed,
)
from .runtime_paths import (
    read_version_file,
    resolve_env_path,
    vibecrafted_home,
    xdg_config_home,
)
from .supervisor_async import AsyncRunHandle, AsyncSupervisor

__version__ = "3.2.0"

_LAZY_EXPORTS = {
    "WorkflowLaunchSpec": ".workflow",
    "await_launch_truth": ".workflow",
    "build_launch_command": ".workflow",
    "launch_workflow": ".workflow",
    "normalize_launch_spec": ".workflow",
    "retry_run": ".workflow",
    "stop_run": ".workflow",
    "vibecrafted_launcher": ".workflow",
}


def __getattr__(name: str) -> Any:
    """Lazily expose optional workflow helpers without preloading CLI modules."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    if module_name == ".workflow":
        from . import workflow as module
    else:  # pragma: no cover - _LAZY_EXPORTS is the whitelist.
        raise AttributeError(f"module {__name__!r} has no lazy module for {name!r}")

    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "RunStatus",
    "Event",
    "EventKind",
    "ArtifactValidation",
    "ToolCapability",
    "WatchOutcome",
    "DEFAULT_MCP_TRANSPORT",
    "AsyncRunHandle",
    "AsyncSupervisor",
    "RunState",
    "WorkflowLaunchSpec",
    "append_event",
    "await_run",
    "await_launch_truth",
    "build_launch_command",
    "control_plane_home",
    "doctor_run",
    "doctor_summary",
    "ensure_watch",
    "event_stream_path",
    "foundation_capabilities",
    "loctree_mcp_config_entry",
    "mcp_endpoint",
    "mcp_servers_config",
    "port_for_root",
    "probe_tool",
    "watcher_running",
    "launch_workflow",
    "lookup_run",
    "normalize_launch_spec",
    "retry_run",
    "read_event_tail",
    "read_version_file",
    "repo_full",
    "repo_full_summary",
    "resolve_env_path",
    "run_snapshot_dir",
    "stop_run",
    "subscribe_events",
    "sync_state",
    "is_final_state",
    "is_negative_state",
    "transition_allowed",
    "validate_artifacts",
    "vibecrafted_home",
    "vibecrafted_launcher",
    "xdg_config_home",
]
