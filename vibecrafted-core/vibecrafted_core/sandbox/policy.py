"""Sandbox resource/network/mount policy: defaults, YAML overlay, and start kwargs."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecrafted_core.runtime_paths import vibecrafted_home


@dataclass(frozen=True)
class SandboxPolicy:
    """Resource, network, and mount constraints applied to a sandboxed execution."""

    cpu: float = 1.0
    memory_mb: int = 512
    network: str = "deny"
    filesystem_root_readonly: bool = True
    tmp_writable: bool = True
    allow_hosts: tuple[str, ...] = ()
    mounts: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def default(cls, root: str | os.PathLike[str] | None = None) -> SandboxPolicy:
        """Build the baseline policy: `/tmp` writable, and `root` (if given)
        read-only mounted at `/workspace`."""

        root_mount = f"{Path(root).resolve()}:/workspace:ro" if root else ""
        mounts = (root_mount, "/tmp:/tmp:rw") if root_mount else ("/tmp:/tmp:rw",)
        return cls(mounts=mounts)

    @classmethod
    def load(
        cls,
        path: str | os.PathLike[str] | None = None,
        *,
        root: str | os.PathLike[str] | None = None,
    ) -> SandboxPolicy:
        """Build the default policy for `root`, then overlay it with values
        parsed from a simple YAML file at `path` (or `default_policy_path()`)
        when that file exists."""

        policy = cls.default(root)
        candidate = Path(path).expanduser() if path else default_policy_path()
        if not candidate.is_file():
            return policy
        return policy.overlay(_parse_simple_yaml(candidate))

    def overlay(self, data: dict[str, Any]) -> SandboxPolicy:
        """Return a new policy with fields replaced by matching keys in `data`,
        coercing each field to its declared type; unknown keys are ignored."""

        values: dict[str, Any] = {
            "cpu": self.cpu,
            "memory_mb": self.memory_mb,
            "network": self.network,
            "filesystem_root_readonly": self.filesystem_root_readonly,
            "tmp_writable": self.tmp_writable,
            "allow_hosts": self.allow_hosts,
            "mounts": self.mounts,
        }
        for key in values:
            if key not in data:
                continue
            if key == "cpu":
                values[key] = float(data[key])
            elif key == "memory_mb":
                values[key] = int(data[key])
            elif key in {"filesystem_root_readonly", "tmp_writable"}:
                values[key] = _as_bool(data[key])
            elif key in {"allow_hosts", "mounts"}:
                values[key] = tuple(str(item) for item in _as_list(data[key]))
            else:
                values[key] = str(data[key]).lower()
        return SandboxPolicy(**values)

    def to_start_kwargs(self) -> dict[str, int | float]:
        """Project cpu/memory fields into the kwargs microsandbox's `start()`
        expects; network/filesystem/mount fields are not passed here."""

        return {"memory": self.memory_mb, "cpus": self.cpu}


def default_policy_path() -> Path:
    """Default location of the operator-owned sandbox policy YAML file."""

    return vibecrafted_home() / "sandbox" / "policy.yaml"


def _as_bool(value: Any) -> bool:
    """Coerce a YAML scalar to bool: real bools pass through; strings match
    against a case-insensitive truthy set (1/true/yes/on)."""

    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: Any) -> list[Any]:
    """Normalize a YAML value to a list: pass lists through, tuple-to-list,
    empty/None to `[]`, and wrap any other scalar as a single-item list."""

    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in {"", None}:
        return []
    return [value]


def _parse_scalar(raw: str) -> Any:
    """Parse one YAML-flow scalar: bracketed inline lists, booleans, ints,
    floats, falling back to a quote-stripped string."""

    value = raw.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [item.strip().strip("'\"") for item in inner.split(",")]
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value.strip("'\"")


def _parse_simple_yaml(path: Path) -> dict[str, Any]:
    """Parse a restricted YAML subset (flat `key: value` pairs plus `key:`
    followed by `- item` block-list lines; `#` starts a comment); not a
    general-purpose YAML parser."""

    data: dict[str, Any] = {}
    current_list: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].rstrip()
        if not line.strip():
            continue
        stripped = line.strip()
        if stripped.startswith("- ") and current_list:
            data.setdefault(current_list, []).append(stripped[2:].strip().strip("'\""))
            continue
        current_list = None
        if ":" not in stripped:
            continue
        key, raw_value = stripped.split(":", 1)
        key = key.strip().replace("-", "_")
        raw_value = raw_value.strip()
        if raw_value == "":
            data[key] = []
            current_list = key
        else:
            data[key] = _parse_scalar(raw_value)
    return data
