"""Real server + real Guardian proof for f/x/n recovery semantics."""

from __future__ import annotations

import http.client
import json
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import pytest
from vibecrafted_core.events import append_event
from vibecrafted_core.guardian import GuardianState

REPO_ROOT = Path(__file__).resolve().parents[3]
CORE_ROOT = REPO_ROOT / "vibecrafted-core"

FAKE_CODEX = """#!/usr/bin/env python3
import json
import os
import sys

args = sys.argv[1:]
if args == ["--version"]:
    print("codex-cli 0.999.0")
    raise SystemExit(0)
if args == ["--help"]:
    print("usage: codex")
    print("commands: exec resume")
    raise SystemExit(0)

record = {
    "argv": args,
    "agent_session_id": os.environ.get("VIBECRAFTED_AGENT_SESSION_ID", ""),
    "pid": os.getpid(),
}
with open(os.environ["VC_GUARDIAN_PROOF_CODEX_LOG"], "a", encoding="utf-8") as handle:
    handle.write(json.dumps(record, sort_keys=True) + "\\n")
print(
    json.dumps(
        {
            "type": "thread.started",
            "thread_id": record["agent_session_id"],
        }
    ),
    flush=True,
)
print(json.dumps({"type": "turn.completed"}), flush=True)
"""


def _http_json(url: str, *, timeout: float = 5.0) -> dict[str, Any]:
    target = urlsplit(url)
    assert target.scheme == "http"
    assert target.hostname == "127.0.0.1"
    assert target.port is not None
    path = target.path or "/"
    if target.query:
        path = f"{path}?{target.query}"
    connection = http.client.HTTPConnection(
        target.hostname, target.port, timeout=timeout
    )
    try:
        connection.request("GET", path, headers={"Accept": "application/json"})
        response = connection.getresponse()
        assert response.status == 200, (url, response.status)
        payload = json.loads(response.read().decode("utf-8"))
    finally:
        connection.close()
    assert isinstance(payload, dict), payload
    return payload


def _wait_until(
    predicate: Callable[[], Any],
    *,
    timeout: float = 20.0,
    description: str,
) -> Any:
    deadline = time.monotonic() + timeout
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = predicate()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            last = f"{type(exc).__name__}: {exc}"
        if last:
            return last
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {description}; last={last!r}")


def _run_module(
    module: str,
    args: list[str],
    *,
    env: dict[str, str],
    cwd: Path,
    expected_rc: int = 0,
) -> dict[str, Any]:
    result = subprocess.run(
        [sys.executable, "-m", module, *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == expected_rc, (
        module,
        args,
        result.returncode,
        result.stdout,
        result.stderr,
    )
    payload = json.loads(result.stdout)
    assert isinstance(payload, dict), payload
    return payload


def _git_repo(path: Path, *, label: str, env: dict[str, str]) -> str:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, env=env, check=True)
    (path / "proof.txt").write_text(f"guardian proof {label}\n", encoding="utf-8")
    subprocess.run(["git", "add", "proof.txt"], cwd=path, env=env, check=True)
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=Guardian Proof",
            "-c",
            "user.email=guardian-proof@invalid.test",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-q",
            "-m",
            f"seed {label}",
        ],
        cwd=path,
        env=env,
        check=True,
    )
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=path,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    return result.stdout.strip()


