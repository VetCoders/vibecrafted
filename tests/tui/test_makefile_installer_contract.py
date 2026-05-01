from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_makefile_keeps_terminal_first_and_gui_fallback() -> None:
    """Contract: `make vibecrafted` is the terminal-native front door,
    `make wizard` is the optional browser-based GUI surface, and
    `make install` routes through the same vetcoders-installer runner
    with auto-approve for automation parity.

    The `vibecrafted` and `install` recipes must also keep the uv bootstrap
    and the `uv run` invocation inside one shell stanza, otherwise the
    `export PATH=...` from the bootstrap leg dies before `uv run` sees it
    (each `@`-prefixed recipe line spawns a fresh shell). See P1-01.
    """
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert (
        "make vibecrafted   \\033[2mTerminal-native installer wizard "
        "(default shell-first front door)" in text
    )
    assert (
        "make wizard        \\033[2mBrowser-based guided installer "
        "(optional GUI surface)" in text
    )

    vibecrafted_block = text.split("vibecrafted: init-hooks", 1)[1].split(
        "\nwizard: init-hooks", 1
    )[0]
    wizard_block = text.split("wizard: init-hooks", 1)[1].split(
        "\ngui-install: wizard", 1
    )[0]
    install_block = text.split("install: init-hooks", 1)[1].split("\nskills:", 1)[0]

    # The terminal-native front door must end its single shell stanza with
    # `uv run ... vetcoders-installer $(MANIFEST)`.
    assert (
        "uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST)"
        in vibecrafted_block
    )
    # Bootstrap + PATH export + uv run must live in ONE shell stanza.
    # Shape: the last `\` continuation chain must hold both the fi-terminator
    # and the `uv run` line so PATH survives the shell boundary.
    assert 'export PATH="$$HOME/.local/bin:$$PATH"' in vibecrafted_block
    assert "fi; \\" in vibecrafted_block, (
        "vibecrafted recipe must chain the uv bootstrap `fi` into the same "
        "shell as `uv run` via `fi; \\`"
    )

    assert '$(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)"' in wizard_block
    assert "$$VIBECRAFTED_SITE_BUNDLE" in wizard_block
    assert "$(CURDIR)/../vibecrafted-io" in wizard_block
    assert "pnpm run build" in wizard_block
    assert '--bundle-dir "$$site_repo/site/dist"' in wizard_block
    assert "wizard-dev: wizard" in text

    # make install routes through the same runner with --yes auto-approve,
    # so humans (make vibecrafted) and automation (make install) share one engine.
    assert (
        "uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --yes"
        in install_block
    )
    assert 'export PATH="$$HOME/.local/bin:$$PATH"' in install_block
    assert "fi; \\" in install_block, (
        "install recipe must chain the uv bootstrap `fi` into the same "
        "shell as `uv run` via `fi; \\`"
    )


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


def test_makefile_exposes_version_bump_contract() -> None:
    text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "make version-show" in text
    assert "make version-bump VERSION=X" in text
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
