from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

PROMISE = "release engine for ai-built software"
TAGLINE = "ship ai-built software without the vibe hangover"
PRIMARY_CTA = "curl -fsSL https://vibecrafted.io/install.sh | bash -s -- --gui"
SECONDARY_CTA = "curl -fsSL https://vibecrafted.io/install.sh | bash"

EXPECTED_COPY = {
    "README.md": (PROMISE, TAGLINE, PRIMARY_CTA, SECONDARY_CTA),
    "docs/MARKETPLACE_LISTING.md": (PROMISE,),
    "docs/QUICK_START.md": (PRIMARY_CTA, SECONDARY_CTA),
    "docs/RELEASE_KICKOFF.md": (PROMISE, PRIMARY_CTA, SECONDARY_CTA),
    "docs/SUBMISSION_FORMS.md": (PROMISE, PRIMARY_CTA, SECONDARY_CTA),
    "docs/installer/SCAFFOLD.md": (PROMISE, PRIMARY_CTA, SECONDARY_CTA),
}


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


def test_installer_reference_stays_gui_first_and_mock_aligned() -> None:
    text = (REPO_ROOT / "docs/installer/REFERENCE.md").read_text(encoding="utf-8")
    normalized = text.casefold()

    for expected in (
        "twinsweep",
        "rmcp-memex",
        "one-page wizard",
        "progress dots",
        "no page scroll",
    ):
        assert expected in normalized
