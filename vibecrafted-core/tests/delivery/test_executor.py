from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

from vibecrafted_core.delivery.executor import run_evidence, run_pipeline


def _script(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8")
    return path


def test_real_process_populates_execution_evidence(temp_git_repo: Path) -> None:
    source = temp_git_repo / "input.txt"
    source.write_text("witness\n", encoding="utf-8")
    output = temp_git_repo / "output.txt"
    script = _script(
        temp_git_repo / "subject.py",
        "from pathlib import Path\n"
        "data = Path('input.txt').read_text()\n"
        "Path('output.txt').write_text(data.upper())\n"
        "print('subject complete')\n",
    )

    result = run_evidence(
        "subject",
        [sys.executable, str(script)],
        cwd=temp_git_repo,
        parent_contract_id="proof-1",
        run_id="run-1",
        input_paths=[source],
        output_paths=[output],
        timeout_seconds=5,
    )

    evidence = result.evidence
    assert result.succeeded is True
    assert result.spawned is True
    assert result.timed_out is False
    assert evidence.exit_code == 0
    assert Path(evidence.resolved_executable).is_absolute()
    assert evidence.executable_sha256 and evidence.executable_sha256.startswith(
        "sha256:"
    )
    assert evidence.started_at and evidence.ended_at
    assert evidence.elapsed_ms >= 0
    assert (
        evidence.stdout_sha256
        == "sha256:" + hashlib.sha256(b"subject complete\n").hexdigest()
    )
    assert evidence.stderr_sha256.startswith("sha256:")
    assert evidence.input_digests[str(source.resolve())].startswith("sha256:")
    assert evidence.output_digests[str(output.resolve())].startswith("sha256:")
    assert evidence.repo_before["head"]
    assert evidence.repo_before["status_sha256"].startswith("sha256:")
    assert evidence.repo_after["head"] == evidence.repo_before["head"]
    assert evidence.parent_contract_id == "proof-1"
    assert evidence.run_id == "run-1"


def test_t01_missing_subject_is_failed_without_fabricated_exit_zero(
    temp_git_repo: Path,
) -> None:
    result = run_evidence(
        "subject",
        ["definitely-not-a-vibecrafted-binary"],
        cwd=temp_git_repo,
        parent_contract_id="proof-t01",
        run_id="run-t01",
    )

    assert result.succeeded is False
    assert result.spawned is False
    assert result.failure_reason
    assert result.evidence.exit_code is None
    assert result.evidence.resolved_executable == ""


def test_t04_pipeline_retains_each_exit_code_and_fails_red(
    temp_git_repo: Path,
) -> None:
    producer = _script(
        temp_git_repo / "producer.py",
        "import sys\nprint('needle')\nsys.exit(101)\n",
    )
    consumer = _script(
        temp_git_repo / "consumer.py",
        "import sys\ndata = sys.stdin.read()\nprint(data, end='')\nsys.exit(0 if 'needle' in data else 1)\n",
    )

    result = run_pipeline(
        [
            [sys.executable, str(producer)],
            [sys.executable, str(consumer)],
        ],
        cwd=temp_git_repo,
        parent_contract_id="proof-t04",
        run_id="run-t04",
        timeout_seconds=5,
    )

    assert result.segment_exit_codes == (101, 0)
    assert tuple(item.exit_code for item in result.evidences) == (101, 0)
    assert result.evidences[0].stdout_excerpt == "needle\n"
    assert result.evidences[1].stdout_excerpt == "needle\n"
    assert result.evidences[0].stdout_sha256 == result.evidences[1].stdout_sha256
    assert result.succeeded is False
    assert result.failure_reason


def test_timeout_kills_process_and_keeps_partial_stream_digests(
    temp_git_repo: Path,
) -> None:
    script = _script(
        temp_git_repo / "slow.py",
        "import time\nprint('before sleep', flush=True)\ntime.sleep(10)\n",
    )

    result = run_evidence(
        "subject",
        [sys.executable, str(script)],
        cwd=temp_git_repo,
        parent_contract_id="proof-timeout",
        run_id="run-timeout",
        timeout_seconds=0.1,
    )

    assert result.succeeded is False
    assert result.spawned is True
    assert result.timed_out is True
    assert result.evidence.exit_code is None
    assert "before sleep" in result.evidence.stdout_excerpt
    assert result.evidence.stdout_sha256.startswith("sha256:")
    assert result.evidence.stderr_sha256.startswith("sha256:")


def test_environment_manifest_is_allowlisted_and_excerpts_are_redacted(
    temp_git_repo: Path,
) -> None:
    secret = "do-not-leak-this-value"
    script = _script(
        temp_git_repo / "noisy.py",
        "print('FAKE_API_KEY=do-not-leak-this-value')\n",
    )

    result = run_evidence(
        "subject",
        [sys.executable, str(script)],
        cwd=temp_git_repo,
        parent_contract_id="proof-secret",
        run_id="run-secret",
        env={**os.environ, "FAKE_API_KEY": secret},
        timeout_seconds=5,
    )

    assert "FAKE_API_KEY" not in result.evidence.environment
    assert secret not in result.evidence.stdout_excerpt
    assert "[REDACTED]" in result.evidence.stdout_excerpt


def test_output_limit_terminates_noisy_process_with_bounded_excerpt(
    temp_git_repo: Path,
) -> None:
    script = _script(
        temp_git_repo / "noisy_forever.py",
        "import sys\n"
        "while True:\n"
        "    sys.stdout.write('x' * 4096)\n"
        "    sys.stdout.flush()\n",
    )

    result = run_evidence(
        "subject",
        [sys.executable, str(script)],
        cwd=temp_git_repo,
        parent_contract_id="proof-output-limit",
        run_id="run-output-limit",
        timeout_seconds=5,
        max_output_bytes=16_384,
        excerpt_bytes=256,
    )

    assert result.succeeded is False
    assert result.output_limit_exceeded is True
    assert result.evidence.exit_code is None
    assert len(result.evidence.stdout_excerpt.encode()) < 512
    assert "bytes omitted" in result.evidence.stdout_excerpt


def test_paths_outside_declared_roots_fail_before_spawn(
    temp_git_repo: Path, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("outside", encoding="utf-8")

    result = run_evidence(
        "subject",
        [sys.executable, "-c", "print('must not run')"],
        cwd=temp_git_repo,
        parent_contract_id="proof-roots",
        run_id="run-roots",
        input_paths=[outside],
    )

    assert result.succeeded is False
    assert result.spawned is False
    assert "outside allowed roots" in (result.failure_reason or "")
