"""vc-trust journal and settlement helper.

The agent skill owns falsification. This module only provides durable,
deterministic mechanics: enumerate candidate commits, append one structured
verdict, project that verdict onto the existing settlement axis, and wait for a
run boundary without inventing a second monitor.
"""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Mapping, Sequence
from contextlib import nullcontext
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import control_plane
from .run_mutation import run_mutation_locks
from .settlement import (
    Settlement,
    SettlementEventV2,
    SettlementVerdict,
    TrustReceiptV1,
    build_trust_settlement_event,
    emit_settlement_event,
    tui_key_for,
)

TRUST_VERDICTS = ("pass", "pass-with-gaps", "block")
EVIDENCE_GRADES = ("strong", "medium", "weak")
VERDICT_TO_SETTLEMENT = {
    "pass": SettlementVerdict.FINALIZED,
    "pass-with-gaps": SettlementVerdict.NEEDS_ATTENTION,
    "block": SettlementVerdict.FAILED,
}
TRUST_JOURNAL_SCHEMA_V2 = "vibecrafted.trust-journal.v2"
TRUST_OUTBOX_SCHEMA = "vibecrafted.trust-settlement-outbox.v1"

# Subject: [<agent>/<runtime>] <type>(optional scope): <subject>
_SUBJECT_RE = re.compile(
    r"^\[([a-z][a-z0-9_-]*)/[a-z0-9][a-z0-9._-]*\]\s+"
    r"(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert|release)"
    r"(?:\([^)]*\))?:\s+.+",
    re.IGNORECASE,
)
_AUTHORED_BY_RE = re.compile(
    r"^Authored-By:\s*([a-z][a-z0-9_-]*)\s*<agents@vetcoders\.io>\s*$",
    re.IGNORECASE | re.MULTILINE,
)
_VENDOR_FOOTER_RE = re.compile(
    r"(^Co-Authored-By:|noreply@|@anthropic\.com|@openai\.com)",
    re.IGNORECASE | re.MULTILINE,
)
_TRAILER_KEYS = (
    "Authored-By",
    "session_id",
    "time",
    "runtime",
    "Signed-off-by",
    "Vibecrafted-Warn-Signature",
)
_UNEARNED_DONE = re.compile(
    r"\b(done|fixed|complete|shipped|production.?ready|all green)\b",
    re.IGNORECASE,
)
# Path-like tokens claimed in the commit body (message-claimed envelope).
# Matches repo-relative paths with a separator or a dotted filename, optional
# backticks, and optional trailing punctuation from prose.
_CLAIMED_PATH_RE = re.compile(
    r"(?:`(?P<bt>[A-Za-z0-9_./-]{2,200})`"
    r"|(?P<bare>(?:[A-Za-z0-9_.-]+/)+[A-Za-z0-9_.-]+"
    r"|[A-Za-z0-9_.-]+\.[A-Za-z0-9]{1,12}))"
)


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


def _commit_message(repo: Path, sha: str) -> str:
    full_sha = _resolve_commit(repo, sha)
    proc = subprocess.run(
        ["git", "log", "-1", "--format=%B", full_sha],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or f"cannot read message for {full_sha}")
    return proc.stdout


def _commit_files(repo: Path, sha: str) -> list[str]:
    """List paths changed by *sha*, including root commits.

    ``git diff-tree`` without ``--root`` returns no paths for the repository's
    first commit (no parent). Always pass ``--root`` so root commits that
    added real files are not mis-read as empty envelopes.
    """
    full_sha = _resolve_commit(repo, sha)
    proc = subprocess.run(
        [
            "git",
            "diff-tree",
            "--root",
            "--no-commit-id",
            "--name-only",
            "-r",
            full_sha,
        ],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or f"cannot list files for {full_sha}")
    return [line for line in proc.stdout.splitlines() if line.strip()]


_NON_PATH_EXTS = frozenset(
    {
        "com",
        "org",
        "net",
        "io",
        "ai",
        "dev",
        "app",
        "edu",
        "gov",
        "info",
        "co",
        "uk",
        "de",
        "pl",
    }
)


