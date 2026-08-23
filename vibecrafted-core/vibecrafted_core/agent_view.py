"""Agent view — project the packaged skills into the directories agents read.

The DMG publishes a runtime generation under ``<runtime_home>/releases/<version>``
and nothing else; agents never look there. Claude reads ``~/.claude/skills``,
Codex ``~/.codex/skills``, the cross-agent canon ``~/.agents/skills`` — so a
first run of Vibecrafted.app that stops at hydration leaves every agent with
no ``vc-*`` skill at all (measured on 4.2.4, 2026-08-23: Codex answered
"$vc-ship is not available").

This module is the one projection both front doors share: Vibecrafted.app
calls it after every hydration, the installer may call it instead of its own
symlink walk. Contract:

* Only names the package owns are touched: ``vc-*`` skill directories and the
  canon files shipped next to them (``LIVING_TREE_RULE.md`` & co). An entry
  of any other name — an operator's private skill, a vendor skill — is never
  read, replaced or removed.
* A projection is a symlink into a Vibecrafted runtime generation. An entry
  with an owned name that is NOT such a symlink (a real directory, a link
  elsewhere) is left alone and reported as ``kept``: the operator put it there.
* ``remove`` deletes only those projections, so uninstalling a generation
  cannot take a private skill with it.
* ``~/.agents/skills`` is always projected; a runtime directory
  (``~/.claude``, ``~/.codex``, …) only when it already exists — the presence
  of the agent's home is the agent's opt-in.

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Agent homes whose ``skills/`` directory is a projection target when the home
# exists. ``agents`` is the cross-agent canon and is always projected.
AGENT_RUNTIMES: tuple[str, ...] = ("claude", "codex", "gemini", "agy", "junie", "grok")
CANON_RUNTIME = "agents"

# Package-owned names besides ``vc-*``: the doctrine files agents load on
# session start. Everything else in the skills root (``_template``, ``pl``,
# ``vibecraftsmanship``) is either internal or a projection the legacy
# installer made; listed explicitly so the set is reviewable.
CANON_FILES: tuple[str, ...] = (
    "LIVING_TREE_RULE.md",
    "VERIFICATION_RULE.md",
    "DELEGATION_MATRIX.md",
    "RUNTIME_FEEDBACK.md",
    "FOUNDATION_RULE.md",
)
EXTRA_SKILL_DIRS: tuple[str, ...] = ("vibecraftsmanship",)


def owned_name(name: str) -> bool:
    """Whether ``name`` is one this package projects (and may therefore replace)."""
    return name.startswith("vc-") or name in CANON_FILES or name in EXTRA_SKILL_DIRS


def packaged_entries(skills_root: Path) -> list[Path]:
    """The entries under ``skills_root`` that get projected, sorted by name."""
    if not skills_root.is_dir():
        return []
    return sorted(
        entry
        for entry in skills_root.iterdir()
        if owned_name(entry.name)
        and ((entry.is_dir() and entry.name != "_template") or entry.is_file())
    )


def is_projection(link: Path, runtime_home: Path) -> bool:
    """A symlink whose target lives under a Vibecrafted runtime generation."""
    if not link.is_symlink():
        return False
    try:
        target = Path(os.readlink(link))
    except OSError:
        return False
    if not target.is_absolute():
        target = (link.parent / target).resolve()
    releases = (runtime_home / "releases").resolve()
    try:
        return target.resolve().is_relative_to(releases) or target.is_relative_to(
            releases
        )
    except (OSError, ValueError):
        return False


LANGUAGES: tuple[str, ...] = ("en", "pl")


def skills_root_for(skills_root: Path, lang: str) -> Path:
    """The packaged skills set for ``lang``: English is the root itself, every
    other language a mirror directory of the same names under it."""
    if lang not in LANGUAGES:
        raise ValueError(
            f"unknown skills language {lang!r}; known: {', '.join(LANGUAGES)}"
        )
    return skills_root if lang == "en" else skills_root / lang


def detected_runtimes(
    home: Path, runtimes: tuple[str, ...] = AGENT_RUNTIMES
) -> list[str]:
    """Runtimes whose home directory exists — the agent's own opt-in."""
    return [runtime for runtime in runtimes if (home / f".{runtime}").is_dir()]


def target_dirs(home: Path, runtimes: list[str] | None = None) -> list[Path]:
    """``~/.agents/skills`` plus ``~/.<runtime>/skills`` for the chosen runtimes
    (default: every runtime whose home exists)."""
    chosen = detected_runtimes(home) if runtimes is None else list(runtimes)
    dirs = [home / f".{CANON_RUNTIME}" / "skills"]
    for runtime in chosen:
        if runtime == CANON_RUNTIME:
            continue
        dirs.append(home / f".{runtime}" / "skills")
    return dirs


@dataclass
class Report:
    linked: list[str] = field(default_factory=list)
    current: list[str] = field(default_factory=list)
    kept: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, list[str]]:
        return {
            "linked": self.linked,
            "current": self.current,
            "kept": self.kept,
            "removed": self.removed,
            "errors": self.errors,
        }


