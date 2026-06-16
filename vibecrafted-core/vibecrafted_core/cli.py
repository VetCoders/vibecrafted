from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from . import doctor as doctor_module
from .agent_stream import ANSI_PATTERN, AgentStreamParser, resolve_default_model
from .control_plane import RunNotResolved, lookup_run, resolve_run, sync_state
from .package_resources import deck_path, package_root
from .workflow import await_launch_truth, launch_workflow, normalize_launch_spec

AGENTS = {"claude", "codex", "gemini", "agy", "junie", "grok", "swarm"}
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
SUCCESS_STATES = {"report_validated", "completed", "closed"}
TERMINAL_STATES = {
    "blocked",
    "closed",
    "completed",
    "contract_failed",
    "failed",
    "ghost",
    "report_invalid",
    "report_missing",
    "report_validated",
    "stopped",
    "timed_out",
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
    for key in (
        "VIBECRAFTED_OPERATOR_SESSION",
        "VC_FRAME_SESSION_NAME",
        "VC_FRAME_SESSION_NAME",
    ):
        if str(os.environ.get(key) or "").strip():
            return "terminal"
    return "terminal" if sys.stdin.isatty() and sys.stdout.isatty() else "headless"


def _normalize_raw_args(raw_args: list[str]) -> list[str]:
    if len(raw_args) >= 2 and raw_args[0] in AGENTS and raw_args[1] in LAUNCHERS:
        return [raw_args[1], raw_args[0], *raw_args[2:]]
    return raw_args


def _field(payload: dict[str, Any], name: str, default: str = "") -> str:
    return str(payload.get(name) or default)


def _clip_line(line: str, *, max_chars: int = 500) -> str:
    if len(line) <= max_chars:
        return line
    return line[: max_chars - 1] + "…"


def _tail_lines(
    path: str, *, agent: str = "", max_lines: int = 40
) -> tuple[list[str], str]:
    if not path:
        return [], "missing_path"
    transcript = Path(path).expanduser()
    try:
        if not transcript.is_file():
            return [], "missing_file"
        lines = transcript.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return [], f"read_error:{type(exc).__name__}"
    if not lines:
        return [], "empty"
    tail = lines[-max_lines:]
    if not agent:
        return [_clip_line(line) for line in tail], ""
    parser = AgentStreamParser(agent, default_model=resolve_default_model(agent))
    rendered: list[str] = []
    saw_json = False
    for line in tail:
        if line.lstrip().startswith("{"):
            saw_json = True
        text = parser.feed_line((line + "\n").encode("utf-8"))
        for rendered_line in text.splitlines():
            clean = rendered_line.strip()
            if clean and ANSI_PATTERN.sub("", clean).strip():
                rendered.append(_clip_line(clean))
    if rendered:
        return rendered[-max_lines:], ""
    if saw_json:
        return [], "no_renderable_events"
    return [_clip_line(line) for line in tail], ""


def _parse_iso(raw: object) -> dt.datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def _run_age_seconds(run: dict[str, Any]) -> float | None:
    timestamp = _parse_iso(run.get("heartbeat_at") or run.get("updated_at"))
    if timestamp is None:
        return None
    return (dt.datetime.now(dt.timezone.utc) - timestamp).total_seconds()


def _run_succeeded(run: dict[str, Any]) -> bool:
    state = str(run.get("state") or "")
    errors = [str(item) for item in (run.get("artifact_errors") or []) if str(item)]
    return (
        state in SUCCESS_STATES and run.get("artifact_ok") is not False and not errors
    )


def _run_terminal(run: dict[str, Any]) -> bool:
    if str(run.get("state") or "") in TERMINAL_STATES:
        return True
    if str(run.get("liveness") or "") == "terminal":
        return True
    return run.get("exit_code") is not None


def _run_dead_or_stale(run: dict[str, Any], stale_after_seconds: float) -> bool:
    liveness = str(run.get("liveness") or "")
    state = str(run.get("state") or "")
    if liveness not in {"pid_gone", "missing_signal_target"} and state != "stalled":
        return False
    age = _run_age_seconds(run)
    return age is None or age >= stale_after_seconds


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


def _print_launch_input_error(*, command: str, agent: str | None, message: str) -> None:
    base = f"vibecrafted {command}"
    if agent:
        base = f"{base} {agent}"
    print(f"error: {message}", file=sys.stderr)
    print("", file=sys.stderr)
    print("Provide work for the agent with one of:", file=sys.stderr)
    print(f"  {base} --prompt 'what to do'", file=sys.stderr)
    print(f"  {base} --file /path/to/brief.md", file=sys.stderr)


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


def _print_run_status(run: dict[str, Any], *, include_tail: bool = True) -> None:
    state = str(run.get("state") or "")
    print(f"run_id:     {run.get('run_id') or ''}")
    print(f"state:      {state}")
    print(f"agent:      {run.get('agent') or ''}")
    print(f"skill:      {run.get('skill') or ''}")
    print(f"root:       {run.get('root') or ''}")
    print(f"liveness:   {run.get('liveness') or ''}")
    if run.get("last_error") and state not in {"completed", "report_validated"}:
        print(f"last_error: {run.get('last_error')}")
    print(f"report:     {run.get('latest_report') or run.get('report') or ''}")
    transcript = str(run.get("latest_transcript") or run.get("transcript") or "")
    print(f"transcript: {transcript}")
    if not include_tail:
        return
    tail, tail_error = _tail_lines(transcript, agent=str(run.get("agent") or ""))
    if tail:
        print("transcript_tail:")
        for line in tail:
            print(f"  {line}")
    else:
        print(f"transcript_tail: unavailable ({tail_error})")


def _agent_observe(agent: str, argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"vibecrafted {agent} observe")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--last", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv))
    run = _run_for_agent(agent, args.run_id, last=args.last)
    if run is None:
        if args.run_id:
            # Control-plane projection missed it; resolve read-follows-write
            # against runtime_runs/ (where the runtime writes) before giving up.
            return _observe_resolved(args.run_id, json_output=args.json)
        print("No run found. Pass --run-id or --last.", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(run, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    _print_run_status(run)
    return 0


def _observe_resolved(run_id: str, *, json_output: bool) -> int:
    try:
        resolved = resolve_run(run_id)
    except RunNotResolved as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if json_output:
        print(
            json.dumps(
                {
                    "run_id": resolved.run_id,
                    "source": resolved.source,
                    "run_dir": str(resolved.run_dir),
                    "meta": str(resolved.meta) if resolved.meta else "",
                    "transcript": str(resolved.transcript)
                    if resolved.transcript
                    else "",
                    "report": str(resolved.report) if resolved.report else "",
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    print(f"run_id:     {resolved.run_id}")
    print(f"source:     {resolved.source}")
    print(f"run_dir:    {resolved.run_dir}")
    print(f"report:     {resolved.report or ''}")
    print(f"transcript: {resolved.transcript or ''}")
    if resolved.transcript:
        tail, tail_error = _tail_lines(str(resolved.transcript))
        if tail:
            print("transcript_tail:")
            for line in tail:
                print(f"  {line}")
        else:
            print(f"transcript_tail: unavailable ({tail_error})")
    return 0


def _agent_await(agent: str, argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog=f"vibecrafted {agent} await")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--last", action="store_true")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--status-interval", type=float, default=60)
    parser.add_argument("--stale-after", type=float, default=600)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(list(argv))
    run = _run_for_agent(agent, args.run_id, last=args.last)
    if run is None:
        print("No run found. Pass --run-id or --last.", file=sys.stderr)
        return 1
    run_id = str(run.get("run_id") or "")
    if args.json:
        result = await_launch_truth(
            run_id,
            timeout_seconds=args.timeout,
            interval_seconds=args.interval,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if result.get("completed") and result.get("artifact_ok") else 1

    print("await: initial status")
    _print_run_status(run)
    last_status_printed_at = time.monotonic()

    timeout = max(float(args.timeout), 0.0)
    interval = max(float(args.interval), 0.1)
    status_interval = max(float(args.status_interval), interval)
    stale_after = max(float(args.stale_after), 0.0)
    deadline = time.monotonic() + timeout
    next_status = time.monotonic() + status_interval

    while True:
        run = lookup_run(run_id)
        if run is None:
            print(f"await: run disappeared: {run_id}", file=sys.stderr)
            return 1
        if _run_succeeded(run):
            print("await: completed")
            if time.monotonic() - last_status_printed_at > 1:
                _print_run_status(run)
            return 0
        if _run_terminal(run):
            print("await: terminal failure")
            if time.monotonic() - last_status_printed_at > 1:
                _print_run_status(run)
            return 1
        if _run_dead_or_stale(run, stale_after):
            print(
                f"await: worker dead or stale for >= {int(stale_after)}s",
            )
            if time.monotonic() - last_status_printed_at > 1:
                _print_run_status(run)
            return 1

        now = time.monotonic()
        if now >= deadline:
            print("await: timed out")
            if time.monotonic() - last_status_printed_at > 1:
                _print_run_status(run)
            return 1
        if now >= next_status:
            print("await: still running")
            _print_run_status(run)
            last_status_printed_at = now
            next_status = now + status_interval
        time.sleep(min(interval, max(deadline - now, 0.0)))


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = _normalize_raw_args(list(sys.argv[1:] if argv is None else argv))
    invoked_as = Path(sys.argv[0]).name if argv is None else "vibecrafted"

    python_commands = {"dispatch", "doctor", "stop"} | set(LAUNCHERS)
    agent_python_verbs = {"observe", "await", "stop"}
    is_lifecycle = False
    if raw_args:
        first = raw_args[0]
        second = raw_args[1] if len(raw_args) > 1 else ""
        if first in AGENTS and second in agent_python_verbs:
            # Core owns agent observe/await/stop (read-follows-write via
            # resolve_run); never delegate these to the legacy deck/observe.sh.
            is_lifecycle = False
        elif first in {"-v", "--version", "version"}:
            is_lifecycle = True
        elif first not in python_commands and not first.startswith("-"):
            is_lifecycle = True

    if is_lifecycle:
        from .runtime_paths import vibecrafted_tools_home
        import subprocess

        deck = (
            vibecrafted_tools_home() / "vibecrafted-current" / "scripts" / "vibecrafted"
        )
        if not deck.is_file():
            deck = deck_path()
        if deck.is_file():
            res = subprocess.run([str(deck), *raw_args])
            return res.returncode

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

    source_dir = args.source_dir or package_root()
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
    try:
        spec = normalize_launch_spec(payload, source_dir)
    except ValueError as exc:
        _print_launch_input_error(
            command=str(args.command), agent=args.agent, message=str(exc)
        )
        return 2
    result = launch_workflow(spec, source_dir)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _print_launch_receipt(result)
    return 0 if result.get("accepted") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