def _normalize_claimed_path(raw: str, *, backtick: bool) -> str | None:
    token = raw.strip().strip("`\"'").rstrip(".,;:)")
    if not token or token in {".", ".."}:
        return None
    # Drop URL-like, emails, and pure version noise.
    if "://" in token or token.startswith("http") or "@" in token:
        return None
    if re.fullmatch(r"v?\d+(\.\d+)+", token):
        return None
    # Ignore bare extensions and single-char noise.
    if token.startswith(".") and "/" not in token:
        return None
    has_ext = bool(re.search(r"\.[A-Za-z0-9]{1,12}$", token))
    slash_count = token.count("/")
    if has_ext and slash_count == 0:
        ext = token.rsplit(".", 1)[-1].lower()
        # Bare "anthropic.com" from email footers is not a repo path.
        if ext in _NON_PATH_EXTS and not backtick:
            return None
    # Reject agent/runtime subject fragments like "codex/workflow" unless the
    # author explicitly backtick-quoted a real path (or it carries an extension
    # / deeper tree path).
    if not backtick and not has_ext and slash_count < 2:
        return None
    if not has_ext and slash_count == 0 and not backtick:
        return None
    # Require either a path separator or a file extension.
    if "/" not in token and "." not in token:
        return None
    return token


def extract_claimed_paths(message: str) -> list[str]:
    """Mechanical paths the message claims to touch (body + path-ish subject).

    The conventional subject prefix ``[<agent>/<runtime>]`` is stripped before
    scanning so it is never mistaken for a repo path.
    """
    body = _message_body_without_trailers(message)
    subject = message.splitlines()[0] if message.splitlines() else ""
    # Drop [<agent>/<runtime>] so "codex/workflow" is not a claimed path.
    subject = re.sub(r"^\[[^\]]+\]\s*", "", subject)
    haystack = f"{subject}\n{body}"
    found: list[str] = []
    seen: set[str] = set()
    for match in _CLAIMED_PATH_RE.finditer(haystack):
        bt = match.group("bt")
        bare = match.group("bare")
        raw = bt or bare or ""
        path = _normalize_claimed_path(raw, backtick=bool(bt))
        if path is None or path in seen:
            continue
        # Skip trailer-looking keys that can look path-ish.
        if path.lower().startswith("authored-by"):
            continue
        seen.add(path)
        found.append(path)
    return found


def _envelope_path_mismatch(
    *,
    claimed: Sequence[str],
    files: Sequence[str],
) -> tuple[list[str], list[str]]:
    """Return (claimed_missing_from_diff, foreign_unclaimed_in_diff).

    Matching is suffix/basename tolerant so a body may say ``trust.py`` while
    the tree carries ``vibecrafted_core/trust.py``.
    """
    file_set = list(files)
    claimed_list = list(claimed)

    def _covers(claimed_path: str, actual: str) -> bool:
        if claimed_path == actual:
            return True
        # Prefix-tolerant: body says trust.py, tree has vibecrafted_core/trust.py
        if actual.endswith("/" + claimed_path) or claimed_path.endswith("/" + actual):
            return True
        return Path(claimed_path).name == Path(actual).name and (
            "/" not in claimed_path or "/" not in actual
        )

    missing: list[str] = []
    for path in claimed_list:
        if not any(_covers(path, actual) for actual in file_set):
            missing.append(path)

    foreign: list[str] = []
    if claimed_list:
        for actual in file_set:
            if not any(_covers(path, actual) for path in claimed_list):
                foreign.append(actual)
    return missing, foreign


def _message_body_without_trailers(message: str) -> str:
    lines = message.splitlines()
    if not lines:
        return ""
    body_lines: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if any(stripped.startswith(f"{key}:") for key in _TRAILER_KEYS):
            continue
        body_lines.append(line)
    return "\n".join(body_lines).strip()


def parse_subject_agent(subject: str) -> str | None:
    match = _SUBJECT_RE.match(subject.strip())
    if not match:
        return None
    return match.group(1).lower()


def parse_authored_by_agent(message: str) -> str | None:
    match = _AUTHORED_BY_RE.search(message)
    if not match:
        return None
    return match.group(1).lower()


