from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Sequence

from . import doctor as doctor_module
from .agent_stream import ANSI_PATTERN, AgentStreamParser, resolve_default_model
from .control_plane import (
    RunNotResolved,
    await_run,
    lookup_run,
    resolve_run,
    sync_state,
)
from .package_resources import deck_path, package_root
from .workflow import await_launch_truth, launch_workflow, normalize_launch_spec

AGENTS = {"claude", "codex", "agy", "junie", "grok", "swarm"}
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
    "paste",
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
# These installed names are symlinks to the ``vibecrafted`` Python entrypoint,
# but their behavior is still owned by the shell deck. Preserve the invoked
# name as an explicit deck verb instead of silently treating the first user
# argument as the command.
SHELL_WRAPPER_VERBS = {
    "telemetry": "telemetry",
    "vc-dashboard": "dashboard",
    "vc-dispatch": "dispatch",
    "vc-help": "help",
    "vc-init": "init",
    "vc-justdo": "justdo",
    "vc-resume": "resume",
    "vc-start": "start",
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
    if name == "research":
        run.add_argument("agent", nargs="*")
    else:
        run.add_argument("agent", nargs="?")
    if name == "paste":
        run.add_argument("--skill", default="workflow")
        run.add_argument("--root", default="")
        run.add_argument("--print-prompt", action="store_true")
        run.add_argument("--dry-run", action="store_true")
        run.add_argument("--json", action="store_true")
        return
    run.add_argument("-p", "--prompt", default="")
    run.add_argument("-f", "--file", default="")
    run.add_argument("--runtime", default="")
    run.add_argument("--root", default="")
    run.add_argument("--mode", default="")
    run.add_argument("--count", type=int)
    run.add_argument("--depth", type=int)
    run.add_argument("--model", default="")
    if name == "research":
        run.add_argument("--synthesizer", default="")
        run.add_argument("--synthesizer-model", default="")
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
    doctor.add_argument(
        "--quarantine-legacy-runs",
        action="store_true",
        help=(
            "one-shot migration: mark terminal runs without worker_pgid as "
            "reaper_ownership=legacy; best-effort recover pgid for live runs "
            "only when SPAWN_RUN_ID is positively visible"
        ),
    )
    capabilities = sub.add_parser(
        "capabilities",
        help="describe workflow execution contracts (versioned, machine-readable)",
    )
    capabilities.add_argument("--json", action="store_true")
    config = sub.add_parser(
        "config",
        help="install/wire packaged vc-frame config into the tools store and ~/.config/vc-frame",
    )
    config_sub = config.add_subparsers(dest="config_action")
    config_install = config_sub.add_parser(
        "install",
        help="stage package config → tools store + wire ~/.config/vc-frame view",
    )
    config_install.add_argument(
        "--dry-run",
        action="store_true",
        help="print the wiring plan without mutating the filesystem",
    )
    config_install.add_argument(
        "--force",
        action="store_true",
        help="replace healthy view links (default: leave healthy wiring alone)",
    )
    config_install.add_argument(
        "--prefer-repo",
        action="store_true",
        help="wire view to checkout config/vc-frame (dev mode)",
    )
    config_zshrc = config_sub.add_parser(
        "ensure-zshrc",
        help="idempotent host ~/.zshrc onboarding (create or fenced append)",
    )
    config_zshrc.add_argument("--dry-run", action="store_true")
    reap = sub.add_parser(
        "reap",
        help="terminate processes that outlived their run (survivors of terminal runs)",
    )
    reap.add_argument(
        "--dry-run",
        action="store_true",
        help="print the would-kill table with ownership evidence, signal nothing",
    )
    reap.add_argument("--json", action="store_true")
    reap.add_argument(
        "--resettle",
        action="store_true",
        help=(
            "re-run settlement over retained control_plane/runs snapshots "
            "(honest: automatic FINALIZED only from a sealed delivery or an "
            "explicit worker attestation; a traced operator waive remains an "
            "override; never from bare exit 0)"
        ),
    )
    settle = sub.add_parser(
        "settle",
        help="settlement board maintenance (resettle retained snapshots)",
    )
    settle.add_argument(
        "--resettle",
        action="store_true",
        help="re-classify retained snapshots from existing axes (no invented f)",
    )
    settle.add_argument(
        "--dry-run",
        action="store_true",
        help="count would-rewrite only; do not write snapshots",
    )
    settle.add_argument("--json", action="store_true")
    procs = sub.add_parser(
        "procs",
        help="identity-qualified process snapshot/terminate for vc-procs TUI",
    )
    procs_sub = procs.add_subparsers(dest="procs_action")
    procs_sub.add_parser("snapshot", help="JSON process snapshot")
    term = procs_sub.add_parser("terminate", help="TERM→KILL with identity proof")
    term.add_argument("--pid", type=int, required=True)
    term.add_argument("--expected-start", required=True)
    term.add_argument("--expected-command-sha256", required=True)
    term.add_argument("--expected-run-id", default="")
    for name in LAUNCHERS:
        _add_launch_parser(sub, name)
    return parser


def _live_operator_session_exists(root: str) -> bool:
    """True when a live repo-bound vc-frame session exists to host a visible tab.

    Mirrors the bash runtime's repo-bound discovery (``spawn_effective_operator_session``
    / ``spawn_session_is_live`` in ``runtime/scripts/lib/vc_frame.sh``): the operator
    session is named after ``basename "$root"`` and counts only when vc-frame lists it
    as live (not ``EXITED``). Keeping the python runtime-default decision in lockstep
    with the shell spawn path is what lets a CLI/headless/nested dispatch land as a
    visible tab instead of degrading to an invisible headless orphan.
    """
    bin_path = shutil.which("vc-frame")
    if not bin_path:
        return False
    name = os.path.basename(os.path.abspath(root.strip() or os.getcwd()))
    if not name:
        return False
    try:
        proc = subprocess.run(
            [bin_path, "list-sessions"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    for line in proc.stdout.splitlines():
        clean = ANSI_PATTERN.sub("", line)
        parts = clean.split()
        if parts and parts[0] == name and "EXITED" not in clean:
            return True
    return False


def _default_runtime(explicit_runtime: str, root: str = "") -> str:
    runtime = str(explicit_runtime or "").strip()
    if runtime:
        return runtime
    for key in (
        "VIBECRAFTED_OPERATOR_SESSION",
        "VC_FRAME_SESSION_NAME",
        "ZELLIJ_SESSION_NAME",
    ):
        if str(os.environ.get(key) or "").strip():
            return "terminal"
    if sys.stdin.isatty() and sys.stdout.isatty():
        return "terminal"
    # Non-TTY dispatch (headless agent, nested dispatch, pipe) with no inherited
    # operator-session env would otherwise pick "headless" here, skipping the
    # vc-frame tab path entirely in spawn_launch(). When the operator has a LIVE
    # repo-bound vc-frame session to host it, prefer a visible tab — that is the
    # whole "command -> vc-frame -> tab" mission. Headless stays the correct
    # fallback only when no such live session exists.
    if _live_operator_session_exists(root):
        return "terminal"
    return "headless"


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
    print(
        f"await (ARM NOW, supervisor-side): vibecrafted {agent} await --run-id {run_id}"
    )
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


def _pid_alive(pid: object) -> bool:
    if not isinstance(pid, (str, int)):
        return False
    try:
        os.kill(int(pid), 0)
    except (ProcessLookupError, ValueError, TypeError):
        return False
    except PermissionError:
        return True  # exists but owned by another user
    return True


def _apply_live_liveness(run: dict[str, Any] | None) -> dict[str, Any] | None:
    """Override a stale ``heartbeat`` liveness with a real-time pid check.

    The snapshot can keep claiming a run is alive for tens of seconds after its
    launcher dies, until the next ``sync_state`` reconciles it. observe must not
    echo that stale "active" for a process that is already gone — that is the
    verification gap (green/heartbeat shown for a dead run). If the recorded
    launcher pid is gone and the run is not already terminal, report it as
    ``pid_gone`` so the operator sees the truth, not the lag.
    """
    if not run:
        return run
    pid = run.get("launcher_pid")
    if not pid or _run_terminal(run) or _pid_alive(pid):
        return run
    run = dict(run)
    run["liveness"] = "pid_gone"
    return run


def _run_for_agent(
    agent: str, run_id: str, *, last: bool = False
) -> dict[str, Any] | None:
    snapshot = sync_state()
    if run_id:
        return _apply_live_liveness(lookup_run(run_id))
    if not last:
        return None
    for key in ("active_runs", "recent_runs"):
        for run in snapshot.get(key) or []:
            if str(run.get("agent") or "") == agent:
                return _apply_live_liveness(dict(run))
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
    # ONE await loop lives in control_plane.await_run — this verb must never
    # grow a private wall-clock loop again. The old inline loop here treated
    # --timeout as an absolute deadline and abandoned demonstrably-working
    # runs at 300s, which taught supervising agents to distrust await and
    # hedge with manual sleep/ps monitors.
    parser = argparse.ArgumentParser(prog=f"vibecrafted {agent} await")
    parser.add_argument("--run-id", default="")
    parser.add_argument("--last", action="store_true")
    parser.add_argument(
        "--timeout",
        type=float,
        default=300,
        help="idle window in seconds — resets on movement or a live worker",
    )
    parser.add_argument("--interval", type=float, default=5)
    parser.add_argument("--status-interval", type=float, default=60)
    parser.add_argument(
        "--stale-after",
        type=float,
        default=600,
        help="deprecated: superseded by the liveness-aware idle window",
    )
    parser.add_argument("--hard-cap", type=float, default=None)
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
            hard_cap_seconds=args.hard_cap,
        )
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return (
            0
            if result.get("completed")
            and result.get("artifact_ok")
            and result.get("terminal_evidence")
            else 1
        )

    print("await: initial status")
    _print_run_status(run)

    interval = max(float(args.interval), 0.1)
    status_interval = max(float(args.status_interval), interval)
    next_status = {"at": time.monotonic() + status_interval}

    def _print_progress(current: dict[str, Any] | None) -> None:
        now = time.monotonic()
        if current is not None and now >= next_status["at"]:
            print("await: still running")
            _print_run_status(current)
            next_status["at"] = now + status_interval

    result = await_run(
        run_id,
        timeout_seconds=args.timeout,
        interval_seconds=interval,
        hard_cap_seconds=args.hard_cap,
        on_poll=_print_progress,
    )
    final_run = dict(result.get("run") or {})
    reason = str(result.get("reason") or "")
    if result.get("completed"):
        worker_alive = bool(result.get("worker_alive"))
        terminal_evidence = bool(
            final_run and _run_terminal(final_run) and not worker_alive
        )
        delivered_evidence = reason == "report_delivered" and not worker_alive
        if terminal_evidence and final_run and not _run_succeeded(final_run):
            print(f"await: terminal failure ({reason})")
            _print_run_status(final_run)
            return 1
        if not (terminal_evidence or delivered_evidence):
            print(
                f"await: non-terminal completion disagreement ({reason})",
                file=sys.stderr,
            )
            if final_run:
                _print_run_status(final_run)
            return 3
        print(f"await: completed ({reason})")
        if final_run:
            _print_run_status(final_run)
        return 0
    if not result.get("found"):
        print(f"await: run disappeared: {run_id}", file=sys.stderr)
        return 1
    print(f"await: timed out ({reason})")
    if final_run:
        _print_run_status(final_run)
    return 1


def _cmd_resettle(args: argparse.Namespace) -> int:
    """Honest re-settlement of retained control_plane/runs snapshots."""
    from .lifecycle_delivery import resettle_retained_snapshots

    result = resettle_retained_snapshots(
        force=True,
        dry_run=bool(getattr(args, "dry_run", False)),
    )
    if getattr(args, "json", False):
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("ok") else 1
    before = result.get("before") or {}
    after = result.get("after") or {}
    print(
        "resettle "
        f"scanned={result.get('scanned', 0)} "
        f"rewritten={result.get('rewritten', 0)} "
        f"unchanged={result.get('unchanged', 0)} "
        f"skipped={result.get('skipped', 0)}"
        + (" (dry-run)" if result.get("dry_run") else "")
    )
    print(
        f"before: f={before.get('f', 0)} x={before.get('x', 0)} "
        f"n={before.get('n', 0)} invalid={before.get('invalid', 0)}"
    )
    print(
        f"after:  f={after.get('f', 0)} x={after.get('x', 0)} "
        f"n={after.get('n', 0)} invalid={after.get('invalid', 0)}"
    )
    print(
        "note: automatic FINALIZED comes only from a sealed delivery or an "
        "explicit worker attestation (finalized: true + claim); a traced "
        "operator waive remains an explicit override; never from bare exit 0"
    )
    return 0 if result.get("ok") else 1


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    invoked_as = Path(sys.argv[0]).name if argv is None else "vibecrafted"
    shell_wrapper_verb = SHELL_WRAPPER_VERBS.get(invoked_as) if argv is None else None
    if shell_wrapper_verb:
        raw_args = [shell_wrapper_verb, *raw_args]
    raw_args = _normalize_raw_args(raw_args)

    # `--version` / `-v` / `version` report the INSTALLED runtime version — the
    # one `vibecrafted start` / `vc-start` actually runs — read straight from the
    # package. Never delegate to the legacy bash deck: its `_version()` resolves
    # VERSION from the current working directory (`repo_root/VERSION`), so invoked
    # from inside a checkout it reports that checkout's version, not the installed
    # one. The package is what executes, so its `__version__` is the honest answer.
    if raw_args and raw_args[0] in {"-v", "--version", "version"}:
        from . import __version__

        print(f"vibecrafted {__version__}")
        return 0

    # Help is a product surface, not argparse fallout.  Resolve it before the
    # shell-deck compatibility router or any workflow runtime is imported so
    # every installed entrypoint teaches the same contract.  ``help --all``
    # deliberately stays with the deck: it is the long operational reference.
    from . import __version__
    from .help_surface import (
        has_workflow_help,
        render_root_help,
        render_workflow_help,
    )

    if not raw_args or raw_args[0] in {"-h", "--help"}:
        print(render_root_help(__version__), end="")
        return 0
    if raw_args[0] == "help":
        if len(raw_args) == 1:
            print(render_root_help(__version__), end="")
            return 0
        topic = raw_args[1].removeprefix("vc-")
        if topic not in {"--all", "--full"} and has_workflow_help(topic):
            print(render_workflow_help(topic), end="")
            return 0
    if raw_args[0] in LAUNCHERS:
        workflow_args = raw_args[1:]
        help_requested = (
            bool(workflow_args)
            and workflow_args[0] == "help"
            or any(arg in {"-h", "--help"} for arg in workflow_args)
        )
        if help_requested:
            print(render_workflow_help(raw_args[0]), end="")
            return 0

    python_commands = {
        "capabilities",
        "config",
        "dispatch",
        "doctor",
        "paste",
        "procs",
        "reap",
        "settle",
        "stop",
    } | set(LAUNCHERS)
    agent_python_verbs = {"observe", "await", "stop"}
    is_lifecycle = shell_wrapper_verb is not None
    if raw_args and shell_wrapper_verb is None:
        first = raw_args[0]
        second = raw_args[1] if len(raw_args) > 1 else ""
        if first in AGENTS and second in agent_python_verbs:
            # Core owns agent observe/await/stop (read-follows-write via
            # resolve_run); never delegate these to the legacy deck/observe.sh.
            is_lifecycle = False
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
        if shell_wrapper_verb is not None:
            print(
                f"error: {invoked_as} cannot find the runtime deck at {deck}",
                file=sys.stderr,
            )
            return 1

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
        return 0
    if args.command == "config":
        from .vc_frame_delivery import ensure_zshrc, stage_vc_frame_config

        action = getattr(args, "config_action", None)
        if action == "ensure-zshrc":
            result = ensure_zshrc(dry_run=bool(getattr(args, "dry_run", False)))
            print(f"ensure-zshrc: {result['action']} -> {result['path']}")
            return 0
        if action != "install":
            print(
                "usage: vibecrafted config install [--dry-run] [--force] [--prefer-repo]\n"
                "       vibecrafted config ensure-zshrc [--dry-run]",
                file=sys.stderr,
            )
            return 2
        plan = stage_vc_frame_config(
            dry_run=bool(getattr(args, "dry_run", False)),
            force=bool(getattr(args, "force", False)),
            prefer_repo=True if getattr(args, "prefer_repo", False) else None,
        )
        print(plan.render(), end="")
        return 0
    if args.command == "doctor":
        if getattr(args, "quarantine_legacy_runs", False):
            from .run_reaper import quarantine_legacy_runs

            quarantine = quarantine_legacy_runs()
            payload = quarantine.as_dict()
            if args.json:
                print(json.dumps(payload, ensure_ascii=False, indent=2))
            else:
                print(
                    "quarantine-legacy-runs: "
                    f"changed={payload['changed']} "
                    f"marked_legacy={len(payload['marked_legacy'])} "
                    f"recovered_pgid={len(payload['recovered_pgid'])} "
                    f"skipped_live={len(payload['skipped_live'])} "
                    f"skipped_has_pgid={len(payload['skipped_has_pgid'])} "
                    f"already_legacy={len(payload['already_legacy'])} "
                    f"parse_errors={len(payload['parse_errors'])}"
                )
                for run_id in payload["marked_legacy"]:
                    print(f"  legacy: {run_id}")
                for row in payload["recovered_pgid"]:
                    print(
                        f"  recovered: {row.get('run_id')} "
                        f"worker_pgid={row.get('worker_pgid')}"
                    )
                for err in payload["parse_errors"]:
                    print(f"  parse_error: {err}")
            return 0
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
    if args.command == "reap":
        if getattr(args, "resettle", False):
            return _cmd_resettle(args)
        from .run_reaper import main as reap_main

        reap_argv: list[str] = []
        if args.dry_run:
            reap_argv.append("--dry-run")
        if args.json:
            reap_argv.append("--json")
        return reap_main(reap_argv)
    if args.command == "settle":
        if not getattr(args, "resettle", False):
            print(
                "usage: vibecrafted settle --resettle [--dry-run] [--json]",
                file=sys.stderr,
            )
            return 2
        return _cmd_resettle(args)
    if args.command == "procs":
        from .process_control import main as procs_main

        action = getattr(args, "procs_action", None) or "snapshot"
        if action == "snapshot":
            return procs_main(["snapshot", "--json"])
        if action == "terminate":
            return procs_main(
                [
                    "terminate",
                    "--pid",
                    str(args.pid),
                    "--expected-start",
                    args.expected_start,
                    "--expected-command-sha256",
                    args.expected_command_sha256,
                    "--expected-run-id",
                    args.expected_run_id or "",
                    "--json",
                ]
            )
        print("usage: vibecrafted procs {snapshot|terminate}", file=sys.stderr)
        return 2
    if args.command == "capabilities":
        from .workflow_capabilities import (
            render_capabilities_lines,
            workflow_capabilities_payload,
        )

        capabilities_payload = workflow_capabilities_payload()
        if args.json:
            print(
                json.dumps(
                    capabilities_payload, ensure_ascii=False, indent=2, sort_keys=True
                )
            )
        else:
            for line in render_capabilities_lines(capabilities_payload):
                print(line)
        return 0
    if args.command == "paste":
        from .paste import run_namespace

        return run_namespace(args, source_dir=package_root())

    source_dir = args.source_dir or package_root()
    agent_arg = args.agent
    research_agents = ()
    if args.command == "research" and isinstance(agent_arg, list):
        research_agents = tuple(agent_arg) if len(agent_arg) > 1 else ()
    payload = {
        "skill": LAUNCH_ALIASES.get(args.command, args.command),
        "agent": args.agent,
        "prompt": args.prompt,
        "file": args.file,
        "runtime": _default_runtime(args.runtime, args.root),
        "root": args.root or str(Path.cwd()),
        "mode": args.mode or args.command,
        "count": args.count,
        "depth": args.depth,
        "model": args.model,
        "research_agents": research_agents,
        "synthesizer": getattr(args, "synthesizer", ""),
        "synthesizer_model": getattr(args, "synthesizer_model", ""),
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
