from __future__ import annotations

from argparse import Namespace
import io
import shutil
from pathlib import Path

from scripts import vetcoders_install as installer


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _write_minimal_source(root: Path, *, helper: str, launcher: str) -> None:
    (root / "skills" / "vc-agents" / "shell").mkdir(parents=True)
    (root / "skills" / "vc-agents" / "SKILL.md").write_text(
        "# vc-agents\n", encoding="utf-8"
    )
    (root / "skills" / "vc-agents" / "shell" / "vetcoders.sh").write_text(
        helper, encoding="utf-8"
    )
    (root / "scripts").mkdir(parents=True)
    _write_executable(root / "scripts" / "vibecrafted", launcher)
    (root / "VERSION").write_text("1.5.0-test\n", encoding="utf-8")


def _hide_rsync(monkeypatch) -> None:
    real_which = shutil.which

    def fake_which(name: str) -> str | None:
        if name == "rsync":
            return None
        return real_which(name)

    monkeypatch.setattr(installer.shutil, "which", fake_which)


class _TtyBuffer:
    def __init__(self) -> None:
        self.parts: list[str] = []

    def write(self, text: str) -> int:
        self.parts.append(text)
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return True

    @property
    def text(self) -> str:
        return "".join(self.parts)


def test_compact_status_updates_one_tty_row() -> None:
    out = _TtyBuffer()

    installer._compact_line(out, "✓", "Skills", "27 installed")
    installer._compact_line(out, "✓", "Store", "~/.vibecrafted/skills")
    installer._clear_compact_status(out)

    assert "\n" not in out.text
    assert out.text.count("\r\033[K") == 3
    assert "Skills" in out.text
    assert "Store" in out.text
    assert out.text.endswith("\r\033[K")


def test_compact_status_appends_lines_for_non_tty_logs() -> None:
    out = io.StringIO()

    installer._compact_line(out, "✓", "Skills", "27 installed")
    installer._compact_line(out, "✓", "Store", "~/.vibecrafted/skills")
    installer._clear_compact_status(out)

    assert out.getvalue().splitlines() == [
        "  ✓ Skills        27 installed",
        "  ✓ Store         ~/.vibecrafted/skills",
    ]


def test_compact_checkpoint_preserves_reason_context() -> None:
    out = io.StringIO()

    installer._compact_checkpoint(
        out,
        2,
        "Diagnostics and Plan",
        "We show the shape before changing files.",
        ("Skills   27 -> ~/.vibecrafted/skills", "Shell    enabled"),
    )

    assert out.getvalue().splitlines() == [
        "",
        "  [2/4] Diagnostics and Plan",
        "      REASON  We show the shape before changing files.",
        "      Skills   27 -> ~/.vibecrafted/skills",
        "      Shell    enabled",
    ]


def test_refresh_current_tools_mirrors_shadowing_files(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    crafted_home = tmp_path / "home" / ".vibecrafted"
    old_target = crafted_home / "tools" / "vibecrafted-main"
    current_link = crafted_home / "tools" / "vibecrafted-current"

    _write_minimal_source(
        source,
        helper='printf "fresh helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "fresh launcher\\n"\n',
    )
    (old_target / "skills" / "vc-agents" / "shell").mkdir(parents=True)
    (old_target / "scripts").mkdir(parents=True)
    (old_target / "skills" / "vc-agents" / "shell" / "vetcoders.sh").write_text(
        'printf "stale helper\\n"\n', encoding="utf-8"
    )
    (old_target / "scripts" / "vibecrafted").write_text(
        'printf "stale launcher\\n"\n', encoding="utf-8"
    )
    (old_target / "obsolete.txt").write_text("delete me\n", encoding="utf-8")
    current_link.parent.mkdir(parents=True, exist_ok=True)
    current_link.symlink_to(old_target)
    _hide_rsync(monkeypatch)

    refreshed = installer.refresh_current_tools(
        source, crafted_home, dry_run=False, mirror=True
    )

    assert refreshed == current_link
    assert current_link.is_symlink()
    assert (old_target / "skills" / "vc-agents" / "shell" / "vetcoders.sh").read_text(
        encoding="utf-8"
    ) == 'printf "fresh helper\\n"\n'
    assert (old_target / "scripts" / "vibecrafted").read_text(
        encoding="utf-8"
    ) == '#!/usr/bin/env bash\nprintf "fresh launcher\\n"\n'
    assert not (old_target / "obsolete.txt").exists()


def test_compact_install_refreshes_current_tools_from_local_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    source = tmp_path / "checkout"
    crafted_home = home / ".vibecrafted"
    old_target = crafted_home / "tools" / "vibecrafted-main"
    current_link = crafted_home / "tools" / "vibecrafted-current"

    _write_minimal_source(
        source,
        helper='printf "fresh installed helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "fresh installed launcher\\n"\n',
    )
    (old_target / "skills" / "vc-agents" / "shell").mkdir(parents=True)
    (old_target / "scripts").mkdir(parents=True)
    (old_target / "skills" / "vc-agents" / "shell" / "vetcoders.sh").write_text(
        'printf "stale staged helper\\n"\n', encoding="utf-8"
    )
    (old_target / "scripts" / "vibecrafted").write_text(
        'printf "stale staged launcher\\n"\n', encoding="utf-8"
    )
    current_link.parent.mkdir(parents=True, exist_ok=True)
    current_link.symlink_to(old_target)

    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home / ".config"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))
    monkeypatch.setattr(
        installer,
        "detect_system_deps",
        lambda: {"python3": "/usr/bin/python3", "git": "/usr/bin/git", "rsync": None},
    )
    monkeypatch.setattr(
        installer,
        "detect_agent_runtimes",
        lambda: {"claude": None, "codex": None, "gemini": None},
    )
    monkeypatch.setattr(installer, "FOUNDATIONS", [])
    monkeypatch.setattr(installer, "run_doctor", lambda _store, _state: [])
    monkeypatch.setattr(
        installer,
        "write_start_here_guide",
        lambda _store, _state, _findings: crafted_home / "START_HERE.md",
    )
    _hide_rsync(monkeypatch)

    exit_code = installer._cmd_install_compact(
        Namespace(dry_run=False, mirror=True, with_shell=False),
        source,
    )

    assert exit_code == 0
    assert (current_link / "skills" / "vc-agents" / "shell" / "vetcoders.sh").read_text(
        encoding="utf-8"
    ) == 'printf "fresh installed helper\\n"\n'
    assert (current_link / "scripts" / "vibecrafted").read_text(
        encoding="utf-8"
    ) == '#!/usr/bin/env bash\nprintf "fresh installed launcher\\n"\n'
