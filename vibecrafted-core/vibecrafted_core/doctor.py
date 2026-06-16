from __future__ import annotations

import importlib.util
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .package_resources import deck_path, runtime_path, skills_path

_INSTALLER_MODULE: Any | None = None


@dataclass(frozen=True)
class _Finding:
    """Duck-typed finding compatible with the installer's DoctorFinding."""

    level: str
    component: str
    message: str


def _uv_tool_shim() -> Path:
    data_home = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    return Path(data_home) / "uv" / "tools" / "vibecrafted" / "bin" / "vibecrafted"


def _launcher_shim_findings(
    which: Callable[[str], str | None] = shutil.which,
) -> list[_Finding]:
    """Verify that `vibecrafted` on PATH is the uv-tool shim, not the legacy deck.

    The bash command-deck shadows the uv-tool entry point when installed into
    ~/.local/bin; it calls bare `python3`, which breaks under a non-uv
    interpreter. The uv-tool shim carries the uv python in its shebang and
    imports `vibecrafted_core.cli`. Report the truth so the operator can see
    which one wins PATH.
    """
    resolved = which("vibecrafted")
    if not resolved:
        return [
            _Finding(
                "warn",
                "launcher",
                "vibecrafted not found on PATH — run the installer or "
                "`uv tool install vibecrafted`",
            )
        ]
    path = Path(resolved)
    try:
        head = path.read_text(encoding="utf-8", errors="ignore")[:4096]
    except OSError as exc:
        return [_Finding("warn", "launcher", f"cannot read {path}: {exc}")]

    if "vibecrafted_core.cli" in head and "import main" in head:
        return [_Finding("ok", "launcher", f"uv-tool shim on PATH -> {path}")]

    if head.lstrip().startswith("#!") and "bash" in head.splitlines()[0]:
        shim = _uv_tool_shim()
        shim_hint = f" (uv-tool shim lives at {shim})" if shim.exists() else ""
        return [
            _Finding(
                "fail",
                "launcher",
                f"vibecrafted on PATH ({path}) is the legacy bash command-deck, "
                f"not the uv-tool shim — it calls bare python3 and shadows the "
                f"uv-tool entry point{shim_hint}. Reinstall so the uv-tool shim "
                f"wins PATH.",
            )
        ]

    return [
        _Finding(
            "warn",
            "launcher",
            f"vibecrafted on PATH ({path}) is neither the uv-tool shim nor the "
            f"known deck — verify the install channel",
        )
    ]


def _repo_root_from_source() -> Path | None:
    package_root = Path(__file__).resolve().parents[1]
    candidate = package_root.parent if package_root.name == "vibecrafted-core" else None
    if candidate and (candidate / "scripts" / "vetcoders_install.py").is_file():
        return candidate
    return None


def _installer_module() -> Any:
    global _INSTALLER_MODULE
    if _INSTALLER_MODULE is not None:
        return _INSTALLER_MODULE

    repo_root = _repo_root_from_source()
    if repo_root is not None:
        installer_path = repo_root / "scripts" / "vetcoders_install.py"
        spec = importlib.util.spec_from_file_location(
            "vibecrafted_runtime_vetcoders_install", installer_path
        )
        if spec is None or spec.loader is None:
            raise ModuleNotFoundError(f"Cannot load installer module: {installer_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        previous_path = list(sys.path)
        try:
            sys.path.insert(0, str(repo_root))
            spec.loader.exec_module(module)
        except Exception:
            sys.modules.pop(spec.name, None)
            raise
        finally:
            sys.path[:] = previous_path
        _INSTALLER_MODULE = module
        return module

    import vetcoders_install  # type: ignore[import-not-found]

    _INSTALLER_MODULE = vetcoders_install
    return vetcoders_install


def _packaged_asset_findings() -> list[_Finding]:
    checks = (
        (
            "runtime",
            runtime_path() / "scripts" / "await.sh",
            "packaged runtime scripts present",
        ),
        (
            "skills",
            skills_path() / "vc-justdo" / "SKILL.md",
            "packaged canonical skills present",
        ),
        ("deck", deck_path(), "packaged command deck present"),
    )
    findings: list[_Finding] = []
    for component, path, ok_message in checks:
        if path.is_file():
            findings.append(_Finding("ok", component, ok_message))
        else:
            findings.append(
                _Finding("fail", component, f"missing package asset: {path}")
            )
    return findings


def doctor_run(
    store_path: str | Path | None = None,
    state: Any | None = None,
) -> list[Any]:
    """Run the existing Vibecrafted installer doctor through a package API."""
    try:
        installer = _installer_module()
    except ModuleNotFoundError:
        findings = _packaged_asset_findings()
    else:
        resolved_store = (
            Path(store_path)
            if store_path is not None
            else installer._canonical_store_path(installer.vibecrafted_home())
        )
        resolved_state = (
            state if state is not None else installer.InstallState.load(resolved_store)
        )
        findings = list(installer.run_doctor(resolved_store, resolved_state))
        findings.extend(_packaged_asset_findings())
    findings.extend(_launcher_shim_findings())
    return findings


def doctor_summary(findings: Sequence[Any]) -> dict[str, Any]:
    oks = sum(1 for finding in findings if finding.level == "ok")
    warnings = sum(1 for finding in findings if finding.level == "warn")
    failures = sum(1 for finding in findings if finding.level == "fail")
    return {
        "ok": oks,
        "warnings": warnings,
        "failures": failures,
        "healthy": failures == 0,
        "findings": [
            {
                "level": finding.level,
                "component": finding.component,
                "message": finding.message,
            }
            for finding in findings
        ],
    }
