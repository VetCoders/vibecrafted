"""Stage package vc-frame config into the tools store and wire ~/.config/vc-frame.

Delivery contract (plan vcframe-config-delivery):
- Source: ``vc_frame_config_source()`` (wheel package data or checkout).
- Stage: copy into ``tools/vibecrafted-<version>/config/vc-frame/``.
- Flip: atomic ``vibecrafted-current`` symlink.
- View: ``$XDG_CONFIG_HOME/vc-frame/{config.kdl,layouts,themes}`` → store-current
  (or checkout when ``VIBECRAFTED_PREFER_REPO_VC_FRAME=1``).
- Stage-time pane-shell: rewrite ``command="zsh"`` only when zsh is missing.
"""

from __future__ import annotations

import os
import re
import shutil
import stat
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .frontier_assets import vc_frame_config_source
from .runtime_paths import (
    read_version_file,
    vibecrafted_tools_home,
    xdg_config_home,
)

_PANE_ZSH_RE = re.compile(r'command="zsh"')
_FENCE_BEGIN = "# >>> vibecrafted >>>"
_FENCE_END = "# <<< vibecrafted <<<"


@dataclass
class WireAction:
    kind: str  # link | backup | skip | remove | stage | flip | note
    path: str
    detail: str = ""


@dataclass
class DeliveryPlan:
    source: Path
    version_dir: Path
    current_link: Path
    view_root: Path
    channel: str  # store-current | dev-checkout
    dry_run: bool = False
    actions: list[WireAction] = field(default_factory=list)
    pane_shell: str = "zsh"

    def render(self) -> str:
        lines = [
            f"source: {self.source}",
            f"version_dir: {self.version_dir}",
            f"current_link: {self.current_link}",
            f"view_root: {self.view_root}",
            f"channel: {self.channel}",
            f"pane_shell: {self.pane_shell}",
            f"dry_run: {self.dry_run}",
            "actions:",
        ]
        for act in self.actions:
            lines.append(
                f"  - {act.kind}: {act.path}"
                + (f" ({act.detail})" if act.detail else "")
            )
        return "\n".join(lines) + "\n"


def prefer_repo_vc_frame(env: dict[str, str] | None = None) -> bool:
    source = env if env is not None else os.environ
    raw = str(source.get("VIBECRAFTED_PREFER_REPO_VC_FRAME", "") or "").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def vc_frame_user_config_dir(home: Path | None = None) -> Path:
    """Directory bare vc-frame reads (respects XDG_CONFIG_HOME)."""
    if home is not None:
        # Sandbox: treat HOME's .config unless XDG is set in env
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg).expanduser() / "vc-frame"
        return home / ".config" / "vc-frame"
    return xdg_config_home() / "vc-frame"


def tools_current_path(tools_home: Path | None = None) -> Path:
    base = tools_home if tools_home is not None else vibecrafted_tools_home()
    return base / "vibecrafted-current"


def tools_version_dir(
    version: str | None = None, tools_home: Path | None = None
) -> Path:
    base = tools_home if tools_home is not None else vibecrafted_tools_home()
    ver = version or _default_version_token()
    safe = ver.replace("/", "-").replace(" ", "-")
    return base / f"vibecrafted-{safe}"


def _default_version_token() -> str:
    # Prefer package VERSION when available
    try:
        from .package_resources import resource_path

        vpath = resource_path("VERSION")
        if vpath.is_file():
            text = vpath.read_text(encoding="utf-8").strip()
            if text:
                return text
    except FileNotFoundError:
        pass
    # Checkout VERSION
    here = Path(__file__).resolve()
    for parent in here.parents:
        vf = parent / "VERSION"
        if vf.is_file():
            text = read_version_file(parent)
            if text and text != "unknown":
                return text
    return datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")


