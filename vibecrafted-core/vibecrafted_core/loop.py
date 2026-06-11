from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

from . import ui


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def repo_root(start: Path | None = None) -> Path:
    proc = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start or Path.cwd(),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode == 0 and proc.stdout.strip():
        return Path(proc.stdout.strip())
    return (start or Path.cwd()).resolve()


def default_state_file(root: Path | None = None) -> Path:
    return repo_root(root) / ".vibecrafted" / "operator-loop.local.md"


@dataclass
class LoopState:
    path: Path
    fields: dict[str, str]
    prompt: str

    @property
    def active(self) -> bool:
        return self.fields.get("active") == "true"

    @property
    def iteration(self) -> int:
        return int(self.fields.get("iteration") or "0")

    @property
    def max_iterations(self) -> int:
        return int(self.fields.get("max_iterations") or "0")


def quote_yaml(value: str | None) -> str:
    if value is None:
        return "null"
    return json.dumps(value, ensure_ascii=False)


def parse_state(path: Path) -> LoopState:
    if not path.is_file():
        raise FileNotFoundError(f"no active operator loop state: {path}")
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    fields: dict[str, str] = {}
    prompt_start = 0
    if lines[:1] == ["---"]:
        for idx, line in enumerate(lines[1:], start=1):
            if line == "---":
                prompt_start = idx + 1
                break
            if ":" in line:
                key, raw = line.split(":", 1)
                fields[key.strip()] = raw.strip().strip('"')
    prompt = "\n".join(lines[prompt_start:]).lstrip("\n")
    return LoopState(path=path, fields=fields, prompt=prompt)


