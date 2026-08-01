from __future__ import annotations

import hashlib
import importlib.util
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from xml.parsers.expat import ExpatError

from .package_resources import deck_path, runtime_path, skills_path
from .vc_frame_delivery import (
    classify_view_path,
    frontier_root,
    list_dangling_frontier_links,
    prefer_repo_vc_frame,
    resolve_clipboard_command,
    resolve_pane_shell,
    tools_current_path,
    vc_frame_user_config_dir,
)

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
    """Verify that `vibecrafted` enters an installed owner, never a checkout."""
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

    findings: list[_Finding] = []
    if "vibecrafted_core.cli" in head and "import main" in head:
        findings.append(
            _Finding("ok", "launcher", f"Python package entrypoint on PATH -> {path}")
        )
    elif head.lstrip().startswith("#!") and "bash" in head.splitlines()[0]:
        try:
            deck = path.resolve(strict=True)
        except OSError:
            deck = path
        installed_deck = (
            deck.name == "vibecrafted"
            and deck.parent.name == "deck"
            and deck.parent.parent.name == "vibecrafted_core"
            and any(part.startswith("vibecrafted-generation-") for part in deck.parts)
        )
        if installed_deck:
            findings.append(
                _Finding(
                    "ok",
                    "launcher",
                    f"immutable runtime command deck on PATH -> {deck}",
                )
            )
        else:
            shim = _uv_tool_shim()
            shim_hint = f" (uv-tool shim lives at {shim})" if shim.exists() else ""
            return [
                _Finding(
                    "fail",
                    "launcher",
                    f"vibecrafted on PATH ({path}) is a checkout/legacy bash deck, "
                    f"not the immutable runtime deck or uv-tool shim{shim_hint}. "
                    "Reinstall so an installed owner wins PATH.",
                )
            ]
    else:
        findings.append(
            _Finding(
                "warn",
                "launcher",
                f"vibecrafted on PATH ({path}) is neither a package entrypoint "
                f"nor the known deck — verify the install channel",
            )
        )

    # Version identity: bare package VERSION (no +gSHA) means an unstamped
    # editable / living-tree checkout. Even when resolve lifts to the staged
    # stamp for --version honesty, surface the PATH shadow so doctor is not
    # "190 ok" while Homebrew editable wins the binary.
    from . import __file__ as package_file
    from . import __version__ as resolved_version
    from .runtime_paths import (
        read_staged_tools_version,
        read_version_file,
        version_is_stamped,
        vibecrafted_tools_home,
    )

    staged = read_staged_tools_version()
    package_dir = Path(package_file).resolve().parent
    package_version = read_version_file(package_dir)
    tools_home = vibecrafted_tools_home().resolve()
    package_outside_tools = tools_home not in package_dir.parents

    if not version_is_stamped(resolved_version):
        staged_hint = (
            f" Staged install stamp is {staged}."
            if version_is_stamped(staged)
            else " Run `make install` to stamp tools/vibecrafted-current."
        )
        findings.append(
            _Finding(
                "fail",
                "version",
                f"vibecrafted --version is unstamped ({resolved_version}) — "
                f"install identity must be X.Y.Z+gSHORTSHA.{staged_hint} "
                f"Common cause: Homebrew/pip editable install of the living "
                f"tree shadows ~/.local/bin (PATH order). Uninstall the "
                f"editable package or put ~/.local/bin first.",
            )
        )
    else:
        findings.append(
            _Finding("ok", "version", f"stamped install identity {resolved_version}")
        )

    if (
        package_outside_tools
        and not version_is_stamped(package_version)
        and version_is_stamped(staged)
    ):
        findings.append(
            _Finding(
                "fail",
                "launcher",
                f"loaded package tree is unstamped ({package_version} at "
                f"{package_dir}) while make-install stamp is {staged}. "
                f"PATH winner {path} is almost certainly a pip/Homebrew "
                f"editable living-tree install. Uninstall it "
                f"(`python3 -m pip uninstall vibecrafted`) or ensure "
                f"~/.local/bin precedes Homebrew on PATH.",
            )
        )
    elif version_is_stamped(staged) and resolved_version != staged:
        findings.append(
            _Finding(
                "warn",
                "version",
                f"resolved version {resolved_version} differs from staged "
                f"tools stamp {staged} — re-run make install or clear an "
                f"editable PATH shadow",
            )
        )

    return findings


