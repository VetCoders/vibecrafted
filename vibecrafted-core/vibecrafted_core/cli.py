from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .workflow import launch_workflow, normalize_launch_spec


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vibecrafted",
        description="Vibecrafted core command surface.",
    )
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("dispatch", help="run or validate a dispatch plan")
    for name in ("workflow", "implement", "review", "research", "marbles"):
        run = sub.add_parser(name, help=f"launch vc-{name} through core runtime")
        run.add_argument("agent", nargs="?")
        run.add_argument("--prompt", default="")
        run.add_argument("--file", default="")
        run.add_argument("--runtime", default="headless")
        run.add_argument("--root", default="")
        run.add_argument("--mode", default="")
        run.add_argument("--count", type=int)
        run.add_argument("--depth", type=int)
        run.add_argument("--source-dir", default="")
        run.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    raw_args = list(sys.argv[1:] if argv is None else argv)
    if raw_args and raw_args[0] == "dispatch":
        from .dispatch.cli import main as dispatch_main

        return dispatch_main(raw_args[1:])

    parser = _build_parser()
    args = parser.parse_args(raw_args)
    if not args.command:
        parser.print_help()
        return 2

    source_dir = args.source_dir or Path(__file__).resolve().parents[2]
    payload = {
        "skill": args.command,
        "agent": args.agent,
        "prompt": args.prompt,
        "file": args.file,
        "runtime": args.runtime,
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
        print(result["message"])
        print(f"run_id={result['run_id']}")
        if result.get("report"):
            print(f"report={result['report']}")
        if result.get("transcript"):
            print(f"transcript={result['transcript']}")
    return 0 if result.get("accepted") else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
