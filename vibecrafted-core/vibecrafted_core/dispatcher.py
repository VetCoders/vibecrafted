from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Sequence

from .supervisor_async import AsyncSupervisor


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m vibecrafted_core.dispatcher",
        description="Run one command under the Vibecrafted async lifecycle supervisor.",
    )
    sub = parser.add_subparsers(dest="command")
    run = sub.add_parser("run", help="spawn, observe, validate, and close one run")
    run.add_argument("--run-id", required=True)
    run.add_argument("--root", default=".")
    run.add_argument("--meta")
    run.add_argument("--report")
    run.add_argument("--transcript")
    run.add_argument(
        "--prompt-file",
        help="deliver this prompt file to the worker on stdin and VIBECRAFTED_PROMPT_PATH",
    )
    run.add_argument(
        "--lifecycle-state",
        default="",
        help=(
            "lifecycle state.json this run belongs to; on worker failure the "
            "dispatcher records the terminal truth there (push-side "
            "report-on-death)"
        ),
    )
    run.add_argument("--timeout", type=float)
    run.add_argument(
        "--no-require-report",
        action="store_true",
        help="do not fail the artifact contract when the report file is absent",
    )
    run.add_argument(
        "--require-transcript-output",
        action="store_true",
        help="require at least one byte of captured stdout/stderr",
    )
    run.add_argument(
        "--tee-output",
        action="store_true",
        help="also write worker stdout/stderr to this terminal while capturing transcript",
    )
    run.add_argument(
        "--json",
        action="store_true",
        help="print the final lifecycle summary as JSON",
    )
    run.add_argument(
        "--quiet",
        action="store_true",
        help="do not print the final lifecycle summary",
    )
    run.add_argument("worker", nargs=argparse.REMAINDER)
    return parser


def _normalize_worker(argv: Sequence[str]) -> list[str]:
    worker = list(argv)
    if worker and worker[0] == "--":
        worker = worker[1:]
    if not worker:
        raise ValueError("missing worker command after --")
    return worker


def _lifecycle_recorded_failure(state_path: str, run_id: str) -> bool:
    """True when state.json already records a FAILED worker_exit for run_id."""
    try:
        payload = json.loads(Path(state_path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    if not isinstance(payload, dict):
        return False
    candidates: list[dict[str, Any]] = []
    top = payload.get("stage_worker_exit")
    if isinstance(top, dict) and str(top.get("run_id") or "") == run_id:
        candidates.append(top)
    for stage in payload.get("stages") or []:
        if not isinstance(stage, dict):
            continue
        launch = stage.get("launch") or {}
        exit_record = stage.get("worker_exit")
        if (
            isinstance(exit_record, dict)
            and isinstance(launch, dict)
            and str(launch.get("run_id") or "") == run_id
        ):
            candidates.append(exit_record)
    for record in candidates:
        exit_code = record.get("exit_code")
        if (isinstance(exit_code, int) and exit_code != 0) or not record.get(
            "artifact_ok"
        ):
            return True
    return False


def _maybe_record_lifecycle_worker_exit(
    state_path: str, summary: dict[str, Any]
) -> None:
    """Push-side report-on-death (docs/runtime/AGENT_OPS.md, Class 2).

    Failures are always written back. A success is written back ONLY when the
    state already records a failed worker_exit for this run — i.e. a resumed
    worker just healed an earlier death, and leaving the stale failure in
    state.json would make the lifecycle and the report disagree. A healthy
    first-pass handoff still writes nothing, keeping the write rare and the
    window for racing an operator verb on state.json effectively closed.
    """
    exit_code = summary.get("exit_code")
    failed = (isinstance(exit_code, int) and exit_code != 0) or not summary.get(
        "artifact_ok"
    )
    run_id = str(summary.get("run_id") or "")
    if not failed and not _lifecycle_recorded_failure(state_path, run_id):
        return
    from .lifecycle_runner import record_stage_worker_exit

    record_stage_worker_exit(
        state_path,
        run_id,
        {
            "state": summary.get("state"),
            "exit_code": exit_code,
            "artifact_ok": bool(summary.get("artifact_ok")),
            "artifact_errors": list(summary.get("artifact_errors") or []),
            "transcript": str(summary.get("transcript") or ""),
        },
    )


async def _run(args: argparse.Namespace) -> int:
    worker = _normalize_worker(args.worker)
    handle = await AsyncSupervisor().run(
        run_id=args.run_id,
        command=worker,
        root=args.root,
        meta_path=args.meta,
        report_path=args.report,
        transcript_path=args.transcript,
        prompt_file_path=args.prompt_file,
        timeout=args.timeout,
        require_report=not args.no_require_report,
        require_transcript_output=args.require_transcript_output,
        tee_output=args.tee_output,
    )
    validation = handle.artifact_validation
    artifact_errors = list(validation.errors if validation is not None else ())
    summary = {
        "run_id": handle.run_id,
        "state": handle.state.value,
        "states": [state.value for state in handle.states],
        "exit_code": handle.exit_code,
        "root": str(handle.root),
        "report": str(handle.report_path or ""),
        "transcript": str(handle.transcript_path or ""),
        "artifact_ok": bool(validation.ok if validation is not None else False),
        "artifact_errors": artifact_errors,
    }

    lifecycle_state = str(getattr(args, "lifecycle_state", "") or "")
    if lifecycle_state:
        _maybe_record_lifecycle_worker_exit(lifecycle_state, summary)

    if args.quiet:
        pass
    elif args.json:
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    else:
        print(f"run_id: {summary['run_id']}")
        print(f"state: {summary['state']}")
        print(f"exit_code: {summary['exit_code']}")
        print(f"artifact_ok: {str(summary['artifact_ok']).lower()}")
        if artifact_errors:
            print("artifact_errors: " + ",".join(artifact_errors))

    exit_code = handle.exit_code
    if isinstance(exit_code, int) and exit_code != 0:
        return exit_code
    return 0 if summary["artifact_ok"] else 2


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command != "run":
        parser.print_help(sys.stderr)
        return 2
    if "--tee-output" in (argv or sys.argv[1:]):
        os.environ["VIBECRAFTED_TEE_OUTPUT"] = "1"
    try:
        return asyncio.run(_run(args))
    except ValueError as exc:
        print(f"dispatcher: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