def project(
    skills_root: Path,
    runtime_home: Path,
    home: Path,
    *,
    runtimes: list[str] | None = None,
    lang: str = "en",
    report: Report | None = None,
) -> Report:
    """Symlink every packaged entry (of ``lang``) into every target directory.

    Existing projections (links into ``releases/``) are repointed to this
    generation — so switching language or version is the same operation;
    anything else under an owned name is kept untouched.
    """
    report = report or Report()
    source = skills_root_for(skills_root, lang)
    entries = packaged_entries(source)
    if not entries:
        report.errors.append(f"no packaged skills under {source}")
        return report
    for target_dir in target_dirs(home, runtimes):
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            report.errors.append(f"{target_dir}: {exc}")
            continue
        for entry in entries:
            link = target_dir / entry.name
            label = f"{target_dir}/{entry.name}"
            if link.is_symlink():
                if not is_projection(link, runtime_home):
                    report.kept.append(label)
                    continue
                if os.readlink(link) == str(entry):
                    report.current.append(label)
                    continue
                try:
                    link.unlink()
                except OSError as exc:
                    report.errors.append(f"{label}: {exc}")
                    continue
            elif link.exists():
                report.kept.append(label)
                continue
            try:
                link.symlink_to(entry)
                report.linked.append(label)
            except OSError as exc:
                report.errors.append(f"{label}: {exc}")
    return report


def remove(
    runtime_home: Path,
    home: Path,
    *,
    runtimes: list[str] | None = None,
    report: Report | None = None,
) -> Report:
    """Delete every projection (link into ``releases/``) under an owned name."""
    report = report or Report()
    for target_dir in target_dirs(home, runtimes):
        if not target_dir.is_dir():
            continue
        for link in sorted(target_dir.iterdir()):
            if not owned_name(link.name):
                continue
            if not is_projection(link, runtime_home):
                if link.is_symlink() or link.exists():
                    report.kept.append(f"{target_dir}/{link.name}")
                continue
            try:
                link.unlink()
                report.removed.append(f"{target_dir}/{link.name}")
            except OSError as exc:
                report.errors.append(f"{target_dir}/{link.name}: {exc}")
    return report


def _default_runtime_home() -> Path:
    explicit = os.environ.get("VIBECRAFTED_RUNTIME_HOME")
    if explicit:
        return Path(explicit)
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "vibecrafted"
    return Path.home() / ".local" / "share" / "vibecrafted"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vibecrafted_core.agent_view",
        description="Project packaged vc-* skills into the agents' skills directories.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    p_project = sub.add_parser(
        "project", help="link this generation's skills (default)"
    )
    p_project.add_argument(
        "--skills",
        type=Path,
        default=None,
        help="packaged skills root (default: <VIBECRAFTED_RUNTIME_ROOT>/vibecrafted-core/vibecrafted_core/skills)",
    )
    p_project.add_argument(
        "--lang",
        choices=LANGUAGES,
        default="en",
        help="which packaged skills set to project (default: en)",
    )
    p_remove = sub.add_parser(
        "remove", help="delete every projection; private skills stay"
    )
    p_detect = sub.add_parser(
        "detect", help="print the agent runtimes present on this machine, one per line"
    )
    for p in (p_project, p_remove):
        p.add_argument(
            "--runtimes",
            default=None,
            help="comma-separated agent runtimes to project into (default: every "
            f"runtime whose home exists; known: {', '.join(AGENT_RUNTIMES)})",
        )
    for p in (p_project, p_remove, p_detect):
        p.add_argument("--runtime-home", type=Path, default=None)
        p.add_argument("--home", type=Path, default=None)
        p.add_argument("--json", action="store_true", help="machine-readable report")
    args = parser.parse_args(argv)

    home = args.home or Path.home()
    if args.action == "detect":
        found = detected_runtimes(home)
        print(json.dumps(found) if args.json else "\n".join(found))
        return 0

    runtime_home = args.runtime_home or _default_runtime_home()
    runtimes: list[str] | None = None
    if args.runtimes is not None:
        runtimes = [name.strip() for name in args.runtimes.split(",") if name.strip()]
        unknown = [name for name in runtimes if name not in AGENT_RUNTIMES]
        if unknown:
            parser.error(f"unknown runtime(s): {', '.join(unknown)}")
    if args.action == "project":
        skills = args.skills
        if skills is None:
            root = os.environ.get("VIBECRAFTED_RUNTIME_ROOT")
            if not root:
                parser.error("--skills or VIBECRAFTED_RUNTIME_ROOT is required")
            skills = Path(root) / "vibecrafted-core" / "vibecrafted_core" / "skills"
        report = project(skills, runtime_home, home, runtimes=runtimes, lang=args.lang)
    else:
        report = remove(runtime_home, home, runtimes=runtimes)

    if args.json:
        print(json.dumps(report.as_dict(), indent=2, sort_keys=True))
    else:
        for key in ("linked", "removed", "kept", "errors"):
            for item in getattr(report, key):
                print(f"{key}: {item}")
        print(
            f"agent view: {len(report.linked)} linked, {len(report.current)} current, "
            f"{len(report.kept)} kept, {len(report.removed)} removed, "
            f"{len(report.errors)} errors"
        )
    return 1 if report.errors else 0


if __name__ == "__main__":
    sys.exit(main())
