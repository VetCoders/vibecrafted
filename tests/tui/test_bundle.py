import json
import zipfile
from pathlib import Path

from scripts import build_marketplace_bundle as bundle


def test_parse_listing_metadata_reads_current_registry_fields() -> None:
    text = (bundle.REPO_ROOT / "docs" / "MARKETPLACE_LISTING.md").read_text(
        encoding="utf-8"
    )

    metadata = bundle.parse_listing_metadata(text)

    assert metadata.homepage == "https://vibecrafted.io/"
    assert metadata.repository == "https://github.com/VetCoders/vibecrafted"
    assert metadata.documentation == "https://vibecrafted.io/en/quickstart/"
    assert metadata.faq == "https://vibecrafted.io/en/faq/"
    assert metadata.license.startswith("Business Source License 1.1")
    assert "codex" in metadata.keywords


def test_discover_bundle_skills_tracks_live_skill_surface() -> None:
    skill_names = [
        skill.name for skill in bundle.discover_bundle_skills(bundle.REPO_ROOT)
    ]

    assert "vc-implement" in skill_names
    assert "vc-justdo" in skill_names  # legacy alias kept in bundle
    assert "vc-marbles" in skill_names
    assert "vc-ship" not in skill_names
    assert "vc-ownership" in skill_names
    assert "vc-screenscribe" not in skill_names


def test_top_level_skill_dirs_are_live_skills_or_foundations() -> None:
    allowed_non_skill_dirs = {"foundations"}
    offenders: list[str] = []

    for path in sorted((bundle.REPO_ROOT / "skills").iterdir()):
        if not path.is_dir() or path.name in allowed_non_skill_dirs:
            continue

        missing = [
            marker
            for marker in ("SKILL.md", "FLOW.md")
            if not (path / marker).is_file()
        ]
        if missing:
            offenders.append(
                f"{path.relative_to(bundle.REPO_ROOT)} missing {', '.join(missing)}"
            )

    assert not offenders, "\n".join(offenders)


def test_write_bundle_uses_current_metadata_and_skill_inventory(tmp_path: Path) -> None:
    output_path = tmp_path / bundle.OUTPUT_FILENAME

    bundle.write_bundle(bundle.REPO_ROOT, output_path)

    with zipfile.ZipFile(output_path) as archive:
        manifest = json.loads(archive.read(".claude-plugin/plugin.json"))
        members = set(archive.namelist())

    assert manifest["version"] == bundle.read_version(bundle.REPO_ROOT)
    assert manifest["license"] != "MIT"
    assert "skills/vc-implement/SKILL.md" in members
    assert "skills/vc-justdo/SKILL.md" in members  # legacy alias kept in bundle
    assert "skills/vc-marbles/SKILL.md" in members
    assert "skills/vc-ship/SKILL.md" not in members
    assert "skills/vc-ownership/SKILL.md" in members
    assert "skills/vc-screenscribe/SKILL.md" not in members
    assert "docs/RELEASE_KICKOFF.md" in members
    assert "docs/SUBMISSION_FORMS.md" in members


def test_framework_playground_uses_vibecrafted_command_deck() -> None:
    text = (bundle.REPO_ROOT / "docs" / "presence" / "framework.js").read_text(
        encoding="utf-8"
    )

    assert "vibecrafted scaffold claude" in text
    assert "vibecrafted partner claude" in text
    assert "vibecrafted marbles codex --count " in text
    assert "return 'vc-' + phaseDef.name;" not in text
