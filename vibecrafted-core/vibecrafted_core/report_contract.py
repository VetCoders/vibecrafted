"""Canonical agent report frontmatter — claim surface for board f/x/n + vc-server.

Philosophy (dashboard-ready):

* Frontmatter is **mandatory** on every agent report markdown.
* Agent fields are a **claim**. ``finalized: true`` plus a non-empty ``claim``
  is an explicit self-attestation tier, never a delivery-kernel seal.
* Runtime triangulates claim against exit code, report/transcript artifacts,
  optional declared artifact paths, and delivery-kernel axes when present.

Contract id: ``vibecrafted.report-frontmatter.v1``
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

CONTRACT_ID = "vibecrafted.report-frontmatter.v1"
CLAIM_DIGEST_ENV = "VIBECRAFTED_CLAIM_DIGEST"

# Required keys for a steerable, dashboard-visible report.
REQUIRED_KEYS: tuple[str, ...] = (
    "run_id",
    "agent",
    "skill",
    "status",
)

# Optional but recommended for board + aicx.
RECOMMENDED_KEYS: tuple[str, ...] = (
    "project",
    "date",
    "session_id",
    "claim_status",
    "claim_kind",
    "finalized",
    "claim",
    "claim_digest",
    "repo_path",
    "model",
)

# Agent claim vocabulary (status / claim_status).
CLAIM_COMPLETED = frozenset({"completed", "complete", "success", "ok", "done"})
CLAIM_FAILED = frozenset({"failed", "fail", "error"})
CLAIM_BLOCKED = frozenset({"blocked", "blocked_on_operator", "waived"})
CLAIM_PARTIAL = frozenset(
    {"partial", "in-progress", "in_progress", "pending", "running"}
)

_VALID_STATUS = CLAIM_COMPLETED | CLAIM_FAILED | CLAIM_BLOCKED | CLAIM_PARTIAL
_TRUTHY = frozenset({"1", "true", "yes", "on"})
_LAUNCHER_TEMPLATE_KEY = "launcher_template"
_PENDING_TEMPLATE_STATUS = "pending-unset"

_FRONTMATTER_RE = re.compile(
    r"\A---\s*\n(?P<body>.*?)\n---\s*(?:\n|\Z)",
    re.DOTALL,
)


@dataclass(frozen=True)
class ReportFrontmatter:
    """Parsed report claim surface."""

    fields: dict[str, str] = field(default_factory=dict)
    body: str = ""
    has_frontmatter: bool = False
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        """True when frontmatter parsed and no required-key/structural errors exist."""
        return self.has_frontmatter and not self.errors

    @property
    def run_id(self) -> str:
        """The ``run_id`` field, stripped; empty string if absent."""
        return self.fields.get("run_id", "").strip()

    @property
    def agent(self) -> str:
        """The ``agent`` field, stripped; empty string if absent."""
        return self.fields.get("agent", "").strip()

    @property
    def skill(self) -> str:
        """The ``skill`` field, stripped; empty string if absent."""
        return self.fields.get("skill", "").strip()

    @property
    def claim_status(self) -> str:
        """Normalized claim: claim_status wins over status when set."""
        raw = (
            (self.fields.get("claim_status") or self.fields.get("status") or "")
            .strip()
            .lower()
        )
        return raw

    @property
    def claim_kind(self) -> str:
        """``claim_kind`` field, falling back to ``skill`` when unset."""
        return (self.fields.get("claim_kind") or self.fields.get("skill") or "").strip()

    @property
    def finalized(self) -> bool:
        """Whether the worker deliberately asserted successful completion."""
        return (self.fields.get("finalized") or "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    @property
    def claim(self) -> str:
        """Human-readable claim attached to a positive self-attestation."""
        return (self.fields.get("claim") or "").strip()

    def as_payload(self) -> dict[str, Any]:
        """Serialize this frontmatter for JSON output / dashboard consumption."""
        return {
            "contract": CONTRACT_ID,
            "has_frontmatter": self.has_frontmatter,
            "ok": self.ok,
            "fields": dict(self.fields),
            "claim_status": self.claim_status,
            "claim_kind": self.claim_kind,
            "finalized": self.finalized,
            "claim": self.claim,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def parse_report_text(text: str) -> tuple[dict[str, str], str, bool]:
    """Return (fields, body, has_frontmatter)."""
    if not text:
        return {}, "", False
    match = _FRONTMATTER_RE.match(text)
    if not match:
        # Tolerate BOM / leading blank lines.
        stripped = text.lstrip("\ufeff")
        match = _FRONTMATTER_RE.match(stripped)
        if not match:
            return {}, text, False
        text = stripped
    raw = match.group("body")
    fields: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if not key:
            continue
        fields[key] = value.strip().strip("\"'")
    body = text[match.end() :]
    body = body.removeprefix("\n")
    return fields, body, True


def parse_report_path(path: str | Path) -> ReportFrontmatter:
    """Read and validate a report file's frontmatter; never raises on I/O errors."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ReportFrontmatter(
            errors=(f"report_unreadable:{type(exc).__name__}",),
        )
    fields, body, has_fm = parse_report_text(text)
    return validate_frontmatter_fields(fields, body, has_fm=has_fm)


