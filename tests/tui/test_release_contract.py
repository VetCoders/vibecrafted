from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DMG_URL = (
    "https://github.com/vetcoders/vibecrafted/releases/latest/download/Vibecrafted.dmg"
)


def test_public_install_surfaces_point_at_the_single_dmg() -> None:
    surfaces = (
        "README.md",
        "docs/QUICK_START.md",
        "docs/public/getting-started/install.md",
    )
    for relative in surfaces:
        text = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert DMG_URL in text, f"{relative} must point to the unified DMG"
        assert "vc-frame/releases/latest/download/install.sh" not in text


def test_tag_workflow_is_a_read_only_source_gate() -> None:
    workflow = (REPO_ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")

    assert "permissions:\n  contents: read" in workflow
    assert "persist-credentials: false" in workflow
    assert 'test "$(git cat-file -t "$GITHUB_REF_NAME")" = "tag"' in workflow
    assert "run: make unified-product-contract-gate" in workflow
    assert "run: make test-core" in workflow
    assert "run: make semgrep" in workflow
    assert "contents: write" not in workflow
    assert "gh release create" not in workflow
    assert "gh release upload" not in workflow
    assert "install.sh" not in workflow
    assert "vibecrafted-framework.plugin" not in workflow


def test_macos_publisher_cold_verifies_exact_uploaded_bytes() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
    publisher = (REPO_ROOT / "scripts/publish-vibecrafted-release.sh").read_text(
        encoding="utf-8"
    )

    assert "publish-release:" in makefile
    assert "scripts/publish-vibecrafted-release.sh" in makefile
    assert 'DMG="$DIST/Vibecrafted.dmg"' in publisher
    assert 'test "$(uname -s)" = "Darwin"' in publisher
    assert "verify-vibecrafted-walkaround verify-release" in publisher
    assert "verify-vibecrafted-walkaround walkaround" in publisher
    assert 'gh release download "$TAG"' in publisher
    assert 'cmp "$DMG" "$DOWNLOAD_DIR/Vibecrafted.dmg"' in publisher
    assert "xcrun stapler validate" in publisher
    assert "spctl --assess --type open" in publisher
    assert "code-scanning/alerts?state=open&ref=refs/heads/main" in publisher
    assert 'gh release edit "$TAG"' in publisher

    expected_assets = publisher.split('EXPECTED_ASSETS="', 1)[1].split('"', 1)[0]
    assert expected_assets.splitlines() == [
        "Vibecrafted.dmg",
        "release-output.json",
        "release-output.json.sig",
    ]


def test_publisher_writes_the_mandatory_release_report() -> None:
    publisher = (REPO_ROOT / "scripts/publish-vibecrafted-release.sh").read_text(
        encoding="utf-8"
    )
    for heading in (
        "## 1. Security gate",
        "## 2. Exposed surface inventory",
        "## 3. Deployment mode decision",
        "## 4. Post-release install smoke",
        "## Sign-off",
    ):
        assert heading in publisher
    assert ".vibecrafted/artifacts" in publisher
    assert "100.82.232.70:3025" in publisher


def test_vc_release_skill_locks_four_mandatory_report_sections() -> None:
    skill = (REPO_ROOT / "skills/vc-release/SKILL.md").read_text(encoding="utf-8")
    template = REPO_ROOT / "skills/vc-release/references/release-report-template.md"

    assert "## Release Report Contract" in skill
    for required in (
        "**Security gate**",
        "**Exposed surface inventory**",
        "**Deployment mode decision**",
        "**Post-release install smoke**",
    ):
        assert required in skill
    assert "make semgrep" in skill
    assert "references/release-report-template.md" in skill

    template_text = template.read_text(encoding="utf-8")
    for heading in (
        "## 1. Security gate",
        "## 2. Exposed surface inventory",
        "## 3. Deployment mode decision",
        "## 4. Post-release install smoke",
        "## Sign-off",
    ):
        assert heading in template_text
