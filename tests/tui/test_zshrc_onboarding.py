"""W1-B: explicit PATH-only host zshrc onboarding."""

from __future__ import annotations

from pathlib import Path

from vibecrafted_core.vc_frame_delivery import ensure_zshrc, zshrc_template_text


def test_fresh_home_creates_zshrc(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    result = ensure_zshrc(home)
    assert result["action"] == "create"
    zshrc = home / ".zshrc"
    assert zshrc.is_file()
    text = zshrc.read_text(encoding="utf-8")
    assert ".local/bin" in text
    assert "vc-skills" not in text
    assert "VETCODERS_CONFIG_DIR" not in text
    assert "starship init" not in text


def test_existing_zshrc_gets_fenced_append_idempotent(tmp_path: Path) -> None:
    home = tmp_path / "h"
    home.mkdir()
    zshrc = home / ".zshrc"
    original = "# operator content\nexport FOO=1\n"
    zshrc.write_text(original, encoding="utf-8")
    r1 = ensure_zshrc(home)
    assert r1["action"] == "append_fence"
    mid = zshrc.read_text(encoding="utf-8")
    assert mid.startswith("# operator content")
    assert ">>> vibecrafted >>>" in mid
    assert "vc-skills" not in mid
    assert 'export PATH="$HOME/.local/bin:$PATH"' in mid
    r2 = ensure_zshrc(home)
    assert r2["action"] == "already_present"
    assert zshrc.read_text(encoding="utf-8") == mid


def test_template_nonempty() -> None:
    assert "PATH" in zshrc_template_text()
