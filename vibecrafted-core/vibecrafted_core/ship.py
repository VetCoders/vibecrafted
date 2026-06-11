from __future__ import annotations

import argparse
import subprocess
from pathlib import Path
from typing import Sequence

from . import loop, ui


SUPPORTED_AGENTS = {"claude", "codex", "gemini", "agy", "junie", "grok", "opencode"}


def deck_command() -> str:
    return loop.command_deck()


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
    parser.add_argument("--checkpoint", default="workflow")
    parser.add_argument("-f", "--file", default="")
    parser.add_argument("-p", "--prompt", default="")
    parser.add_argument("--max-iterations", type=int, default=0)
    parser.add_argument("--loop-only", action="store_true")
    args = parser.parse_args(argv)

    if args.agent not in SUPPORTED_AGENTS:
        ui.err(
            f"unknown agent: {args.agent}",
            fix="use one of: claude · codex · gemini · agy · junie · grok · opencode",
        )
        return 1
    prompt = args.prompt or ""
    dispatch_args: list[str]
    if args.file:
        path = Path(args.file).expanduser()
        prompt = path.read_text(encoding="utf-8")
        dispatch_args = [
            deck_command(),
            args.checkpoint,
            args.agent,
            "--file",
            str(path),
        ]
    elif args.prompt:
        dispatch_args = [
            deck_command(),
            args.checkpoint,
            args.agent,
            "--prompt",
            args.prompt,
        ]
    else:
        ui.err("ship needs a prompt", fix='vibecrafted ship codex -p "<task>"')
        return 1

    loop_prompt = build_ship_prompt(args.agent, args.checkpoint, prompt)
    loop_rc = loop.main(
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
    if loop_rc != 0:
        return loop_rc
    if args.loop_only:
        return 0
    return subprocess.call(dispatch_args)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
