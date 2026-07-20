from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_vc_skills_preserve_init_and_loctree_orientation_contract() -> None:
    skill_files = sorted((REPO_ROOT / "skills").glob("vc-*/SKILL.md"))
    assert skill_files, "No vc-* skill files discovered"

    missing: list[str] = []
    for skill_file in skill_files:
        if skill_file.parent.name == "vc-init":
            continue
        text = skill_file.read_text(encoding="utf-8")
        has_gate = (
            "## Canonical Orientation Gate" in text
            or "## Canonical Structural Gate" in text
        )
        required = [
            ("canonical gate", has_gate),
            ("vc-init procedure", "`vc-init`" in text),
            ("Loctree skill", "`Loctree:loctree`" in text),
            ("Code-Derived Application Map", "Code-Derived Application Map" in text),
        ]
        for label, ok in required:
            if not ok:
                missing.append(f"{skill_file.relative_to(REPO_ROOT)} missing {label}")

    assert not missing, "\n".join(missing)


def test_loctree_skills_match_literal_and_structural_runtime_truth() -> None:
    paths = [
        REPO_ROOT / "skills/vc-loctree/SKILL.md",
        REPO_ROOT / "skills/pl/vc-loctree/SKILL.md",
    ]
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "`loct find Identifier`" in text
        assert "`loct find --discover Terms`" in text
        assert "`loct find Identifier --where-symbol`" in text
        assert "38/38" in text
        assert "22/22" in text
        assert (
            "zero-consumer/dead result is a candidate" in text
            or "Zero konsumentów/dead to kandydat" in text
        )
        assert "objective structural truth" not in text
        assert "Every action must trace" not in text