def resolve_pane_shell(path_env: str | None = None) -> str:
    """First available: zsh → $SHELL basename → bash."""
    path = path_env if path_env is not None else os.environ.get("PATH", "")
    if shutil.which("zsh", path=path):
        return "zsh"
    shell = os.environ.get("SHELL", "")
    if shell:
        base = Path(shell).name
        if base and shutil.which(base, path=path):
            return base
    if shutil.which("bash", path=path):
        return "bash"
    return "sh"


def substitute_pane_shell(kdl_text: str, shell: str) -> str:
    """Replace only command=\"zsh\" with command=\"<shell>\"."""
    if shell == "zsh":
        return kdl_text
    return _PANE_ZSH_RE.sub(f'command="{shell}"', kdl_text)


def classify_view_path(
    path: Path,
    *,
    store_current: Path,
    checkout: Path | None,
) -> str:
    """Classify a view entry: store-current | dev-checkout | foreign | STALE-FILE | DANGLING."""
    if path.is_symlink():
        try:
            target = path.resolve(strict=True)
        except OSError:
            return "DANGLING"
        store_res = store_current.resolve() if store_current.exists() else store_current
        try:
            target.relative_to(store_res)
            return "store-current"
        except ValueError:
            pass
        if checkout is not None:
            check_res = checkout.resolve() if checkout.exists() else checkout
            try:
                target.relative_to(check_res)
                return "dev-checkout"
            except ValueError:
                pass
        return "foreign"
    if path.is_file() or path.is_dir():
        return "STALE-FILE"
    if path.exists():
        return "foreign"
    return "missing"


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _copy_tree_with_shell(
    source: Path,
    dest: Path,
    pane_shell: str,
    *,
    dry_run: bool,
    actions: list[WireAction],
) -> None:
    actions.append(WireAction("stage", str(dest), f"from {source}"))
    if dry_run:
        return
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)
    for root, dirs, files in os.walk(source):
        rel = Path(root).relative_to(source)
        out_dir = dest / rel
        out_dir.mkdir(parents=True, exist_ok=True)
        for name in files:
            src_f = Path(root) / name
            dst_f = out_dir / name
            if name.endswith(".kdl") and pane_shell != "zsh":
                text = src_f.read_text(encoding="utf-8")
                dst_f.write_text(
                    substitute_pane_shell(text, pane_shell), encoding="utf-8"
                )
            else:
                shutil.copy2(src_f, dst_f)
            # preserve exec bit for auto-theme.sh
            if name.endswith(".sh"):
                mode = dst_f.stat().st_mode
                dst_f.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _atomic_symlink(
    target: Path, link: Path, *, dry_run: bool, actions: list[WireAction]
) -> None:
    actions.append(WireAction("flip", str(link), f"-> {target}"))
    if dry_run:
        return
    link.parent.mkdir(parents=True, exist_ok=True)
    tmp = link.parent / f".{link.name}.tmp.{os.getpid()}"
    if tmp.exists() or tmp.is_symlink():
        tmp.unlink()
    tmp.symlink_to(target)
    os.replace(tmp, link)


