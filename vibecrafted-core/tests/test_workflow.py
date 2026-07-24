from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import pytest
from vibecrafted_core import workflow


def _source_dir(tmp_path: Path) -> Path:
    root = tmp_path / "src"
    root.mkdir(parents=True)
    return root


def _write_run_meta(home: Path, payload: dict[str, object]) -> Path:
    run_dir = home / "artifacts" / "Vetcoders" / "vibecrafted" / "2026_0611" / "reports"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / f"{payload['run_id']}.meta.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_normalize_launch_spec_requires_prompt_or_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Launch requires"):
        workflow.normalize_launch_spec({"skill": "workflow"}, tmp_path)


def test_normalize_launch_spec_prune_without_input_uses_discovery_prompt(
    tmp_path: Path,
) -> None:
    spec = workflow.normalize_launch_spec(
        {"skill": "prune", "agent": "claude", "root": str(tmp_path)},
        tmp_path,
    )

    assert spec.skill == "prune"
    assert spec.agent == "claude"
    assert spec.file == ""
    assert "Repository health / prune ACTION run." in spec.prompt
    assert (
        "Never `--no-verify`. Never `git push` — push is an operator button."
        in spec.prompt
    )
    assert "Mode: DISCOVER -> PROVE -> CUT -> COMMIT." in spec.prompt


def test_normalize_launch_spec_uses_registry_for_marbles_defaults(
    tmp_path: Path,
) -> None:
    spec = workflow.normalize_launch_spec(
        {"skill": "marbles", "agent": "codex", "root": str(tmp_path)},
        tmp_path,
    )

    assert spec.prompt == ""
    assert spec.count == 3
    assert spec.depth == 3


def test_normalize_launch_spec_keeps_justdo_as_own_skill(tmp_path: Path) -> None:
    spec = workflow.normalize_launch_spec(
        {"skill": "justdo", "agent": "codex", "prompt": "ship"},
        tmp_path,
    )

    assert spec.skill == "justdo"
    assert spec.agent == "codex"


def test_normalize_launch_spec_reads_model_from_brief_frontmatter(
    tmp_path: Path,
) -> None:
    brief = tmp_path / "brief.md"
    brief.write_text(
        "---\nmodel: opus\ntitle: sample cut\n---\n\ndo the work\n",
        encoding="utf-8",
    )

    spec = workflow.normalize_launch_spec(
        {"skill": "implement", "agent": "claude", "file": str(brief)},
        tmp_path,
    )

    assert spec.model == "opus"


def test_normalize_launch_spec_model_flag_wins_over_brief_frontmatter(
    tmp_path: Path,
) -> None:
    brief = tmp_path / "brief.md"
    brief.write_text("---\nmodel: opus\n---\n\ndo the work\n", encoding="utf-8")

    spec = workflow.normalize_launch_spec(
        {
            "skill": "implement",
            "agent": "claude",
            "file": str(brief),
            "model": "claude-sonnet-5",
        },
        tmp_path,
    )

    assert spec.model == "claude-sonnet-5"


def test_normalize_launch_spec_no_model_without_frontmatter(tmp_path: Path) -> None:
    brief = tmp_path / "brief.md"
    brief.write_text("do the work\n", encoding="utf-8")

    spec = workflow.normalize_launch_spec(
        {"skill": "implement", "agent": "claude", "file": str(brief)},
        tmp_path,
    )

    assert spec.model == ""


def test_artifact_slug_skips_boilerplate_research_words() -> None:
    assert (
        workflow._artifact_slug(
            "perform the research workflow on ACP versus native cli agent", "fallback"
        )
        == "acp-versus-native"
    )


def test_artifact_org_repo_reads_git_config_with_duplicate_options(
    tmp_path: Path,
) -> None:
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text(
        '[branch "release"]\n'
        "\tvscode-merge-base = a\n"
        "\tvscode-merge-base = b\n"
        '[remote "origin"]\n'
        "\turl = https://github.com/vetcoders/vibecrafted.git\n",
        encoding="utf-8",
    )

    assert workflow._artifact_org_repo(tmp_path) == ("vetcoders", "vibecrafted")


def test_launch_workflow_returns_pid_and_logs_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setenv("VIBECRAFTED_CLAIM_DIGEST", "ambient-wrong")
    source = _source_dir(tmp_path)
    spec = workflow.normalize_launch_spec(
        {"skill": "workflow", "agent": "claude", "prompt": "go"},
        source,
    )

    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import os, sys; "
                "assert sys.stdin.read() == Path(os.environ['VIBECRAFTED_PROMPT_PATH']).read_text(); "
                "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text('ok\\n')"
            ),
        ],
    )
    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert isinstance(payload["pid"], int)
    assert payload["prompt_file"]
    assert ".vibecrafted/artifacts/local/src/" in payload["report"]
    assert "/reports/workflow/" in payload["report"]
    assert Path(payload["report"]).name.endswith("_go_report.md")
    assert ".vibecrafted/control_plane/runtime_runs/" in payload["transcript"]
    assert ".vibecrafted/control_plane/runtime_runs/" in payload["meta"]
    assert ".vibecrafted/control_plane/runtime_runs/" in payload["prompt_file"]
    assert payload["workflow"] == {
        "id": "workflow",
        "phase": "write",
        "can_modify_code": True,
        "runtime_kind": "direct_agent",
        "tooling": ["vc-init", "vc-research", "vc-justdo"],
        "lifecycle_order": 40,
    }
    assert "go" not in payload["worker_command"]
    log_lines = Path(payload["launch_log"]).read_text(encoding="utf-8").splitlines()
    assert any(json.loads(line).get("event") == "spawned" for line in log_lines)
    assert payload["control_plane"] == {
        "sync": "deferred",
        "run_id": payload["run_id"],
    }