def _server_supervision_findings(
    *,
    platform: str | None = None,
    which: Callable[[str], str | None] = shutil.which,
    config_factory: Callable[..., Any] | None = None,
    status_reader: Callable[[Any], Any] | None = None,
) -> list[_Finding]:
    """Fail closed when the macOS control-plane service is not truly supervised."""
    resolved_platform = sys.platform if platform is None else platform
    if resolved_platform != "darwin":
        return [
            _Finding(
                "ok",
                "server-supervisor",
                f"LaunchAgent supervision not applicable on {resolved_platform}",
            )
        ]

    resolved_launcher = which("vibecrafted")
    if not resolved_launcher:
        return [
            _Finding(
                "fail",
                "server-supervisor",
                "cannot verify supervised control plane because `vibecrafted` is "
                "not on PATH — reinstall Vibecrafted",
            )
        ]

    if config_factory is None or status_reader is None:
        from .server_supervisor import default_config, service_status

        config_factory = config_factory or default_config
        status_reader = status_reader or service_status

    try:
        service_launcher = _uv_tool_shim()
        if not service_launcher.is_file():
            service_launcher = Path(resolved_launcher)
        config = config_factory(launcher=service_launcher)
        status = status_reader(config)
    except (
        OSError,
        RuntimeError,
        ValueError,
        subprocess.SubprocessError,
        ExpatError,
    ) as exc:
        return [
            _Finding(
                "fail",
                "server-supervisor",
                "cannot prove the installed control-plane supervisor healthy: "
                f"{exc}. Run `vibecrafted server service install`",
            )
        ]

    supervisor_pid = getattr(status, "supervisor_pid", None)
    required = {
        "installed": bool(getattr(status, "installed", False)),
        "loaded": bool(getattr(status, "loaded", False)),
        "supervisor_live": bool(getattr(status, "supervisor_live", False)),
        "supervisor_verified": bool(getattr(status, "supervisor_verified", False)),
        "supervisor_service_managed": bool(
            getattr(status, "supervisor_service_managed", False)
        ),
        "build_current": bool(getattr(status, "build_current", False)),
        "pair_healthy": bool(getattr(status, "pair_healthy", False)),
        "supervisor_pid": supervisor_pid is not None,
    }
    failed = [name for name, healthy in required.items() if not healthy]
    if failed:
        return [
            _Finding(
                "fail",
                "server-supervisor",
                "control plane is not durably supervised "
                f"(failed: {', '.join(failed)}). Run "
                "`vibecrafted server service install` and re-run doctor",
            )
        ]

    return [
        _Finding(
            "ok",
            "server-supervisor",
            "verified LaunchAgent-managed supervisor and healthy server/guardian "
            f"pair (pid={supervisor_pid}, current build)",
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


def _vc_frame_delivery_findings(
    *,
    home: Path | None = None,
    tools_home: Path | None = None,
    path_env: str | None = None,
) -> list[_Finding]:
    """Config delivery health: view channel, themes, pane-shell, frontier zombies."""
    findings: list[_Finding] = []
    view = vc_frame_user_config_dir(home)
    current = tools_current_path(tools_home)
    store_cfg = current
    checkout = None
    try:
        from .frontier_assets import vc_frame_config_source

        checkout = vc_frame_config_source()
    except FileNotFoundError:
        pass
    use_repo = prefer_repo_vc_frame()
    generated = current / "runtime" / "generated" / "vc-frame"
    materialized_paths = (
        generated / "config.kdl",
        generated / "layouts",
        generated / "themes",
    )
    materialized = all(
        path.is_file() if path.suffix else path.is_dir() for path in materialized_paths
    )
    if use_repo:
        findings.append(
            _Finding(
                "ok",
                "vc-frame:runtime",
                "dev-checkout channel does not require a published config generation",
            )
        )
        view_repair = "`vibecrafted config install --prefer-repo`"
    elif materialized:
        findings.append(
            _Finding(
                "ok",
                "vc-frame:runtime",
                f"pre-materialized config present under {generated}",
            )
        )
        view_repair = "`vibecrafted config install`"
    else:
        findings.append(
            _Finding(
                "fail",
                "vc-frame:runtime",
                f"published runtime has no complete pre-materialized config "
                f"under {generated} — run `vibecrafted update`",
            )
        )
        view_repair = "`vibecrafted update`"

    channels: list[str] = []
    for name in ("config.kdl", "layouts", "themes"):
        path = view / name
        ch = classify_view_path(path, store_current=store_cfg, checkout=checkout)
        channels.append(ch)
        if ch == "DANGLING":
            findings.append(
                _Finding(
                    "fail",
                    "vc-frame:view",
                    f"{path} is a dangling symlink — run {view_repair}",
                )
            )
        elif ch == "STALE-FILE":
            findings.append(
                _Finding(
                    "fail",
                    "vc-frame:view",
                    f"{path} is a regular file shadowing the store view — "
                    f"run {view_repair} (backs up as .stale.* when wiring)",
                )
            )
        elif ch == "missing":
            findings.append(
                _Finding(
                    "warn",
                    "vc-frame:view",
                    f"{path} missing — run {view_repair}",
                )
            )
        elif ch == "foreign":
            findings.append(
                _Finding(
                    "warn",
                    "vc-frame:view",
                    f"{path} is user-managed (foreign) — not store/dev view",
                )
            )
        else:
            findings.append(_Finding("ok", "vc-frame:view", f"{name}: {ch} -> {path}"))

    # themes presence under view or source
    themes_dir = view / "themes"
    if themes_dir.is_dir() or themes_dir.is_symlink():
        try:
            resolved = themes_dir.resolve(strict=True)
            theme_files = list(resolved.glob("*.kdl"))
            if theme_files:
                findings.append(
                    _Finding(
                        "ok",
                        "vc-frame:themes",
                        f"{len(theme_files)} theme file(s) under {themes_dir}",
                    )
                )
            else:
                findings.append(
                    _Finding(
                        "warn",
                        "vc-frame:themes",
                        f"themes dir empty: {themes_dir}",
                    )
                )
        except OSError:
            findings.append(
                _Finding(
                    "fail",
                    "vc-frame:themes",
                    f"themes path does not resolve: {themes_dir}",
                )
            )
    else:
        findings.append(
            _Finding(
                "warn",
                "vc-frame:themes",
                f"themes view missing at {themes_dir}",
            )
        )

    # Host commands: every shipped KDL must match the available shell/clipboard.
    shell = resolve_pane_shell(path_env)
    clipboard = resolve_clipboard_command(path_env)
    layouts = view / "layouts"
    unresolved: list[str] = []
    kdl_files: list[Path] = []
    config_file = view / "config.kdl"
    if config_file.exists():
        kdl_files.append(config_file)
    if layouts.exists():
        try:
            kdl_files.extend(sorted(layouts.resolve().glob("*.kdl")))
        except OSError:
            pass
    for kdl_file in kdl_files:
        try:
            text = kdl_file.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if shell != "zsh" and any(
            token in text
            for token in (
                'command="zsh"',
                'default_shell "zsh"',
                "exec zsh -l",
                "exec /bin/zsh -l",
            )
        ):
            unresolved.append(f"{kdl_file.name}:zsh")
        if clipboard is None and (
            'copy_command "pbcopy"' in text or "pbcopy <" in text
        ):
            unresolved.append(f"{kdl_file.name}:pbcopy")
    if unresolved:
        remediation = (
            "dev checkout is intentionally raw; install the referenced host "
            "commands or unset VIBECRAFTED_PREFER_REPO_VC_FRAME and run "
            "`vibecrafted update`"
            if use_repo
            else "republish host-adapted config via `vibecrafted update`"
        )
        findings.append(
            _Finding(
                "warn",
                "vc-frame:pane-shell",
                f"unresolved host commands for shell={shell!r}, "
                f"clipboard={clipboard or 'internal'}: {', '.join(unresolved)}; "
                f"{remediation}",
            )
        )
    else:
        findings.append(
            _Finding(
                "ok",
                "vc-frame:pane-shell",
                f"host commands ok (shell={shell}, clipboard={clipboard or 'internal'})",
            )
        )

    # frontier zombies
    froot = frontier_root(home)
    zombies = list_dangling_frontier_links(froot)
    if zombies:
        findings.append(
            _Finding(
                "fail",
                "frontier:zombies",
                f"{len(zombies)} dangling link(s) under {froot} — "
                f"re-run install-frontier-config.sh or `vibecrafted update`",
            )
        )
    else:
        findings.append(
            _Finding(
                "ok",
                "frontier:zombies",
                f"no dangling frontier links under {froot}",
            )
        )

    if use_repo:
        findings.append(
            _Finding(
                "ok",
                "vc-frame:channel",
                "VIBECRAFTED_PREFER_REPO_VC_FRAME=1 (dev-checkout preferred)",
            )
        )
    return findings


_TRUTH_PATTERNS = ("config.kdl", "auto-theme.sh", "layouts/*.kdl", "themes/*.kdl")


def _hash_config_tree(root: Path) -> dict[str, str]:
    """sha256 map of the canonical vc-frame config files under one truth root."""
    hashes: dict[str, str] = {}
    if not root.is_dir():
        return hashes
    for pattern in _TRUTH_PATTERNS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            try:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                continue
            hashes[str(path.relative_to(root))] = digest
    return hashes


def _diverged_files(left: dict[str, str], right: dict[str, str]) -> list[str]:
    return sorted(
        name for name in left.keys() | right.keys() if left.get(name) != right.get(name)
    )


def _vc_frame_truth_drift_findings(
    *,
    home: Path | None = None,
    tools_home: Path | None = None,
) -> list[_Finding]:
    """Content drift across the vc-frame config truths.

    The delivery checks prove the FORM of the view (symlink channels, dangling
    links). This proves the CONTENT: the published generation must agree with
    itself (config/ vs runtime/generated/), the dev checkout may run ahead of
    the store but never silently, and no projection link may resolve into a
    parked generation instead of vibecrafted-current.
    """
    findings: list[_Finding] = []
    current = tools_current_path(tools_home)
    store_cfg = current / "config" / "vc-frame"
    generated = current / "runtime" / "generated" / "vc-frame"

    store_map = _hash_config_tree(store_cfg)
    generated_map = _hash_config_tree(generated)
    if store_map and generated_map:
        split = _diverged_files(store_map, generated_map)
        if split:
            findings.append(
                _Finding(
                    "fail",
                    "vc-frame:truth",
                    "published generation disagrees with itself "
                    f"(config/ vs runtime/generated/): {', '.join(split[:6])}"
                    f"{' …' if len(split) > 6 else ''} — run `vibecrafted update`",
                )
            )
        else:
            findings.append(
                _Finding(
                    "ok",
                    "vc-frame:truth",
                    f"store truths agree ({len(store_map)} file(s) hashed)",
                )
            )

    checkout: Path | None = None
    try:
        from .frontier_assets import vc_frame_config_source

        checkout = vc_frame_config_source()
    except FileNotFoundError:
        checkout = None
    if checkout is not None and store_map:
        drift = _diverged_files(_hash_config_tree(checkout), store_map)
        if drift:
            findings.append(
                _Finding(
                    "warn",
                    "vc-frame:truth",
                    f"dev checkout differs from published store on {len(drift)} "
                    f"file(s): {', '.join(drift[:6])}"
                    f"{' …' if len(drift) > 6 else ''} — legal mid-development; "
                    "republish via `vibecrafted update` before trusting "
                    "env-less sessions",
                )
            )
        else:
            findings.append(
                _Finding("ok", "vc-frame:truth", "dev checkout matches published store")
            )

    tools_root = current.parent
    try:
        current_real = current.resolve(strict=True)
    except OSError:
        return findings
    projection_roots = (
        vc_frame_user_config_dir(home),
        frontier_root(home) / "vc-frame",
    )
    stale: list[Path] = []
    for root in projection_roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_symlink():
                continue
            try:
                target = path.resolve(strict=True)
            except OSError:
                continue  # dangling links are the delivery check's finding
            if target.is_relative_to(tools_root) and not target.is_relative_to(
                current_real
            ):
                stale.append(path)
    if stale:
        listed = ", ".join(str(path) for path in stale[:4])
        findings.append(
            _Finding(
                "fail",
                "vc-frame:truth",
                f"{len(stale)} projection link(s) resolve into a parked "
                f"generation instead of vibecrafted-current: {listed}"
                f"{' …' if len(stale) > 4 else ''} — re-run `vibecrafted update`",
            )
        )
    else:
        findings.append(
            _Finding(
                "ok",
                "vc-frame:truth",
                "all projection links resolve inside vibecrafted-current",
            )
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
    findings.extend(_server_supervision_findings())
    findings.extend(_vc_frame_delivery_findings())
    findings.extend(_vc_frame_truth_drift_findings())
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