def _wire_one(
    view_path: Path,
    target: Path,
    *,
    force: bool,
    dry_run: bool,
    actions: list[WireAction],
    store_current: Path,
    checkout: Path | None,
) -> None:
    channel = (
        classify_view_path(view_path, store_current=store_current, checkout=checkout)
        if view_path.exists() or view_path.is_symlink()
        else "missing"
    )
    if channel in {"store-current", "dev-checkout"} and not force:
        # Healthy: leave alone if already points at the intended target
        try:
            if view_path.is_symlink() and view_path.resolve() == target.resolve():
                actions.append(WireAction("skip", str(view_path), channel))
                return
        except OSError:
            pass
        # Healthy other store/dev target — still skip unless force
        if channel in {"store-current", "dev-checkout"} and not force:
            try:
                current = view_path.resolve()
                # If it already resolves under store or checkout, skip
                for base in (store_current, checkout):
                    if base is None:
                        continue
                    try:
                        current.relative_to(base.resolve() if base.exists() else base)
                        actions.append(WireAction("skip", str(view_path), channel))
                        return
                    except ValueError:
                        continue
            except OSError:
                pass

    if view_path.is_symlink() and channel == "DANGLING":
        actions.append(WireAction("remove", str(view_path), "dangling"))
        if not dry_run:
            view_path.unlink(missing_ok=True)
    elif channel == "STALE-FILE" or (view_path.exists() and not view_path.is_symlink()):
        backup = Path(f"{view_path}.stale.{_timestamp()}")
        actions.append(WireAction("backup", str(view_path), f"-> {backup.name}"))
        if not dry_run:
            view_path.rename(backup)
    elif view_path.is_symlink() and force:
        actions.append(WireAction("remove", str(view_path), "force rewire"))
        if not dry_run:
            view_path.unlink()

    actions.append(WireAction("link", str(view_path), f"-> {target}"))
    if dry_run:
        return
    view_path.parent.mkdir(parents=True, exist_ok=True)
    if view_path.exists() or view_path.is_symlink():
        if view_path.is_dir() and not view_path.is_symlink():
            shutil.rmtree(view_path)
        else:
            view_path.unlink(missing_ok=True)
    view_path.symlink_to(target)


def plan_delivery(
    *,
    home: Path | None = None,
    tools_home: Path | None = None,
    version: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    prefer_repo: bool | None = None,
    path_env: str | None = None,
) -> DeliveryPlan:
    source = vc_frame_config_source()
    tools = tools_home if tools_home is not None else vibecrafted_tools_home()
    if home is not None:
        # Isolate tools under sandbox when tools_home not overridden
        if tools_home is None:
            tools = home / ".local" / "share" / "vibecrafted" / "tools"
    version_dir = tools_version_dir(version, tools)
    current = tools / "vibecrafted-current"
    view_root = vc_frame_user_config_dir(home)
    use_repo = prefer_repo if prefer_repo is not None else prefer_repo_vc_frame()
    channel = "dev-checkout" if use_repo else "store-current"
    pane_shell = resolve_pane_shell(path_env)
    plan = DeliveryPlan(
        source=source,
        version_dir=version_dir,
        current_link=current,
        view_root=view_root,
        channel=channel,
        dry_run=dry_run,
        pane_shell=pane_shell,
    )

    staged_cfg = version_dir / "config" / "vc-frame"
    if not use_repo:
        _copy_tree_with_shell(
            source, staged_cfg, pane_shell, dry_run=dry_run, actions=plan.actions
        )
        _atomic_symlink(version_dir, current, dry_run=dry_run, actions=plan.actions)
        base = current / "config" / "vc-frame"
    else:
        plan.actions.append(
            WireAction("note", str(source), "dev-checkout: skip stage copy")
        )
        base = source

    checkout = source if use_repo else None
    store_anchor = current / "config" / "vc-frame"
    for name in ("config.kdl", "layouts", "themes"):
        _wire_one(
            view_root / name,
            base / name,
            force=force,
            dry_run=dry_run,
            actions=plan.actions,
            store_current=store_anchor if not use_repo else current,
            checkout=checkout,
        )
    # auto-theme.sh optional at view root for operators who expect it nearby
    if (base / "auto-theme.sh").exists() or dry_run:
        _wire_one(
            view_root / "auto-theme.sh",
            base / "auto-theme.sh",
            force=force,
            dry_run=dry_run,
            actions=plan.actions,
            store_current=store_anchor if not use_repo else current,
            checkout=checkout,
        )
    return plan


def stage_vc_frame_config(
    *,
    home: Path | None = None,
    tools_home: Path | None = None,
    version: str | None = None,
    dry_run: bool = False,
    force: bool = False,
    prefer_repo: bool | None = None,
    path_env: str | None = None,
) -> DeliveryPlan:
    """Plan then apply (unless dry_run). Returns the plan with actions taken."""
    plan = plan_delivery(
        home=home,
        tools_home=tools_home,
        version=version,
        dry_run=dry_run,
        force=force,
        prefer_repo=prefer_repo,
        path_env=path_env,
    )
    return plan