def test_launch_workflow_preseeds_machine_owned_claim_digest(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    source = _source_dir(tmp_path)
    digest = "9e0d59e1dc48bc42"
    spec = workflow.WorkflowLaunchSpec(
        agent="codex",
        mode="implement",
        skill="implement",
        prompt="close the bound mission",
        file="",
        runtime="headless",
        root=str(source),
        lifecycle_state_path="/control-plane/lifecycle/state.json",
        claim_digest=digest,
    )
    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: [sys.executable, "-c", "pass"],
    )

    payload = workflow.launch_workflow(spec, source)

    truth = workflow.await_launch_truth(
        payload,
        timeout_seconds=10,
        interval_seconds=0.05,
        require_transcript_output=False,
    )
    assert truth["completed"] is True
    meta = json.loads(Path(payload["meta"]).read_text(encoding="utf-8"))
    assert meta["run_id"] == payload["run_id"]
    assert meta["claim_digest"] == digest
    assert f"claim_digest: {digest}" in Path(payload["report"]).read_text(
        encoding="utf-8"
    )
    assert "ambient-wrong" not in Path(payload["report"]).read_text(encoding="utf-8")
    exports = workflow._runtime_script_exports(
        run_id=payload["run_id"],
        prompt_path=Path(payload["prompt_file"]),
        report_path=Path(payload["report"]),
        transcript_path=Path(payload["transcript"]),
        meta_path=Path(payload["meta"]),
        agent="codex",
        skill="implement",
        runtime="terminal",
        claim_digest=digest,
    )
    assert exports["VIBECRAFTED_CLAIM_DIGEST"] == digest


def test_launch_workflow_never_runs_global_sync_after_spawn(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    source = _source_dir(tmp_path)
    spec = workflow.normalize_launch_spec(
        {"skill": "workflow", "agent": "claude", "prompt": "go"}, source
    )
    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: [sys.executable, "-c", "pass"],
    )
    monkeypatch.setattr(
        workflow,
        "sync_state",
        lambda: pytest.fail("launch acknowledgement must not acquire board-sync lock"),
    )

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert payload["control_plane"]["sync"] == "deferred"


def test_launch_workflow_records_skipped_model_override_for_unknown_flag(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    source = _source_dir(tmp_path)
    spec = workflow.WorkflowLaunchSpec(
        agent="agy",
        mode="implement",
        skill="implement",
        prompt="go",
        file="",
        runtime="headless",
        root=str(source),
        model="gemini-pro",
    )
    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import os; "
                "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text('ok\\n')"
            ),
        ],
    )

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert (
        payload["model_requested"] == "gemini-pro"
    )  # Google family label preserved for agy telemetry
    assert payload["model_override_supported"] is False
    assert payload["model_override_skipped"] is True
    assert payload["model_override_skip_reason"] == "unsupported_agent_model_flag"
    assert "gemini-pro" not in payload["worker_command"]


def test_launch_workflow_records_failure_event_when_spawn_errors(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    source = _source_dir(tmp_path)
    spec = workflow.normalize_launch_spec(
        {"skill": "workflow", "agent": "claude", "prompt": "go"},
        source,
    )
    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: [sys.executable, "-c", "pass"],
    )

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("no such dispatcher binary")

    monkeypatch.setattr(workflow.subprocess, "Popen", _boom)

    events: list[dict[str, Any]] = []
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: events.append(kwargs),
    )

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is False
    assert "no such dispatcher binary" in payload["error"]
    # A terminal "failed" event must be recorded — otherwise the earlier
    # "launch accepted" (state="created") strands the run as a phantom active
    # run that reconciliation never resolves.
    states = [event["payload"].get("state") for event in events]
    assert "failed" in states


def test_launch_workflow_reports_read_phase_metadata(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    spec = workflow.normalize_launch_spec(
        {"skill": "dou", "agent": "codex", "prompt": "audit launch readiness"},
        tmp_path,
    )
    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import os; "
                "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text('ok\\n')"
            ),
        ],
    )

    payload = workflow.launch_workflow(spec, tmp_path)

    assert payload["workflow"]["phase"] == "read"
    assert payload["workflow"]["can_modify_code"] is False
    assert payload["workflow"]["tooling"] == ["vc-init", "vc-intents", "vc-loctree"]


def test_launch_workflow_keeps_dispatcher_launch_even_if_worker_command_is_bad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    spec = workflow.WorkflowLaunchSpec(
        agent="claude",
        mode="workflow",
        skill="workflow",
        prompt="go",
        file="",
        runtime="headless",
        root=str(tmp_path),
    )

    def _missing_command(*_args: Any, **_kwargs: Any) -> list[str]:
        return ["definitely-missing-vibecrafted-binary"]

    monkeypatch.setattr(workflow, "build_launch_command", _missing_command)
    payload = workflow.launch_workflow(spec, tmp_path)

    assert payload["accepted"] is True
    assert payload["run_id"]
    assert payload["worker_command"] == ["definitely-missing-vibecrafted-binary"]


def test_build_launch_command_never_delegates_to_legacy_shell_runtime() -> None:
    """RC 3.2.0 polarize contract: vibecrafted-core is the single runtime.

    build_launch_command must spawn through the Python runtime
    (vibecrafted_core.workflow_runtime) or an agent stdin command — never a
    legacy runtime/scripts/*_spawn.sh launcher or the bash deck. This locks the
    split-brain shut so it cannot re-grow.
    """
    for skill, agent in (
        ("marbles", "codex"),
        ("polarize", "codex"),
        ("research", "claude"),
        ("implement", "codex"),
    ):
        spec = workflow.WorkflowLaunchSpec(
            agent=agent,
            mode=skill,
            skill=skill,
            prompt="x",
            file="",
            runtime="headless",
            root="/tmp",
        )
        cmd = workflow.build_launch_command(spec, "/tmp", prompt_file="/tmp/p.md")
        joined = " ".join(cmd)
        assert "_spawn.sh" not in joined, f"{skill} delegates to legacy shell: {joined}"
        assert "scripts/vibecrafted" not in joined, f"{skill} calls the deck: {joined}"

    marbles = workflow.build_launch_command(
        workflow.WorkflowLaunchSpec(
            agent="codex",
            mode="marbles",
            skill="marbles",
            prompt="x",
            file="",
            runtime="headless",
            root="/tmp",
        ),
        "/tmp",
        prompt_file="/tmp/p.md",
    )
    assert marbles[0] == sys.executable
    assert "vibecrafted_core.workflow_runtime" in marbles


