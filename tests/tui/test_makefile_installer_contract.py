from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from scripts import vetcoders_install as installer

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_makefile_keeps_install_as_terminal_first_front_door() -> None:
    """Contract: `make install` is the terminal-native human front door — a
    compact, log-quiet step runner that greets, walks the canonical install
    steps through $(INSTALL_STEP), and ends by pointing at `vc-start`.
    `make install-auto` is the unattended automation path that reuses the same
    front door, and `make setup-dev` opens the uv meta-installer in advanced
    mode.

    Every recipe that bootstraps uv (setup-dev, install-all, tui-installer)
    must keep the uv bootstrap and the `uv run` invocation inside one shell
    stanza, otherwise the `export PATH=...` from the bootstrap leg dies before
    `uv run` sees it (each `@`-prefixed recipe line spawns a fresh shell).
    See P1-01.
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

    # The front door is the compact step runner: it greets, walks the canonical
    # install steps through $(INSTALL_STEP), and ends by pointing at vc-start.
    install_block = text.split("\ninstall:\n", 1)[1].split(
        "\ninstall-python-tools:", 1
    )[0]
    assert 'printf "Installing Vibecrafted\\n"' in install_block
    for label in (
        "foundations",
        "skills and launchers",
        "runtime tools",
        "app and server",
    ):
        assert f'$(INSTALL_STEP) "{label}"' in install_block, (
            f"front door must walk the `{label}` install step via $(INSTALL_STEP)"
        )
    assert "vc-start" in install_block

    # install-auto is the unattended path: it reuses the same front door rather
    # than forking a second installer recipe.
    assert "install-auto: install" in text

    # setup-dev opens the uv meta-installer in advanced mode. Advanced is an
    # interactive surface, so it never carries the auto-approve `--yes`.
    setup_dev_block = text.split("setup-dev: init-hooks", 1)[1].split("\ndry-run:", 1)[
        0
    ]
    assert "vetcoders-installer $(MANIFEST)" in setup_dev_block
    assert "--advanced --quiet" in setup_dev_block
    assert "--yes" not in setup_dev_block

    # install-all is the auto-approved meta-installer: same runner, but --yes.
    install_all_block = text.split("install-all: init-hooks", 1)[1].split(
        "\n# Output discipline", 1
    )[0]
    assert (
        "uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --yes --quiet"
        in install_all_block
    )

    # P1-01: every uv-bootstrapping recipe exports PATH first and chains the
    # bootstrap `fi` into the same shell as `uv run` via `fi; \`, so the
    # freshly-installed uv is visible to `uv run`.
    tui_installer_block = text.split("tui-installer: init-hooks", 1)[1].split(
        "\n# BUNDLE_DIR", 1
    )[0]
    for name, block in (
        ("setup-dev", setup_dev_block),
        ("install-all", install_all_block),
        ("tui-installer", tui_installer_block),
    ):
        assert 'export PATH="$$HOME/.local/bin:$$PATH"' in block, (
            f"{name} must export PATH before `uv run`"
        )
        assert "fi; \\" in block, (
            f"{name} must chain the uv bootstrap `fi` into the same shell as "
            "`uv run` via `fi; \\`"
        )
        assert (
            "uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST)"
            in block
        ), f"{name} must invoke the uv meta-installer"


def test_bundle_check_uses_portable_mktemp_template() -> None:
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert 'mktemp "$$tmp_root/vibecrafted-bundle.XXXXXX"' in text
    assert 'mktemp "$$tmp_root/vibecrafted-bundle.XXXXXX.plugin"' not in text


def test_bundle_targets_use_distribution_manifest_for_runtime_archive() -> None:
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    bundle_block = text.split("\nbundle:\n", 1)[1].split("\nbundle-check:\n", 1)[0]
    check_block = text.split("\nbundle-check:\n", 1)[1].split(
        "\nversion version-show:", 1
    )[0]

    for block in (bundle_block, check_block):
        assert "scripts/distribution_manifest.py archive" in block
        assert "scripts/distribution_manifest.py check" in check_block
    assert (
        "BUNDLE_ARCHIVE ?= $(SOURCE)/dist/vibecrafted-$(BUNDLE_VERSION).tar.gz" in text
    )
    assert '--root-name "vibecrafted-$(BUNDLE_VERSION)"' in bundle_block
    assert "build_marketplace_bundle.py" in bundle_block
    assert "build_marketplace_bundle.py" in check_block
    assert "cmp -s" not in check_block
    assert 'test -s "$$tmp_bundle"' in check_block
    assert check_block.lstrip().startswith("@set -e;")


def test_control_plane_staging_delegates_to_distribution_manifest(
    monkeypatch, tmp_path: Path
) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    source.mkdir()
    seen: dict[str, object] = {}

    def fake_stage(src: Path, dst: Path, *, mirror: bool) -> None:
        seen.update(source=src, destination=dst, mirror=mirror)
        dst.mkdir(parents=True)
        (dst / "payload.txt").write_text("validated\n", encoding="utf-8")

    monkeypatch.setattr(installer, "stage_distribution_payload", fake_stage)

    installer.sync_control_plane_tree(source, destination, mirror=True)

    assert seen["source"] == source
    assert seen["destination"] != destination
    assert Path(seen["destination"]).parent == destination.parent
    assert seen["mirror"] is True
    assert (destination / "payload.txt").read_text(encoding="utf-8") == "validated\n"
    source_text = (REPO_ROOT / "scripts" / "vetcoders_install.py").read_text(
        encoding="utf-8"
    )
    assert "_CONTROL_PLANE_EXCLUDES" not in source_text


def test_install_manifest_post_install_uses_mirror_sync() -> None:
    text = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    assert (
        'python3 scripts/vetcoders_install.py install --source "." '
        "--compact --non-interactive --mirror"
    ) in text
    assert "make --no-print-directory install-python-tools" in text


def test_installer_copies_skill_rules_to_fresh_skills_root(tmp_path: Path) -> None:
    source_skills = tmp_path / "source" / "skills"
    install_skills = tmp_path / "install" / "skills"
    runtime_skills = tmp_path / "home" / ".claude" / "skills"
    installed_skill = install_skills / "vc-implement"
    runtime_skill = runtime_skills / "vc-implement"

    (source_skills / "vc-implement").mkdir(parents=True)
    (source_skills / "vc-implement" / "SKILL.md").write_text(
        "See [Verification Rule](../VERIFICATION_RULE.md).\n"
        "See [Living Tree Rule](../LIVING_TREE_RULE.md).\n",
        encoding="utf-8",
    )
    (source_skills / "VERIFICATION_RULE.md").write_text(
        "# Verification\n", encoding="utf-8"
    )
    (source_skills / "FOUNDATION_RULE.md").write_text(
        "# Foundation\n", encoding="utf-8"
    )
    (source_skills / "LIVING_TREE_RULE.md").write_text(
        "# Living Tree\n", encoding="utf-8"
    )
    (source_skills / "pl").mkdir()
    (source_skills / "pl" / "LIVING_TREE_RULE.md").write_text(
        "# Zywe Drzewo\n", encoding="utf-8"
    )
    installed_skill.mkdir(parents=True)
    runtime_skill.mkdir(parents=True)

    copied = installer.sync_skill_root_rules(source_skills, install_skills)
    copied_again = installer.sync_skill_root_rules(source_skills, install_skills)
    runtime_copied = installer.sync_skill_root_rules(source_skills, runtime_skills)

    assert copied == copied_again
    assert runtime_copied == copied
    assert Path("VERIFICATION_RULE.md") in copied
    assert Path("FOUNDATION_RULE.md") in copied
    assert Path("LIVING_TREE_RULE.md") in copied
    assert Path("pl/LIVING_TREE_RULE.md") in copied
    assert (installed_skill / ".." / "VERIFICATION_RULE.md").is_file()
    assert (installed_skill / ".." / "FOUNDATION_RULE.md").is_file()
    assert (installed_skill / ".." / "LIVING_TREE_RULE.md").is_file()
    assert (runtime_skills / "VERIFICATION_RULE.md").is_file()
    assert (runtime_skills / "FOUNDATION_RULE.md").is_file()
    assert (runtime_skills / "LIVING_TREE_RULE.md").is_file()
    assert (runtime_skill / ".." / "VERIFICATION_RULE.md").is_file()
    assert (install_skills / "pl" / "LIVING_TREE_RULE.md").is_file()
    assert (runtime_skills / "pl" / "LIVING_TREE_RULE.md").is_file()
    assert not (install_skills / "pl" / "VERIFICATION_RULE.md").exists()


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


def test_install_all_default_output_is_quiet_and_points_to_vc_start() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    step_runner = (REPO_ROOT / "scripts" / "install-step.sh").read_text(
        encoding="utf-8"
    )

    install_all_block = makefile.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    receipt_start = install_all_block.index("Vibecrafted is ready.")
    vc_start_index = install_all_block.index("vc-start")
    doctor_index = install_all_block.index("vibecrafted doctor")
    log_index = install_all_block.index("~/.vibecrafted/install.log")

    assert 'printf "Installing Vibecrafted\\n"' in install_all_block
    for label in (
        "foundations",
        "frontier config",
        "skills and launchers",
        "runtime tools",
        "app and server",
    ):
        assert f'$(INSTALL_STEP) "{label}" --' in install_all_block

    assert receipt_start < vc_start_index < doctor_index < log_index
    assert "VIBECRAFTED_INSTALL_LOG" in install_all_block
    assert ': > "$(INSTALL_LOG)"' in install_all_block
    assert "VERBOSE ?= 0" in makefile
    assert 'tee -a "$log_path"' in step_runner
    assert "Install failed during: %s" in step_runner
    assert "vibecrafted doctor" in step_runner


def test_install_all_user_facing_output_has_no_ghost_anxiety_copy() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    output_lines = [
        line for line in makefile.splitlines() if "echo " in line or "printf " in line
    ]
    output_text = "\n".join(output_lines).lower()

    for forbidden in ("cargo " + "ghosts", "ghost " + "symlink", "cargo-" + "ghost"):
        assert forbidden not in output_text


def test_install_all_installs_python_tools_with_uv_tool_install() -> None:
    """install-all owns Python console scripts through uv tool install.

    De-fragile contract: the uv-tool editable source is the STABLE runtime home
    (resolved via runtime_paths -> vibecrafted-current), NEVER the dev-workspace
    checkout ($(SOURCE)). An editable install pointed at the checkout breaks the
    `vibecrafted` CLI the moment the dev tree switches to a branch without
    vibecrafted_core/cli.py. The MCP server is installed as its own tool, with
    the stable-home vibecrafted-core injected as the dependency source.
    """
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    manifest = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    assert "install-python-tools:" in makefile

    install_all_block = makefile.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    python_tools_block = makefile.split("install-python-tools:", 1)[1].split(
        "\n# install-all owns", 1
    )[0]

    assert "make --no-print-directory install-python-tools" in install_all_block
    # The uv-tool editable installs must source from the resolved stable home
    # ($$stable_root -> vibecrafted-current), not the dev checkout.
    assert (
        'uv tool install --force --reinstall --editable "$$stable_root/vibecrafted-core"'
    ) in python_tools_block
    assert (
        "uv tool install --force --reinstall --editable "
        '"$$stable_root/vibecrafted-mcp" --with-editable '
        '"$$stable_root/vibecrafted-core"'
    ) in python_tools_block
    # Non-fakeable: no `uv tool install` may take its editable source from the
    # dev-workspace checkout ($(SOURCE)). That is the whole point of de-fragiling.
    assert (
        'uv tool install --force --reinstall --editable "$(SOURCE)'
        not in python_tools_block
    )
    assert "vibecrafted-current" in python_tools_block
    assert "vibecrafted-mcp" in (
        REPO_ROOT / "vibecrafted-mcp" / "pyproject.toml"
    ).read_text(encoding="utf-8")

    assert "make --no-print-directory install-python-tools" in manifest


def test_install_all_covers_app_binaries_as_real_files() -> None:
    """install-all must own the shipped Rust binaries (voc, vc-admin, and
    vc-server): built from source in release and copied into
    ~/.local/bin as REAL files. `cargo install` is forbidden in that path because
    it can create ~/.local/bin -> ~/.cargo/bin symlink drift. The install.toml
    installation phase mirrors install-all line-by-line, so it must carry the
    same steps."""
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    manifest = (REPO_ROOT / "install.toml").read_text(encoding="utf-8")

    install_all_block = makefile.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    assert "install-vendored-binaries" in install_all_block
    assert "install-app-binaries" in install_all_block
    assert "install-server" in install_all_block

    assert (
        "VENDORED_FOUNDATION_BINARIES := vc-frame loctree-mcp loct aicx aicx-mcp"
        in makefile
    )
    assert "bin/vendor/$(HOST_VENDOR_PLATFORM)" in makefile
    assert "APP_BINARIES := voc vc-admin" in makefile
    assert "SERVER_PACKAGE := vibecrafted-server-web" in makefile
    assert "SERVER_BIN  := vc-server" in makefile
    assert "SERVER_COMPAT_BIN := vibecrafted-server-web" in makefile
    assert "BIN_DIR := $(HOME)/.local/bin" in makefile

    app_block = makefile.split("\ninstall-app-binaries:", 1)[1].split("\nskills:", 1)[0]
    assert "cargo build --release -p voc" in app_block
    assert "cargo install" not in app_block
    assert 'install -m 0755 "$(APP_DIR)/target/release/$$bin" "$(BIN_DIR)/$$bin"' in (
        app_block
    )

    assert "make --no-print-directory install-vendored-binaries" in manifest
    assert "make --no-print-directory install-app-binaries" in manifest
    assert "make --no-print-directory install-server" in manifest


def test_bin_dir_owned_entries_are_never_cargo_owned_symlink_drift() -> None:
    """Runtime contract: BIN (~/.local/bin) holds real files or symlinks into
    the vibecrafted runtime — never a symlink resolving into ~/.cargo/bin.
    A cargo-owned symlink is a side-installed binary the canonical installer
    does not own; the machine then drifts the moment `cargo install` re-runs."""
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
        "unexpected cargo-owned symlinks in ~/.local/bin (run `make install-all` to "
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
        "# ---------------------------------------------------------------------------\n# vc-frame installer",
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
    entrypoint_block = installer.split("PYTHON_ENTRYPOINT_LAUNCHERS = [", 1)[1].split(
        "\n]", 1
    )[0]
    for name in ("vc-audit", "vc-dou", "vc-hydrate", "vc-polarize", "vc-marbles"):
        assert f'"{name}"' in entrypoint_block


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
        # `git ls-files` lists tracked symlinks-to-directories (e.g. `runtime`,
        # `skills`) and gitlinks as entries; those are not file content to
        # scan. is_file() follows symlinks, so file-symlinks are still read.
        if not path.is_file():
            continue
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


def test_install_server_is_in_install_all() -> None:
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    assert "install-server:" in text

    install_all_block = text.split("install-all:", 1)[1].split("\nskills:", 1)[0]
    assert "make --no-print-directory install-server" in install_all_block
