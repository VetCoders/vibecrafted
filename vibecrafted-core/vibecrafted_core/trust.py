"""vc-trust journal and settlement helper.

The agent skill owns falsification. This module only provides durable,
deterministic mechanics: enumerate candidate commits, append one structured
verdict, project that verdict onto the existing settlement axis, and wait for a
run boundary without inventing a second monitor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import control_plane
from .settlement import (
    Settlement,
    SettlementVerdict,
    persist_settlement_to_meta,
    tui_key_for,
)

TRUST_VERDICTS = ("pass", "pass-with-gaps", "block")
EVIDENCE_GRADES = ("strong", "medium", "weak")
VERDICT_TO_SETTLEMENT = {
    "pass": SettlementVerdict.FINALIZED,
    "pass-with-gaps": SettlementVerdict.NEEDS_ATTENTION,
    "block": SettlementVerdict.FAILED,
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_root(path: Path | None = None) -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=str(path or Path.cwd()),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "not inside a git repository")
    return Path(proc.stdout.strip()).resolve()


def default_journal_path() -> Path:
    override = str(os.environ.get("VIBECRAFTED_TRUST_JOURNAL") or "").strip()
    if override:
        return Path(override).expanduser()
    home = Path(
        os.environ.get("VIBECRAFTED_HOME") or Path.home() / ".vibecrafted"
    ).expanduser()
    return home / "trust" / "journal.jsonl"


def _resolve_commit(repo: Path, sha: str) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "--verify", f"{sha}^{{commit}}"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(f"not a commit in {repo}: {sha}")
    return proc.stdout.strip()


def _commit_record(repo: Path, sha: str) -> dict[str, str]:
    full_sha = _resolve_commit(repo, sha)
    proc = subprocess.run(
        [
            "git",
            "show",
            "-s",
            "--format=%H%x00%an%x00%ae%x00%aI%x00%s",
            full_sha,
        ],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or f"cannot read commit {full_sha}")
    fields = proc.stdout.rstrip("\n").split("\0")
    if len(fields) != 5:
        raise ValueError(f"unexpected git metadata for {full_sha}")
    return dict(
        zip(
            ("sha", "author_name", "author_email", "authored_at", "subject"),
            fields,
            strict=True,
        )
    )


def _read_journal(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    records: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid journal JSON at {path}:{line_number}") from exc
        if not isinstance(payload, dict):
            raise TypeError(f"invalid journal record at {path}:{line_number}")
        records.append(payload)
    return records


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = (
        json.dumps(dict(payload), sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    descriptor = os.open(
        path,
        os.O_APPEND | os.O_CREAT | os.O_WRONLY,
        0o600,
    )
    try:
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError(f"short append to {path}: {written}/{len(encoded)} bytes")
    finally:
        os.close(descriptor)


def _git_log_range(repo: Path, since: str) -> list[str]:
    if not since:
        return []
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", f"{since}^{{commit}}"],
        cwd=str(repo),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return [f"{since}..HEAD"]
    return [f"--since={since}"]


def enumerate_commits(
    *,
    repo: Path,
    journal: Path,
    author: str = "",
    since: str = "",
    limit: int = 100,
    include_noted: bool = False,
) -> list[dict[str, str]]:
    command = [
        "git",
        "log",
        f"--max-count={max(limit, 1)}",
        "--format=%H",
        *_git_log_range(repo, since),
    ]
    if author:
        command.append(f"--author={author}")
    proc = subprocess.run(
        command,
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "git log failed")
    noted = {
        str(item.get("sha") or "")
        for item in _read_journal(journal)
        if str(item.get("repo_root") or "") == str(repo)
    }
    commits = []
    for sha in proc.stdout.splitlines():
        record = _commit_record(repo, sha)
        if include_noted or record["sha"] not in noted:
            commits.append(record)
    return commits


def _claims_from_args(args: argparse.Namespace) -> list[dict[str, str]]:
    claims = list(args.claim or [])
    grades = list(args.grade or [])
    evidence = list(args.evidence or [])
    if not claims:
        raise ValueError("note requires at least one --claim")
    if not (len(claims) == len(grades) == len(evidence)):
        raise ValueError("each --claim requires one matching --grade and --evidence")
    return [
        {"claim": claim, "grade": grade, "evidence": proof}
        for claim, grade, proof in zip(claims, grades, evidence, strict=True)
    ]


def _claims_digest(claims: Sequence[Mapping[str, str]]) -> str:
    raw = json.dumps(list(claims), sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def _persist_trust_settlement(
    *,
    run_id: str,
    verdict: str,
    sha: str,
    claims: Sequence[Mapping[str, str]],
    stamp: str,
) -> str:
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError(f"invalid run id: {run_id!r}")
    resolved = control_plane.resolve_run(run_id)
    if resolved.meta is None:
        raise ValueError(f"run {run_id} has no meta.json to settle")
    terminal = VERDICT_TO_SETTLEMENT[verdict]
    settlement = Settlement(
        verdict=terminal,
        reason=f"trust_{verdict.replace('-', '_')}:{sha}",
        settled_at=stamp,
        source="trust",
        claim_digest=_claims_digest(claims),
    )
    if not persist_settlement_to_meta(resolved.meta, settlement):
        raise OSError(f"failed to persist trust settlement to {resolved.meta}")
    control_plane.sync_state(only_run_id=run_id)
    snapshot = control_plane.run_snapshot_dir() / f"{run_id}.json"
    if snapshot.is_file() and not persist_settlement_to_meta(snapshot, settlement):
        raise OSError(f"failed to persist trust settlement to {snapshot}")
    return tui_key_for(terminal)


def note_verdict(
    *,
    repo: Path,
    journal: Path,
    sha: str,
    verdict: str,
    claims: Sequence[Mapping[str, str]],
    run_id: str = "",
) -> dict[str, Any]:
    if verdict not in TRUST_VERDICTS:
        raise ValueError(f"unsupported trust verdict: {verdict}")
    commit = _commit_record(repo, sha)
    stamp = _now_iso()
    tui = (
        _persist_trust_settlement(
            run_id=run_id,
            verdict=verdict,
            sha=commit["sha"],
            claims=claims,
            stamp=stamp,
        )
        if run_id
        else tui_key_for(VERDICT_TO_SETTLEMENT[verdict])
    )
    entry: dict[str, Any] = {
        "schema": "vibecrafted.trust-journal.v1",
        "recorded_at": stamp,
        "repo_root": str(repo),
        **commit,
        "verdict": verdict,
        "settlement_tui": tui,
        "run_id": run_id,
        "claims": list(claims),
    }
    _append_jsonl(journal, entry)
    return entry


def triage_records(
    records: Sequence[Mapping[str, Any]], *, run_id: str = ""
) -> dict[str, Any]:
    latest: dict[tuple[str, str], Mapping[str, Any]] = {}
    for record in records:
        if run_id and str(record.get("run_id") or "") != run_id:
            continue
        key = (str(record.get("repo_root") or ""), str(record.get("sha") or ""))
        if all(key):
            latest[key] = record
    counts = {"f": 0, "x": 0, "n": 0}
    for record in latest.values():
        cell = str(record.get("settlement_tui") or "")
        if cell in counts:
            counts[cell] += 1
    return {
        "schema": "vibecrafted.trust-triage.v1",
        "run_id": run_id,
        "counts": counts,
        "commits": len(latest),
    }


def _read_run_meta(run_id: str) -> dict[str, Any]:
    resolved = control_plane.resolve_run(run_id)
    if resolved.meta is None:
        return {}
    try:
        payload = json.loads(resolved.meta.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _run_start(payload: Mapping[str, Any]) -> str:
    for key in ("started_at", "created_at", "launched_at", "timestamp"):
        value = str(payload.get(key) or "").strip()
        if value:
            return value
    return ""


def await_primary(
    *,
    run_id: str,
    repo: Path,
    journal: Path,
    author: str = "",
    since: str = "",
    interval: float = 5.0,
    timeout: float = 0.0,
) -> dict[str, Any]:
    started = time.monotonic()
    initial_meta = _read_run_meta(run_id)
    while True:
        remaining = max(timeout - (time.monotonic() - started), 0.0) if timeout else 0.0
        window = min(max(interval, 0.1), remaining) if timeout else max(interval, 0.1)
        result = control_plane.await_run(
            run_id,
            timeout_seconds=window,
            interval_seconds=min(max(interval, 0.1), 1.0),
        )
        if result.get("completed"):
            break
        if timeout and time.monotonic() - started >= timeout:
            raise TimeoutError(f"trust await timed out for run {run_id}")
    candidates = enumerate_commits(
        repo=repo,
        journal=journal,
        author=author,
        since=since or _run_start(initial_meta),
        include_noted=False,
    )
    return {
        "schema": "vibecrafted.trust-await-primary.v1",
        "run_id": run_id,
        "await": {
            "completed": bool(result.get("completed")),
            "reason": str(result.get("reason") or ""),
            "await_rc": result.get("await_rc"),
            "await_outcome": str(result.get("await_outcome") or ""),
        },
        "candidate_commits": candidates,
        "next": (
            "Falsify every candidate claim, then record each commit with "
            "python -m vibecrafted_core.trust note ..."
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m vibecrafted_core.trust",
        description="Append-only vc-trust journal and settlement helper.",
    )
    parser.add_argument("--journal", type=Path, default=default_journal_path())
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)

    enumerate_parser = commands.add_parser("enumerate")
    enumerate_parser.add_argument("author", nargs="?", default="")
    enumerate_parser.add_argument("--since", default="")
    enumerate_parser.add_argument("--limit", type=int, default=100)
    enumerate_parser.add_argument("--all", action="store_true")

    note_parser = commands.add_parser("note")
    note_parser.add_argument("sha")
    note_parser.add_argument("verdict", choices=TRUST_VERDICTS)
    note_parser.add_argument("--run-id", default="")
    note_parser.add_argument("--claim", action="append", required=True)
    note_parser.add_argument(
        "--grade", action="append", choices=EVIDENCE_GRADES, required=True
    )
    note_parser.add_argument("--evidence", action="append", required=True)

    triage_parser = commands.add_parser("triage")
    triage_parser.add_argument("--run-id", default="")

    await_parser = commands.add_parser("await-primary")
    await_parser.add_argument("run_id")
    await_parser.add_argument("--author", default="")
    await_parser.add_argument("--since", default="")
    await_parser.add_argument("--interval", type=float, default=5.0)
    await_parser.add_argument("--timeout", type=float, default=0.0)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        repo = _repo_root(args.repo)
        journal = args.journal.expanduser()
        if args.command == "enumerate":
            result: Any = enumerate_commits(
                repo=repo,
                journal=journal,
                author=args.author,
                since=args.since,
                limit=args.limit,
                include_noted=args.all,
            )
        elif args.command == "note":
            result = note_verdict(
                repo=repo,
                journal=journal,
                sha=args.sha,
                verdict=args.verdict,
                claims=_claims_from_args(args),
                run_id=args.run_id,
            )
        elif args.command == "triage":
            result = triage_records(
                _read_journal(journal),
                run_id=args.run_id,
            )
        else:
            result = await_primary(
                run_id=args.run_id,
                repo=repo,
                journal=journal,
                author=args.author,
                since=args.since,
                interval=args.interval,
                timeout=args.timeout,
            )
    except (OSError, TimeoutError, ValueError, control_plane.RunNotResolved) as exc:
        print(f"vc-trust: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
