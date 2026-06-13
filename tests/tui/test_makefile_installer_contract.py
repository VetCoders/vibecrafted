from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

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

    # CLI_PRODUCT_SPEC §6.5: `make help` is the six-target deck; everything
    # else lives in `make help-dev`.
    assert "make install      \\033[2mGuided install" in text
    assert "make doctor       \\033[2mHealth check" in text
    assert "dev targets: make help-dev" in text
    assert "help-dev:" in text
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
        "--compact --non-interactive --mirror"
    ) in text
    assert "make --no-print-directory install-python-tools" in text


def test_install_all_paths_do_not_install_shell_helpers_by_default() -> None:
    """New runtime contract: install-all installs tools and views, but does not
    wire legacy shell helpers or mutate shell rc files by default."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    manifest = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    install_all_block = makefile.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    assert "--with-shell" not in install_all_block
    assert "--write-shell-rc" not in install_all_block

    installation_phase = manifest.split('key = "installation"', 1)[1].split(
        "\n\n[[phase]]", 1
    )[0]
    assert "--with-shell" not in installation_phase
    assert "--write-shell-rc" not in installation_phase


def test_install_all_installs_python_tools_with_uv_tool_install() -> None:
    """install-all owns Python console scripts through uv tool install.

    The MCP server is installed as its own tool, with local vibecrafted-core
    injected as the dependency source, so ~/.local/bin/vibecrafted-mcp comes
    from the package entrypoint instead of a shell helper wrapper.
    """
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    manifest = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    assert "install-python-tools:" in makefile

    install_all_block = makefile.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    python_tools_block = makefile.split("install-python-tools:", 1)[1].split(
        "\n# install-all owns", 1
    )[0]

    assert "$(MAKE) --no-print-directory install-python-tools" in install_all_block
    assert (
        'uv tool install --force --reinstall --editable "$(SOURCE)/vibecrafted-core"'
    ) in python_tools_block
    assert (
        "uv tool install --force --reinstall --editable "
        '"$(SOURCE)/vibecrafted-mcp" --with-editable '
        '"$(SOURCE)/vibecrafted-core"'
    ) in python_tools_block
    assert "vibecrafted-mcp" in (
        REPO_ROOT / "vibecrafted-mcp" / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert "make --no-print-directory install-python-tools" in manifest


def test_install_all_covers_app_binaries_as_real_files() -> None:
    """install-all must own the vibecrafted-app member binaries (voc,
    vc-admin): built from source in release and copied into ~/.local/bin as
    REAL files. `cargo install` is forbidden in that path — it is what breeds
    the ~/.local/bin -> ~/.cargo/bin ghost symlinks the runtime contract bans.
    The install.toml installation phase mirrors install-all line-by-line, so
    it must carry the same step."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    manifest = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    install_all_block = makefile.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    assert "install-app-binaries" in install_all_block

    assert "APP_BINARIES := voc vc-admin" in makefile
    assert "BIN_DIR := $(HOME)/.local/bin" in makefile

    app_block = makefile.split("\ninstall-app-binaries:", 1)[1].split("\nskills:", 1)[0]
    assert "cargo build --release -p voc" in app_block
    assert "cargo install" not in app_block
    assert 'install -m 0755 "$(APP_DIR)/target/release/$$bin" "$(BIN_DIR)/$$bin"' in (
        app_block
    )

    assert "make --no-print-directory install-app-binaries" in manifest


def test_bin_dir_owned_entries_are_never_cargo_ghost_symlinks() -> None:
    """Runtime contract: BIN (~/.local/bin) holds real files or symlinks into
    the vibecrafted runtime — never a symlink resolving into ~/.cargo/bin.
    A cargo ghost is a side-installed binary the canonical installer does not
    own; the machine then drifts the moment `cargo install` re-runs."""
    bin_dir = Path.home() / ".local" / "bin"
    if not bin_dir.is_dir():
        pytest.skip("no ~/.local/bin on this machine")

    cargo_bin = Path.home() / ".cargo" / "bin"
    owned_names = {"voc", "vc-admin", "vibecraft", "vibecrafted", "telemetry"}

    offenders = []
    for entry in bin_dir.iterdir():
        owned = entry.name in owned_names or (
            entry.name.startswith("vc-") and entry.name != "vc-frame"
        )
        if not owned or not entry.is_symlink():
            continue
        resolved = Path(os.path.realpath(entry))
        if resolved.is_relative_to(cargo_bin):
            offenders.append(f"{entry.name} -> {resolved}")

    assert offenders == [], (
        "cargo-ghost symlinks in ~/.local/bin (run `make install-all` to "
        f"install real files): {offenders}"
    )


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


