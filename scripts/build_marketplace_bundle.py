#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

try:
    from vetcoders_install import discover_skills
except ModuleNotFoundError:  # pragma: no cover - import path depends on entrypoint
    from scripts.vetcoders_install import discover_skills

OUTPUT_FILENAME = "vibecrafted-framework.plugin"
PLUGIN_NAME = "vibecrafted-framework"
FIXED_ZIP_DATE_TIME = (2026, 3, 30, 0, 0, 0)
DEFAULT_FILE_MODE = 0o100644
IGNORED_PATH_PARTS = {".DS_Store", "__pycache__", ".pytest_cache"}


@dataclass(frozen=True)
class ListingMetadata:
    description: str
    keywords: tuple[str, ...]
    homepage: str
    repository: str
    documentation: str
    faq: str
    license: str


REPO_ROOT = Path(__file__).resolve().parent.parent


def read_version(repo_root: Path) -> str:
    return (repo_root / "VERSION").read_text(encoding="utf-8").strip()


def parse_listing_metadata(text: str) -> ListingMetadata:
    in_registry_section = False
    values: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if line.strip() in {"## Registry Metadata", "## Registry Metadata Draft"}:
            in_registry_section = True
            continue
        if not in_registry_section:
            continue
        if line.startswith("## "):
            break
        match = re.match(r"-\s+([a-z]+):\s*(.+)", line)
        if match:
            values[match.group(1)] = match.group(2).strip()

    required = {
        "description",
        "keywords",
        "homepage",
        "repository",
        "documentation",
        "faq",
        "license",
    }
    missing = sorted(required - values.keys())
    if missing:
        raise ValueError(
            f"Missing registry metadata in docs/MARKETPLACE_LISTING.md: {', '.join(missing)}"
        )

    keywords = tuple(
        keyword.strip() for keyword in values["keywords"].split(",") if keyword.strip()
    )
    return ListingMetadata(
        description=values["description"],
        keywords=keywords,
        homepage=values["homepage"],
        repository=values["repository"],
        documentation=values["documentation"],
        faq=values["faq"],
        license=values["license"],
    )


def load_listing_metadata(repo_root: Path) -> ListingMetadata:
    listing_path = repo_root / "docs" / "MARKETPLACE_LISTING.md"
    return parse_listing_metadata(listing_path.read_text(encoding="utf-8"))


def discover_bundle_skills(repo_root: Path) -> list[Path]:
    return sorted(
        (skill for skill in discover_skills(repo_root) if skill.name.startswith("vc-")),
        key=lambda path: path.name,
    )


def should_skip_path(path: Path) -> bool:
    if path.name.endswith(".pyc"):
        return True
    return any(part in IGNORED_PATH_PARTS for part in path.parts)


def iter_skill_files(skill_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in skill_dir.rglob("*")
            if path.is_file() and not should_skip_path(path.relative_to(skill_dir))
        ),
        key=lambda path: path.relative_to(skill_dir).as_posix(),
    )


def plugin_manifest(version: str, metadata: ListingMetadata) -> dict[str, object]:
    return {
        "name": PLUGIN_NAME,
        "version": version,
        "description": metadata.description,
        "author": {
            "name": "VetCoders",
            "email": "hello@vetcoders.io",
        },
        "homepage": metadata.homepage,
        "repository": metadata.repository,
        "license": metadata.license,
        "keywords": list(metadata.keywords),
    }


def mcp_config() -> dict[str, object]:
    return {
        "mcpServers": {
            "loctree": {
                "command": "loctree-mcp",
                "args": [],
                "env": {},
            }
        }
    }


def write_zip_entry(
    bundle: zipfile.ZipFile, arcname: str, data: bytes, mode: int
) -> None:
    info = zipfile.ZipInfo(arcname, FIXED_ZIP_DATE_TIME)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 3
    info.external_attr = (mode & 0xFFFF) << 16
    bundle.writestr(info, data)


def build_bundle_bytes(repo_root: Path) -> bytes:
    version = read_version(repo_root)
    metadata = load_listing_metadata(repo_root)
    listing_path = repo_root / "docs" / "MARKETPLACE_LISTING.md"

    generated_files = {
        ".claude-plugin/plugin.json": json.dumps(
            plugin_manifest(version, metadata), indent=2
        )
        + "\n",
        ".mcp.json": json.dumps(mcp_config(), indent=2) + "\n",
        "README.md": listing_path.read_text(encoding="utf-8").rstrip() + "\n",
        "LICENSE": (repo_root / "LICENSE").read_text(encoding="utf-8").rstrip() + "\n",
        "VERSION": version + "\n",
        "docs/QUICK_START.md": (repo_root / "docs" / "QUICK_START.md")
        .read_text(encoding="utf-8")
        .rstrip()
        + "\n",
        "docs/FAQ.md": (repo_root / "docs" / "FAQ.md")
        .read_text(encoding="utf-8")
        .rstrip()
        + "\n",
    }

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for arcname, text in generated_files.items():
            write_zip_entry(
                bundle,
                arcname,
                text.encode("utf-8"),
                DEFAULT_FILE_MODE,
            )

        for skill_dir in discover_bundle_skills(repo_root):
            for source_file in iter_skill_files(skill_dir):
                relative = source_file.relative_to(skill_dir).as_posix()
                arcname = f"skills/{skill_dir.name}/{relative}"
                write_zip_entry(
                    bundle,
                    arcname,
                    source_file.read_bytes(),
                    source_file.stat().st_mode,
                )

    return buffer.getvalue()


def write_bundle(repo_root: Path, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(build_bundle_bytes(repo_root))


def check_bundle(repo_root: Path, output_path: Path) -> int:
    expected = build_bundle_bytes(repo_root)
    if not output_path.exists():
        print(f"Marketplace bundle missing at {output_path}")
        print("Run: python3 scripts/build_marketplace_bundle.py")
        return 1

    actual = output_path.read_bytes()
    if actual != expected:
        print(f"Marketplace bundle drift detected at {output_path}")
        print("Run: python3 scripts/build_marketplace_bundle.py")
        return 1

    print(
        f"Marketplace bundle is current: {output_path} ({len(discover_bundle_skills(repo_root))} skills)"
    )
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. marketplace bundle from current repo state."
    )
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / OUTPUT_FILENAME),
        help="Path to the .plugin zip to write or validate.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if the existing bundle does not match the current repo state.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output_path = Path(args.output).expanduser().resolve()

    if args.check:
        return check_bundle(REPO_ROOT, output_path)

    write_bundle(REPO_ROOT, output_path)
    print(
        f"Built {output_path} from 𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. {read_version(REPO_ROOT)} "
        f"with {len(discover_bundle_skills(REPO_ROOT))} current skills."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
