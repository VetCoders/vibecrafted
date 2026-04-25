from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PROMISE = "release engine for ai-built software"
TAGLINE = "ship ai-built software without the vibe hangover"
PRIMARY_CTA = "curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui"
SECONDARY_CTA = "curl -fsSL https://vibecrafted.io/install.sh | bash"
TRUST_PROMISE = "explains what it will do and asks before proceeding"

EXPECTED_COPY = {
    "README.md": (PROMISE, TAGLINE, PRIMARY_CTA, SECONDARY_CTA, TRUST_PROMISE),
    "docs/MARKETPLACE_LISTING.md": (PROMISE,),
    "docs/QUICK_START.md": (PRIMARY_CTA, SECONDARY_CTA, TRUST_PROMISE),
    "docs/RELEASE_KICKOFF.md": (PROMISE, PRIMARY_CTA, SECONDARY_CTA),
    "docs/SUBMISSION_FORMS.md": (PROMISE, PRIMARY_CTA, SECONDARY_CTA),
    "docs/installer/SCAFFOLD.md": (PROMISE, PRIMARY_CTA, SECONDARY_CTA),
}


def test_quick_start_keeps_public_gui_cta_before_compact_path() -> None:
    text = (REPO_ROOT / "docs/QUICK_START.md").read_text(encoding="utf-8")

    primary_heading = text.index("Browser-guided path for the human kickoff")
    primary_index = text.index(PRIMARY_CTA, primary_heading)
    compact_heading = text.index("Compact path for scripting or terminal-only installs")
    compact_index = text.index(SECONDARY_CTA, compact_heading)

    assert primary_index < compact_index


def test_release_contract_stays_polarized_across_public_surfaces() -> None:
    errors: list[str] = []

    for relative_path, expected_strings in EXPECTED_COPY.items():
        text = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        normalized = text.casefold()
        for expected in expected_strings:
            haystack = normalized if expected in {PROMISE, TAGLINE} else text
            if expected not in haystack:
                errors.append(f"{relative_path} missing: {expected}")

    assert not errors, "\n".join(errors)


def test_installer_reference_keeps_public_gui_and_local_shell_contract() -> None:
    reference = (REPO_ROOT / "docs/installer/REFERENCE.md").read_text(encoding="utf-8")
    scaffold = (REPO_ROOT / "docs/installer/SCAFFOLD.md").read_text(encoding="utf-8")
    normalized = reference.casefold()

    for expected in (
        "twinsweep",
        "rmcp-memex",
        "one-page wizard",
        "progress dots",
        "no page scroll",
    ):
        assert expected in normalized

    for text in (reference, scaffold):
        assert "Local terminal-native entrypoint: `make vibecrafted`" in text
        assert "Local browser GUI entrypoint: `make wizard`" in text

    assert f"Public compact path: `{SECONDARY_CTA}`" in reference
    assert (
        "`make vibecrafted`\n  Runs the terminal-native installer wizard from a local checkout."
        in reference
    )
    assert (
        "`make wizard` / `make gui-install`\n  Open the browser-guided installer from a local checkout when you want the GUI surface."
        in reference
    )


def test_release_archive_preserves_bundled_tool_slot() -> None:
    release_workflow = (REPO_ROOT / ".github" / "workflows" / "release.yml").read_text(
        encoding="utf-8"
    )
    tools_readme = (REPO_ROOT / "tools" / "bin" / "README.md").read_text(
        encoding="utf-8"
    )

    assert "tar -czf" in release_workflow
    assert "--exclude='./tools/bin'" not in release_workflow
    assert "$SOURCE/tools/bin/<os>-<arch>" in tools_readme


def test_vc_release_skill_locks_four_mandatory_report_sections() -> None:
    skill = (REPO_ROOT / "skills/vc-release/SKILL.md").read_text(encoding="utf-8")

    assert "## Release Report Contract" in skill, (
        "vc-release SKILL.md must keep the Release Report Contract section"
    )
    for required in (
        "**Security gate**",
        "**Exposed surface inventory**",
        "**Deployment mode decision**",
        "**Post-release install smoke**",
    ):
        assert required in skill, (
            f"vc-release SKILL.md missing mandatory item: {required}"
        )

    assert "make semgrep" in skill, (
        "Semgrep gate must reference the canonical make target"
    )
    assert "references/release-report-template.md" in skill, (
        "vc-release SKILL.md must link to the release report template"
    )

    template = REPO_ROOT / "skills/vc-release/references/release-report-template.md"
    assert template.is_file(), "release report template must exist"
    template_text = template.read_text(encoding="utf-8")
    for heading in (
        "## 1. Security gate",
        "## 2. Exposed surface inventory",
        "## 3. Deployment mode decision",
        "## 4. Post-release install smoke",
        "## Sign-off",
    ):
        assert heading in template_text, f"release report template missing: {heading}"


def test_deployment_reality_documents_exposed_surface_inventory() -> None:
    text = (REPO_ROOT / "skills/vc-release/references/deployment-reality.md").read_text(
        encoding="utf-8"
    )

    assert "## Exposed Surface Inventory" in text, (
        "deployment-reality.md must carry the Exposed Surface Inventory section"
    )
    for required_token in (
        "Bind address",
        "Proxy in front",
        "TLS terminator",
        "Auth boundary",
        "Edge headers",
        "Secret materialization",
    ):
        assert required_token in text, (
            f"deployment-reality.md inventory missing token: {required_token}"
        )
