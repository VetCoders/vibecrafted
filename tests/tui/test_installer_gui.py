from __future__ import annotations

from pathlib import Path

from scripts import installer_gui


def test_build_install_command_respects_shell_toggle(tmp_path: Path) -> None:
    installer = tmp_path / "scripts" / "vetcoders_install.py"
    installer.parent.mkdir(parents=True)
    installer.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    with_shell = installer_gui.build_install_command(str(tmp_path), with_shell=True)
    without_shell = installer_gui.build_install_command(str(tmp_path), with_shell=False)

    assert with_shell[-1] == "--with-shell"
    assert "--with-shell" not in without_shell
    assert with_shell[:5] == without_shell[:5]


def test_build_install_steps_include_foundations_before_installer(
    tmp_path: Path,
) -> None:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "vetcoders_install.py").write_text(
        "#!/usr/bin/env python3\n", encoding="utf-8"
    )
    (scripts_dir / "install-foundations.sh").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )

    steps = installer_gui.build_install_steps(str(tmp_path), with_shell=True)

    assert [step.label for step in steps] == [
        "Bootstrap foundations",
        "Install Vibecrafted",
    ]
    assert steps[0].command == ["bash", str(scripts_dir / "install-foundations.sh")]
    assert steps[1].command[-1] == "--with-shell"


def test_preflight_payload_summarizes_diagnostics(monkeypatch, tmp_path: Path) -> None:
    diagnostics = {
        "frameworks": {
            "workflows": {
                "label": "workflows",
                "found": True,
                "detail": "ready",
            }
        },
        "foundations": {
            "loctree-mcp": {
                "label": "loctree-mcp",
                "found": False,
                "detail": "missing",
            }
        },
        "toolchains": {},
        "agents": {},
        "additional_tools": {},
    }
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "vetcoders_install.py").write_text(
        "#!/usr/bin/env python3\n", encoding="utf-8"
    )
    (scripts_dir / "install-foundations.sh").write_text(
        "#!/usr/bin/env bash\n", encoding="utf-8"
    )

    monkeypatch.setattr(installer_gui, "read_framework_version", lambda _: "1.2.1")
    monkeypatch.setattr(installer_gui, "run_diagnostics", lambda: diagnostics)
    monkeypatch.setattr(
        installer_gui,
        "start_here_path",
        lambda: tmp_path / "guide" / "START_HERE.md",
    )
    monkeypatch.setattr(
        installer_gui,
        "helper_layer_path",
        lambda: tmp_path / ".config" / "vetcoders" / "vc-skills.sh",
    )

    controller = installer_gui.InstallController(str(tmp_path))
    payload = controller.preflight_payload()

    assert payload["version"] == "1.2.1"
    assert payload["found_count"] == 1
    assert payload["missing_count"] == 1
    assert payload["found_items"] == ["Frameworks: workflows"]
    assert payload["missing_items"] == ["Foundations: loctree-mcp"]
    assert payload["needs_install"] == {"foundations": ["loctree-mcp"]}
    assert [step["label"] for step in payload["install_plan"]] == [
        "Bootstrap foundations",
        "Install Vibecrafted",
    ]
    assert payload["status"]["completed"] is False


def test_install_runtime_env_prepends_repo_owned_bins(
    monkeypatch, tmp_path: Path
) -> None:
    crafted_home = tmp_path / ".vibecrafted"
    cargo_bin = tmp_path / ".cargo" / "bin"
    node_bin = crafted_home / "tools" / "node" / "bin"
    crafted_bin = crafted_home / "bin"
    for path in (cargo_bin, node_bin, crafted_bin):
        path.mkdir(parents=True)

    monkeypatch.setattr(installer_gui, "vibecrafted_home", lambda: crafted_home)
    monkeypatch.setattr(installer_gui.Path, "home", lambda: tmp_path)

    env = installer_gui.install_runtime_env({"PATH": "/usr/bin"})
    pieces = env["PATH"].split(":")

    assert pieces[:3] == [str(cargo_bin), str(node_bin), str(crafted_bin)]


def test_build_html_renders_wizard_shell() -> None:
    html = installer_gui.build_html(
        {
            "version": "1.2.1",
            "source_dir_display": "~/src/vibecrafted",
            "guide_path_display": "~/.vibecrafted/START_HERE.md",
            "helper_path_display": "~/.config/vetcoders/vc-skills.sh",
            "found_count": 3,
            "missing_count": 2,
            "found_items": ["Frameworks: workflows"],
            "missing_items": ["Foundations: loctree-mcp"],
            "needs_install": {"foundations": ["loctree-mcp"]},
            "install_plan": [
                {
                    "label": "Bootstrap foundations",
                    "command": "bash scripts/install-foundations.sh",
                },
                {
                    "label": "Install Vibecrafted",
                    "command": "python3 scripts/vetcoders_install.py install --compact",
                },
            ],
            "categories": [],
            "status": {"completed": False, "running": False, "output": []},
        }
    )

    assert 'id="wizard-progress"' in html
    assert 'data-step="5"' in html
    assert "Launch guided install" in html
    assert "Finish state" in html
    assert "make wizard" in html
    assert "height: calc(100dvh - 36px);" in html
    assert "overflow: hidden;" in html
    assert "-webkit-overflow-scrolling: touch;" in html
    assert "grid-template-rows: auto minmax(0, 1fr);" in html
    assert "document.addEventListener('keydown'" in html
    assert "activeSlide?.querySelector('.slide-body')?.scrollTo" in html
