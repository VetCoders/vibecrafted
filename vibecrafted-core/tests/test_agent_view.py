"""agent_view — the skills projection both front doors (DMG, installer) share.

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from vibecrafted_core import agent_view

SKILLS = ("vc-agents", "vc-ship", "vc-init")
CANON = ("LIVING_TREE_RULE.md", "VERIFICATION_RULE.md")


def _generation(
    runtime_home: Path, version: str, langs: tuple[str, ...] = ("en",)
) -> Path:
    gen = runtime_home / "releases" / version
    root = gen / "vibecrafted-core" / "vibecrafted_core" / "skills"
    for lang in langs:
        base = root if lang == "en" else root / lang
        for name in SKILLS:
            (base / name).mkdir(parents=True)
            (base / name / "SKILL.md").write_text(f"# {name} ({lang}, {version})\n")
        for name in CANON:
            (base / name).write_text(f"{name} {lang} {version}\n")
        (base / "_template").mkdir()
        (base / "vibecraftsmanship").mkdir()
        (base / "pl-notes.md").write_text("not owned\n")
    return root


@pytest.fixture
def home(tmp_path: Path) -> Path:
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".codex").mkdir()
    # no ~/.gemini, ~/.agy, ~/.junie, ~/.grok: those agents are not on this machine
    return home


@pytest.fixture
def runtime_home(tmp_path: Path) -> Path:
    return tmp_path / "share" / "vibecrafted"


def test_projects_into_canon_and_every_present_runtime(
    home: Path, runtime_home: Path
) -> None:
    root = _generation(runtime_home, "4.2.4+gaaaaaaaa")
    report = agent_view.project(root, runtime_home, home)

    assert not report.errors
    for agent in (".agents", ".claude", ".codex"):
        skills = home / agent / "skills"
        for name in SKILLS + CANON + ("vibecraftsmanship",):
            link = skills / name
            assert link.is_symlink(), link
            assert os.readlink(link) == str(root / name)
        assert not (skills / "_template").exists()
        assert not (skills / "pl-notes.md").exists()
    assert not (home / ".gemini").exists()
    assert len(report.linked) == 3 * (len(SKILLS) + len(CANON) + 1)

    # idempotent: a second run links nothing and reports everything current
    again = agent_view.project(root, runtime_home, home)
    assert again.linked == []
    assert len(again.current) == len(report.linked)


def test_new_generation_repoints_old_projections(
    home: Path, runtime_home: Path
) -> None:
    old = _generation(runtime_home, "4.1.0+g11111111")
    agent_view.project(old, runtime_home, home)
    new = _generation(runtime_home, "4.2.4+g22222222")
    report = agent_view.project(new, runtime_home, home)

    assert not report.errors
    assert report.kept == []
    link = home / ".claude" / "skills" / "vc-ship"
    assert os.readlink(link) == str(new / "vc-ship")
    assert (link / "SKILL.md").read_text().endswith("4.2.4+g22222222)\n")


def test_private_and_foreign_entries_are_never_touched(
    home: Path, runtime_home: Path
) -> None:
    root = _generation(runtime_home, "4.2.4+gaaaaaaaa")
    claude_skills = home / ".claude" / "skills"
    claude_skills.mkdir(parents=True)
    # an operator's private skill with an owned-looking name, as a real directory
    (claude_skills / "vc-deprivatize").mkdir()
    (claude_skills / "vc-deprivatize" / "SKILL.md").write_text("private\n")
    # an owned name pointing somewhere that is not a Vibecrafted generation
    elsewhere = home / "dev" / "vc-ship"
    elsewhere.mkdir(parents=True)
    (claude_skills / "vc-ship").symlink_to(elsewhere)
    # a vendor skill
    (claude_skills / "docx").mkdir()

    report = agent_view.project(root, runtime_home, home)

    assert str(claude_skills / "vc-ship") in report.kept
    assert os.readlink(claude_skills / "vc-ship") == str(elsewhere)
    assert (claude_skills / "vc-deprivatize" / "SKILL.md").read_text() == "private\n"
    assert (claude_skills / "docx").is_dir()
    assert str(claude_skills / "vc-deprivatize") not in report.linked
    # the other runtimes still got vc-ship
    assert os.readlink(home / ".codex" / "skills" / "vc-ship") == str(root / "vc-ship")

    removed = agent_view.remove(runtime_home, home)
    assert str(claude_skills / "vc-ship") in removed.kept
    assert (claude_skills / "vc-deprivatize").is_dir()
    assert (claude_skills / "docx").is_dir()
    assert os.readlink(claude_skills / "vc-ship") == str(elsewhere)
    assert not (home / ".codex" / "skills" / "vc-ship").exists()
    assert not (home / ".agents" / "skills" / "vc-agents").exists()
    assert len(removed.removed) == 3 * (len(SKILLS) + len(CANON) + 1) - 1


def test_language_selects_the_mirror_set(home: Path, runtime_home: Path) -> None:
    root = _generation(runtime_home, "4.2.4+gaaaaaaaa", langs=("en", "pl"))
    agent_view.project(root, runtime_home, home, lang="pl")
    link = home / ".claude" / "skills" / "vc-ship"
    assert os.readlink(link) == str(root / "pl" / "vc-ship")
    assert "(pl," in (link / "SKILL.md").read_text()

    # switching back is the same operation
    agent_view.project(root, runtime_home, home, lang="en")
    assert os.readlink(link) == str(root / "vc-ship")

    with pytest.raises(ValueError):
        agent_view.skills_root_for(root, "de")


def test_explicit_runtimes_limit_the_projection(home: Path, runtime_home: Path) -> None:
    root = _generation(runtime_home, "4.2.4+gaaaaaaaa")
    report = agent_view.project(root, runtime_home, home, runtimes=["codex"])
    assert not report.errors
    assert (home / ".codex" / "skills" / "vc-ship").is_symlink()
    assert (home / ".agents" / "skills" / "vc-ship").is_symlink()
    assert not (home / ".claude" / "skills").exists()


def test_cli_project_detect_remove(
    home: Path, runtime_home: Path, capsys, monkeypatch
) -> None:
    root = _generation(runtime_home, "4.2.4+gaaaaaaaa", langs=("en", "pl"))
    gen = runtime_home / "releases" / "4.2.4+gaaaaaaaa"
    monkeypatch.setenv("VIBECRAFTED_RUNTIME_ROOT", str(gen))
    monkeypatch.setenv("VIBECRAFTED_RUNTIME_HOME", str(runtime_home))

    assert agent_view.main(["detect", "--home", str(home), "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == ["claude", "codex"]

    assert (
        agent_view.main(["project", "--home", str(home), "--lang", "pl", "--json"]) == 0
    )
    payload = json.loads(capsys.readouterr().out)
    assert payload["errors"] == []
    assert str(home / ".claude" / "skills" / "vc-init") in payload["linked"]
    assert os.readlink(home / ".claude" / "skills" / "vc-init") == str(
        root / "pl" / "vc-init"
    )

    assert agent_view.main(["remove", "--home", str(home)]) == 0
    out = capsys.readouterr().out
    assert "removed: " in out and "0 errors" in out
    assert not (home / ".claude" / "skills" / "vc-init").exists()

    with pytest.raises(SystemExit):
        agent_view.main(["project", "--home", str(home), "--runtimes", "claude,vim"])


def test_missing_skills_root_is_an_error(home: Path, runtime_home: Path) -> None:
    report = agent_view.project(runtime_home / "nope", runtime_home, home)
    assert report.errors and report.linked == []
