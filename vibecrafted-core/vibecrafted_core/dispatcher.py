from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from typing import Sequence

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
