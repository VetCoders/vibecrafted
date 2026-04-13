from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_makefile_keeps_terminal_first_and_gui_fallback() -> None:
    """Contract: `make vibecrafted` is the terminal-native front door,
    `make wizard` is the optional browser-based GUI surface, and
    `make install` routes through the same vetcoders-installer runner
    with auto-approve for automation parity.
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

    assert (
        "@uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST)"
        in vibecrafted_block
    )
    assert '@$(PYTHON) $(GUI_INSTALLER) --source "$(SOURCE)"' in wizard_block
    # make install routes through the same runner with --yes auto-approve,
    # so humans (make vibecrafted) and automation (make install) share one engine.
    assert (
        "@uv run --project $(INSTALLER_DIR) --quiet vetcoders-installer $(MANIFEST) --yes"
        in install_block
    )
