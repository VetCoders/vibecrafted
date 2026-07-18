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


def test_scaffold_and_dispatch_enforce_operator_chosen_baseline() -> None:
    baseline_rule = REPO_ROOT / "skills" / "BASELINE_RULE.md"
    assert baseline_rule.exists(), "Missing shared operator-chosen baseline doctrine"

    rule_text = baseline_rule.read_text(encoding="utf-8")
    for token in (
        "OPERATOR_CHOSEN_BASELINE",
        "baseline_repo_root",
        "baseline_branch",
        "baseline_sha",
        "baseline_status",
        "remote_refresh",
        "git fetch --all --prune",
        "git merge-base --is-ancestor",
        "DIVERGED-STOP",
    ):
        assert token in rule_text, f"BASELINE_RULE.md missing {token}"

    for locale in (Path(), Path("pl")):
        doctrine_link = (
            "../../BASELINE_RULE.md" if locale.parts else "../BASELINE_RULE.md"
        )
        for skill_name in ("vc-scaffold", "vc-dispatch"):
            skill_file = REPO_ROOT / "skills" / locale / skill_name / "SKILL.md"
            text = skill_file.read_text(encoding="utf-8")
            label = skill_file.relative_to(REPO_ROOT)
            frontmatter = text.split("---", 2)[1].lower()
            assert "checkout" in frontmatter, (
                f"{label} description missing checkout trigger"
            )
            assert "baseline" in frontmatter, (
                f"{label} description missing baseline trigger"
            )
            assert "OPERATOR_CHOSEN_BASELINE" in text, (
                f"{label} missing baseline trigger"
            )
            assert doctrine_link in text, f"{label} missing shared doctrine link"
            assert "DIVERGED-STOP" in text, f"{label} missing divergence stop"
            assert "git fetch --all --prune" in text, f"{label} missing remote refresh"

    contract_files = (
        REPO_ROOT / "skills" / "vc-dispatch" / "references" / "prompt-checklist.md",
        REPO_ROOT / "skills" / "vc-scaffold" / "references" / "output-shapes.md",
        REPO_ROOT / "skills" / "vc-scaffold" / "references" / "plan-template.md",
        REPO_ROOT
        / "skills"
        / "pl"
        / "vc-dispatch"
        / "references"
        / "prompt-checklist.md",
        REPO_ROOT / "skills" / "pl" / "vc-scaffold" / "references" / "output-shapes.md",
        REPO_ROOT / "skills" / "pl" / "vc-scaffold" / "references" / "plan-template.md",
    )
    for contract_file in contract_files:
        text = contract_file.read_text(encoding="utf-8")
        label = contract_file.relative_to(REPO_ROOT)
        assert "OPERATOR_CHOSEN_BASELINE" in text, f"{label} missing baseline artifact"
        assert "DIVERGED-STOP" in text, f"{label} missing receiver gate"
