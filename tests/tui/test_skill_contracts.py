from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

FLEET_IMPERATIVE_START = "<!-- fleet-imperative: v1 -->"
FLEET_IMPERATIVE_END = "<!-- /fleet-imperative -->"
FLEET_EXCEPTION_START = "<!-- fleet-imperative-exception: v1 -->"
FLEET_EXCEPTION_END = "<!-- /fleet-imperative-exception -->"


def test_vc_skills_preserve_init_and_loctree_orientation_contract() -> None:
    skill_files = sorted((REPO_ROOT / "skills").glob("vc-*/SKILL.md"))
    assert skill_files, "No vc-* skill files discovered"

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


def test_vc_skills_carry_fleet_imperative_block() -> None:
    """Every /vc-* invocation means dispatching the external fleet — never a no-op.

    The sole carve-out is vc-delegate (native in-process subagents). The block is
    the structural guarantee; this gate keeps it from regressing into prose an
    agent can absorb without acting.
    """
    skill_files = sorted((REPO_ROOT / "skills").glob("vc-*/SKILL.md"))
    assert skill_files, "No vc-* skill files discovered"

    failures: list[str] = []
    for skill_file in skill_files:
        rel = skill_file.relative_to(REPO_ROOT)
        text = skill_file.read_text(encoding="utf-8")

        if skill_file.parent.name == "vc-delegate":
            if FLEET_EXCEPTION_START not in text or FLEET_EXCEPTION_END not in text:
                failures.append(f"{rel} missing fleet-imperative exception carve-out")
                continue
            if FLEET_IMPERATIVE_START in text:
                failures.append(
                    f"{rel} must NOT carry the regular fleet-imperative block"
                )
            carve_out = text.split(FLEET_EXCEPTION_START, 1)[1].split(
                FLEET_EXCEPTION_END, 1
            )[0]
            for needle in ("THE exception", "NOT the external", "in-process"):
                if needle not in carve_out:
                    failures.append(
                        f"{rel} exception carve-out missing phrase: {needle!r}"
                    )
            continue

        if FLEET_IMPERATIVE_START not in text or FLEET_IMPERATIVE_END not in text:
            failures.append(f"{rel} missing fleet-imperative block")
            continue
        first_heading = text.find("\n# ")
        if first_heading != -1 and text.index(FLEET_IMPERATIVE_START) > first_heading:
            failures.append(
                f"{rel} fleet-imperative block is not at the top (before the H1)"
            )
        block = text.split(FLEET_IMPERATIVE_START, 1)[1].split(FLEET_IMPERATIVE_END, 1)[
            0
        ]
        for needle in (
            "DISPATCHING THE",
            "`vibecrafted <workflow> <agent>`",
            "not a no-op",
            "native in-process subagents",
            "STOP and dispatch through the launcher",
            "`vc-delegate`",
        ):
            if needle not in block:
                failures.append(
                    f"{rel} fleet-imperative block missing phrase: {needle!r}"
                )

    assert not failures, "\n".join(failures)
