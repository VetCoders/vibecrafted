from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Sequence

from . import doctor as doctor_module
from .control_plane import lookup_run, sync_state
from .workflow import await_launch_truth, launch_workflow, normalize_launch_spec

AGENTS = {"claude", "codex", "gemini", "agy", "junie", "grok"}
LAUNCHERS = (
    "audit",
    "decorate",
    "delegate",
    "dou",
    "followup",
    "hydrate",
    "implement",
    "intents",
    "justdo",
    "marbles",
    "ownership",
    "partner",
    "polarize",
    "prune",
    "release",
    "research",
    "review",
    "scaffold",
    "workflow",
)
LAUNCH_ALIASES = {
    "justdo": "implement",
}


def _add_launch_parser(sub: argparse._SubParsersAction, name: str) -> None:
    run = sub.add_parser(name, help=f"launch vc-{name} through core runtime")
    run.add_argument("agent", nargs="?")
    run.add_argument("--prompt", default="")
    run.add_argument("--file", default="")
    run.add_argument("--runtime", default="")
    run.add_argument("--root", default="")
    run.add_argument("--mode", default="")
    run.add_argument("--count", type=int)
    run.add_argument("--depth", type=int)
    run.add_argument("--source-dir", default="")
    run.add_argument("--json", action="store_true")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibecrafted",
        description="Vibecrafted core command surface.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("dispatch", help="run or validate a dispatch plan")
    doctor = sub.add_parser("doctor", help="verify installed Vibecrafted runtime")
    doctor.add_argument("--json", action="store_true")
    for name in LAUNCHERS:
        _add_launch_parser(sub, name)
    return parser


def _default_runtime(explicit_runtime: str) -> str:
    runtime = str(explicit_runtime or "").strip()
    if runtime:
        return runtime
    return "terminal" if sys.stdin.isatty() and sys.stdout.isatty() else "headless"


def _normalize_raw_args(raw_args: list[str]) -> list[str]:
    if len(raw_args) >= 2 and raw_args[0] in AGENTS and raw_args[1] in LAUNCHERS:
        return [raw_args[1], raw_args[0], *raw_args[2:]]
    return raw_args


def _field(payload: dict[str, Any], name: str, default: str = "") -> str:
    return str(payload.get(name) or default)


def _print_launch_receipt(payload: dict[str, Any]) -> None:
    run_id = _field(payload, "run_id")
    agent = _field(payload, "agent")
    print("==================== VIBECRAFTED LAUNCH RECEIPT ====================")
    print(f"run_id:     {run_id}")
    print(f"agent:      {agent}")
    print(f"skill:      {_field(payload, 'skill')}")
    print(f"root:       {_field(payload, 'root')}")
    print(f"dispatch:   {_field(payload, 'dispatch', '0')}")
    print(f"status:     {_field(payload, 'status', 'launching')}")
    print(f"control:    {_field(payload, 'control')}")
    print(f"report:     {_field(payload, 'report')}")
    print(f"transcript: {_field(payload, 'transcript')}")
    print(f"observe:    vibecrafted {agent} observe --run-id {run_id}")
    print(f"await:      vibecrafted {agent} await --run-id {run_id}")
    print("=====================================================================")


def _run_for_agent(
    agent: str, run_id: str, *, last: bool = False
) -> dict[str, Any] | None:
    snapshot = sync_state()
    if run_id:
        return lookup_run(run_id)
    if not last:
        return None
    for key in ("active_runs", "recent_runs"):
        for run in snapshot.get(key) or []:
            if str(run.get("agent") or "") == agent:
                return dict(run)
    return None


def _agent_observe(agent: str, argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"vibecrafted {agent} observe")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--last", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv))
    run = _run_for_agent(agent, args.run_id, last=args.last)
    if run is None:
        print("No run found. Pass --run-id or --last.", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    print(f"run_id:     {run.get('run_id') or ''}")
    print(f"state:      {run.get('state') or ''}")
    print(f"agent:      {run.get('agent') or ''}")
    print(f"skill:      {run.get('skill') or ''}")
    print(f"root:       {run.get('root') or ''}")
    print(f"report:     {run.get('latest_report') or run.get('report') or ''}")
    print(f"transcript: {run.get('latest_transcript') or run.get('transcript') or ''}")
    return 0


def _agent_await(agent: str, argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"vibecrafted {agent} await")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--last", action="store_true")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv))
    run = _run_for_agent(agent, args.run_id, last=args.last)
    if run is None:
        print("No run found. Pass --run-id or --last.", file=sys.stderr)
        return 1
    result = await_launch_truth(
        str(run.get("run_id") or ""),
        timeout_seconds=args.timeout,
        interval_seconds=args.interval,
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("completed") and result.get("artifact_ok") else 1
    print(f"run_id:      {result.get('run_id') or ''}")
    print(f"completed:   {str(bool(result.get('completed'))).lower()}")
    print(f"terminal:    {str(bool(result.get('terminal'))).lower()}")
    print(f"artifact_ok: {str(bool(result.get('artifact_ok'))).lower()}")
    print(f"report:      {result.get('report') or ''}")
    print(f"transcript:  {result.get('transcript') or ''}")
    return 0 if result.get("completed") and result.get("artifact_ok") else 1


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = _normalize_raw_args(list(sys.argv[1:] if argv is None else argv))
    invoked_as = Path(sys.argv[0]).name if argv is None else "vibecrafted"
    if raw_args and raw_args[0] == "dispatch":
        from .dispatch.cli import main as dispatch_main

        return dispatch_main(raw_args[1:])
    if raw_args and raw_args[0] == "stop":
        from .wrappers import stop_main

        return stop_main(raw_args[1:])
    if len(raw_args) >= 2 and raw_args[0] in AGENTS and raw_args[1] == "stop":
        from .wrappers import stop_main

        return stop_main(["--agent", raw_args[0], *raw_args[2:]])
    if len(raw_args) >= 2 and raw_args[0] in AGENTS and raw_args[1] == "observe":
        return _agent_observe(raw_args[0], raw_args[2:])
    if len(raw_args) >= 2 and raw_args[0] in AGENTS and raw_args[1] == "await":
        return _agent_await(raw_args[0], raw_args[2:])

    parser = _build_parser()
    args = parser.parse_args(raw_args)
    if not args.command:
        parser.print_help()
        return 0 if invoked_as in {"vc-help", "vc-dashboard"} else 2
    if args.command == "doctor":
        findings = doctor_module.doctor_run()
        summary = doctor_module.doctor_summary(findings)
        if args.json:
            print(json.dumps(summary, ensure_ascii=False, indent=2))
        else:
            for finding in summary["findings"]:
                print(
                    f"{finding['level']}: {finding['component']} - {finding['message']}"
                )
            print(
                f"summary: {summary['ok']} ok, {summary['warnings']} warnings, "
                f"{summary['failures']} failures"
            )
        return 0 if summary["failures"] == 0 else 1

    source_dir = args.source_dir or Path(__file__).resolve().parents[2]
    payload = {
        "skill": LAUNCH_ALIASES.get(args.command, args.command),
        "agent": args.agent,
        "prompt": args.prompt,
        "file": args.file,
        "runtime": _default_runtime(args.runtime),
        "root": args.root or str(Path.cwd()),
        "mode": args.mode or args.command,
        "count": args.count,
        "depth": args.depth,
    }
    spec = normalize_launch_spec(payload, source_dir)
    result = launch_workflow(spec, source_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_launch_receipt(result)
    return 0 if result.get("accepted") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
