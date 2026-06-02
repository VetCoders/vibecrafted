from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_makefile_keeps_install_as_terminal_first_front_door() -> None:
    """Contract: `make install` is the terminal-native human front door,
    `make setup-dev` opens the same meta-installer in advanced mode, and
    `make install-auto` is the auto-approved automation path.

    The installer recipes must also keep the uv bootstrap
    and the `uv run` invocation inside one shell stanza, otherwise the
    `export PATH=...` from the bootstrap leg dies before `uv run` sees it
    (each `@`-prefixed recipe line spawns a fresh shell). See P1-01.
    """
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert (
        "make install       \\033[2mInstall interactively with checkpoints and REASON"
        in text
    )
    assert "make setup-dev     \\033[2mOpen the meta-installer for options" in text
    assert "make install-auto  \\033[2mAutomation path: same installer" in text
    assert "make skills" not in text.split("help:", 1)[1].split("\nvibecrafted:", 1)[0]
    assert "vibecrafted: install" in text

    install_block = text.split("install: init-hooks", 1)[1].split("\n# BUNDLE_DIR", 1)[
        0
    ]
    wizard_block = text.split("wizard: init-hooks", 1)[1].split(
        "\ngui-install: wizard", 1
    )[0]
    install_auto_block = text.split("install-auto: init-hooks", 1)[1].split(
        "\nskills:", 1
    )[0]
    setup_dev_block = text.split("setup-dev: init-hooks", 1)[1].split("\ndry-run:", 1)[
        0
    ]

    # The terminal-native front door suppresses nested subprocess chatter while
    # retaining the full log on disk.
    assert (
        "uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --quiet"
        in install_block
    )
    assert "--yes" not in install_block
    assert 'export PATH="$$HOME/.local/bin:$$PATH"' in install_block
    assert "fi; \\" in install_block, (
        "install recipe must chain the uv bootstrap `fi` into the same "
        "shell as `uv run` via `fi; \\`"
    )

    assert '$(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)"' in wizard_block
    assert "$$VIBECRAFTED_SITE_BUNDLE" in wizard_block
    assert "$(CURDIR)/../vibecrafted-io" in wizard_block
    assert "pnpm run build" in wizard_block
    assert '--bundle-dir "$$site_repo/site/dist"' in wizard_block
    assert "wizard-dev: wizard" in text

    # Automation still shares the same runner, but the target name says what it does.
    assert (
        "uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --yes --quiet"
        in install_auto_block
    )
    assert 'export PATH="$$HOME/.local/bin:$$PATH"' in install_auto_block
    assert "fi; \\" in install_auto_block, (
        "install-auto recipe must chain the uv bootstrap `fi` into the same "
        "shell as `uv run` via `fi; \\`"
    )
    assert "--advanced --quiet" in setup_dev_block
    assert "vetcoders-installer $(MANIFEST)" in setup_dev_block


def test_bundle_check_uses_portable_mktemp_template() -> None:
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert 'mktemp "$$tmp_root/vibecrafted-bundle.XXXXXX"' in text
    assert 'mktemp "$$tmp_root/vibecrafted-bundle.XXXXXX.plugin"' not in text


def test_install_manifest_post_install_uses_mirror_sync() -> None:
    text = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    assert (
        'python3 scripts/vetcoders_install.py install --source "." '
        "--with-shell --compact --non-interactive --mirror"
    ) in text


def test_install_manifest_uses_four_human_checkpoints_with_artifact_reason() -> None:
    text = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    phase_text = text.split("[branding]", 1)[0]
    labels = [
        line.split("=", 1)[1].strip().strip('"')
        for line in phase_text.splitlines()
        if line.startswith("label = ")
    ]
    assert labels == [
        "Introduction",
        "Diagnostics and plan",
        "Installation",
        "Onboarding",
    ]
    assert "Set your artifacts storage location." in text
    assert "keeps the persistent artifacts on developer's hard disks" in text
    assert 'installer_cmd = "make install"' in text


def test_makefile_exposes_version_bump_contract() -> None:
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "version-show:" in text
    assert "version-bump:" in text
    assert (
        "VERSION is required. Usage: make version-bump VERSION={patch|minor|major|x.y.z}"
        in text
    )
    assert "scripts/version_bump.py" in text


def test_make_version_bump_updates_configured_version_file(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    version_file.write_text("1.4.1\n", encoding="utf-8")

    result = subprocess.run(
        [
            "make",
            "-f",
            str(REPO_ROOT / "Makefile"),
            "version-bump",
            "VERSION=minor",
            f"VERSION_FILE={version_file}",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "Bumped: v1.4.1 -> v1.5.0" in result.stdout
    assert version_file.read_text(encoding="utf-8") == "1.5.0\n"


def test_foundations_product_binaries_require_explicit_owner_opt_in() -> None:
    text = (REPO_ROOT / "scripts" / "install-foundations.sh").read_text(
        encoding="utf-8"
    )

    loctree_block = text.split("install_loctree() {", 1)[1].split(
        "# ---------------------------------------------------------------------------\n# Generic cargo installer",
        1,
    )[0]
    aicx_block = text.split("install_aicx() {", 1)[1].split(
        "# ---------------------------------------------------------------------------\n# Zellij installer",
        1,
    )[0]

    guard = 'if [[ "$OWN_PRODUCT_BINARIES" != "1" ]]; then'
    assert loctree_block.index(guard) < loctree_block.index(
        'install_from_bundled "loctree"'
    )
    assert loctree_block.index(guard) < loctree_block.index(
        'install_from_cargo "loctree" "loct"'
    )
    assert aicx_block.index(guard) < aicx_block.index('install_from_bundled "aicx-mcp"')
    assert aicx_block.index(guard) < aicx_block.index(
        'install_from_cargo "$AICX_CRATE" "aicx-mcp"'
    )


def test_installer_paths_do_not_write_shell_rc_without_consent_flag() -> None:
    install_shell = (
        REPO_ROOT / "skills" / "vc-agents" / "scripts" / "install-shell.sh"
    ).read_text(encoding="utf-8")
    installer = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(
        encoding="utf-8"
    )

    assert "write_rc=0" in install_shell
    assert "if (( write_rc && update_zshrc )); then" in install_shell
    assert "if (( write_rc && update_bashrc )); then" in install_shell
    assert '"--write-shell-rc"' in installer
    assert "update_rc=write_shell_rc" in installer
    assert "if write_shell_rc:\n        for rcname in" in installer


def test_product_mcp_paths_do_not_hardcode_cargo_bin() -> None:
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    offenders = []
    product_markers = ("loctree-mcp", "aicx-mcp", "rust-memex")
    cargo_markers = ("~/.cargo/bin", "$HOME/.cargo/bin")
    for rel in tracked:
        path = REPO_ROOT / rel
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(text.splitlines(), 1):
            if any(product in line for product in product_markers) and any(
                cargo in line for cargo in cargo_markers
            ):
                offenders.append(f"{rel}:{line_no}: {line.strip()}")

    assert offenders == []
