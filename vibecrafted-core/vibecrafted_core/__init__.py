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
from .workflow import (
    WorkflowLaunchSpec,
    build_launch_command,
    launch_workflow,
    normalize_launch_spec,
    vibecrafted_launcher,
)
from .supervisor_async import AsyncRunHandle, AsyncSupervisor

__version__ = "0.1.0"

_LAZY_EXPORTS = {
    "PROFILE_SPECS": ".iterm2_profiles",
    "ProfileSpec": ".iterm2_profiles",
    "block_end": ".iterm2_osc",
    "block_start": ".iterm2_osc",
    "build_profiles_document": ".iterm2_profiles",
    "custom_button": ".iterm2_osc",
    "cursor_shape": ".iterm2_osc",
    "default_install_dir": ".iterm2_profiles",
    "ftcs_command_executed": ".iterm2_osc",
    "ftcs_command_finished": ".iterm2_osc",
    "ftcs_command_start": ".iterm2_osc",
    "ftcs_prompt": ".iterm2_osc",
    "hex_to_iterm2": ".iterm2_profiles",
    "highlight_cursor_line": ".iterm2_osc",
    "hyperlink": ".iterm2_osc",
    "install_profiles": ".iterm2_profiles",
    "invalidate_buttons": ".iterm2_osc",
    "iterm2_plugin": ".iterm2_plugin",
    "post_notification": ".iterm2_osc",
    "progress": ".iterm2_osc",
    "remote_host": ".iterm2_osc",
    "request_attention": ".iterm2_osc",
    "serialize": ".iterm2_profiles",
    "set_badge": ".iterm2_osc",
    "set_colors": ".iterm2_osc",
    "set_current_dir": ".iterm2_osc",
    "set_mark": ".iterm2_osc",
    "set_profile": ".iterm2_osc",
    "set_user_var": ".iterm2_osc",
    "stable_guid": ".iterm2_profiles",
    "steal_focus": ".iterm2_osc",
    "uninstall_profiles": ".iterm2_profiles",
    "update_block": ".iterm2_osc",
}


def __getattr__(name: str) -> Any:
    """Lazily expose iTerm helpers without preloading CLI modules."""
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    if module_name == ".iterm2_profiles":
        from . import iterm2_profiles as module
    elif module_name == ".iterm2_osc":
        from . import iterm2_osc as module
    elif module_name == ".iterm2_plugin":
        from . import iterm2_plugin as module
    else:  # pragma: no cover - _LAZY_EXPORTS is the whitelist.
        raise AttributeError(f"module {__name__!r} has no lazy module for {name!r}")

    value = module if name == "iterm2_plugin" else getattr(module, name)
    globals()[name] = value
    return value


__all__ = [
    "PROFILE_SPECS",
    "ProfileSpec",
    "RunStatus",
    "Event",
    "EventKind",
    "ArtifactValidation",
    "AsyncRunHandle",
    "AsyncSupervisor",
    "RunState",
    "WorkflowLaunchSpec",
    "append_event",
    "await_run",
    "block_end",
    "block_start",
    "build_launch_command",
    "build_profiles_document",
    "control_plane_home",
    "custom_button",
    "cursor_shape",
    "default_install_dir",
    "doctor_run",
    "doctor_summary",
    "event_stream_path",
    "ftcs_command_executed",
    "ftcs_command_finished",
    "ftcs_command_start",
    "ftcs_prompt",
    "hex_to_iterm2",
    "highlight_cursor_line",
    "hyperlink",
    "install_profiles",
    "invalidate_buttons",
    "iterm2_plugin",
    "launch_workflow",
    "lookup_run",
    "normalize_launch_spec",
    "post_notification",
    "progress",
    "read_event_tail",
    "read_version_file",
    "remote_host",
    "repo_full",
    "repo_full_summary",
    "request_attention",
    "resolve_env_path",
    "run_snapshot_dir",
    "serialize",
    "set_badge",
    "set_colors",
    "set_current_dir",
    "set_mark",
    "set_profile",
    "set_user_var",
    "stable_guid",
    "steal_focus",
    "subscribe_events",
    "sync_state",
    "is_final_state",
    "is_negative_state",
    "transition_allowed",
    "uninstall_profiles",
    "update_block",
    "validate_artifacts",
    "vibecrafted_home",
    "vibecrafted_launcher",
    "xdg_config_home",
]