def test_build_launch_command_applies_stage_model_flags_by_runner(
    tmp_path: Path,
) -> None:
    claude = workflow.build_launch_command(
        workflow.WorkflowLaunchSpec(
            agent="claude",
            mode="implement",
            skill="implement",
            prompt="x",
            file="",
            runtime="headless",
            root=str(tmp_path),
            model="opus",
        ),
        tmp_path,
        prompt_file=tmp_path / "p.md",
    )
    assert claude[:3] == ["claude", "--model", "opus"]

    codex = workflow.build_launch_command(
        workflow.WorkflowLaunchSpec(
            agent="codex",
            mode="implement",
            skill="implement",
            prompt="x",
            file="",
            runtime="headless",
            root=str(tmp_path),
            model="gpt-5.5",
        ),
        tmp_path,
        prompt_file=tmp_path / "p.md",
    )
    assert codex[:4] == ["codex", "exec", "-m", "gpt-5.5"]

    agy = workflow.build_launch_command(
        workflow.WorkflowLaunchSpec(
            agent="agy",
            mode="implement",
            skill="implement",
            prompt="x",
            file="",
            runtime="headless",
            root=str(tmp_path),
            model="gemini-pro",  # model name may be Google family even on agy
        ),
        tmp_path,
        prompt_file=tmp_path / "p.md",
    )
    assert "gemini-pro" not in agy
    assert "--model" not in agy
    assert "-m" not in agy

    marbles = workflow.build_launch_command(
        workflow.WorkflowLaunchSpec(
            agent="codex",
            mode="marbles",
            skill="marbles",
            prompt="x",
            file="",
            runtime="headless",
            root=str(tmp_path),
            model="gpt-5.5",
        ),
        tmp_path,
        prompt_file=tmp_path / "p.md",
    )
    assert marbles[marbles.index("--model") + 1] == "gpt-5.5"


def test_terminal_runtime_launches_worker_in_vc_frame_tab(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.delenv("VIBECRAFTED_OPERATOR_SESSION", raising=False)
    monkeypatch.setenv("VC_FRAME_SESSION_NAME", "operator-live")
    source = _source_dir(tmp_path)
    vc_frame = tmp_path / "bin" / "vc-frame"
    vc_frame.parent.mkdir()
    vc_frame.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    spec = workflow.WorkflowLaunchSpec(
        agent="codex",
        mode="implement",
        skill="implement",
        prompt="go",
        file="",
        runtime="terminal",
        root=str(tmp_path),
    )
    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: ["codex", "exec"],
    )
    monkeypatch.setattr(
        workflow.shutil,
        "which",
        lambda name: str(vc_frame) if name == "vc-frame" else None,
    )
    monkeypatch.setattr(workflow, "_vc_frame_session_active", lambda _vc, _s: True)

    captured: dict[str, Any] = {}

    def fake_host_action(
        command: list[str], *, operator_session: str, timeout: float = 30.0
    ) -> workflow._HostActionResult:
        captured["command"] = command
        captured["operator_session"] = operator_session
        return workflow._HostActionResult(True, 4242, "", "", False)

    monkeypatch.setattr(workflow, "_vc_frame_run_host_action", fake_host_action)

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert payload["pid"] == 4242
    assert payload["transport"] == "vc-frame"
    assert captured["command"][:5] == [
        str(vc_frame),
        "--session",
        tmp_path.name,
        "action",
        "new-tab",
    ]
    assert payload["operator_session"] == tmp_path.name
    assert "--name" in captured["command"]
    assert (
        captured["command"][captured["command"].index("--name") + 1]
        == payload["run_id"]
    )
    assert "--cwd" in captured["command"]
    assert captured["command"][captured["command"].index("--cwd") + 1] == str(tmp_path)
    script = Path(captured["command"][-1])
    assert script.is_file()
    script_body = script.read_text(encoding="utf-8")
    assert "vibecrafted_core.dispatcher" in script_body
    assert f"export PYTHONPATH={workflow._core_package_root()}" in script_body
    assert "export PYTHONDONTWRITEBYTECODE=1" in script_body
    assert "--tee-output" in script_body
    assert "--quiet" in script_body
    assert "--json" not in script_body
    assert payload["command"] == captured["command"]
    assert payload["dispatch_command"] != payload["command"]
    assert payload["control"].endswith(f"{payload['run_id']}.json")


