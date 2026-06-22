from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from . import loop, ui
from .lifecycle_runner import LifecycleRunSpec, run_lifecycle


SUPPORTED_AGENTS = {"claude", "codex", "gemini", "agy", "junie", "grok"}


def build_ship_prompt(agent: str, checkpoint: str, prompt: str) -> str:
    return "\n".join(
        [
            "VC-SHIP interactive supervisor loop.",
            "",
            f"agent: {agent}",
            f"checkpoint: {checkpoint}",
            "",
            "Rules:",
            "- Keep LOOP active until the ship checkpoint is genuinely handled.",
            "- Before final answer, run: vc-loop next",
            "- Complete only with: vc-loop complete --promise VC_SHIP_DONE",
            "- Use Loctree + AICX as constant context when prior intent matters.",
            "",
            "--- INPUT ---",
            prompt,
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="vc-ship")
    parser.add_argument("agent", nargs="?", default="codex")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("-f", "--file", default="")
    parser.add_argument("-p", "--prompt", default="")
    parser.add_argument("--runtime", default="")
    parser.add_argument("--root", default="")
    parser.add_argument("--start-stage", default="")
    parser.add_argument("--await-stages", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--loop-only", action="store_true")
    args = parser.parse_args(argv)

    if args.agent not in SUPPORTED_AGENTS:
        ui.err(
            f"unknown agent: {args.agent}",
            fix="use one of: claude · codex · gemini · agy · junie · grok",
        )
        return 1
    if not args.file and not args.prompt:
        ui.err("ship needs a prompt", fix='vibecrafted ship codex -p "<task>"')
        return 1

    if args.loop_only:
        prompt = args.prompt or ""
        if args.file:
            prompt = Path(args.file).expanduser().read_text(encoding="utf-8")
        loop_prompt = build_ship_prompt(
            args.agent, args.checkpoint or "scaffold", prompt
        )
        return loop.main(
            [
                "start",
                "--prompt",
                loop_prompt,
                "--completion-promise",
                "VC_SHIP_DONE",
                "--max-iterations",
                str(args.max_iterations),
            ]
        )

    state = run_lifecycle(
        LifecycleRunSpec(
            workflow_id="vc-ship",
            agent=args.agent,
            prompt=args.prompt,
            file=args.file,
            root=args.root or str(Path.cwd()),
            runtime=args.runtime or "headless",
            await_stages=args.await_stages,
            start_stage=args.start_stage or args.checkpoint or "scaffold",
        )
    )
    print("==================== VC-SHIP LIFECYCLE RECEIPT ====================")
    print(f"run_id:     {state.get('run_id')}")
    print(f"workflow:   {state.get('workflow')}")
    print(f"status:     {state.get('status')}")
    print(f"state:      {state.get('state_path')}")
    print(f"report:     {state.get('report_path')}")
    print("===================================================================")
    return 0 if state.get("status") in {"launching", "completed"} else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