# ---------------------------------------------------------------------------
# Host zshrc onboarding (W1-B)
# ---------------------------------------------------------------------------

_ZSHRC_TEMPLATE = """\
# vibecrafted host zshrc template — minimal, guarded optionals
# Installed by vibecrafted ensure_zshrc / make install

export PATH="$HOME/.local/bin:$HOME/.vibecrafted/bin:$HOME/.cargo/bin:$PATH"
export VETCODERS_CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/vetcoders"
if [ -f "$VETCODERS_CONFIG_DIR/vc-skills.sh" ]; then
  # shellcheck source=/dev/null
  source "$VETCODERS_CONFIG_DIR/vc-skills.sh"
fi

# Optional tooling (no hard failure if absent)
command -v starship >/dev/null 2>&1 && eval "$(starship init zsh)"
command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init zsh)"
command -v mise >/dev/null 2>&1 && eval "$(mise activate zsh)"
"""

_FENCED_BLOCK = f"""\
{_FENCE_BEGIN}
export PATH="$HOME/.local/bin:$HOME/.vibecrafted/bin:$HOME/.cargo/bin:$PATH"
export VETCODERS_CONFIG_DIR="${{XDG_CONFIG_HOME:-$HOME/.config}}/vetcoders"
if [ -f "$VETCODERS_CONFIG_DIR/vc-skills.sh" ]; then
  # shellcheck source=/dev/null
  source "$VETCODERS_CONFIG_DIR/vc-skills.sh"
fi
{_FENCE_END}
"""


def zshrc_template_text() -> str:
    """Return the host zshrc template (also loadable from package runtime)."""
    try:
        from .package_resources import resource_path

        path = resource_path("runtime", "templates", "zshrc-host.template")
        if path.is_file():
            return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    # Checkout fallback
    here = Path(__file__).resolve().parent
    candidate = here / "runtime" / "templates" / "zshrc-host.template"
    if candidate.is_file():
        return candidate.read_text(encoding="utf-8")
    return _ZSHRC_TEMPLATE


def ensure_zshrc(home: Path | None = None, *, dry_run: bool = False) -> dict[str, str]:
    """Idempotent host zshrc ensure. Never overwrites operator content outside fence."""
    root = home if home is not None else Path.home()
    zshrc = root / ".zshrc"
    result = {"path": str(zshrc), "action": "noop"}
    if not zshrc.exists():
        result["action"] = "create"
        if not dry_run:
            zshrc.write_text(zshrc_template_text(), encoding="utf-8")
        return result
    text = zshrc.read_text(encoding="utf-8")
    if _FENCE_BEGIN in text and _FENCE_END in text:
        result["action"] = "already_present"
        return result
    result["action"] = "append_fence"
    if not dry_run:
        suffix = "" if text.endswith("\n") else "\n"
        zshrc.write_text(text + suffix + "\n" + _FENCED_BLOCK, encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Frontier zombies (W2-B helpers usable from doctor)
# ---------------------------------------------------------------------------


def frontier_root(home: Path | None = None) -> Path:
    if home is not None:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg).expanduser() / "vetcoders" / "frontier"
        return home / ".config" / "vetcoders" / "frontier"
    return xdg_config_home() / "vetcoders" / "frontier"


def list_dangling_frontier_links(root: Path | None = None) -> list[Path]:
    base = root if root is not None else frontier_root()
    dangling: list[Path] = []
    if not base.exists():
        return dangling
    for path in base.rglob("*"):
        if path.is_symlink():
            try:
                path.resolve(strict=True)
            except OSError:
                dangling.append(path)
    return dangling


def remove_dangling_frontier_links(
    root: Path | None = None, *, dry_run: bool = False
) -> list[Path]:
    removed: list[Path] = []
    for path in list_dangling_frontier_links(root):
        removed.append(path)
        if not dry_run:
            path.unlink(missing_ok=True)
    return removed