def test_terminal_runtime_resurrects_missing_host_session(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G3: missing host → one create-background + retry, not silent headless."""
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setenv("VC_FRAME_SESSION_NAME", "host-session")
    source = _source_dir(tmp_path)
    vc_frame = tmp_path / "bin" / "vc-frame"
    vc_frame.parent.mkdir()
    state = tmp_path / "vc_state"
    state.mkdir()
    vc_frame.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'STATE="{state}"',
                'args=("$@")',
                'printf -- "--CALL--\\n" >> "$STATE/calls"',
                'printf "%s\\n" "$@" >> "$STATE/calls"',
                'if [[ "${1:-}" == "list-sessions" ]]; then',
                '  if [[ -f "$STATE/live" ]]; then printf "host-session [Created]\\n"; fi',
                "  exit 0",
                "fi",
                'if [[ "${1:-}" == "attach" && "${2:-}" == "--create-background" ]]; then',
                '  touch "$STATE/live"',
                '  printf "created\\n" >> "$STATE/create"',
                "  exit 0",
                "fi",
                # action path: --session NAME action ...
                'if [[ "${1:-}" == "--session" ]]; then',
                '  if [[ ! -f "$STATE/live" ]]; then',
                '    printf "Session \'%s\' not found\\n" "${2:-}" >&2',
                "    exit 1",
                "  fi",
                "  exit 0",
                "fi",
                "exit 0",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    vc_frame.chmod(0o755)

    spec = workflow.WorkflowLaunchSpec(
        agent="codex",
        mode="implement",
        skill="implement",
        prompt="go",
        file="",
        runtime="terminal",
        root=str(tmp_path),
    )
    monkeypatch.setattr(workflow, "_stdin_command", lambda _agent: ["codex", "exec"])
    monkeypatch.setattr(
        workflow.shutil,
        "which",
        lambda name: str(vc_frame) if name == "vc-frame" else None,
    )

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert payload["transport"] == "vc-frame"
    assert (state / "create").is_file()
    calls = (state / "calls").read_text(encoding="utf-8")
    assert "attach" in calls
    assert "--create-background" in calls
    assert calls.count("--CALL--") >= 2  # action + list-sessions + create etc.


def test_terminal_runtime_host_double_fail_marks_failed_with_last_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """G3: create-background also fails → state=failed + last_error immediately."""
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.setenv("VC_FRAME_SESSION_NAME", "ghost-host")
    source = _source_dir(tmp_path)
    vc_frame = tmp_path / "bin" / "vc-frame"
    vc_frame.parent.mkdir()
    vc_frame.write_text(
        '#!/usr/bin/env bash\nset -euo pipefail\nif [[ "${1:-}" == "list-sessions" ]]; then exit 0; fi\nif [[ "${1:-}" == "attach" ]]; then\n  printf "attach failed for %s\\n" "${3:-}" >&2\n  exit 1\nfi\nif [[ "${1:-}" == "--session" ]]; then\n  printf "Session \'%s\' not found\\n" "${2:-}" >&2\n  exit 1\nfi\nexit 1'
        + "\n",
        encoding="utf-8",
    )
    vc_frame.chmod(0o755)

    spec = workflow.WorkflowLaunchSpec(
        agent="codex",
        mode="implement",
        skill="implement",
        prompt="go",
        file="",
        runtime="terminal",
        root=str(tmp_path),
    )
    monkeypatch.setattr(workflow, "_stdin_command", lambda _agent: ["codex", "exec"])
    monkeypatch.setattr(
        workflow.shutil,
        "which",
        lambda name: str(vc_frame) if name == "vc-frame" else None,
    )
    # Force the operator session name the stub fails on.
    monkeypatch.setattr(
        workflow,
        "_effective_operator_session",
        lambda **_kwargs: "ghost-host",
    )

    events: list[dict[str, Any]] = []

    def _capture_event(**kwargs: Any) -> None:
        events.append(kwargs)

    monkeypatch.setattr(workflow, "append_event", _capture_event)
    monkeypatch.setattr(workflow, "sync_state", lambda: {"sync": "test"})

    t0 = time.monotonic()
    payload = workflow.launch_workflow(spec, source)
    elapsed = time.monotonic() - t0

    assert payload["accepted"] is False
    assert (
        "not found" in (payload.get("last_error") or payload.get("error") or "").lower()
        or "create-background"
        in (payload.get("last_error") or payload.get("error") or "").lower()
    )
    assert elapsed < 5.0
    states = [e.get("payload", {}).get("state") for e in events]
    assert "failed" in states
    failed = next(e for e in events if e.get("payload", {}).get("state") == "failed")
    err = str(
        failed["payload"].get("last_error") or failed["payload"].get("error") or ""
    )
    assert err
    assert "not found" in err.lower() or "create-background" in err.lower()


def test_vc_frame_session_active_parses_list_sessions(tmp_path: Path) -> None:
    vc_frame = tmp_path / "vc-frame"
    vc_frame.write_text(
        "#!/usr/bin/env bash\n"
        'if [ "$1" = "list-sessions" ]; then '
        'printf "\\033[32;1mvc-frame\\033[m [Created 2h ago]\\n"; '
        'printf "\\033[32;1maicx\\033[m [Created 3h ago]\\n"; fi\n',
        encoding="utf-8",
    )
    vc_frame.chmod(0o755)

    assert workflow._vc_frame_session_active(str(vc_frame), "vc-frame") is True
    assert workflow._vc_frame_session_active(str(vc_frame), "aicx") is True
    assert workflow._vc_frame_session_active(str(vc_frame), "vibecrafted") is False
    assert workflow._vc_frame_session_active(str(vc_frame), "") is False


def test_effective_operator_session_g7_worker_host_routing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # G7: worker host is per-project / override; never the dispatcher seat.
    # Liveness is G3's job (create-background); resolution always returns host.
    root = "/Users/x/work/vibecrafted"
    root_foo = "/Users/x/work/foo"

    # 1. Outside any pane → basename(root).
    assert (
        workflow._effective_operator_session(root=root, run_id="r1", env={})
        == "vibecrafted"
    )

    # 2. Ambient VIBECRAFTED_OPERATOR_SESSION (human seat) is ignored as target.
    assert (
        workflow._effective_operator_session(
            root=root,
            run_id="r2",
            env={"VIBECRAFTED_OPERATOR_SESSION": "vc-workspace"},
        )
        == "vibecrafted"
    )

    # 3. Dispatch from seat X for repo foo → host foo (not X).
    assert (
        workflow._effective_operator_session(
            root=root_foo,
            run_id="r3",
            env={"VC_FRAME_SESSION_NAME": "operator-X"},
        )
        == "foo"
    )

    # 4. Name collision: seat == basename → "<repo> workers".
    assert (
        workflow._effective_operator_session(
            root=root,
            run_id="r4",
            env={"VC_FRAME_SESSION_NAME": "vibecrafted"},
        )
        == "vibecrafted workers"
    )

    # 5. Explicit worker-session override wins (even over collision).
    assert (
        workflow._effective_operator_session(
            root=root,
            run_id="r5",
            env={
                "VC_FRAME_SESSION_NAME": "vibecrafted",
                "VIBECRAFTED_WORKER_SESSION": "bar",
            },
        )
        == "bar"
    )


def test_research_terminal_runtime_uses_vc_frame_research_layout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    monkeypatch.delenv("VIBECRAFTED_OPERATOR_SESSION", raising=False)
    monkeypatch.setenv("VC_FRAME_SESSION_NAME", "operator-live")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))
    source = _source_dir(tmp_path)
    vc_frame = tmp_path / "bin" / "vc-frame"
    vc_frame.parent.mkdir()
    vc_frame.write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    spec = workflow.normalize_launch_spec(
        {
            "skill": "research",
            "agent": "claude",
            "prompt": "map it",
            "runtime": "terminal",
            "root": str(tmp_path),
        },
        source,
    )
    digest = "9e0d59e1dc48bc42"
    spec = workflow.WorkflowLaunchSpec(**{**spec.to_payload(), "claim_digest": digest})
    monkeypatch.setattr(
        workflow.shutil,
        "which",
        lambda name: str(vc_frame) if name == "vc-frame" else None,
    )
    monkeypatch.setattr(workflow, "_vc_frame_session_active", lambda _vc, _s: True)

    captured: dict[str, Any] = {}

    def fake_host_action(
        command: list[str], *, operator_session: str, timeout: float = 30.0
    ) -> workflow._HostActionResult:
        captured["command"] = command
        captured["kwargs"] = {"operator_session": operator_session}
        return workflow._HostActionResult(True, 4243, "", "", False)

    monkeypatch.setattr(workflow, "_vc_frame_run_host_action", fake_host_action)

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    runtime_bucket = (
        tmp_path / ".vibecrafted" / "control_plane" / "runtime_runs" / payload["run_id"]
    )
    assert Path(payload["report"]).parent.name == "research"
    assert "/artifacts/local/" in payload["report"]
    assert "/reports/research/" in payload["report"]
    assert Path(payload["transcript"]).parent == runtime_bucket
    assert Path(payload["meta"]).parent == runtime_bucket
    assert Path(payload["prompt_file"]).parent == runtime_bucket
    # Host-action path does not re-Popen; report path is still on the receipt.
    assert payload["report"]
    assert Path(payload["report"]).parent.name == "research"
    command = captured["command"]
    assert command[:5] == [
        str(vc_frame),
        "--session",
        tmp_path.name,
        "action",
        "new-tab",
    ]
    assert "--layout" in command
    layout = Path(command[command.index("--layout") + 1])
    assert layout.is_file()
    layout_body = layout.read_text(encoding="utf-8")
    assert 'pane name="synthesis"' in layout_body
    assert 'pane name="claude"' in layout_body
    assert 'pane name="codex"' in layout_body
    assert 'pane name="agy"' in layout_body or 'pane name="codex"' in layout_body
    launch_dir = Path(payload["command_script"]).parent
    lane_bodies = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(launch_dir.glob(f"{payload['run_id']}-research-*.sh"))
    )
    assert "research-lane --agent claude" in lane_bodies
    assert "research-lane --agent codex" in lane_bodies
    assert (
        "research-lane --agent agy" in lane_bodies
        or "research-lane --agent codex" in lane_bodies
    )
    assert "export VIBECRAFTED_RUN_ID=" in lane_bodies
    assert "export VIBECRAFTED_REPORT_PATH=" in lane_bodies
    assert "export VIBECRAFTED_TRANSCRIPT_PATH=" in lane_bodies
    assert "export VIBECRAFTED_META_PATH=" in lane_bodies
    assert "export VIBECRAFTED_PROMPT_PATH=" in lane_bodies
    assert f"export VIBECRAFTED_CLAIM_DIGEST={digest}" in lane_bodies
    assert "export VIBECRAFTED_CANONICAL_REPORT_DIR=" in lane_bodies
    assert "export VIBECRAFTED_ARTIFACT_SLUG=map-it" in lane_bodies
    assert (
        f"export VIBECRAFTED_ARTIFACT_TS={workflow.time.strftime('%Y-%m-%d')}"
        in lane_bodies
    )
    assert "export VIBECRAFTED_TEE_OUTPUT=1" in lane_bodies
    assert "${VIBECRAFTED_PROMPT_PATH}" not in lane_bodies
    assert "--" not in command
    assert payload["worker_command"][3] == "research-synthesis"
    assert payload["transport"] == "vc-frame"


def test_claude_terminal_command_streams_visible_json(tmp_path: Path) -> None:
    spec = workflow.WorkflowLaunchSpec(
        agent="claude",
        mode="audit",
        skill="audit",
        prompt="prove it",
        file="",
        runtime="terminal",
        root=str(tmp_path),
    )

    command = workflow.build_launch_command(spec, tmp_path)

    assert command[:4] == ["claude", "-p", "--output-format", "stream-json"]
    assert "--verbose" in command
    assert "--dangerously-skip-permissions" in command


def test_stream_capable_agents_use_native_stream_commands(tmp_path: Path) -> None:
    expected = {
        "codex": ("--json",),
        "agy": ("bash", "-c"),  # agy uses bash -c shim containing agy
        "junie": ("--output-format", "json-stream"),
        "grok": ("--output-format", "streaming-json"),
    }

    for agent, required in expected.items():
        spec = workflow.WorkflowLaunchSpec(
            agent=agent,
            mode="audit",
            skill="audit",
            prompt="prove it",
            file="",
            runtime="terminal",
            root=str(tmp_path),
        )

        command = workflow.build_launch_command(spec, tmp_path)

        for token in required:
            assert token in command


def test_runtime_prompt_keeps_metadata_runtime_owned(tmp_path: Path) -> None:
    spec = workflow.WorkflowLaunchSpec(
        agent="codex",
        mode="workflow",
        skill="workflow",
        prompt="ship it",
        file="",
        runtime="headless",
        root=str(tmp_path),
    )

    prompt = workflow._runtime_prompt(spec)

    assert "Write your final report to the path in VIBECRAFTED_REPORT_PATH" in prompt
    assert "`run_id` and `session_id`" in prompt
    assert "preserve those values and never copy or guess identity" in prompt
    assert "keeping `finalized: false`" in prompt
    assert "`finalized: true` plus a non-empty `claim`" in prompt
    assert "non-empty `agent`, `skill`, and `status` keys" in prompt
    assert "Preserve an honest blocked/partial/failed status" in prompt
    assert "runtime owns VIBECRAFTED_META_PATH" in prompt
    assert "If you create or update run metadata" not in prompt
    # Every dispatched worker is oriented first: the vc-init Step 0 rides in the
    # runtime prompt itself, not left to each skill's prose gate to self-enforce.
    assert "Step 0 — orient before you touch (the vc-init pass)." in prompt
    assert "Loctree context atlas" in prompt
    assert "AICX history" in prompt


def test_launch_workflow_artifact_paths_are_terminal_truth(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / ".vibecrafted"))
    source = _source_dir(tmp_path)
    spec = workflow.normalize_launch_spec(
        {"skill": "workflow", "agent": "claude", "prompt": "go"},
        source,
    )

    monkeypatch.setattr(
        workflow,
        "_stdin_command",
        lambda _agent: [
            sys.executable,
            "-c",
            (
                "from pathlib import Path; import os, sys; "
                "assert 'launcher truth worker complete' not in sys.stdin.read(); "
                "Path(os.environ['VIBECRAFTED_REPORT_PATH']).write_text("
                "'---\\nstatus: completed\\nnext_stage: polarize\\n"
                "next_agent: codex\\ndou_index: 3\\n---\\nbody\\n', "
                "encoding='utf-8'"
                "); "
                "print('launcher truth worker complete')"
            ),
        ],
    )

    payload = workflow.launch_workflow(spec, source)

    assert payload["accepted"] is True
    assert payload["run_id"]
    assert payload["report"]
    assert payload["transcript"]
    assert payload["meta"]
    assert payload["prompt_file"]
    assert payload["control_plane_identity"] == {
        "run_id": payload["run_id"],
        "session_id": payload["session_id"],
        "operator_session": payload["operator_session"],
    }

    truth = workflow.await_launch_truth(
        payload,
        timeout_seconds=10,
        interval_seconds=0.05,
        require_transcript_output=True,
    )

    assert truth["completed"] is True
    assert truth["terminal_evidence"] is True
    assert truth["worker_alive"] is False
    assert truth["artifact_ok"] is True
    assert truth["paths_exist"] == {
        "report": True,
        "transcript": True,
        "meta": True,
    }
    assert truth["run"]["state"] in {"completed", "report_validated"}
    assert truth["run"]["liveness"] == "terminal"
    assert truth["run"]["artifact_gate"] == "validated"
    assert truth["meta_payload"]["run_id"] == payload["run_id"]
    assert truth["meta_payload"]["terminal"] is True
    assert truth["meta_payload"]["state"] == truth["run"]["state"]
    assert truth["meta_payload"]["report"] == payload["report"]
    assert truth["next_stage"] == "polarize"
    assert truth["next_agent"] == "codex"
    assert truth["dou_index"] == 3


def test_report_requested_next_stage_reads_report_frontmatter(
    tmp_path: Path,
) -> None:
    report = tmp_path / "report.md"
    report.write_text(
        "---\nstatus: completed\nnext_stage: marbles\n---\nbody\n",
        encoding="utf-8",
    )
    assert workflow._report_requested_next_stage(str(report)) == "marbles"

    bare = tmp_path / "bare.md"
    bare.write_text("no frontmatter here\n", encoding="utf-8")
    assert workflow._report_requested_next_stage(str(bare)) == ""
    assert workflow._report_requested_next_stage("") == ""
    assert workflow._report_requested_next_stage(str(tmp_path / "missing.md")) == ""


def test_report_requested_next_agent_reads_report_frontmatter(
    tmp_path: Path,
) -> None:
    report = tmp_path / "report.md"
    report.write_text(
        "---\nstatus: completed\nnext_agent: junie\n---\nbody\n",
        encoding="utf-8",
    )
    assert workflow._report_requested_next_agent(str(report)) == "junie"

    bare = tmp_path / "bare.md"
    bare.write_text("no frontmatter here\n", encoding="utf-8")
    assert workflow._report_requested_next_agent(str(bare)) == ""
    assert workflow._report_requested_next_agent("") == ""
    assert workflow._report_requested_next_agent(str(tmp_path / "missing.md")) == ""


def test_report_dou_index_reads_report_frontmatter(tmp_path: Path) -> None:
    zero = tmp_path / "zero.md"
    zero.write_text(
        "---\nstatus: completed\ndou_index: 0\n---\nbody\n", encoding="utf-8"
    )
    # 0 is the whole point (ZERO DoU index) — it must survive as 0, not None.
    assert workflow.report_dou_index(str(zero)) == 0

    gaps = tmp_path / "gaps.md"
    gaps.write_text(
        "---\nstatus: completed\ndou_index: 7\n---\nbody\n", encoding="utf-8"
    )
    assert workflow.report_dou_index(str(gaps)) == 7

    for invalid in ("banana", "-2", "true"):
        bad = tmp_path / "bad.md"
        bad.write_text(
            f"---\nstatus: completed\ndou_index: {invalid}\n---\nbody\n",
            encoding="utf-8",
        )
        assert workflow.report_dou_index(str(bad)) is None

    bare = tmp_path / "bare.md"
    bare.write_text("no frontmatter here\n", encoding="utf-8")
    assert workflow.report_dou_index(str(bare)) is None
    assert workflow.report_dou_index("") is None
    assert workflow.report_dou_index(str(tmp_path / "missing.md")) is None


def test_stop_run_terms_live_launcher_process_group(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    proc = subprocess.Popen(["sleep", "60"], start_new_session=True)
    try:
        _write_run_meta(
            home,
            {
                "run_id": "wflw-live-stop",
                "status": "running",
                "agent": "codex",
                "mode": "workflow",
                "root": str(tmp_path),
                "updated_at": "2026-06-11T00:00:00+00:00",
                "skill_code": "wflw",
                "launcher_pid": proc.pid,
                "liveness": "pid_alive",
            },
        )

        payload = workflow.stop_run(
            "wflw-live-stop", reason="manual", grace_seconds=0.05
        )
        proc.wait(timeout=2)

        assert payload["accepted"] is True
        assert payload["target"] == "launcher_pid"
        assert payload["target_pid"] == proc.pid
        assert payload["target_pgid"] == proc.pid
        assert payload["signal_sent"] is True
        run = payload["run"]
        assert run["state"] == "stopped"
        assert run["exit_code"] == 143
        assert run["operator_state"] == "stopped"
        assert run["lifecycle"]["stop"] is False
    finally:
        if proc.poll() is None:
            proc.terminate()
            proc.wait(timeout=2)


def test_stop_run_records_already_dead_launcher_without_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    _write_run_meta(
        home,
        {
            "run_id": "wflw-dead-stop",
            "status": "running",
            "agent": "codex",
            "mode": "workflow",
            "root": str(tmp_path),
            "updated_at": "2026-06-11T00:00:00+00:00",
            "skill_code": "wflw",
            "launcher_pid": 999999999,
            "liveness": "pid_alive",
        },
    )

    payload = workflow.stop_run("wflw-dead-stop", reason="manual", grace_seconds=0)

    assert payload["accepted"] is True
    assert payload["already_dead"] is True
    assert payload["error"] == ""
    run = payload["run"]
    assert run["state"] == "stopped"
    assert run["liveness"] == "terminal"
    assert run["stop_already_dead"] is True
    assert run["lifecycle"]["stop"] is False


def test_stop_run_terminal_record_is_noop(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    home = tmp_path / ".vibecrafted"
    monkeypatch.setenv("VIBECRAFTED_HOME", str(home))
    _write_run_meta(
        home,
        {
            "run_id": "wflw-terminal-stop",
            "status": "completed",
            "agent": "codex",
            "mode": "workflow",
            "root": str(tmp_path),
            "updated_at": "2026-06-11T00:00:00+00:00",
            "skill_code": "wflw",
            "exit_code": 0,
            "launcher_pid": 999999999,
            "liveness": "terminal",
        },
    )

    payload = workflow.stop_run("wflw-terminal-stop", reason="manual")

    assert payload["accepted"] is False
    assert payload["reason"] == "run_terminal"
    run = workflow.lookup_run("wflw-terminal-stop")
    assert run is not None
    assert run["state"] == "completed"
    assert run["exit_code"] == 0
    assert run["lifecycle"]["stop"] is False


def test_block_run_marks_active_run_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    states = iter(["active", "blocked"])
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": next(states),
            "exit_code": None,
        },
    )
    calls: dict[str, Any] = {}
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: calls.setdefault("events", []).append(kwargs),
    )

    payload = workflow.block_run(
        "wflw-010101-0001", reason="needs creds", note="api key"
    )

    assert payload["accepted"] is True
    assert payload["run"]["state"] == "blocked"
    event = calls["events"][0]
    assert event["kind"] == "audit:block"
    assert event["payload"]["state"] == "blocked"
    assert event["payload"]["note"] == "api key"


def test_block_run_rejects_terminal_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {"run_id": run_id, "state": "completed", "exit_code": 0},
    )
    calls: dict[str, Any] = {}
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: calls.setdefault("events", []).append(kwargs),
    )

    payload = workflow.block_run("wflw-010101-0001")

    assert payload["accepted"] is False
    assert payload["reason"] == "run_terminal"
    assert calls["events"][0]["payload"]["accepted"] is False


def test_retry_run_relaunches_terminal_run(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        workflow,
        "lookup_run",
        lambda run_id: {
            "run_id": run_id,
            "state": "failed",
            "agent": "claude",
            "skill": "workflow",
            "mode": "workflow",
            "runtime": "headless",
            "prompt": "go",
            "file": "",
            "root": str(tmp_path),
            "exit_code": 1,
        },
    )
    captured: dict[str, Any] = {}

    def _launch(
        spec: workflow.WorkflowLaunchSpec,
        source_dir: str | Path,
        *,
        env: dict[str, str] | None = None,
        retry_of: str = "",
    ) -> dict[str, Any]:
        captured["spec"] = spec
        captured["source_dir"] = str(source_dir)
        captured["retry_of"] = retry_of
        return {"accepted": True, "run_id": "wflw-020202-0002"}

    monkeypatch.setattr(workflow, "launch_workflow", _launch)
    monkeypatch.setattr(
        workflow,
        "append_event",
        lambda **kwargs: captured.setdefault("events", []).append(kwargs),
    )

    payload = workflow.retry_run("wflw-010101-0001", source_dir=tmp_path)

    assert payload["accepted"] is True
    assert payload["retry_run_id"] == "wflw-020202-0002"
    assert captured["retry_of"] == "wflw-010101-0001"


def test_build_launch_command_uses_core_stdin_agent_command_not_legacy_deck(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, str] = {}

    def _fake_stdin(agent: str) -> list[str]:
        captured["agent"] = agent
        return ["agent-bin", "-"]

    monkeypatch.setattr(workflow, "_stdin_command", _fake_stdin)
    spec = workflow.WorkflowLaunchSpec(
        agent="claude",
        mode="implement",
        skill="implement",
        prompt="ship it",
        file="",
        runtime="headless",
        root=str(tmp_path),
    )

    command = workflow.build_launch_command(spec, tmp_path / "source")

    assert command[0] == "agent-bin"
    assert command[0:2] != [
        "bash",
        str(tmp_path / "source" / "scripts" / "vibecrafted"),
    ]
    assert command == ["agent-bin", "-"]
    assert captured["agent"] == "claude"


def test_research_swarm_uses_core_codex_coordinator(
    tmp_path: Path,
) -> None:
    spec = workflow.normalize_launch_spec(
        {"skill": "research", "prompt": "map the surface", "root": str(tmp_path)},
        tmp_path,
    )

    command = workflow.build_launch_command(spec, tmp_path)

    assert spec.agent == "swarm"
    assert command[:3] == [sys.executable, "-m", "vibecrafted_core.workflow_runtime"]
    assert command[3] == "research"
    assert "--prompt-file" in command
    assert "map the surface" not in command


def test_research_agentless_form_uses_runtime_config_swarm(tmp_path: Path) -> None:
    spec = workflow.normalize_launch_spec(
        {"skill": "research", "prompt": "map the surface", "root": str(tmp_path)},
        tmp_path,
    )

    assert spec.agent == "swarm"
    assert spec.research_agents == ()
    assert spec.research_synthesizer == ""


def test_research_single_agent_form_keeps_synthesizer_pick(tmp_path: Path) -> None:
    spec = workflow.normalize_launch_spec(
        {
            "skill": "research",
            "agent": ["claude"],
            "prompt": "map the surface",
            "root": str(tmp_path),
        },
        tmp_path,
    )

    command = workflow.build_launch_command(spec, tmp_path)

    assert spec.agent == "swarm"
    assert spec.research_agents == ()
    assert spec.research_synthesizer == "claude"
    assert command[command.index("--synthesizer") + 1] == "claude"


def test_research_multi_agent_form_overrides_lanes_and_first_synthesizes(
    tmp_path: Path,
) -> None:
    spec = workflow.normalize_launch_spec(
        {
            "skill": "research",
            "agent": ["codex", "agy"],
            "prompt": "map the surface",
            "root": str(tmp_path),
        },
        tmp_path,
    )

    assert spec.agent == "swarm"
    assert spec.research_agents == ("codex", "agy")
    assert spec.research_synthesizer == "codex"


def test_marbles_uses_supervised_core_runtime(tmp_path: Path) -> None:
    spec = workflow.normalize_launch_spec(
        {
            "skill": "marbles",
            "agent": "codex",
            "prompt": "converge",
            "root": str(tmp_path),
            "count": 2,
            "depth": 4,
        },
        tmp_path,
    )

    command = workflow.build_launch_command(spec, tmp_path)

    assert command[:3] == [sys.executable, "-m", "vibecrafted_core.workflow_runtime"]
    assert command[3] == "marbles"
    assert command[command.index("--workflow") + 1] == "marbles"
    assert "--prompt-file" in command
    assert command[command.index("--count") + 1] == "2"
    assert command[command.index("--depth") + 1] == "4"


def test_polarize_uses_supervised_marbles_runtime_with_polarize_prompt(
    tmp_path: Path,
) -> None:
    spec = workflow.normalize_launch_spec(
        {
            "skill": "polarize",
            "agent": "codex",
            "prompt": "cut excess",
            "root": str(tmp_path),
            "count": 2,
            "depth": 4,
        },
        tmp_path,
    )

    command = workflow.build_launch_command(spec, tmp_path)

    assert spec.prompt == "cut excess"
    assert command[:3] == [sys.executable, "-m", "vibecrafted_core.workflow_runtime"]
    assert command[3] == "marbles"
    assert command[command.index("--workflow") + 1] == "polarize"
    assert "--prompt-file" in command
    assert command[command.index("--count") + 1] == "2"
    assert command[command.index("--depth") + 1] == "4"


def test_runtime_prompt_carries_worker_signal_discipline(tmp_path: Path) -> None:
    spec = workflow.WorkflowLaunchSpec(
        agent="codex",
        mode="workflow",
        skill="workflow",
        prompt="ship it",
        file="",
        runtime="headless",
        root=str(tmp_path),
    )

    prompt = workflow._runtime_prompt(spec)

    # Gate-nap prevention (docs/runtime/AGENT_OPS.md, Class 1): every dispatched
    # worker is told WHY waiting is futile, not merely forbidden from doing it —
    # the bare prohibition was broken in the wild.
    assert "background-task completions will NEVER wake" in prompt
    assert "Never end your turn waiting" in prompt


def test_dispatcher_command_carries_lifecycle_state_flag() -> None:
    base = {
        "run_id": "impl-1",
        "root": "/repo",
        "meta_path": Path("/tmp/m.json"),
        "report_path": Path("/tmp/r.md"),
        "transcript_path": Path("/tmp/t.log"),
        "worker_command": ["codex", "exec"],
    }

    with_state = workflow._dispatcher_command(
        **base, lifecycle_state_path="/cp/lifecycle_runs/x/state.json"
    )
    assert "--lifecycle-state" in with_state
    flag_index = with_state.index("--lifecycle-state")
    assert with_state[flag_index + 1] == "/cp/lifecycle_runs/x/state.json"

    without_state = workflow._dispatcher_command(**base)
    assert "--lifecycle-state" not in without_state