def validate_frontmatter_fields(
    fields: Mapping[str, str],
    body: str = "",
    *,
    has_fm: bool,
    require_recommended: bool = False,
) -> ReportFrontmatter:
    """Validate parsed frontmatter fields against required/recommended keys and
    the known claim-status vocabulary, producing errors and warnings.
    """
    errors: list[str] = []
    warnings: list[str] = []
    normalized = {
        str(k).strip(): str(v).strip() for k, v in fields.items() if str(k).strip()
    }

    if not has_fm:
        errors.append("report_frontmatter_missing")
        return ReportFrontmatter(
            fields=normalized,
            body=body,
            has_frontmatter=False,
            errors=tuple(errors),
        )

    for key in REQUIRED_KEYS:
        value = normalized.get(key, "").strip()
        if not value:
            errors.append(f"report_frontmatter_missing_key:{key}")
            continue
        # Runtime salvage may write "unknown" when the worker left no claim.
        # Structure is present (dashboard can index); quality is a warning.
        if value.lower() in {"unknown", "none", "null", "pending-unset"}:
            warnings.append(f"report_frontmatter_placeholder:{key}")

    # A launcher template is transport scaffolding, not worker evidence. Keep
    # the historical ``report_missing`` signal even though the runtime has
    # materialized a file, so exit-0-without-report still parks at n.
    if normalized.get(_LAUNCHER_TEMPLATE_KEY, "").strip().lower() in _TRUTHY:
        errors.append("report_missing")

    status = (
        (normalized.get("claim_status") or normalized.get("status") or "")
        .strip()
        .lower()
    )
    if status and status not in _VALID_STATUS:
        warnings.append(f"report_frontmatter_status_unrecognized:{status}")

    if require_recommended:
        for key in RECOMMENDED_KEYS:
            if not normalized.get(key, "").strip():
                warnings.append(f"report_frontmatter_recommended_missing:{key}")

    # artifacts: optional comma-separated paths for dashboard proof list
    artifacts_raw = (
        normalized.get("artifacts") or normalized.get("artifact_paths") or ""
    )
    if artifacts_raw and artifacts_raw.lower() not in {"none", "[]", "-"}:
        # Keep as opaque string; triage may split later.
        pass

    return ReportFrontmatter(
        fields=normalized,
        body=body,
        has_frontmatter=True,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_report_file(
    path: str | Path | None,
    *,
    require_frontmatter: bool = True,
) -> ReportFrontmatter:
    """Validate a report file on disk; missing/unreadable files are errors.

    When ``require_frontmatter`` is False, a missing frontmatter block is
    downgraded from an error to a warning instead of failing validation.
    """
    if path is None:
        return ReportFrontmatter(errors=("report_path_missing",))
    p = Path(path)
    if not p.is_file():
        return ReportFrontmatter(errors=("report_missing",))
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return ReportFrontmatter(errors=(f"report_unreadable:{type(exc).__name__}",))
    fields, body, has_fm = parse_report_text(text)
    result = validate_frontmatter_fields(fields, body, has_fm=has_fm)
    if not require_frontmatter and "report_frontmatter_missing" in result.errors:
        # Downgrade hard missing-block to warning when caller opts out.
        errors = tuple(e for e in result.errors if e != "report_frontmatter_missing")
        warnings = result.warnings + ("report_frontmatter_missing",)
        return ReportFrontmatter(
            fields=result.fields,
            body=result.body,
            has_frontmatter=result.has_frontmatter,
            errors=errors,
            warnings=warnings,
        )
    return result


def claim_bucket_hint(claim_status: str) -> str | None:
    """Map agent claim to a soft drawer hint (never alone decisive)."""
    status = (claim_status or "").strip().lower()
    if status in CLAIM_COMPLETED:
        return "completed"
    if status in CLAIM_FAILED:
        return "failed"
    if status in CLAIM_BLOCKED or status in CLAIM_PARTIAL:
        return "needs_attention"
    return None


def render_minimal_frontmatter(
    *,
    run_id: str,
    agent: str,
    skill: str,
    status: str,
    extra: Mapping[str, object] | None = None,
) -> str:
    """Canonical minimal block for salvage/fallback writers."""
    data: dict[str, object] = {
        "run_id": run_id or "unknown",
        "agent": agent or "unknown",
        "skill": skill or "unknown",
        "status": status or "completed",
        "claim_status": status or "completed",
        # The worker must flip this deliberately and add ``claim``. A fallback
        # or launcher-normalized report never self-finalizes by construction.
        "finalized": "false",
    }
    if extra:
        for key, value in extra.items():
            if value is not None and str(value).strip() != "":
                data[str(key)] = value
    order = [
        "run_id",
        "agent",
        "skill",
        "project",
        "status",
        "claim_status",
        "claim_kind",
        "finalized",
        "claim",
        "date",
        "session_id",
        "model",
        "repo_path",
    ]
    lines = ["---"]
    emitted: set[str] = set()
    for key in order:
        if key in data:
            lines.append(f"{key}: {data[key]}")
            emitted.add(key)
    for key in sorted(k for k in data if k not in emitted):
        lines.append(f"{key}: {data[key]}")
    lines.extend(["---", ""])
    return "\n".join(lines)


def _render_frontmatter_fields(fields: Mapping[str, str], body: str) -> str:
    """Re-render a frontmatter block from an already-parsed field mapping + body."""
    return render_minimal_frontmatter(
        run_id=fields.get("run_id", ""),
        agent=fields.get("agent", ""),
        skill=fields.get("skill", ""),
        status=fields.get("status", "completed"),
        extra={
            key: value
            for key, value in fields.items()
            if key not in REQUIRED_KEYS and key != "status"
        },
    ) + body.lstrip("\n")


def materialize_launcher_report_template(
    path: str | Path,
    *,
    run_id: str,
    agent: str,
    skill: str,
    claim_digest: str = "",
) -> bool:
    """Create the machine-owned identity shell before the worker writes.

    The marker makes the untouched shell fail artifact validation as
    ``report_missing``. The worker must add evidence or an explicit claim; the
    launcher later removes the marker and stamps the child agent session.
    """

    report = Path(path)
    try:
        if report.is_file() and report.stat().st_size > 0:
            return False
    except OSError:
        return False
    report.parent.mkdir(parents=True, exist_ok=True)
    extra = {
        "claim_status": "pending",
        "finalized": "false",
        "session_id": _PENDING_TEMPLATE_STATUS,
        _LAUNCHER_TEMPLATE_KEY: "true",
    }
    launcher_digest = str(claim_digest or "").strip()
    if launcher_digest:
        extra["claim_digest"] = launcher_digest
    report.write_text(
        render_minimal_frontmatter(
            run_id=run_id,
            agent=agent,
            skill=skill,
            status=_PENDING_TEMPLATE_STATUS,
            extra=extra,
        ),
        encoding="utf-8",
    )
    return True


def stamp_launcher_report_identity(
    path: str | Path,
    *,
    run_id: str,
    session_id: str,
    agent: str,
    skill: str,
    status: str,
    model: str = "",
    claim_digest: str = "",
) -> bool:
    """Authoritatively stamp launcher-owned identity without clobbering claims."""

    report = Path(path)
    try:
        text = report.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return False

    fields, body, has_fm = parse_report_text(text)
    if not has_fm:
        fields = {}
        body = text

    # run_id/session_id are runtime facts, never agent claims. Always replace
    # copied or guessed values. An unavailable child session stays explicit.
    fields["run_id"] = run_id or "unknown"
    fields["session_id"] = session_id or _PENDING_TEMPLATE_STATUS
    launcher_digest = str(claim_digest or "").strip()
    if launcher_digest:
        fields["claim_digest"] = launcher_digest
    if agent and not fields.get("agent"):
        fields["agent"] = agent
    if skill and not fields.get("skill"):
        fields["skill"] = skill
    if model and not fields.get("model"):
        fields["model"] = model
    if not fields.get("status"):
        fields["status"] = status or "completed"
    if not fields.get("claim_status"):
        fields["claim_status"] = fields["status"]
    if "finalized" not in fields:
        fields["finalized"] = "false"

    template_pending = fields.get(_LAUNCHER_TEMPLATE_KEY, "").strip().lower() in _TRUTHY
    worker_touched = any(
        (
            bool(body.strip()),
            fields.get("finalized", "").strip().lower() in _TRUTHY,
            bool(fields.get("claim", "").strip()),
            fields.get("status", "").strip().lower()
            not in {"", _PENDING_TEMPLATE_STATUS},
        )
    )
    if template_pending and worker_touched:
        fields.pop(_LAUNCHER_TEMPLATE_KEY, None)

    normalized = _render_frontmatter_fields(fields, body)
    if normalized == text:
        return False
    report.write_text(normalized, encoding="utf-8")
    return True


def ensure_frontmatter_on_text(
    text: str,
    *,
    run_id: str = "",
    agent: str = "",
    skill: str = "",
    status: str = "completed",
    extra: Mapping[str, object] | None = None,
) -> str:
    """If text lacks a valid frontmatter block, prepend a minimal one."""
    fields, body, has_fm = parse_report_text(text)
    if has_fm:
        # Merge missing required keys without clobbering agent claim.
        changed = False
        for key, value in (
            ("run_id", run_id),
            ("agent", agent),
            ("skill", skill),
        ):
            if value and not fields.get(key):
                fields[key] = value
                changed = True
        if not fields.get("status") and status:
            fields["status"] = status
            changed = True
        if not fields.get("claim_status") and fields.get("status"):
            fields["claim_status"] = fields["status"]
            changed = True
        if "finalized" not in fields:
            fields["finalized"] = "false"
            changed = True
        if extra:
            for key, extra_value in extra.items():
                if (
                    extra_value is not None
                    and str(extra_value).strip()
                    and key not in fields
                ):
                    fields[key] = str(extra_value)
                    changed = True
        if not changed:
            return text if text.endswith("\n") else text + "\n"
        return render_minimal_frontmatter(
            run_id=fields.get("run_id", run_id),
            agent=fields.get("agent", agent),
            skill=fields.get("skill", skill),
            status=fields.get("status", status),
            extra={
                k: v
                for k, v in fields.items()
                if k not in REQUIRED_KEYS and k != "status"
            },
        ) + body.lstrip("\n")

    return render_minimal_frontmatter(
        run_id=run_id,
        agent=agent,
        skill=skill,
        status=status,
        extra=extra,
    ) + (text.lstrip("\n") if text else "")
