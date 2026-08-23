"""First-run decisions — the product's `[product]` table and the moment it is written.

Four decisions belong to the person who installs Vibecrafted, not to the
package (operator, 2026-08-23, after a 4.2.4 first run that decided all of
them silently):

* ``agents``            which agent runtimes get the skills projection
* ``skills_lang``       which packaged skills set (``en`` | ``pl``)
* ``work_mode``         ``living-tree`` | ``worktrees`` | ``vm`` — how dispatch
                        gives agents a place to work
* ``agent_permissions`` ``ask`` | ``bypass`` — whether spawned agents run with
                        their vendor's skip-permissions / bypass-sandbox flags

They live in ``~/.config/vibecrafted/config.toml`` under ``[product]``, next to
the operator-owned ``[server]`` table. Vibecrafted.app asks for them on the
first launch (or applies an explicit unattended preset and says so); every
later launch re-applies what is recorded here, so an upgrade keeps the
projection current without asking again.

``apply`` is the one entry point: write the table, project the skills, return
a machine-readable summary for the dialog that shows what landed.

𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍. with AI Agents by Vetcoders (c)2024-2026 LibraxisAI
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import tomllib

from vibecrafted_core import agent_view
from vibecrafted_core.server_config import config_path

WORK_MODES: tuple[str, ...] = ("living-tree", "worktrees", "vm")
PERMISSION_MODES: tuple[str, ...] = ("ask", "bypass")
SCHEMA = "vibecrafted.product.v1"
SECTION = "product"
_SECTION_RE = re.compile(r"^\[product\][^\n]*\n(?:(?!\[).*\n?)*", re.MULTILINE)


class FirstRunError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProductDecisions:
    agents: tuple[str, ...]
    skills_lang: str = "en"
    work_mode: str = "living-tree"
    agent_permissions: str = "ask"
    decided_by: str = "operator"  # or "unattended-preset"
    decided_at: str = ""
    version: str = ""

    def validate(self) -> None:
        unknown = [a for a in self.agents if a not in agent_view.AGENT_RUNTIMES]
        if unknown:
            raise FirstRunError(f"unknown agent runtime(s): {', '.join(unknown)}")
        if self.skills_lang not in agent_view.LANGUAGES:
            raise FirstRunError(f"unknown skills_lang {self.skills_lang!r}")
        if self.work_mode not in WORK_MODES:
            raise FirstRunError(f"unknown work_mode {self.work_mode!r}")
        if self.agent_permissions not in PERMISSION_MODES:
            raise FirstRunError(f"unknown agent_permissions {self.agent_permissions!r}")

    def toml(self) -> str:
        agents = ", ".join(json.dumps(a) for a in self.agents)
        return (
            f"[{SECTION}]\n"
            f'schema = "{SCHEMA}"\n'
            f"agents = [{agents}]\n"
            f"skills_lang = {json.dumps(self.skills_lang)}\n"
            f"work_mode = {json.dumps(self.work_mode)}\n"
            f"agent_permissions = {json.dumps(self.agent_permissions)}\n"
            f"decided_by = {json.dumps(self.decided_by)}\n"
            f"decided_at = {json.dumps(self.decided_at)}\n"
            f"version = {json.dumps(self.version)}\n"
        )


def load(path: Path | None = None) -> ProductDecisions | None:
    """The recorded decisions, or None when nothing was decided yet (no file,
    no table). Invalid content raises FirstRunError — a broken table must not
    silently become defaults."""
    resolved = path or config_path()
    try:
        raw = resolved.read_bytes()
    except FileNotFoundError:
        return None
    try:
        payload = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise FirstRunError(f"invalid TOML in {resolved}: {exc}") from exc
    section = payload.get(SECTION)
    if section is None:
        return None
    if not isinstance(section, dict):
        raise FirstRunError(f"[{SECTION}] must be a TOML table")
    agents = section.get("agents", [])
    if not isinstance(agents, list) or not all(isinstance(a, str) for a in agents):
        raise FirstRunError(f"[{SECTION}] agents must be a list of strings")
    decisions = ProductDecisions(
        agents=tuple(agents),
        skills_lang=str(section.get("skills_lang", "en")),
        work_mode=str(section.get("work_mode", "living-tree")),
        agent_permissions=str(section.get("agent_permissions", "ask")),
        decided_by=str(section.get("decided_by", "operator")),
        decided_at=str(section.get("decided_at", "")),
        version=str(section.get("version", "")),
    )
    decisions.validate()
    return decisions


def write(decisions: ProductDecisions, path: Path | None = None) -> Path:
    """Replace (or append) the `[product]` table; every other byte of the file
    — the operator's `[server]` table, comments — stays as it was."""
    decisions.validate()
    resolved = path or config_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    try:
        existing = resolved.read_text(encoding="utf-8")
    except FileNotFoundError:
        existing = ""
    block = decisions.toml()
    if _SECTION_RE.search(existing):
        updated = _SECTION_RE.sub(lambda _m: block + "\n", existing, count=1)
    else:
        separator = (
            ""
            if not existing or existing.endswith("\n\n")
            else ("\n" if existing.endswith("\n") else "\n\n")
        )
        updated = existing + separator + block
    temporary = resolved.with_name(f".{resolved.name}.first-run-{os.getpid()}")
    temporary.write_text(updated.rstrip("\n") + "\n", encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(resolved)
    return resolved


def apply(
    decisions: ProductDecisions,
    *,
    skills_root: Path,
    runtime_home: Path,
    home: Path,
    config: Path | None = None,
) -> dict:
    """Record the decisions and project the skills accordingly. Returns the
    summary the first-run dialog shows: what was written where, what got
    linked for whom, and what is still missing."""
    written = write(decisions, config)
    report = agent_view.project(
        skills_root,
        runtime_home,
        home,
        runtimes=list(decisions.agents),
        lang=decisions.skills_lang,
    )
    per_agent: dict[str, int] = {}
    for label in report.linked + report.current:
        parent = Path(label).parent  # <home>/.<agent>/skills
        agent = parent.parent.name.lstrip(".")
        per_agent[agent] = per_agent.get(agent, 0) + 1
    launcher_bin = home / ".local" / "bin"
    mcp = launcher_bin / "vibecrafted-mcp"
    return {
        "schema": "vibecrafted.first-run-summary.v1",
        "decisions": asdict(decisions),
        "config": str(written),
        "skills": {
            "source": str(
                agent_view.skills_root_for(skills_root, decisions.skills_lang)
            ),
            "per_agent": per_agent,
            "linked": len(report.linked),
            "current": len(report.current),
            "kept": report.kept,
            "errors": report.errors,
        },
        "mcp": {
            "launcher": str(mcp),
            "present": mcp.is_file() and os.access(mcp, os.X_OK),
        },
        "ok": not report.errors,
    }


# ---------------------------------------------------------------------------
# agent_permissions — consumed by spawn / workflow_runtime
# ---------------------------------------------------------------------------

# The vendor flag(s) that make an agent skip its own approval prompts. Used
# only under `agent_permissions = "bypass"`.
_BYPASS_FLAGS: dict[str, tuple[str, ...]] = {
    "claude": ("--dangerously-skip-permissions",),
    "codex": ("--dangerously-bypass-approvals-and-sandbox",),
    "agy": ("--dangerously-skip-permissions",),
    "grok": ("--permission-mode", "bypassPermissions"),
}
_PERMISSIONS_ENV = "VIBECRAFTED_AGENT_PERMISSIONS"
_permissions_cache: dict[str, str] = {}


def agent_permissions_mode(config: Path | None = None) -> str:
    """`ask` | `bypass` for spawned agents.

    Order: VIBECRAFTED_AGENT_PERMISSIONS (a dispatch may override per run),
    then the recorded `[product]` decision. A machine with no decision yet —
    every operator checkout that predates the first-run moment — keeps the
    behaviour those machines were built on, `bypass`; the first run records
    an explicit choice and that choice wins from then on.
    """
    override = os.environ.get(_PERMISSIONS_ENV, "").strip().lower()
    if override in PERMISSION_MODES:
        return override
    key = str(config or "")
    if key not in _permissions_cache:
        try:
            decisions = load(config)
        except FirstRunError:
            decisions = None
        _permissions_cache[key] = (
            decisions.agent_permissions if decisions is not None else "bypass"
        )
    return _permissions_cache[key]


def permission_flags(agent: str, config: Path | None = None) -> list[str]:
    """The flags to splice into `agent`'s argv for the recorded permission
    mode: the vendor's bypass flags under `bypass`, nothing under `ask`."""
    if agent_permissions_mode(config) != "bypass":
        return []
    return list(_BYPASS_FLAGS.get(agent, ()))


def _parse_agents(value: str) -> tuple[str, ...]:
    return tuple(name.strip() for name in value.split(",") if name.strip())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="vibecrafted_core.first_run",
        description="Record the first-run decisions and project the skills.",
    )
    sub = parser.add_subparsers(dest="action", required=True)
    p_apply = sub.add_parser("apply", help="write [product] and project the skills")
    p_apply.add_argument("--agents", required=True, help="comma-separated runtimes")
    p_apply.add_argument("--lang", choices=agent_view.LANGUAGES, default="en")
    p_apply.add_argument("--work-mode", choices=WORK_MODES, default="living-tree")
    p_apply.add_argument("--permissions", choices=PERMISSION_MODES, default="ask")
    p_apply.add_argument(
        "--unattended",
        action="store_true",
        help="record that a preset, not a person, made these decisions",
    )
    p_apply.add_argument("--version", default="")
    p_apply.add_argument("--skills", type=Path, default=None)
    p_apply.add_argument("--runtime-home", type=Path, default=None)
    p_apply.add_argument("--home", type=Path, default=None)
    p_apply.add_argument("--config", type=Path, default=None)
    p_show = sub.add_parser("show", help="print the recorded decisions as JSON")
    p_show.add_argument("--config", type=Path, default=None)
    p_reapply = sub.add_parser(
        "reapply",
        help="project the skills again from the recorded decisions (every launch)",
    )
    p_reapply.add_argument("--skills", type=Path, default=None)
    p_reapply.add_argument("--runtime-home", type=Path, default=None)
    p_reapply.add_argument("--home", type=Path, default=None)
    p_reapply.add_argument("--config", type=Path, default=None)
    args = parser.parse_args(argv)

    if args.action == "show":
        try:
            decisions = load(args.config)
        except FirstRunError as exc:
            print(json.dumps({"error": str(exc)}))
            return 1
        print(json.dumps(asdict(decisions) if decisions else None, indent=2))
        return 0

    home = args.home or Path.home()
    runtime_home = args.runtime_home
    if runtime_home is None:
        explicit = os.environ.get("VIBECRAFTED_RUNTIME_HOME")
        runtime_home = (
            Path(explicit) if explicit else home / ".local" / "share" / "vibecrafted"
        )
    skills = args.skills
    if skills is None:
        root = os.environ.get("VIBECRAFTED_RUNTIME_ROOT")
        if not root:
            parser.error("--skills or VIBECRAFTED_RUNTIME_ROOT is required")
        skills = Path(root) / "vibecrafted-core" / "vibecrafted_core" / "skills"
    if args.action == "reapply":
        try:
            recorded = load(args.config)
        except FirstRunError as exc:
            print(json.dumps({"error": str(exc)}))
            return 2
        if recorded is None:
            print(json.dumps({"error": "no decisions recorded yet"}))
            return 3
        report = agent_view.project(
            skills,
            runtime_home,
            home,
            runtimes=list(recorded.agents),
            lang=recorded.skills_lang,
        )
        print(
            json.dumps(
                {"decisions": asdict(recorded), **report.as_dict()}, sort_keys=True
            )
        )
        return 1 if report.errors else 0

    decisions = ProductDecisions(
        agents=_parse_agents(args.agents),
        skills_lang=args.lang,
        work_mode=args.work_mode,
        agent_permissions=args.permissions,
        decided_by="unattended-preset" if args.unattended else "operator",
        decided_at=datetime.now(UTC).isoformat(timespec="seconds"),
        version=args.version,
    )
    try:
        summary = apply(
            decisions,
            skills_root=skills,
            runtime_home=runtime_home,
            home=home,
            config=args.config,
        )
    except FirstRunError as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