def test_foundations_product_binaries_are_validation_only() -> None:
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

    forbidden = (
        "VIBECRAFTED_OWN_PRODUCT_BINARIES",
        "OWN_PRODUCT_BINARIES",
        "LOCTREE_VERSION",
        "AICX_VERSION",
        "install_from_bundled",
        "install_from_cargo",
        "install_from_npm",
        "github_release_asset_url",
        "cargo install",
        "LOCTREE_SOURCE",
        "AICX_SOURCE",
        "../loctree-suite",
        "../aicx",
    )
    for needle in forbidden:
        assert needle not in loctree_block
        assert needle not in aicx_block

    assert "curl -fsSL $LOCTREE_INSTALL_URL | sh" in loctree_block
    assert "curl -fsSL $LOCTREE_INSTALL_URL | sh" in aicx_block
    assert (
        "will not guess crates, npm packages, or local checkout paths" in loctree_block
    )
    assert "will not guess crates, npm packages, or local checkout paths" in aicx_block


def test_setup_installer_uses_canonical_foundation_action_only() -> None:
    installer = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(
        encoding="utf-8"
    )
    skills_sync = (REPO_ROOT / "runtime" / "scripts" / "skills_sync.sh").read_text(
        encoding="utf-8"
    )

    for name in ("aicx-mcp", "loct", "loctree", "loctree-mcp"):
        block = installer.split(f'name="{name}"', 1)[1].split("verify_cmd=", 1)[0]
        assert 'channels=["canonical"]' in block
        assert "curl -fsSL https://loct.io/install.sh | sh" in block
        assert '"crates"' not in block
        assert '"npm"' not in block
        assert '"github"' not in block
        assert "LOCTREE_SOURCE" not in block
        assert "AICX_SOURCE" not in block
        assert "../loctree-suite" not in block
        assert "../aicx" not in block

    forbidden = (
        "install_foundation_cargo",
        "Install {f.name} with cargo?",
        "has_cargo = detect_cargo()",
        "cargo not found — cannot auto-install foundations",
        "fallback cargo install loctree-mcp",
        "fallback cargo install ai-contexters",
    )
    for needle in forbidden:
        assert needle not in installer
        assert needle not in skills_sync


def test_installer_publishes_async_dispatch_wrapper() -> None:
    installer = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(
        encoding="utf-8"
    )
    launcher_block = installer.split("LAUNCHER_WRAPPERS = [", 1)[1].split("\n]", 1)[0]

    assert '"vc-loop"' in launcher_block
    assert '"vc-ship"' in launcher_block
    assert '"vc-cron"' in launcher_block
    assert '"vc-dispatch"' in launcher_block
    assert '"vc-dashboard"' in launcher_block


def test_installer_paths_do_not_write_shell_rc_without_consent_flag() -> None:
    install_shell = (REPO_ROOT / "runtime" / "scripts" / "install-shell.sh").read_text(
        encoding="utf-8"
    )
    installer = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(
        encoding="utf-8"
    )

    assert "write_rc=0" in install_shell
    assert "if (( write_rc && update_zshrc )); then" in install_shell
    assert "if (( write_rc && update_bashrc )); then" in install_shell
    assert '"--write-shell-rc"' in installer
    assert "update_rc=write_shell_rc" in installer
    assert "if write_shell_rc:\n        for rcname in" in installer

    # The "already sourced" skip must be ACTIVE-only: a commented/disabled hook
    # cannot count as present, or a cleaned machine never re-wires on reinstall.
    assert 'grep -Fq "vetcoders/vc-skills.sh"' not in install_shell
    assert "[^#[:space:]].*vetcoders/vc-skills" in install_shell


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


def test_install_server_not_in_install_all() -> None:
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "install-server:" in text

    install_all_block = text.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    assert "install-server" not in install_all_block
