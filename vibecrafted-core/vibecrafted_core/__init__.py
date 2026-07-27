from __future__ import annotations

import importlib.metadata
from pathlib import Path
from typing import Any

from .artifacts import ArtifactValidation, validate_artifacts
from .capabilities import (
    ToolCapability,
    foundation_capabilities,
    probe_tool,
)
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
from .doctor import doctor_run, doctor_summary
from .events import append_event
from .git import repo_full, repo_full_summary
from .lifecycle import (
    EventKind,
    RunState,
    is_final_state,
    is_negative_state,
    transition_allowed,
)
from .perception import (
    DEFAULT_MCP_TRANSPORT,
    DEFAULT_WATCH_MODE,
    WatchOutcome,
    ensure_watch,
    loctree_mcp_config_entry,
    mcp_endpoint,
    mcp_servers_config,
    port_for_root,
    watcher_running,
)
from .runtime_paths import (
    read_version_file,
    resolve_env_path,
    vibecrafted_home,
    xdg_config_home,
)
from .supervisor_async import AsyncRunHandle, AsyncSupervisor


def _resolve_installed_version() -> str:
    packaged_version = read_version_file(Path(__file__).resolve().parent)
    if packaged_version != "unknown":
        return packaged_version
    try:
        return importlib.metadata.version("vibecrafted")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


__version__ = _resolve_installed_version()

_LAZY_EXPORTS = {
    "DELIVERY_EVENT_KINDS": ".events",
    "DeliveryAxes": ".control_plane",
    "DeliveryEventKind": ".events",
    "DeliveryStore": ".delivery",
    "DeliveryStoreError": ".delivery",
    "ProviderCapability": ".continuity",
    "SettlementLedgerAppendResult": ".settlement_ledger",
    "SettlementLedgerCollision": ".settlement_ledger",
    "SettlementLedgerCorrupt": ".settlement_ledger",
    "SettlementLedgerError": ".settlement_ledger",
    "SettlementLedgerOrderError": ".settlement_ledger",
    "append_delivery_event": ".events",
    "capability_registry": ".continuity",
    "probe_provider": ".continuity",
    "read_delivery_axes": ".control_plane",
    "read_settlement_ledger": ".settlement_ledger",
    "settlement_ledger_path": ".settlement_ledger",
    "WorkflowLaunchSpec": ".workflow",
    "await_launch_truth": ".workflow",
    "build_launch_command": ".workflow",
    "launch_workflow": ".workflow",
    "native_resume_run": ".workflow",
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

    module: Any
    if module_name == ".workflow":
        from . import workflow

        module = workflow
    elif module_name == ".continuity":
        from . import continuity

        module = continuity
    elif module_name == ".delivery":
        from . import delivery

        module = delivery
    elif module_name == ".events":
        from . import events

        module = events
    elif module_name == ".control_plane":
        from . import control_plane

        module = control_plane
    elif module_name == ".settlement_ledger":
        from . import settlement_ledger

        module = settlement_ledger
    else:  # pragma: no cover - _LAZY_EXPORTS is the whitelist.
        raise AttributeError(f"module {__name__!r} has no lazy module for {name!r}")

    value = getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "DEFAULT_MCP_TRANSPORT",
    "DEFAULT_WATCH_MODE",
    "DELIVERY_EVENT_KINDS",
    "ArtifactValidation",
    "AsyncRunHandle",
    "AsyncSupervisor",
    "DeliveryAxes",
    "DeliveryEventKind",
    "DeliveryStore",
    "DeliveryStoreError",
    "Event",
    "EventKind",
    "ProviderCapability",
    "RunState",
    "RunStatus",
    "SettlementLedgerAppendResult",
    "SettlementLedgerCollision",
    "SettlementLedgerCorrupt",
    "SettlementLedgerError",
    "SettlementLedgerOrderError",
    "ToolCapability",
    "WatchOutcome",
    "WorkflowLaunchSpec",
    "append_delivery_event",
    "append_event",
    "await_launch_truth",
    "await_run",
    "build_launch_command",
    "capability_registry",
    "control_plane_home",
    "doctor_run",
    "doctor_summary",
    "ensure_watch",
    "event_stream_path",
    "foundation_capabilities",
    "is_final_state",
    "is_negative_state",
    "launch_workflow",
    "loctree_mcp_config_entry",
    "lookup_run",
    "mcp_endpoint",
    "mcp_servers_config",
    "native_resume_run",
    "normalize_launch_spec",
    "port_for_root",
    "probe_provider",
    "probe_tool",
    "read_delivery_axes",
    "read_event_tail",
    "read_settlement_ledger",
    "read_version_file",
    "repo_full",
    "repo_full_summary",
    "resolve_env_path",
    "retry_run",
    "run_snapshot_dir",
    "settlement_ledger_path",
    "stop_run",
    "subscribe_events",
    "sync_state",
    "transition_allowed",
    "validate_artifacts",
    "vibecrafted_home",
    "vibecrafted_launcher",
    "watcher_running",
    "xdg_config_home",
]
