from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


# Foundation tools ARE the orientation surface (vc-loctree, vc-aicx), and the
# standalone utility skills below are not repo-structural workflows — none carry
# the repo-orientation gate. They were flattened into skills/ out of
# skills/foundations/, so they now match the vc-*/SKILL.md glob and must be exempt.
_ORIENTATION_EXEMPT = {
    "vc-loctree",
    "vc-aicx",
    "vc-prview",
    "vc-screenscribe",
    "vc-skillaunch",
}


def test_vc_skills_preserve_init_and_loctree_orientation_contract() -> None:
    skill_files = sorted((REPO_ROOT / "skills").glob("vc-*/SKILL.md"))
    assert skill_files, "No vc-* skill files discovered"

    skill_files = [f for f in skill_files if f.parent.name not in _ORIENTATION_EXEMPT]

    missing: list[str] = []
    for skill_file in skill_files:
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