def extract_fairness_and_completeness_claims(
    *,
    repo: Path,
    sha: str,
) -> dict[str, Any]:
    """Turn a commit message + envelope into falsifiable claims.

    Agent fairness is first-class: subject agent must match Authored-By, vendor
    footers are banned, and the message body must carry substance before trailers.
    Format legality alone never upgrades a verdict to pass.
    """
    commit = _commit_record(repo, sha)
    message = _commit_message(repo, sha)
    files = _commit_files(repo, sha)
    subject = commit["subject"]
    subject_agent = parse_subject_agent(subject)
    authored_by = parse_authored_by_agent(message)
    body = _message_body_without_trailers(message)
    has_vendor = bool(_VENDOR_FOOTER_RE.search(message))
    claims: list[dict[str, str]] = []
    failures: list[str] = []
    gaps: list[str] = []

    # --- Agent fairness axis ---
    if subject_agent is None:
        failures.append("subject lacks mandatory [<agent>/<runtime>] type prefix")
        claims.append(
            {
                "claim": "subject declares executor as [<agent>/<runtime>] conventional type",
                "grade": "strong",
                "evidence": f"subject failed pattern: {subject!r}",
            }
        )
    else:
        claims.append(
            {
                "claim": f"subject agent is {subject_agent}",
                "grade": "strong",
                "evidence": f"parsed from subject: {subject!r}",
            }
        )

    if authored_by is None:
        failures.append("missing Authored-By: <agent> <agents@vetcoders.io>")
        claims.append(
            {
                "claim": "Authored-By trailer names the executing agent at agents@vetcoders.io",
                "grade": "strong",
                "evidence": "Authored-By trailer missing or non-canonical",
            }
        )
    else:
        claims.append(
            {
                "claim": f"Authored-By is {authored_by} <agents@vetcoders.io>",
                "grade": "strong",
                "evidence": "canonical Authored-By trailer present",
            }
        )

    if subject_agent and authored_by and subject_agent != authored_by:
        failures.append(
            f"agent fairness breach: subject agent {subject_agent!r} "
            f"!= Authored-By {authored_by!r}"
        )
        claims.append(
            {
                "claim": "subject agent matches Authored-By executor (agent fairness)",
                "grade": "strong",
                "evidence": (
                    f"mismatch subject={subject_agent!r} authored_by={authored_by!r}"
                ),
            }
        )
    elif subject_agent and authored_by and subject_agent == authored_by:
        claims.append(
            {
                "claim": "subject agent matches Authored-By executor (agent fairness)",
                "grade": "strong",
                "evidence": f"both name {subject_agent}",
            }
        )

    if has_vendor:
        failures.append("vendor Co-Authored-By / vendor email footer present")
        claims.append(
            {
                "claim": "no vendor Co-Authored-By or vendor emails (agent fairness)",
                "grade": "strong",
                "evidence": "vendor footer pattern matched in message",
            }
        )
    else:
        claims.append(
            {
                "claim": "no vendor Co-Authored-By or vendor emails (agent fairness)",
                "grade": "strong",
                "evidence": "no vendor footer patterns found",
            }
        )

    # --- Completeness axis (message shape is necessary, never sufficient) ---
    if not body:
        failures.append("commit message has no explanatory body before trailers")
        claims.append(
            {
                "claim": "explanatory body exists before trailers",
                "grade": "strong",
                "evidence": "body empty after stripping subject and trailers",
            }
        )
    else:
        claims.append(
            {
                "claim": "explanatory body exists before trailers",
                "grade": "medium",
                "evidence": f"body length={len(body)} chars",
            }
        )
        if _UNEARNED_DONE.search(body) and not re.search(
            r"\b(test|pytest|cargo|verify|gate|evidence|proof)\b", body, re.IGNORECASE
        ):
            gaps.append(
                "unearned done-language without named test/gate/evidence in body"
            )
            claims.append(
                {
                    "claim": "done/fixed language is backed by named verification",
                    "grade": "weak",
                    "evidence": "done-language present without test/gate/evidence tokens",
                }
            )

    if not files:
        gaps.append("commit touches no files (empty envelope)")
        claims.append(
            {
                "claim": "commit envelope lists changed files",
                "grade": "strong",
                "evidence": "git diff-tree --root returned zero paths",
            }
        )
    else:
        claims.append(
            {
                "claim": "commit envelope lists changed files",
                "grade": "strong",
                "evidence": f"{len(files)} path(s): {', '.join(files[:8])}",
            }
        )

    # --- Envelope honesty: message-claimed paths vs diff-tree files ---
    # Foreign/unclaimed files are a first-class agent-fairness axis: a commit
    # that smuggles paths the message does not claim (or claims paths the
    # commit never touched) fails the envelope contract.
    claimed_paths = extract_claimed_paths(message)
    missing_claimed, foreign_files = _envelope_path_mismatch(
        claimed=claimed_paths, files=files
    )
    if claimed_paths:
        claims.append(
            {
                "claim": "message-claimed paths are present in the commit envelope",
                "grade": "strong",
                "evidence": (
                    f"claimed={claimed_paths!r}; missing_from_diff={missing_claimed!r}"
                    if missing_claimed
                    else f"all claimed paths covered by envelope: {claimed_paths!r}"
                ),
            }
        )
        claims.append(
            {
                "claim": (
                    "staged/commit envelope does not carry foreign unclaimed files"
                ),
                "grade": "strong",
                "evidence": (
                    f"foreign_unclaimed={foreign_files!r} vs claimed={claimed_paths!r}"
                    if foreign_files
                    else f"no foreign files beyond claimed set ({len(files)} path(s))"
                ),
            }
        )
        if missing_claimed:
            failures.append(
                "message claims paths absent from the commit envelope: "
                + ", ".join(missing_claimed)
            )
        if foreign_files:
            # Multi-file smuggling is a fairness/completeness gap (or block when
            # combined with other fairness failures). Named evidence is required.
            gaps.append(
                "commit envelope carries foreign unclaimed files: "
                + ", ".join(foreign_files)
            )
    elif files:
        # No path tokens in the message: still emit the axis so inspect always
        # surfaces the envelope contract (cannot prove foreign without claims).
        claims.append(
            {
                "claim": (
                    "staged/commit envelope does not carry foreign unclaimed files"
                ),
                "grade": "medium",
                "evidence": (
                    "message claims no concrete paths; envelope has "
                    f"{len(files)} path(s) — scope honesty not path-checkable"
                ),
            }
        )

    # Align git author email with Authored-By when the author is a named agent
    # mailbox (not the shared agents@ fleet identity).
    git_email = commit.get("author_email", "")
    if (
        authored_by
        and git_email.endswith("@vetcoders.io")
        and "agents@" not in git_email
        and authored_by not in git_email
    ):
        gaps.append(
            f"git author email {git_email!r} does not align with Authored-By {authored_by!r}"
        )

    if failures:
        recommended = "block"
    elif gaps:
        recommended = "pass-with-gaps"
    else:
        # Format + fairness can only ever justify pass-with-gaps unless the
        # operator/agent supplies strong runtime evidence via note.
        recommended = "pass-with-gaps"

    return {
        "schema": "vibecrafted.trust-inspect.v1",
        "sha": commit["sha"],
        "subject": subject,
        "subject_agent": subject_agent,
        "authored_by_agent": authored_by,
        "files": files,
        "failures": failures,
        "gaps": gaps,
        "claims": claims,
        "recommended_verdict": recommended,
        "note": (
            "Format/trailer legality and agent-fairness checks never alone "
            "produce pass; pass requires strong runtime evidence supplied via note."
        ),
    }