def _seed_run(
    vc_home: Path,
    *,
    run_id: str,
    repo: Path,
    commit_sha: str,
    state: str,
    exit_code: int,
    agent_session_id: str,
) -> None:
    stamp = "2026-07-26T08:00:00+00:00"
    runtime_session_id = f"runtime-{run_id}"
    common = {
        "run_id": run_id,
        "agent": "codex",
        "skill": "implement",
        "mode": "workflow",
        "root": str(repo.resolve()),
        "repo_root": str(repo.resolve()),
        "commit_sha": commit_sha,
        "operator_session": f"proof-{run_id}",
        "updated_at": stamp,
        "started_at": stamp,
        "completed_at": stamp,
        "exit_code": exit_code,
        "liveness": "terminal",
        "worker_alive": False,
        "recovery_required": True,
        "stop_reason": "signal_exit",
        "agent_session_id": agent_session_id,
        "runtime_session_id": runtime_session_id,
        "attempt": 0,
    }
    meta = {
        **common,
        "status": state,
        "report": "",
        "transcript": "",
        "message": "",
        "reason": "",
    }
    snapshot = {
        **common,
        "state": state,
        "latest_report": "",
        "latest_transcript": "",
        "last_error": "",
        "health": "final",
        "source": "agent-meta",
        "lock_present": False,
    }
    runtime_dir = vc_home / "control_plane" / "runtime_runs" / run_id
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    snapshot_path = vc_home / "control_plane" / "runs" / f"{run_id}.json"
    snapshot_path.write_text(
        json.dumps(snapshot, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _trust_note(
    *,
    repo: Path,
    journal: Path,
    sha: str,
    verdict: str,
    run_id: str,
    env: dict[str, str],
) -> dict[str, Any]:
    return _run_module(
        "vibecrafted_core.trust",
        [
            "--journal",
            str(journal),
            "--repo",
            str(repo),
            "note",
            sha,
            verdict,
            "--run-id",
            run_id,
            "--claim",
            f"{run_id} settlement is backed by the isolated proof fixture",
            "--grade",
            "strong",
            "--evidence",
            f"{run_id} runtime and snapshot projections agree",
        ],
        env=env,
        cwd=repo,
    )


def _actual_invocations(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _settlement_event(vc_home: Path, run_id: str) -> dict[str, Any]:
    stream = vc_home / "control_plane" / "events.jsonl"
    matches = []
    for line in stream.read_text(encoding="utf-8").splitlines():
        payload = json.loads(line)
        if (
            payload.get("kind") == "settlement.changed"
            and payload.get("run_id") == run_id
        ):
            matches.append(payload)
    assert len(matches) == 1, matches
    return matches[0]


def test_guardian_real_server_fxn_exactly_once(
    vc_home: Path,
    live_server: tuple[str, subprocess.Popen[str]],
    server_binary: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Live SSE delivers f/x/n; only n gets one guarded native resume."""

    expected_server = (
        REPO_ROOT
        / "vibecrafted-server"
        / "target"
        / "release"
        / "vibecrafted-server-web"
    )
    assert server_binary.resolve() == expected_server.resolve(), (
        "this proof must never fall back to an installed host server",
        server_binary,
    )
    base_url, server_process = live_server
    assert server_process.poll() is None

    isolated_os_home = tmp_path / "os-home"
    fake_bin = tmp_path / "fake-bin"
    xdg_cache = tmp_path / "xdg-cache"
    xdg_config = tmp_path / "xdg-config"
    xdg_state = tmp_path / "xdg-state"
    isolated_tmp = tmp_path / "tmp"
    for directory in (
        isolated_os_home,
        fake_bin,
        xdg_cache,
        xdg_config,
        xdg_state,
        isolated_tmp,
    ):
        directory.mkdir()

    git_binary = shutil.which("git")
    assert git_binary, "real git is required to create isolated proof repositories"
    (fake_bin / "git").symlink_to(git_binary)
    codex = fake_bin / "codex"
    codex.write_text(
        FAKE_CODEX.replace("#!/usr/bin/env python3", f"#!{sys.executable}"),
        encoding="utf-8",
    )
    codex.chmod(0o755)
    codex_log = tmp_path / "codex-invocations.jsonl"
    journal = vc_home / "trust" / "journal.jsonl"
    guardian_dir = vc_home / "guardian-proof"
    guardian_dir.mkdir()
    guardian_state = guardian_dir / "state.json"
    guardian_lock = guardian_dir / "guardian.lock"
    ready_file = guardian_dir / "ready.json"
    guardian_log = guardian_dir / "guardian.log"

    monkeypatch.setenv("HOME", str(isolated_os_home))
    monkeypatch.setenv("XDG_CACHE_HOME", str(xdg_cache))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg_config))
    monkeypatch.setenv("XDG_STATE_HOME", str(xdg_state))
    monkeypatch.setenv("TMPDIR", str(isolated_tmp))
    monkeypatch.setenv("VIBECRAFTED_HOME", str(vc_home))
    monkeypatch.setenv("VIBECRAFTED_TRUST_JOURNAL", str(journal))
    monkeypatch.setenv("VIBECRAFTED_GUARD", "1")
    monkeypatch.setenv("VC_GUARDIAN_PROOF_CODEX_LOG", str(codex_log))
    monkeypatch.setenv("PATH", str(fake_bin))
    monkeypatch.setenv(
        "PYTHONPATH",
        os.pathsep.join(
            part for part in (str(CORE_ROOT), os.environ.get("PYTHONPATH", "")) if part
        ),
    )
    for key in tuple(os.environ):
        if key.startswith(("LEPTOS_", "SPAWN_")) or key == "VIBECRAFTED_ROOT":
            monkeypatch.delenv(key, raising=False)
    proof_env = os.environ.copy()
    proof_env["GIT_CONFIG_NOSYSTEM"] = "1"
    proof_env["GIT_CONFIG_GLOBAL"] = os.devnull
    assert shutil.which("codex", path=proof_env["PATH"]) == str(codex)
    assert shutil.which("claude", path=proof_env["PATH"]) is None
    assert shutil.which("grok", path=proof_env["PATH"]) is None

    repos: dict[str, Path] = {}
    shas: dict[str, str] = {}
    sessions: dict[str, str] = {}
    for cell in ("f", "x", "n"):
        repo = tmp_path / f"repo-{cell}"
        repos[cell] = repo
        shas[cell] = _git_repo(repo, label=cell, env=proof_env)
        sessions[cell] = f"codex-proof-{cell}-session"
        _seed_run(
            vc_home,
            run_id=f"proof-{cell}",
            repo=repo,
            commit_sha=shas[cell],
            state="completed" if cell == "f" else "failed",
            exit_code=0 if cell == "f" else 9,
            agent_session_id=sessions[cell],
        )

    append_event(
        kind="guardian.proof.baseline",
        run_id="",
        message="establish isolated SSE baseline",
        payload={"proof": True},
    )

    guardian_handle = guardian_log.open("w", encoding="utf-8")
    guardian = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "vibecrafted_core.guardian",
            "--server-url",
            base_url,
            "--state",
            str(guardian_state),
            "--lock",
            str(guardian_lock),
            "--ready-file",
            str(ready_file),
            "--ready-nonce",
            "guardian-proof-ready",
            "--no-desktop",
            "--connect-timeout",
            "2",
            "--recovery-timeout",
            "2",
            "--backoff-initial",
            "0.05",
            "--backoff-max",
            "0.2",
            "--replay-heartbeats",
            "4",
            "--log-level",
            "DEBUG",
        ],
        cwd=repos["n"],
        env=proof_env,
        stdout=guardian_handle,
        stderr=subprocess.STDOUT,
        text=True,
    )

    try:

        def baseline() -> GuardianState | None:
            assert guardian.poll() is None, guardian_log.read_text(
                encoding="utf-8", errors="replace"
            )
            state = GuardianState.load(guardian_state)
            return (
                state
                if state.baseline_complete and str(state.cursor).startswith("v2:")
                else None
            )

        _wait_until(
            lambda: ready_file.is_file(),
            description="Guardian HTTP readiness receipt",
        )
        _wait_until(baseline, description="authoritative Guardian SSE baseline")

        receipts = {
            "f": _trust_note(
                repo=repos["f"],
                journal=journal,
                sha=shas["f"],
                verdict="pass",
                run_id="proof-f",
                env=proof_env,
            ),
            "x": _trust_note(
                repo=repos["x"],
                journal=journal,
                sha=shas["x"],
                verdict="block",
                run_id="proof-x",
                env=proof_env,
            ),
            "n": _trust_note(
                repo=repos["n"],
                journal=journal,
                sha=shas["n"],
                verdict="pass-with-gaps",
                run_id="proof-n",
                env=proof_env,
            ),
        }
        assert {
            cell: receipt["trust_receipt"]["settlement_tui"]
            for cell, receipt in receipts.items()
        } == {"f": "f", "x": "x", "n": "n"}

        state_payload = _wait_until(
            lambda: (
                payload
                if (
                    (payload := _http_json(f"{base_url}/api/control/state"))[
                        "settlement_counts"
                    ]["f"]
                    == 1
                    and payload["settlement_counts"]["x"] == 1
                    and payload["settlement_counts"]["n"] == 1
                    and payload["settlement_counts"]["total_settled"] == 3
                )
                else None
            ),
            description="server settlement board f=x=n=1",
        )
        assert state_payload["settlement_counts"]["scope"] == (
            "retained_control_plane_snapshots"
        )

        projected_n = _http_json(f"{base_url}/api/control/runs/proof-n")
        assert projected_n["commit_sha"] == shas["n"]
        assert projected_n["trust_receipt"]["commit_sha"] == shas["n"]
        assert projected_n["controls"]["native_resume_candidate"] == {
            "agent": "codex",
            "agent_session_id": sessions["n"],
        }

        def completed_state() -> GuardianState | None:
            assert guardian.poll() is None, guardian_log.read_text(
                encoding="utf-8", errors="replace"
            )
            state = GuardianState.load(guardian_state)
            expected = {("proof-f", 1), ("proof-x", 1), ("proof-n", 1)}
            return state if set(state.processed) == expected else None

        completed = _wait_until(
            completed_state,
            description="Guardian processing all live SSE settlements",
        )
        assert completed.highwater["proof-f"].outcome == "terminal"
        assert completed.highwater["proof-f"].reason == "settlement_f_not_resumable"
        assert completed.highwater["proof-x"].outcome == "terminal"
        assert completed.highwater["proof-x"].reason == "settlement_x_not_resumable"
        assert completed.highwater["proof-n"].outcome == "accepted"
        assert completed.highwater["proof-n"].reason == "dispatched"

        invocations = _wait_until(
            lambda: (
                calls if len(calls := _actual_invocations(codex_log)) == 1 else None
            ),
            description="one fake Codex native resume",
        )
        assert invocations == [
            {
                "argv": [
                    "exec",
                    "resume",
                    "--json",
                    "--dangerously-bypass-approvals-and-sandbox",
                    sessions["n"],
                    "-",
                ],
                "agent_session_id": sessions["n"],
                "pid": invocations[0]["pid"],
            }
        ]

        guardian_text = guardian_log.read_text(encoding="utf-8", errors="replace")
        assert guardian_text.count("Vibecrafted f: finalized") == 1
        assert guardian_text.count("Vibecrafted x: failed") == 1
        assert guardian_text.count("Vibecrafted n: needs attention") == 1

        idempotency_files = list(
            (vc_home / "control_plane" / "native_resume_idempotency").glob("*.json")
        )
        assert len(idempotency_files) == 1
        idempotency = json.loads(idempotency_files[0].read_text(encoding="utf-8"))
        assert idempotency["idempotency_key"] == "settlement:proof-n:1"
        assert idempotency["parent_run_id"] == "proof-n"
        assert idempotency["agent_session_id"] == sessions["n"]
        assert idempotency["state"] == "dispatched"
        assert idempotency["automatic_attempt_number"] == 1

        triage = _run_module(
            "vibecrafted_core.trust",
            [
                "--journal",
                str(journal),
                "--repo",
                str(repos["n"]),
                "triage",
            ],
            env=proof_env,
            cwd=repos["n"],
        )
        assert triage["counts"] == {"f": 1, "x": 1, "n": 1}
        assert triage["commits"] == 3

        guard_n = _run_module(
            "vibecrafted_core.guard",
            [
                "--journal",
                str(journal),
                "--repo",
                str(repos["n"]),
                "check",
                "--sha",
                shas["n"],
                "--skill",
                "implement",
            ],
            env=proof_env,
            cwd=repos["n"],
        )
        assert guard_n["allowed"] is True
        assert guard_n["reason"] == "trust_verdict_pass-with-gaps"
        guard_x = _run_module(
            "vibecrafted_core.guard",
            [
                "--journal",
                str(journal),
                "--repo",
                str(repos["x"]),
                "check",
                "--sha",
                shas["x"],
                "--skill",
                "implement",
            ],
            env=proof_env,
            cwd=repos["x"],
            expected_rc=1,
        )
        assert guard_x["allowed"] is False
        assert guard_x["reason"] == "trust_block"

        before_replay = GuardianState.load(guardian_state)
        duplicate = _settlement_event(vc_home, "proof-n")
        append_event(
            kind=str(duplicate["kind"]),
            run_id=str(duplicate["run_id"]),
            message=str(duplicate["message"]),
            payload=dict(duplicate["payload"]),
        )
        replayed = _wait_until(
            lambda: (
                state
                if (state := GuardianState.load(guardian_state)).cursor
                != before_replay.cursor
                else None
            ),
            description="Guardian consuming duplicate settlement over live SSE",
        )
        assert set(replayed.processed) == {
            ("proof-f", 1),
            ("proof-x", 1),
            ("proof-n", 1),
        }
        assert _actual_invocations(codex_log) == invocations
        replay_log = guardian_log.read_text(encoding="utf-8", errors="replace")
        assert replay_log.count("Vibecrafted f: finalized") == 1
        assert replay_log.count("Vibecrafted x: failed") == 1
        assert replay_log.count("Vibecrafted n: needs attention") == 1
        assert (
            len(
                list(
                    (vc_home / "control_plane" / "native_resume_idempotency").glob(
                        "*.json"
                    )
                )
            )
            == 1
        )
    finally:
        if guardian.poll() is None:
            guardian.terminate()
            try:
                guardian.wait(timeout=5)
            except subprocess.TimeoutExpired:
                guardian.kill()
                guardian.wait(timeout=2)
        guardian_handle.close()