def write_state(path: Path, fields: dict[str, str], prompt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["---"]
    for key, value in fields.items():
        lines.append(f"{key}: {value}")
    lines.extend(["---", "", prompt])
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def update_field(state: LoopState, key: str, value: str) -> None:
    fields = dict(state.fields)
    fields[key] = value
    write_state(state.path, fields, state.prompt)


def resolve_state_file(raw: str = "") -> Path:
    if raw:
        return Path(raw).expanduser()
    env = os.environ.get("VIBECRAFTED_LOOP_STATE_FILE")
    if env:
        return Path(env).expanduser()
    return default_state_file()


def command_deck() -> str:
    return os.environ.get("VIBECRAFTED_CMD") or "vibecrafted"


def cmd_start(args: argparse.Namespace) -> int:
    state_file = resolve_state_file(args.state_file)
    prompt = args.prompt or ""
    if args.file:
        prompt = Path(args.file).expanduser().read_text(encoding="utf-8")
    if not prompt:
        ui.err("loop needs a prompt", fix='vibecrafted loop start -p "<prompt>"')
        return 1
    if args.max_iterations < 0:
        ui.err("--max-iterations must be >= 0")
        return 1
    session_id = (
        os.environ.get("CODEX_SESSION_ID")
        or os.environ.get("CLAUDE_CODE_SESSION_ID")
        or os.environ.get("VIBECRAFTED_OPERATOR_SESSION_ID")
        or ""
    )
    now = utc_now()
    fields = {
        "active": "true",
        "runtime": "operator-interactive",
        "iteration": "1",
        "session_id": quote_yaml(session_id),
        "max_iterations": str(args.max_iterations),
        "completion_promise": quote_yaml(args.completion_promise)
        if args.completion_promise
        else "null",
        "started_at": quote_yaml(now),
        "updated_at": quote_yaml(now),
        "root": quote_yaml(str(repo_root())),
    }
    write_state(state_file, fields, prompt)
    max_desc = str(args.max_iterations) if args.max_iterations else "unlimited"
    promise = args.completion_promise or "none"
    ui.ok(f"operator loop activated · iteration 1 · max {max_desc}")
    print(f"  state: {state_file}")
    print(f"  promise: {promise}")
    print()
    print("Protocol for the active Agent-Operator:")
    print("1. Work normally in this same interactive session.")
    print("2. Before final answer, run: vibecrafted loop next")
    print("3. If it prints CONTINUE, continue with the printed prompt.")
    print('4. Stop only with: vibecrafted loop complete --promise "<text>"')
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    state = parse_state(resolve_state_file(args.state_file))
    for key, value in state.fields.items():
        print(f"{key}: {value}")
    return 0


def cmd_cancel(args: argparse.Namespace) -> int:
    state = parse_state(resolve_state_file(args.state_file))
    fields = dict(state.fields)
    fields["active"] = "false"
    fields["stopped_at"] = quote_yaml(utc_now())
    fields["stop_reason"] = "cancel"
    write_state(state.path, fields, state.prompt)
    ui.ok(f"cancelled operator loop at iteration {state.fields.get('iteration', '0')}")
    return 0


def cmd_complete(args: argparse.Namespace) -> int:
    state = parse_state(resolve_state_file(args.state_file))
    expected = state.fields.get("completion_promise", "null").strip('"')
    if expected not in {"", "null"} and args.promise != expected:
        ui.err(f"promise mismatch — expected: {expected}")
        return 3
    fields = dict(state.fields)
    fields["active"] = "false"
    fields["stopped_at"] = quote_yaml(utc_now())
    fields["stop_reason"] = "promise"
    write_state(state.path, fields, state.prompt)
    if expected not in {"", "null"}:
        print(f"Completed operator loop with <promise>{expected}</promise>.")
    else:
        print("Completed operator loop.")
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    state = parse_state(resolve_state_file(args.state_file))
    if not state.active:
        print("STOP: operator loop inactive.")
        return 0
    if state.max_iterations > 0 and state.iteration >= state.max_iterations:
        fields = dict(state.fields)
        fields["active"] = "false"
        fields["stopped_at"] = quote_yaml(utc_now())
        fields["stop_reason"] = "max_iterations"
        write_state(state.path, fields, state.prompt)
        print(f"STOP: max iterations reached ({state.max_iterations}).")
        return 0
    next_iteration = state.iteration + 1
    fields = dict(state.fields)
    fields["iteration"] = str(next_iteration)
    fields["updated_at"] = quote_yaml(utc_now())
    write_state(state.path, fields, state.prompt)
    print(f"CONTINUE: operator loop iteration {next_iteration}")
    promise = state.fields.get("completion_promise", "null").strip('"')
    if promise not in {"", "null"}:
        print(
            f"Completion promise: <promise>{promise}</promise> only when completely true."
        )
    print("\n--- PROMPT ---")
    print(state.prompt, end="" if state.prompt.endswith("\n") else "\n")
    return 0


def cmd_await_run(args: argparse.Namespace) -> int:
    if args.agent not in {
        "claude",
        "codex",
        "gemini",
        "agy",
        "junie",
        "grok",
        "opencode",
    }:
        ui.err(
            f"unknown agent: {args.agent}",
            fix="use one of: claude · codex · gemini · agy · junie · grok · opencode",
        )
        return 1
    if not args.run_id:
        ui.err("await-run requires --run-id")
        return 1

    def run_wait() -> int:
        print(f"[{utc_now()}] awaiting {args.run_id} via {args.agent}")
        proc = subprocess.run(
            [command_deck(), args.agent, "await", "--run-id", args.run_id], check=False
        )
        print(f"[{utc_now()}] await finished rc={proc.returncode} for {args.run_id}")
        if proc.returncode == 0 and args.then_cmd:
            print(
                f"[{utc_now()}] running operator-approved next command via argv: {args.then_cmd}"
            )
            return subprocess.run(shlex.split(args.then_cmd), check=False).returncode
        return proc.returncode

    if args.foreground:
        return run_wait()

    log_path = (
        Path(args.log).expanduser()
        if args.log
        else repo_root()
        / ".vibecrafted"
        / "reports"
        / f"operator-loop-await-{args.run_id}.log"
    )
    log_path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "from vibecrafted_core.loop import main; "
        f"raise SystemExit(main(['await-run','--foreground','--agent',{args.agent!r},'--run-id',{args.run_id!r}"
    )
    if args.then_cmd:
        script += f",'--then-cmd',{args.then_cmd!r}"
    script += "]))"
    with log_path.open("ab") as out:
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=out,
            stderr=subprocess.STDOUT,
            cwd=repo_root(),
            env=os.environ.copy(),
        )
    ui.ok(f"await armed · {args.run_id} · pid {proc.pid}")
    print(f"  log: {log_path}")
    if args.then_cmd:
        print(f"  then: {args.then_cmd}")
    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="vibecrafted loop")
    sub = parser.add_subparsers(dest="command")

    start = sub.add_parser("start")
    start.add_argument("--state-file", default="")
    start.add_argument("-p", "--prompt", default="")
    start.add_argument("-f", "--file", default="")
    start.add_argument("--max-iterations", type=int, default=0)
    start.add_argument("--completion-promise", default="")
    start.set_defaults(func=cmd_start)

    for name, func in {
        "status": cmd_status,
        "next": cmd_next,
        "cancel": cmd_cancel,
    }.items():
        item = sub.add_parser(name)
        item.add_argument("--state-file", default="")
        item.set_defaults(func=func)

    complete = sub.add_parser("complete")
    complete.add_argument("--state-file", default="")
    complete.add_argument("--promise", default="")
    complete.set_defaults(func=cmd_complete)

    await_run = sub.add_parser("await-run")
    await_run.add_argument("--run-id", default="")
    await_run.add_argument("--agent", default="codex")
    await_run.add_argument("--then-cmd", default="")
    await_run.add_argument("--foreground", action="store_true")
    await_run.add_argument("--log", default="")
    await_run.set_defaults(func=cmd_await_run)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 2
    try:
        return int(args.func(args))
    except FileNotFoundError as exc:
        ui.err(str(exc), fix='vibecrafted loop start -p "<prompt>"')
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
