from __future__ import annotations

import io
from argparse import Namespace
from pathlib import Path

from scripts import vetcoders_install as installer

REPO_ROOT = Path(__file__).resolve().parents[2]


def _write_executable(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _write_complete_source(root: Path, *, helper: str, launcher: str) -> None:
    installer.stage_distribution_payload(REPO_ROOT, root, mirror=True)
    (root / "runtime" / "shell" / "vetcoders.sh").write_text(helper, encoding="utf-8")
    _write_executable(root / "scripts" / "vibecrafted", launcher)


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


def test_compact_checkpoint_prints_title_and_bounded_details_without_reason() -> None:
    """CLI_PRODUCT_SPEC §4: installers don't explain their own typography —
    the REASON narration line is retired from compact checkpoints."""
    out = io.StringIO()

    installer._compact_checkpoint(
        out,
        2,
        "Diagnostics and Plan",
        ("Skills   27 -> ~/.vibecrafted/skills", "Shell    enabled"),
    )

    assert out.getvalue().splitlines() == [
        "",
        "  [2/4] Diagnostics and Plan",
        "      Skills   27 -> ~/.vibecrafted/skills",
        "      Shell    enabled",
    ]


def test_refresh_current_tools_mirrors_shadowing_files(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "source"
    crafted_home = tmp_path / "home" / ".vibecrafted"
    runtime_tools = tmp_path / "home" / ".local" / "share" / "vibecrafted" / "tools"
    old_target = runtime_tools / "vibecrafted-main"
    current_link = runtime_tools / "vibecrafted-current"

    _write_complete_source(
        source,
        helper='printf "fresh helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "fresh launcher\\n"\n',
    )
    (old_target / "runtime" / "shell").mkdir(parents=True)
    (old_target / "scripts").mkdir(parents=True)
    (old_target / "runtime" / "shell" / "vetcoders.sh").write_text(
        'printf "stale helper\\n"\n', encoding="utf-8"
    )
    (old_target / "scripts" / "vibecrafted").write_text(
        'printf "stale launcher\\n"\n', encoding="utf-8"
    )
    (old_target / "obsolete.txt").write_text("delete me\n", encoding="utf-8")
    stale_cache = old_target / "vibecrafted-core" / "vibecrafted_core" / "__pycache__"
    stale_cache.mkdir(parents=True)
    (stale_cache / "dispatcher.cpython-314.pyc").write_bytes(b"stale")
    current_link.parent.mkdir(parents=True, exist_ok=True)
    current_link.symlink_to(old_target)
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(crafted_home))

    refreshed = installer.refresh_current_tools(
        source, crafted_home, dry_run=False, mirror=True
    )

    assert refreshed == current_link
    assert current_link.is_symlink()
    assert (old_target / "runtime" / "shell" / "vetcoders.sh").read_text(
        encoding="utf-8"
    ) == 'printf "fresh helper\\n"\n'
    assert (old_target / "scripts" / "vibecrafted").read_text(
        encoding="utf-8"
    ) == '#!/usr/bin/env bash\nprintf "fresh launcher\\n"\n'
    assert not (old_target / "obsolete.txt").exists()
    assert not (
        old_target / "vibecrafted-core" / "vibecrafted_core" / "__pycache__"
    ).exists()


def test_compact_install_refreshes_current_tools_from_local_checkout(
    tmp_path: Path, monkeypatch
) -> None:
    home = tmp_path / "home"
    source = tmp_path / "checkout"
    crafted_home = home / ".vibecrafted"
    runtime_tools = home / ".local" / "share" / "vibecrafted" / "tools"
    old_target = runtime_tools / "vibecrafted-main"
    current_link = runtime_tools / "vibecrafted-current"

    _write_complete_source(
        source,
        helper='printf "fresh installed helper\\n"\n',
        launcher='#!/usr/bin/env bash\nprintf "fresh installed launcher\\n"\n',
    )
    (old_target / "runtime" / "shell").mkdir(parents=True)
    (old_target / "scripts").mkdir(parents=True)
    (old_target / "runtime" / "shell" / "vetcoders.sh").write_text(
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

    def fail_runtime_venv(*_args, **_kwargs):
        raise AssertionError("compact install must not prepare runtime venv")

    def fail_runtime_entrypoints(*_args, **_kwargs):
        raise AssertionError("compact install must not publish runtime venv launchers")

    monkeypatch.setattr(installer, "_ensure_runtime_venv", fail_runtime_venv)
    monkeypatch.setattr(
        installer, "_install_python_entrypoint_launchers", fail_runtime_entrypoints
    )
    exit_code = installer._cmd_install_compact(
        Namespace(dry_run=False, mirror=True, with_shell=False),
        source,
    )

    assert exit_code == 0
    assert (current_link / "runtime" / "shell" / "vetcoders.sh").read_text(
        encoding="utf-8"
    ) == 'printf "fresh installed helper\\n"\n'
    assert (current_link / "scripts" / "vibecrafted").read_text(
        encoding="utf-8"
    ) == '#!/usr/bin/env bash\nprintf "fresh installed launcher\\n"\n'


def _build_symlinked_skill_store(tmp_path: Path) -> tuple[Path, Path]:
    """Wire vibecrafted-current -> vibecrafted-main so the skill store and the
    install source resolve to the same inode (portable-CI staging shape)."""
    main = tmp_path / "vibecrafted-main"
    skills = main / "skills"
    skills.mkdir(parents=True)
    for filename in installer.SKILL_ROOT_RULE_FILES:
        (skills / filename).write_text(f"{filename}\n", encoding="utf-8")
    for localized in installer.LOCALIZED_SKILL_RULE_DIRS:
        (skills / localized).mkdir(parents=True, exist_ok=True)
        for filename in installer.SKILL_ROOT_RULE_FILES:
            (skills / localized / filename).write_text(
                f"{localized}/{filename}\n", encoding="utf-8"
            )
    current = tmp_path / "vibecrafted-current"
    current.symlink_to(main)
    # source_skills_root(...).resolve() is what the installer passes as the
    # source; the store comes from the unresolved current-link path -> same
    # inode via two different string paths.
    source = (current / "skills").resolve()
    store = current / "skills"
    return source, store


def test_sync_skill_root_rules_skips_same_inode_store(tmp_path: Path) -> None:
    """Regression: a symlinked store (vibecrafted-current -> vibecrafted-main)
    made copy2 raise shutil.SameFileError during the portable "skills and
    launchers" phase. The sync must treat the self-copy as a no-op."""
    source, store = _build_symlinked_skill_store(tmp_path)

    copied = installer.sync_skill_root_rules(source, store, dry_run=False)

    # All rule files are still reported as synced (they already exist in place).
    expected = {p for _src, p in installer.iter_skill_root_rule_files(source)}
    assert set(copied) == expected
    for filename in installer.SKILL_ROOT_RULE_FILES:
        assert (store / filename).read_text(encoding="utf-8") == f"{filename}\n"


def test_rsync_skill_skips_same_inode_dir(tmp_path: Path, monkeypatch) -> None:
    """Regression: the shutil fallback copied a skill dir onto itself (and under
    --mirror rmtree'd the source) when the store symlinked back to the source."""
    source, store = _build_symlinked_skill_store(tmp_path)
    # A skill living inside the skills dir: source/vc-demo (real) and
    # store/vc-demo (via the current-link symlink) are the same inode.
    src_skill = source / "vc-demo"
    src_skill.mkdir()
    (src_skill / "SKILL.md").write_text("demo\n", encoding="utf-8")
    dst_skill = store / "vc-demo"

    # Force the pure-Python fallback path (no rsync) with mirror=True — the most
    # destructive shape (rmtree of dst == the source) — and assert the source
    # survives untouched.
    monkeypatch.setattr(installer.shutil, "which", lambda _name: None)
    installer.rsync_skill(src_skill, dst_skill, dry_run=False, mirror=True)

    assert (src_skill / "SKILL.md").read_text(encoding="utf-8") == "demo\n"
