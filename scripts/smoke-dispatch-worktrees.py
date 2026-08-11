#!/usr/bin/env python3
"""Run a real local two-worker dispatch smoke and persist its runtime receipt."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path

CORE_ROOT = Path(__file__).resolve().parents[1] / "vibecrafted-core"
sys.path.insert(0, str(CORE_ROOT))


def _git(repo: Path, *args: str) -> str:
    process = subprocess.run(
        ["git", *args], cwd=repo, capture_output=True, text=True, check=True
    )
    return process.stdout.strip()


def _seed_repo(root: Path) -> str:
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "agents@vetcoders.io")
    _git(root, "config", "user.name", "Vibecrafted smoke")
    _git(
        root,
        "remote",
        "add",
        "origin",
        "git@github.com:vetcoders/vibecrafted-smoke.git",
    )
    (root / ".gitignore").write_text("target/\n", encoding="utf-8")
    (root / "README.md").write_text("parallel smoke\n", encoding="utf-8")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "smoke baseline")
    return _git(root, "rev-parse", "HEAD")


def _plan(repo: Path):
    from vibecrafted_core.dispatch.schema import parse_dispatch

    return parse_dispatch(
        f'''schema = "vibecrafted.dispatch.v1"
[meta]
name = "two-worker-parallel-smoke"
repo = "{repo}"
[policy]
concurrency = 2
allow_concurrency = true
require_commit = true
await = {{ poll_s = 0.02, timeout_min = 2.0 }}

[[cuts]]
id = "smoke-left"
agent = "local-smoke"
workflow = "implement"
prompt = "write the left proof"
  [[cuts.verify]]
  run = "test -f smoke-left.txt"
  expect = {{ exit_code = 0 }}

[[cuts]]
id = "smoke-right"
agent = "local-smoke"
workflow = "implement"
prompt = "write the right proof"
  [[cuts.verify]]
  run = "test -f smoke-right.txt"
  expect = {{ exit_code = 0 }}

[[cuts]]
id = "smoke-join"
agent = "local-smoke"
workflow = "implement"
integrator = true
depends_on = ["smoke-left", "smoke-right"]
prompt = "integrate both verified branches"
  [[cuts.verify]]
  run = "test -f smoke-left.txt && test -f smoke-right.txt && test -f smoke-join.txt"
  expect = {{ exit_code = 0 }}
'''
    )


def main() -> int:
    from vibecrafted_core.dispatch.receipts import DispatchReceiptStore
    from vibecrafted_core.dispatch.supervisor import (
        CellRun,
        cleanup_settled_run,
        run_dispatch,
    )
    from vibecrafted_core.dispatch.worktrees import canonical_artifact_root

    run_id = f"dispatch-smoke-{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    with tempfile.TemporaryDirectory(prefix="vibecrafted-dispatch-smoke-") as temporary:
        repo = Path(temporary) / "vibecrafted-smoke"
        baseline = _seed_repo(repo)
        dispatch = _plan(repo)
        dispatch = replace(
            dispatch,
            meta=replace(
                dispatch.meta,
                baseline={
                    "head": baseline,
                    "branch": _git(repo, "branch", "--show-current"),
                },
            ),
        )
        artifact_root = canonical_artifact_root(repo)
        reports = artifact_root / "reports" / "parallel-smoke" / run_id
        reports.mkdir(parents=True, exist_ok=True)

        def launcher(cut, _prompt: str, kind: str) -> CellRun:
            root = Path(cut.runtime_root)
            report = reports / f"{cut.id}.md"
            if cut.integrator:
                body = (
                    "git merge --quiet --no-ff --no-edit cut/smoke-left\n"
                    "git merge --quiet --no-ff --no-edit cut/smoke-right\n"
                    "printf joined > smoke-join.txt\n"
                    "git add smoke-join.txt\n"
                    'git commit --quiet -m "smoke-join local integration"\n'
                )
            else:
                marker = root / f"{cut.id}.txt"
                body = (
                    "sleep 0.5\n"
                    f"printf {shlex.quote(cut.id)} > {shlex.quote(str(marker))}\n"
                    f"git add {shlex.quote(marker.name)}\n"
                    f"git commit --quiet -m {shlex.quote(cut.id + ' local parallel smoke')}\n"
                )
            script = (
                "set -eu\n"
                + body
                + f"printf '%s\\n' {shlex.quote('completed ' + cut.id)} > {shlex.quote(str(report))}\n"
            )
            process = subprocess.Popen(["bash", "-c", script], cwd=root)
            return CellRun(
                cut_id=cut.id,
                kind=kind,
                accepted=True,
                run_id=f"local-{run_id}-{cut.id}",
                pid=process.pid,
                report_path=str(report),
                proc=process,
            )

        result = run_dispatch(
            dispatch,
            launcher=launcher,
            artifacts_dir=artifact_root / "plans" / "dispatch" / run_id,
            run_id=run_id,
            manage_worktrees=True,
        )
        store = DispatchReceiptStore(run_id, dispatch.cuts, concurrency=2)
        before_cleanup = store.read()
        left = before_cleanup["cuts"]["smoke-left"]
        right = before_cleanup["cuts"]["smoke-right"]
        join = before_cleanup["cuts"]["smoke-join"]
        sibling_overlap = max(
            left["launching_epoch_ns"], right["launching_epoch_ns"]
        ) < min(left["reported_epoch_ns"], right["reported_epoch_ns"])
        join_after_siblings = join["integrating_epoch_ns"] >= max(
            left["settled_epoch_ns"], right["settled_epoch_ns"]
        )
        cleanup = cleanup_settled_run(dispatch, run_id)
        payload = {
            "schema": "vibecrafted.parallel-smoke-receipt.v1",
            "run_id": run_id,
            "result": result.to_dict(),
            "sibling_overlap": sibling_overlap,
            "join_after_siblings": join_after_siblings,
            "worker_roots_distinct": left["worktree_path"] != right["worktree_path"],
            "worker_targets_distinct": left["target_path"] != right["target_path"],
            "cleanup": cleanup,
            "receipts_before_cleanup": before_cleanup,
            "receipts_after_cleanup": store.read(),
        }
        receipt = reports / "parallel-smoke-receipt.json"
        receipt.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(receipt)
        return (
            0
            if all(
                (
                    sibling_overlap,
                    join_after_siblings,
                    payload["worker_roots_distinct"],
                    payload["worker_targets_distinct"],
                    all(state == "[x]" for state in result.states.values()),
                )
            )
            else 1
        )


if __name__ == "__main__":
    raise SystemExit(main())
