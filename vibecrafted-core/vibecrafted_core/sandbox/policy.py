from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from vibecrafted_core.runtime_paths import vibecrafted_home


@dataclass(frozen=True)
class SandboxPolicy:
    cpu: float = 1.0
    memory_mb: int = 512
    network: str = "deny"
    filesystem_root_readonly: bool = True
    tmp_writable: bool = True
    allow_hosts: tuple[str, ...] = ()
    mounts: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def default(cls, root: str | os.PathLike[str] | None = None) -> "SandboxPolicy":
        root_mount = f"{Path(root).resolve()}:/workspace:ro" if root else ""
        mounts = (root_mount, "/tmp:/tmp:rw") if root_mount else ("/tmp:/tmp:rw",)
        return cls(mounts=mounts)

    @classmethod
    def load(
        cls,
        path: str | os.PathLike[str] | None = None,
        *,
        root: str | os.PathLike[str] | None = None,
    ) -> "SandboxPolicy":
        policy = cls.default(root)
        candidate = Path(path).expanduser() if path else default_policy_path()
        if not candidate.is_file():
            return policy
        return policy.overlay(_parse_simple_yaml(candidate))

    def overlay(self, data: dict[str, Any]) -> "SandboxPolicy":
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
        return {"memory": self.memory_mb, "cpus": self.cpu}


def default_policy_path() -> Path:
    return vibecrafted_home() / "sandbox" / "policy.yaml"


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if value in {"", None}:
        return []
    return [value]


def _parse_scalar(raw: str) -> Any:
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