def recommend_verdict_from_inspect(inspect: Mapping[str, Any]) -> str:
    verdict = str(inspect.get("recommended_verdict") or "block")
    if verdict not in TRUST_VERDICTS:
        return "block"
    return verdict


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
    existed = path.exists()
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    flags |= getattr(os, "O_CLOEXEC", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(path, flags, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        written = os.write(descriptor, encoded)
        if written != len(encoded):
            raise OSError(f"short append to {path}: {written}/{len(encoded)} bytes")
        os.fsync(descriptor)
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    if not existed:
        control_plane._fsync_directory_durable(path.parent)


# ISO-ish timestamps from control-plane run meta (started_at / created_at).
# Used only when since is not a resolvable commit; never treat failed rev tokens
# (e.g. rootSHA^) as git --since date filters.
_ISO_OR_GIT_DATE_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}"
    r"(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?"
    r"$"
)


def _git_log_range(repo: Path, since: str) -> list[str]:
    """Build git-log range args for *since*.

    - empty → no lower bound
    - resolvable commit → ``<since>..HEAD``
    - ISO/date run-meta token → ``--since=<date>`` (await-primary boundary)
    - unresolvable rev-ish (e.g. ``<root>^``) → no lower bound (fail open)

    Never pass a failed commit token into ``git log --since=…``: git treats that
    as a date filter and can yield zero candidates for commits that exist.
    """
    token = (since or "").strip()
    if not token:
        return []
    probe = subprocess.run(
        ["git", "rev-parse", "--verify", f"{token}^{{commit}}"],
        cwd=str(repo),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if probe.returncode == 0:
        return [f"{token}..HEAD"]
    if _ISO_OR_GIT_DATE_RE.match(token):
        return [f"--since={token}"]
    # Unresolvable rev (root parent, typo, foreign sha): omit lower bound.
    return []


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
    try:
        resolved = str(Path(repo).resolve())
    except OSError:
        resolved = str(repo)
    noted = {
        str(item.get("sha") or "")
        for item in _read_journal(journal)
        if str(item.get("repo_root") or "") in {str(repo), resolved}
        or _same_repo_root(str(item.get("repo_root") or ""), resolved)
    }
    commits = []
    for sha in proc.stdout.splitlines():
        record = _commit_record(repo, sha)
        if include_noted or record["sha"] not in noted:
            commits.append(record)
    return commits


def _same_repo_root(stored: str, resolved: str) -> bool:
    if not stored:
        return False
    try:
        return str(Path(stored).resolve()) == resolved
    except OSError:
        return False


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
    raw = json.dumps(
        [dict(claim) for claim in claims],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _trust_outbox_path(run_id: str) -> Path:
    digest = hashlib.sha256(run_id.encode("utf-8")).hexdigest()
    return (
        control_plane.control_plane_home()
        / "trust_settlement_outbox"
        / f"{digest}.json"
    )


def _nested_settlement(settlement: Settlement) -> dict[str, Any]:
    return {
        "verdict": settlement.verdict.value,
        "reason": settlement.reason,
        "settled_at": settlement.settled_at,
        "source": settlement.source,
        "claim_digest": settlement.claim_digest,
        "waived": settlement.waived,
        "tui": settlement.tui_key,
        "await_rc": settlement.await_rc,
        "await_outcome": settlement.await_outcome,
    }


def _trust_projection_fields(
    settlement: Settlement,
    receipt: TrustReceiptV1,
) -> dict[str, Any]:
    return {
        **settlement.to_payload(),
        "settlement": _nested_settlement(settlement),
        "settlement_revision": receipt.settlement_revision,
        "trust_receipt": receipt.to_payload(),
    }


def _remove_durable(path: Path) -> None:
    path.unlink()
    control_plane._fsync_directory_durable(path.parent)


def _journal_entry_for_receipt(
    journal: Path,
    receipt_id: str,
) -> dict[str, Any] | None:
    latest: dict[str, Any] | None = None
    for item in _read_journal(journal):
        receipt = item.get("trust_receipt")
        if (
            isinstance(receipt, Mapping)
            and str(receipt.get("receipt_id") or "") == receipt_id
        ):
            latest = item
    return latest


def _projection_matches_receipt(
    payload: Mapping[str, Any],
    receipt: TrustReceiptV1,
) -> bool:
    raw = payload.get("trust_receipt")
    if not isinstance(raw, Mapping):
        return False
    try:
        projected = TrustReceiptV1.from_payload(raw)
    except (TypeError, ValueError):
        return False
    return (
        projected == receipt
        and payload.get("settlement_revision") == receipt.settlement_revision
        and str(payload.get("settlement_verdict") or "") == receipt.settlement_verdict
        and str(payload.get("settlement_tui") or "") == receipt.settlement_tui
        and str(payload.get("settlement_source") or "") == "trust"
        and str(payload.get("settlement_claim_digest") or "") == receipt.claim_digest
    )


def _can_complete_projection(
    payload: Mapping[str, Any],
    *,
    receipt: TrustReceiptV1,
    previous_revision: int,
) -> bool:
    if _projection_matches_receipt(payload, receipt):
        return True
    prior = payload.get("trust_receipt")
    if prior not in (None, {}):
        if not isinstance(prior, Mapping):
            return False
        try:
            prior_receipt = TrustReceiptV1.from_payload(prior)
        except (TypeError, ValueError):
            return False
        if prior_receipt.settlement_revision > previous_revision:
            return False
    revision = payload.get("settlement_revision")
    return revision in (None, "") or (
        type(revision) is int and revision <= previous_revision
    )


def _publish_trust_event(event: SettlementEventV2) -> dict[str, Any]:
    """Single indirection kept explicit for crash-injection tests."""

    return emit_settlement_event(event)


def _recover_trust_outbox(
    *,
    run_id: str,
    outbox_path: Path,
) -> dict[str, Any] | None:
    """Finish one journal-committed trust transaction with the same receipt."""

    if not outbox_path.exists():
        return None
    outbox = control_plane._read_json(outbox_path)
    if (
        outbox.get("schema") != TRUST_OUTBOX_SCHEMA
        or str(outbox.get("run_id") or "") != run_id
    ):
        raise ValueError(f"invalid trust settlement outbox: {outbox_path}")
    receipt_payload = outbox.get("trust_receipt")
    event_payload = outbox.get("event")
    entry_payload = outbox.get("journal_entry")
    if not isinstance(receipt_payload, Mapping):
        raise TypeError("trust settlement outbox receipt missing")
    if not isinstance(event_payload, Mapping):
        raise TypeError("trust settlement outbox event missing")
    if not isinstance(entry_payload, Mapping):
        raise TypeError("trust settlement outbox journal entry missing")
    receipt = TrustReceiptV1.from_payload(receipt_payload)
    event = SettlementEventV2.from_payload(event_payload)
    if event.trust_receipt != receipt:
        raise ValueError("trust settlement outbox event receipt mismatch")
    journal = Path(str(outbox.get("journal") or "")).expanduser()
    if not journal.is_absolute():
        raise ValueError("trust settlement outbox journal path invalid")
    journal_entry = _journal_entry_for_receipt(journal, receipt.receipt_id)
    if journal_entry != dict(entry_payload):
        raise ValueError("trust settlement journal receipt missing or mismatched")
    previous_revision = outbox.get("previous_revision")
    if type(previous_revision) is not int or previous_revision < 0:
        raise ValueError("trust settlement outbox previous revision invalid")
    meta_path = Path(str(outbox.get("meta_path") or "")).expanduser()
    snapshot_path = Path(str(outbox.get("snapshot_path") or "")).expanduser()
    if not meta_path.is_absolute() or not snapshot_path.is_absolute():
        raise ValueError("trust settlement outbox projection path invalid")
    fields = outbox.get("projection_fields")
    if not isinstance(fields, Mapping):
        raise TypeError("trust settlement outbox projection fields missing")

    meta = control_plane._read_json(meta_path)
    snapshot = control_plane._read_json(snapshot_path)
    for label, payload in (("meta", meta), ("snapshot", snapshot)):
        if not _can_complete_projection(
            payload,
            receipt=receipt,
            previous_revision=previous_revision,
        ):
            raise ValueError(f"trust settlement recovery {label} projection diverged")

    if not _projection_matches_receipt(meta, receipt):
        meta.update(dict(fields))
        control_plane._write_json_durable(meta_path, meta)
    if not _projection_matches_receipt(snapshot, receipt):
        snapshot.update(dict(fields))
        snapshot.setdefault("run_id", run_id)
        control_plane._write_json_durable(snapshot_path, snapshot)

    if not _projection_matches_receipt(
        control_plane._read_json(meta_path), receipt
    ) or not _projection_matches_receipt(
        control_plane._read_json(snapshot_path), receipt
    ):
        raise OSError("trust settlement projection durability verification failed")
    _publish_trust_event(event)
    _remove_durable(outbox_path)
    return dict(entry_payload)


def _persist_trust_settlement(
    *,
    repo_root: Path,
    journal: Path,
    run_id: str,
    verdict: str,
    sha: str,
    claims: Sequence[Mapping[str, str]],
    stamp: str,
) -> dict[str, Any]:
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError(f"invalid run id: {run_id!r}")
    outbox_path = _trust_outbox_path(run_id)
    recovered = _recover_trust_outbox(run_id=run_id, outbox_path=outbox_path)
    if recovered is not None:
        expected_digest = _claims_digest(claims)
        recovered_receipt = recovered.get("trust_receipt")
        if (
            str(recovered.get("sha") or "") == sha
            and str(recovered.get("verdict") or "") == verdict
            and isinstance(recovered_receipt, Mapping)
            and str(recovered_receipt.get("claim_digest") or "") == expected_digest
            and recovered.get("claims") == list(claims)
        ):
            return recovered

    resolved = control_plane.resolve_run(run_id)
    if resolved.meta is None:
        raise ValueError(f"run {run_id} has no meta.json to settle")
    # Read both live projections while the shared run mutation lock is held.
    # Do not call the generic synchronizer here: it may publish an automatic
    # settlement event, while this transaction's journal authority is not yet
    # durable. Missing snapshots are materialised from the fresh runtime meta.
    snapshot_path = control_plane.run_snapshot_dir() / f"{run_id}.json"
    meta = control_plane._read_json(resolved.meta)
    snapshot = control_plane._read_json(snapshot_path)
    if not meta:
        raise ValueError(f"run {run_id} has unreadable meta.json")
    if not snapshot:
        snapshot = dict(meta)
        snapshot["run_id"] = run_id
    revisions = [
        value
        for value in (
            meta.get("settlement_revision"),
            snapshot.get("settlement_revision"),
        )
        if type(value) is int and value > 0
    ]
    previous_revision = max(revisions, default=0)
    terminal = VERDICT_TO_SETTLEMENT[verdict]
    claim_digest = _claims_digest(claims)
    settlement = Settlement(
        verdict=terminal,
        reason=f"trust_{verdict.replace('-', '_')}:{sha}",
        settled_at=stamp,
        source="trust",
        claim_digest=claim_digest,
    )
    receipt = TrustReceiptV1.issue(
        repo_root=str(repo_root),
        run_id=run_id,
        commit_sha=sha,
        trust_verdict=verdict,
        settlement_verdict=terminal.value,
        settlement_tui=tui_key_for(terminal),
        settlement_revision=previous_revision + 1,
        claim_digest=claim_digest,
    )
    fields = _trust_projection_fields(settlement, receipt)
    journal_entry: dict[str, Any] = {
        "schema": TRUST_JOURNAL_SCHEMA_V2,
        "recorded_at": stamp,
        "repo_root": str(repo_root),
        **_commit_record(repo_root, sha),
        "verdict": verdict,
        "settlement_tui": receipt.settlement_tui,
        "run_id": run_id,
        "claims": list(claims),
        "claim_digest": claim_digest,
        "trust_receipt": receipt.to_payload(),
    }
    event = build_trust_settlement_event(
        previous_payload=snapshot,
        settlement=settlement,
        receipt=receipt,
    )

    # Authority ordering: journal is the human/audit fact; the outbox is the
    # crash receipt; projections become visible next; the notification is last.
    _append_jsonl(journal, journal_entry)
    outbox = {
        "schema": TRUST_OUTBOX_SCHEMA,
        "run_id": run_id,
        "journal": str(journal.resolve()),
        "meta_path": str(resolved.meta.resolve()),
        "snapshot_path": str(snapshot_path.resolve()),
        "previous_revision": previous_revision,
        "trust_receipt": receipt.to_payload(),
        "journal_entry": journal_entry,
        "projection_fields": fields,
        "event": event.to_payload(),
    }
    control_plane._write_json_durable(outbox_path, outbox)
    meta.update(fields)
    snapshot.update(fields)
    snapshot.setdefault("run_id", run_id)
    control_plane._write_json_durable(resolved.meta, meta)
    control_plane._write_json_durable(snapshot_path, snapshot)
    if not _projection_matches_receipt(
        control_plane._read_json(resolved.meta), receipt
    ) or not _projection_matches_receipt(
        control_plane._read_json(snapshot_path), receipt
    ):
        raise OSError("trust settlement projection durability verification failed")
    _publish_trust_event(event)
    _remove_durable(outbox_path)
    return journal_entry


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
    # Always persist the git toplevel path so macOS /var vs /private/var and
    # relative roots still match guard/triage lookups.
    resolved_repo = _repo_root(repo)
    commit = _commit_record(resolved_repo, sha)
    stamp = _now_iso()
    lock = (
        run_mutation_locks(control_plane.control_plane_home(), run_id=run_id)
        if run_id
        else nullcontext()
    )
    with lock:
        if run_id:
            return _persist_trust_settlement(
                repo_root=resolved_repo,
                journal=journal,
                run_id=run_id,
                verdict=verdict,
                sha=commit["sha"],
                claims=claims,
                stamp=stamp,
            )
        tui = tui_key_for(VERDICT_TO_SETTLEMENT[verdict])
        entry: dict[str, Any] = {
            "schema": "vibecrafted.trust-journal.v1",
            "recorded_at": stamp,
            "repo_root": str(resolved_repo),
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

    inspect_parser = commands.add_parser(
        "inspect",
        help=(
            "Extract agent-fairness and completeness claims from a commit "
            "(never auto-notes; never implies pass)."
        ),
    )
    inspect_parser.add_argument("sha")

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
        elif args.command == "inspect":
            result = extract_fairness_and_completeness_claims(repo=repo, sha=args.sha)
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
