from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactValidation:
    meta_path: Path | None
    report_path: Path | None
    transcript_path: Path | None
    meta_exists: bool
    report_exists: bool
    transcript_exists: bool
    report_valid: bool
    transcript_has_output: bool
    meta_payload: dict[str, Any] = field(default_factory=dict)
    errors: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.errors

    def as_payload(self) -> dict[str, Any]:
        return {
            "meta": str(self.meta_path) if self.meta_path else None,
            "report": str(self.report_path) if self.report_path else None,
            "transcript": str(self.transcript_path) if self.transcript_path else None,
            "meta_exists": self.meta_exists,
            "report_exists": self.report_exists,
            "transcript_exists": self.transcript_exists,
            "report_valid": self.report_valid,
            "transcript_has_output": self.transcript_has_output,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def _as_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    return value if isinstance(value, Path) else Path(value)


def _read_meta(path: Path | None) -> tuple[dict[str, Any], list[str], list[str]]:
    if path is None:
        return {}, [], []
    if not path.exists():
        return {}, [], []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"meta_invalid_json:{exc.lineno}:{exc.colno}"], []
    if not isinstance(data, dict):
        return {}, ["meta_invalid_shape"], []
    return data, [], []


def _first_meta_path(meta: dict[str, Any], names: tuple[str, ...]) -> Path | None:
    for name in names:
        value = meta.get(name)
        if isinstance(value, str) and value:
            return Path(value)
    artifacts = meta.get("artifacts")
    if isinstance(artifacts, dict):
        for name in names:
            value = artifacts.get(name)
            if isinstance(value, str) and value:
                return Path(value)
    return None


def _is_non_empty_file(path: Path | None) -> bool:
    if path is None or not path.exists() or not path.is_file():
        return False
    try:
        return path.stat().st_size > 0
    except OSError:
        return False


def validate_artifacts(
    *,
    meta_path: str | Path | None = None,
    report_path: str | Path | None = None,
    transcript_path: str | Path | None = None,
    require_report: bool = True,
    require_transcript_output: bool = False,
) -> ArtifactValidation:
    meta = _as_path(meta_path)
    meta_payload, errors, warnings = _read_meta(meta)

    report = _as_path(report_path) or _first_meta_path(
        meta_payload, ("report", "report_path")
    )
    transcript = _as_path(transcript_path) or _first_meta_path(
        meta_payload, ("transcript", "transcript_path", "trace")
    )

    meta_exists = bool(meta and meta.exists())
    report_exists = bool(report and report.exists())
    transcript_exists = bool(transcript and transcript.exists())
    report_valid = _is_non_empty_file(report)
    transcript_has_output = _is_non_empty_file(transcript)

    if require_report and not report_exists:
        errors.append("report_missing")
    elif require_report and not report_valid:
        errors.append("report_empty")

    # Mandatory frontmatter on every non-empty agent report (dashboard + triage).
    # Missing claim block is a contract failure, not a soft warning: vc-server
    # and SESSIONS f/x/n need steerable structure, not free-form markdown only.
    if report_exists and report_valid and report is not None:
        from .report_contract import validate_report_file

        fm = validate_report_file(report, require_frontmatter=True)
        for err in fm.errors:
            errors.append(err)
        for warn in fm.warnings:
            warnings.append(warn)
        if fm.fields:
            meta_payload = {
                **meta_payload,
                "report_frontmatter": fm.as_payload(),
            }
            if fm.claim_status:
                meta_payload.setdefault("report_claim_status", fm.claim_status)

    if require_transcript_output and not transcript_exists:
        errors.append("transcript_missing")
    elif require_transcript_output and not transcript_has_output:
        errors.append("transcript_empty")

    if meta is not None and not meta_exists:
        warnings.append("meta_missing")

    # Frontmatter errors invalidate the report for board purposes even if non-empty.
    if any(e.startswith("report_frontmatter_") for e in errors):
        report_valid = False

    return ArtifactValidation(
        meta_path=meta,
        report_path=report,
        transcript_path=transcript,
        meta_exists=meta_exists,
        report_exists=report_exists,
        transcript_exists=transcript_exists,
        report_valid=report_valid,
        transcript_has_output=transcript_has_output,
        meta_payload=meta_payload,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
