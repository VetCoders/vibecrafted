from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence

from . import loop, ui
from .lifecycle_runner import LifecycleRunSpec, _control_verbs, run_lifecycle


SUPPORTED_AGENTS = {"claude", "codex", "gemini", "agy", "junie", "grok"}

DEFAULT_SHIP_PROMPT = (
    "Run the full Vibecrafted lifecycle for this repository. Load Context Atlas, "
    "start at the selected lifecycle checkpoint, preserve READ/WRITE phase "
    "boundaries, and hand off through the manifest runner."
)


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
    args_list = list(sys.argv[1:] if argv is None else argv)
    if args_list and args_list[0] in _control_verbs():
        from .lifecycle_control import lifecycle_control_main

        return lifecycle_control_main(args_list, workflow_id="vc-ship")
    parser = argparse.ArgumentParser(prog="vc-ship")
    parser.add_argument("agent", nargs="?", default="codex")
    parser.add_argument("--checkpoint", default="")
    parser.add_argument("-f", "--file", default="")
    parser.add_argument("-p", "--prompt", default="")
    parser.add_argument("--runtime", default="")
    parser.add_argument("--root", default="")
    parser.add_argument("--foundation-receipt", default="")
    parser.add_argument("--start-stage", default="")
    parser.add_argument("--await-stages", action="store_true")
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--loop-only", action="store_true")
    args = parser.parse_args(args_list)

    if args.agent not in SUPPORTED_AGENTS:
        ui.err(
            f"unknown agent: {args.agent}",
            fix="use one of: claude · codex · gemini · agy · junie · grok",
        )
        return 1
    if args.loop_only:
        prompt = args.prompt or DEFAULT_SHIP_PROMPT
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

    # Operator invariant: stage workers fly VISIBLY, in vc-frame tabs, whenever
    # a live operator session can host them. Route through the same resolution
    # the rest of the fleet uses (cli._default_runtime → "terminal" on live
    # session/TTY, "headless" only as the degrade-not-die fallback) instead of
    # hardcoding headless. Continuations inherit spec.runtime via the baton.
    from .cli import _default_runtime

    root = args.root or str(Path.cwd())
    state = run_lifecycle(
        LifecycleRunSpec(
            workflow_id="vc-ship",
            agent=args.agent,
            # The default prompt must not shadow --file: the runner resolves
            # `spec.prompt or read(spec.file)`, so a --file mission needs an
            # empty prompt to actually reach the stage workers.
            prompt=args.prompt or ("" if args.file else DEFAULT_SHIP_PROMPT),
            file=args.file,
            root=root,
            runtime=_default_runtime(args.runtime, root),
            await_stages=args.await_stages,
            start_stage=args.start_stage or args.checkpoint or "scaffold",
            foundation_receipt_path=args.foundation_receipt,
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
