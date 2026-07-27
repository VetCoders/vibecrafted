from __future__ import annotations

import json
from pathlib import Path

import pytest
from vibecrafted_core.runtime_transcript import (
    runtime_transcript_manifest_path,
    validate_runtime_transcript,
    write_runtime_transcript_manifest,
)


def _authorized_transcript(tmp_path: Path) -> tuple[Path, Path]:
    transcript = tmp_path / "run.transcript.log"
    transcript.write_text("durable runtime evidence\n", encoding="utf-8")
    manifest = write_runtime_transcript_manifest(transcript, run_id="run-1")
    assert manifest is not None
    return transcript, manifest


def test_manifest_round_trip_authorizes_one_canonical_transcript(
    tmp_path: Path,
) -> None:
    transcript, manifest = _authorized_transcript(tmp_path)

    assert runtime_transcript_manifest_path(transcript) == manifest
    assert validate_runtime_transcript(transcript, run_id="run-1") == transcript
    assert not list(tmp_path.glob(f".{manifest.name}.*.tmp"))


@pytest.mark.parametrize(
    "corruption",
    [
        "missing_transcript",
        "symlinked_transcript",
        "empty_transcript",
        "missing_manifest",
        "symlinked_manifest",
        "wrong_run",
        "wrong_root",
        "wrong_path",
        "wrong_bytes",
        "wrong_hash",
    ],
)
def test_validation_fails_closed_for_untrusted_evidence(
    tmp_path: Path,
    corruption: str,
) -> None:
    transcript, manifest = _authorized_transcript(tmp_path)
    requested = transcript

    if corruption == "missing_transcript":
        transcript.unlink()
    elif corruption == "symlinked_transcript":
        alias = tmp_path / "alias.log"
        alias.symlink_to(transcript)
        requested = alias
    elif corruption == "empty_transcript":
        transcript.write_bytes(b"")
    elif corruption == "missing_manifest":
        manifest.unlink()
    elif corruption == "symlinked_manifest":
        real_manifest = tmp_path / "real.manifest.json"
        manifest.rename(real_manifest)
        manifest.symlink_to(real_manifest)
    else:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
        if corruption == "wrong_run":
            payload["run_id"] = "some-other-run"
        elif corruption == "wrong_root":
            outside = tmp_path / "outside"
            outside.mkdir()
            payload["root"] = str(outside)
        elif corruption == "wrong_path":
            other = tmp_path / "other.log"
            other.write_bytes(transcript.read_bytes())
            payload["transcript"] = str(other)
        elif corruption == "wrong_bytes":
            payload["bytes"] += 1
        elif corruption == "wrong_hash":
            payload["sha256"] = "0" * 64
        manifest.write_text(json.dumps(payload) + "\n", encoding="utf-8")

    assert validate_runtime_transcript(requested, run_id="run-1") is None
