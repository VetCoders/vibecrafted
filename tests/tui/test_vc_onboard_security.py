from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "vibecrafted-vm" / "wizard" / "vc-onboard.py"


def _load_onboard():
    class _DummyConsole:
        def print(self, *_args, **_kwargs) -> None:
            pass

        def clear(self) -> None:
            pass

    class _DummyRenderable:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        @classmethod
        def fit(cls, *_args, **_kwargs):
            return cls()

    questionary = types.ModuleType("questionary")
    questionary.Choice = _DummyRenderable
    rich = types.ModuleType("rich")
    rich_console = types.ModuleType("rich.console")
    rich_panel = types.ModuleType("rich.panel")
    rich_table = types.ModuleType("rich.table")
    rich_console.Console = _DummyConsole
    rich_panel.Panel = _DummyRenderable
    rich_table.Table = _DummyRenderable
    stubs = {
        "questionary": questionary,
        "rich": rich,
        "rich.console": rich_console,
        "rich.panel": rich_panel,
        "rich.table": rich_table,
    }
    previous = {name: sys.modules.get(name) for name in stubs}
    sys.modules.update(stubs)
    try:
        spec = importlib.util.spec_from_file_location(
            "vc_onboard_security_test", MODULE_PATH
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        for name, original in previous.items():
            if original is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = original


def test_generated_env_never_persists_tailscale_authkey(tmp_path: Path) -> None:
    onboard = _load_onboard()
    state = onboard.WizardState(tailscale_enabled=True)
    target = tmp_path / ".env"

    onboard.render_env_file(state, target)

    rendered = target.read_text(encoding="utf-8")
    assert "TAILSCALE_AUTHKEY=" not in rendered
    assert "inject it in the process environment" in rendered


def test_enabled_tailscale_uses_runtime_environment_reference(tmp_path: Path) -> None:
    onboard = _load_onboard()
    state = onboard.WizardState(tailscale_enabled=True)
    target = tmp_path / "docker-compose.yml"

    onboard.render_compose_file(state, target)

    rendered = target.read_text(encoding="utf-8")
    assert "TAILSCALE_AUTHKEY=${TAILSCALE_AUTHKEY:-}" in rendered
    assert "tailscale-state:/var/lib/tailscale" in rendered


def test_launch_fails_closed_when_enabled_key_is_not_in_environment(
    monkeypatch,
) -> None:
    onboard = _load_onboard()
    monkeypatch.delenv("TAILSCALE_AUTHKEY", raising=False)

    assert onboard.build_and_run(onboard.WizardState(tailscale_enabled=True)) == 2
