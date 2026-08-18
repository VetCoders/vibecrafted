"""Consumer-side AICX session chain for Vibecrafted resume.

AICX MCP 0.12.x is retrieval-only (search / read / rank / steer / intents /
index_status). The sessions → extract → continuity chain lives on the CLI.
This module is the vibecrafted-owned contract those MCP tools must satisfy,
plus the resume pack assembler that never auto-attaches a provider session.

Native provider resume happens only when the operator already passed
``--session``. The pack is continuity transport, not a marriage with the
last same-agent match.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

SCHEMA = "vibecrafted.resume.aicx_fallback.v2"
MAX_PACK_CHARS = 48_000

# Expected AICX MCP names. AICX owns the server; this list is the consumer
# contract resume and TUI will call once those tools exist.
MCP_SESSION_CHAIN_TOOLS: tuple[str, ...] = (
    "aicx_sessions",
    "aicx_session_show",
    "aicx_extract",
    "aicx_continuity",
)

# Retrieval tools that must keep working; this cut does not rebuild indexes.
MCP_RETRIEVAL_TOOLS: tuple[str, ...] = (
    "aicx_search",
    "aicx_read",
    "aicx_rank",
    "aicx_steer",
    "aicx_intents",
    "aicx_index_status",
)

EmptyKind = Literal[
    "none",
    "empty_project",
    "missing_filter",
    "bad_project",
]

RECOVER_FORBIDDEN: tuple[str, ...] = (
    "recover previous session",
    "recover session",
    "continue that session",
    "prefer native resume",
    "native resume of that session",
    "resume that session",
    "odzyskaj tamtą sesję",
)


class SessionChainError(Exception):
    """Loud session-chain failure. Never collapse these into scanned=0."""

    def __init__(
        self,
        kind: str,
        message: str,
        *,
        scanned: int = 0,
        matched: int = 0,
        details: Mapping[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.scanned = scanned
        self.matched = matched
        self.details = dict(details or {})

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": False,
            "kind": self.kind,
            "message": self.message,
            "scanned": self.scanned,
            "matched": self.matched,
            "details": self.details,
        }


@dataclass(frozen=True)
class SessionRecord:
    """One session row, same fields as ``aicx sessions list --format json``."""

    session_id: str
    agent: str = ""
    project: str = ""
    repo_path: str = ""
    title: str = ""
    updated_at: str = ""
    source_path: str = ""
    live: bool = False

    @classmethod
    def from_mapping(cls, item: Mapping[str, Any]) -> SessionRecord | None:
        if not isinstance(item, Mapping):
            return None
        session_id = str(item.get("session_id") or item.get("id") or "").strip()
        if not session_id:
            return None
        source = str(item.get("source_path") or "")
        live_flag = item.get("live")
        if isinstance(live_flag, bool):
            live = live_flag
        else:
            live = bool(source) and Path(source).exists()
        return cls(
            session_id=session_id,
            agent=str(item.get("agent") or ""),
            project=str(item.get("project") or ""),
            repo_path=str(item.get("repo_path") or item.get("cwd") or ""),
            title=str(item.get("title") or ""),
            updated_at=str(item.get("updated_at") or item.get("started_at") or ""),
            source_path=source,
            live=live,
        )


@dataclass
class SessionListResult:
    sessions: list[SessionRecord]
    project_filter: str
    empty_kind: EmptyKind
    scanned: int
    matched: int
    warnings: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "project_filter": self.project_filter,
            "empty_kind": self.empty_kind,
            "scanned": self.scanned,
            "matched": self.matched,
            "warnings": list(self.warnings),
            "sessions": [asdict(row) for row in self.sessions],
        }


@dataclass
class ResumePack:
    context_file: Path
    meta_file: Path
    session_id: str
    session_count: int
    mode: Literal["new_session", "native_resume"]
    project_filter: str
    empty_kind: EmptyKind
    degradations: list[str]
    body: str

    def stdout_lines(self) -> list[str]:
        return [
            f"SESSION_ID={self.session_id}",
            f"CONTEXT_FILE={self.context_file}",
            f"SESSION_COUNT={self.session_count}",
            f"MODE={self.mode}",
            f"EMPTY_KIND={self.empty_kind}",
        ]


def project_filter_for_root(root: str | Path) -> str:
    """Cross-org exact repository name: ``/codescribe``, never a bare token."""
    return f"/{Path(root).resolve().name}"


def matches_exact_project(
    record: SessionRecord,
    *,
    root: Path,
    project_filter: str,
) -> bool:
    """Exact identity. ``codescribe`` does not match ``codescribe-rs``."""
    name = root.name.lower()
    token = project_filter.lstrip("/").lower()
    if name and name != token:
        token = name
    if record.repo_path:
        try:
            if Path(record.repo_path).resolve() == root:
                return True
        except OSError:
            pass
        if Path(record.repo_path).name.lower() == token:
            return True
    project = record.project.lower().strip()
    return bool(project) and (project == token or project.endswith("/" + token))


def pack_contains_recover_instruction(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in RECOVER_FORBIDDEN)


def mcp_session_chain_contract() -> dict[str, Any]:
    """Stable consumer contract for the missing AICX MCP session tools."""
    return {
        "schema": "vibecrafted.aicx.session_chain.v1",
        "mcp_tools": list(MCP_SESSION_CHAIN_TOOLS),
        "retrieval_tools_unchanged": list(MCP_RETRIEVAL_TOOLS),
        "required_list_fields": [
            "agent",
            "project",
            "session_id",
            "title",
            "updated_at",
            "live",
        ],
        "project_filter": "exact",
        "empty_with_project": "empty_project",
        "empty_without_project": "missing_filter",
        "unknown_project": "bad_project",
        "native_resume": "only when operator already supplied --session",
        "pack_must_not": list(RECOVER_FORBIDDEN),
        "continuity_sections": [
            "NOW",
            "PEERS",
            "DECISIONS",
            "TASKS",
            "SOURCES",
            "INDEX HEALTH",
        ],
    }


class SessionChain:
    """Transport-agnostic session chain. CLI today; MCP when AICX ships it."""

    def list_sessions(
        self,
        *,
        project: str | None,
        root: Path | None = None,
        agent: str | None = None,
        hours: int = 48,
        limit: int = 40,
    ) -> SessionListResult:
        raise NotImplementedError

    def show_session(self, session_id: str) -> dict[str, Any]:
        raise NotImplementedError

    def extract_session(
        self,
        agent: str,
        session_id: str,
        *,
        conversation: bool = True,
    ) -> str:
        raise NotImplementedError

    def continuity_pack(
        self,
        *,
        project: str,
        hours: int = 48,
        for_inject: bool = True,
    ) -> str:
        raise NotImplementedError


RunFn = Callable[[Sequence[str], float, Path | None], tuple[int, str, str]]


def _default_run(
    cmd: Sequence[str],
    timeout: float,
    cwd: Path | None,
) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            cwd=str(cwd) if cwd is not None else None,
        )
    except FileNotFoundError:
        return 127, "", "not_found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    return proc.returncode, proc.stdout or "", proc.stderr or ""


class CliSessionChain(SessionChain):
    """AICX CLI transport. Used until MCP grows the session-chain tools."""

    def __init__(
        self,
        aicx_bin: str,
        *,
        runner: RunFn | None = None,
    ) -> None:
        self.aicx_bin = aicx_bin
        self._run = runner or _default_run

    def list_sessions(
        self,
        *,
        project: str | None,
        root: Path | None = None,
        agent: str | None = None,
        hours: int = 48,
        limit: int = 40,
    ) -> SessionListResult:
        if project is None:
            return SessionListResult(
                sessions=[],
                project_filter="",
                empty_kind="missing_filter",
                scanned=0,
                matched=0,
                warnings=[
                    (
                        "missing_filter: sessions list without a project filter "
                        "is not a repo answer; pass exact -p /repo or --root"
                    )
                ],
            )

        since = (
            (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours))
            .date()
            .isoformat()
        )
        warnings: list[str] = []
        raw_items: list[dict[str, Any]] = []
        list_attempts: list[tuple[list[str], Path | None]] = []
        if root is not None:
            list_attempts.append((["--cwd"], root))
        list_attempts.append(([], None))

        for flags, cwd in list_attempts:
            cmd = [
                self.aicx_bin,
                "sessions",
                "list",
                "--format",
                "json",
                "--since",
                since,
                "--limit",
                str(limit),
                *flags,
            ]
            if agent:
                cmd.extend(["--agent", agent])
            code, out, err = self._run(cmd, 18, cwd)
            label = "".join(flags) or "_all"
            if code != 0 or not out.strip():
                warnings.append(f"sessions_list{label}:{code}:{(err or out)[:160]}")
                if code not in {0, 124, 127} and "unexpected argument" in (err or ""):
                    raise SessionChainError(
                        "bad_project",
                        f"aicx sessions list rejected filter ({label}): {(err or out)[:240]}",
                        scanned=0,
                        matched=0,
                        details={"stderr": (err or "")[:240]},
                    )
                continue
            try:
                payload = json.loads(out)
            except json.JSONDecodeError:
                warnings.append(f"sessions_list_json_invalid{label}")
                continue
            if isinstance(payload, list) and payload:
                raw_items = [row for row in payload if isinstance(row, dict)]
                if flags == ["--cwd"]:
                    break
            elif isinstance(payload, list):
                raw_items = []
                if flags == ["--cwd"]:
                    break

        records = [
            rec
            for rec in (SessionRecord.from_mapping(item) for item in raw_items)
            if rec is not None
        ]
        scanned = len(records)
        root_path = root.resolve() if root is not None else None
        if root_path is not None:
            filtered = [
                rec
                for rec in records
                if matches_exact_project(rec, root=root_path, project_filter=project)
            ]
        else:
            token = project.lstrip("/").lower()
            filtered = []
            for rec in records:
                proj = rec.project.lower()
                if proj == token or proj.endswith("/" + token):
                    filtered.append(rec)

        empty_kind: EmptyKind = "none"
        if not filtered:
            empty_kind = "empty_project"
            warnings.append(f"empty_project:{project}:scanned={scanned}:matched=0")
        return SessionListResult(
            sessions=filtered,
            project_filter=project,
            empty_kind=empty_kind,
            scanned=scanned,
            matched=len(filtered),
            warnings=warnings,
        )

    def show_session(self, session_id: str) -> dict[str, Any]:
        code, out, err = self._run(
            [
                self.aicx_bin,
                "sessions",
                "show",
                session_id,
                "--format",
                "json",
            ],
            18,
            None,
        )
        if code != 0:
            kind = (
                "ambiguous_id" if "ambiguous" in (err or out).lower() else "not_found"
            )
            if "unsupported" in (err or out).lower():
                kind = "unsupported_source"
            raise SessionChainError(
                kind,
                f"aicx sessions show failed for {session_id!r}: {(err or out)[:240]}",
                details={"stderr": (err or "")[:240], "session_id": session_id},
            )
        try:
            payload = json.loads(out)
        except json.JSONDecodeError as exc:
            raise SessionChainError(
                "unsupported_source",
                f"aicx sessions show returned non-JSON for {session_id!r}",
            ) from exc
        if not isinstance(payload, dict):
            raise SessionChainError(
                "unsupported_source",
                f"aicx sessions show returned {type(payload).__name__}",
            )
        return payload

    def extract_session(
        self,
        agent: str,
        session_id: str,
        *,
        conversation: bool = True,
    ) -> str:
        cmd = [self.aicx_bin, "extract", agent, "--session", session_id]
        if conversation:
            cmd.append("--conversation")
        code, out, err = self._run(cmd, 30, None)
        if code != 0:
            kind = "not_found"
            blob = f"{err} {out}".lower()
            if "ambiguous" in blob:
                kind = "ambiguous_id"
            elif "unsupported" in blob:
                kind = "unsupported_source"
            raise SessionChainError(
                kind,
                f"aicx extract {agent} --session {session_id} failed: {(err or out)[:240]}",
                details={"stderr": (err or "")[:240]},
            )
        return out

    def continuity_pack(
        self,
        *,
        project: str,
        hours: int = 48,
        for_inject: bool = True,
    ) -> str:
        cmd = [
            self.aicx_bin,
            "continuity",
            "show",
            "-p",
            project,
            "-H",
            str(hours),
        ]
        if for_inject:
            cmd.append("--for-inject")
        code, out, err = self._run(cmd, 20, None)
        if code != 0:
            blob = f"{err} {out}".lower()
            kind = "empty_project"
            if "unknown" in blob or "candidate" in blob:
                kind = "bad_project"
            elif "stale" in blob:
                kind = "stale_index"
            raise SessionChainError(
                kind,
                f"aicx continuity show -p {project} failed: {(err or out)[:240]}",
                details={"stderr": (err or "")[:240]},
            )
        return out


def _parse_ts(value: str) -> dt.datetime | None:
    if not value:
        return None
    text = value.replace("Z", "+00:00")
    try:
        stamp = dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    return stamp.astimezone(dt.timezone.utc)


def _in_window(record: SessionRecord, cutoff: dt.datetime) -> bool:
    stamp = _parse_ts(record.updated_at)
    return stamp is None or stamp >= cutoff


def assemble_resume_continuity_pack(
    *,
    agent: str,
    root: Path,
    hours: int,
    context_file: Path,
    meta_file: Path,
    chain: SessionChain,
    operator_session_id: str = "",
    now: dt.datetime | None = None,
) -> ResumePack:
    """Build the resume pack. Never selects native resume on its own."""
    now = now or dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(hours=hours)
    root = root.resolve()
    project_filter = project_filter_for_root(root)
    degradations: list[str] = []

    listing = chain.list_sessions(
        project=project_filter,
        root=root,
        hours=hours,
        limit=40,
    )
    degradations.extend(listing.warnings)
    catalog = [row for row in listing.sessions if _in_window(row, cutoff)]

    continuity_md = ""
    try:
        continuity_md = chain.continuity_pack(
            project=project_filter,
            hours=hours,
            for_inject=True,
        ).strip()
    except SessionChainError as exc:
        degradations.append(f"continuity:{exc.kind}:{exc.message[:160]}")
    except Exception as exc:  # noqa: BLE001 — pack must degrade, not crash resume
        degradations.append(f"continuity:error:{exc!s:.160}")

    intents_md = ""
    if not continuity_md and isinstance(chain, CliSessionChain):
        intents_md = _cli_intents_fallback(
            chain, project_filter, hours, root, degradations
        )

    operator_id = operator_session_id.strip()
    mode: Literal["new_session", "native_resume"] = (
        "native_resume" if operator_id else "new_session"
    )

    lines: list[str] = [
        "# Resume continuity pack",
        "",
        "AICX multi-agent context for this repository and time window.",
        (
            "This pack is continuity transport. It does not select a provider "
            "session and it is not an instruction to attach or recover one."
        ),
        "",
        f"- agent: `{agent}`",
        f"- root: `{root}`",
        f"- aicx_project_filter: `{project_filter}` (cross-org exact repo name)",
        f"- window: last {hours}h across all agents",
        f"- assembled_at: `{now.isoformat()}`",
        (
            f"- session_list_empty: `{listing.empty_kind}` "
            f"(scanned={listing.scanned}, matched={listing.matched})"
        ),
        "- native_resume: only if the operator already passed `--session`",
        f"- mode: `{mode}`",
    ]
    if operator_id:
        lines.append(
            f"- operator_session: `{operator_id}` (explicit `--session`; "
            "pack is background only)"
        )
    else:
        lines.append("- operator_session: none")
    if degradations:
        lines.append("- degradations:")
        for item in degradations:
            lines.append(f"  - `{item}`")

    lines.extend(["", "## Session catalog (evidence, not a picker)", ""])
    if listing.empty_kind == "empty_project":
        lines.append(
            f"_(empty_project: `{project_filter}` has no sessions in this "
            f"window; scanned={listing.scanned}, matched=0. This is not a "
            "parser miss and not a license to use another project's sessions.)_"
        )
    elif listing.empty_kind == "missing_filter":
        lines.append(
            "_(missing_filter: no project identity was supplied; refusing "
            "to treat an unfiltered catalog as this repo.)_"
        )
    elif listing.empty_kind == "bad_project":
        lines.append(
            "_(bad_project: the project filter was rejected. See degradations.)_"
        )
    elif not catalog:
        lines.append("_(no sessions discovered in window)_")
    else:
        lines.append(
            "Rows below are evidence for a new head. They are not launch "
            "targets. Native attach happens only when the operator already "
            "passed `--session`."
        )
        lines.append("")
        lines.append("| agent | session_id | project | live | updated_at | title |")
        lines.append("| --- | --- | --- | --- | --- | --- |")
        for item in catalog[:30]:
            title = str(item.title or "").replace("|", "/").replace("\n", " ")
            if len(title) > 72:
                title = title[:69] + "..."
            lines.append(
                "| {agent} | `{sid}` | {proj} | {live} | {updated} | {title} |".format(
                    agent=item.agent or "?",
                    sid=item.session_id,
                    proj=item.project or "?",
                    live="yes" if item.live else "no",
                    updated=item.updated_at or "?",
                    title=title or "—",
                )
            )

    lines.extend(["", "## Continuity (NOW / PEERS / DECISIONS / TASKS / SOURCES)", ""])
    if continuity_md:
        lines.append(continuity_md[:28_000])
    elif intents_md:
        lines.append(intents_md[:20_000])
    else:
        lines.append("_(continuity unavailable; see degradations)_")

    lines.extend(
        [
            "",
            "## Operator instruction",
            "",
            (
                "Start a **new** provider session in this repository. Use the "
                "catalog and continuity sections as background. Historical "
                "paths and foreign-agent sessions are evidence only — not "
                "launch destinations."
            ),
            (
                "Native provider attach requires an explicit operator `--session`. "
                "This pack is not that signal."
            ),
            (
                "Re-read files before editing (Living Tree). Prefer runtime "
                "truth over remembered state."
            ),
            "",
        ]
    )

    body = "\n".join(lines)
    if pack_contains_recover_instruction(body):
        raise RuntimeError("resume pack assembler emitted a recover instruction")
    if len(body) > MAX_PACK_CHARS:
        body = (
            body[: MAX_PACK_CHARS - 80] + "\n\n_(truncated for resume pack budget)_\n"
        )

    context_file.parent.mkdir(parents=True, exist_ok=True)
    context_file.write_text(body, encoding="utf-8")
    meta = {
        "schema": SCHEMA,
        "agent": agent,
        "root": str(root),
        "hours": hours,
        "session_id": operator_id,
        "session_count": len(catalog),
        "mode": mode,
        "empty_kind": listing.empty_kind,
        "scanned": listing.scanned,
        "matched": listing.matched,
        "project_filter": project_filter,
        "context_file": str(context_file),
        "degradations": degradations,
    }
    meta_file.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    return ResumePack(
        context_file=context_file,
        meta_file=meta_file,
        session_id=operator_id,
        session_count=len(catalog),
        mode=mode,
        project_filter=project_filter,
        empty_kind=listing.empty_kind,
        degradations=degradations,
        body=body,
    )


def _cli_intents_fallback(
    chain: CliSessionChain,
    project_filter: str,
    hours: int,
    root: Path,
    degradations: list[str],
) -> str:
    code, out, err = chain._run(
        [
            chain.aicx_bin,
            "tail",
            "-H",
            str(hours),
            "--limit",
            "20",
            "-p",
            project_filter,
        ],
        12,
        None,
    )
    if code == 0 and out.strip():
        return out.strip()
    degradations.append(f"tail:{code}:{(err or out)[:160]}")
    code, out, err = chain._run(
        [
            chain.aicx_bin,
            "intents",
            "-H",
            str(hours),
            "--limit",
            "15",
            "--emit",
            "markdown",
            "-p",
            project_filter,
        ],
        12,
        None,
    )
    if code == 0 and out.strip():
        return out.strip()
    degradations.append(f"intents:{code}:{(err or out)[:160]}")
    code, out, err = chain._run(
        [chain.aicx_bin, "overlay", "--repo", str(root), "--format", "json"],
        8,
        None,
    )
    if code == 0 and out.strip():
        return out[:8_000]
    degradations.append(f"overlay:{code}:{(err or out)[:160]}")
    return ""


def _resume_pack_main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vibecrafted_core.aicx_session_chain")
    parser.add_argument("command", choices=["resume-pack", "contract"])
    parser.add_argument("--agent", default="")
    parser.add_argument("--root", default="")
    parser.add_argument("--hours", type=int, default=48)
    parser.add_argument("--aicx", default="")
    parser.add_argument("--context-file", default="")
    parser.add_argument("--meta-file", default="")
    parser.add_argument("--operator-session", default="")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if args.command == "contract":
        sys.stdout.write(json.dumps(mcp_session_chain_contract(), indent=2) + "\n")
        return 0

    if not args.agent or not args.root or not args.aicx:
        print("resume-pack requires --agent --root --aicx", file=sys.stderr)
        return 2
    root = Path(args.root)
    context_file = (
        Path(args.context_file)
        if args.context_file
        else Path(f"resume-aicx-{args.agent}.md")
    )
    meta_file = (
        Path(args.meta_file)
        if args.meta_file
        else Path(str(context_file) + ".meta.json")
    )
    pack = assemble_resume_continuity_pack(
        agent=args.agent,
        root=root,
        hours=args.hours,
        context_file=context_file,
        meta_file=meta_file,
        chain=CliSessionChain(args.aicx),
        operator_session_id=args.operator_session,
    )
    for line in pack.stdout_lines():
        print(line)
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    return _resume_pack_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
