from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = REPO_ROOT / "scripts" / "vibecrafted"


def _write_fake_agent(bin_dir: Path, name: str, capture_file: Path) -> None:
    script = bin_dir / name
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _write_trimmed_launcher(script_path: Path) -> None:
    source = LAUNCHER.read_text(encoding="utf-8").splitlines()
    script_path.write_text("\n".join(source[:-1]) + "\n", encoding="utf-8")
    script_path.chmod(0o755)


def _write_fake_command(bin_dir: Path, name: str, capture_file: Path) -> None:
    script_names = [name]
    if name == "zellij":
        script_names.insert(0, "vc-frame")
    for script_name in script_names:
        script = bin_dir / script_name
        script.write_text(
            "\n".join(
                [
                    "#!/usr/bin/env bash",
                    "set -euo pipefail",
                    "{",
                    '  printf "%s\\n" "$@"',
                    '  printf "ZELLIJ_CONFIG_DIR=%s\\n" "${ZELLIJ_CONFIG_DIR:-}"',
                    '} > "$CAPTURE_FILE"',
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        script.chmod(0o755)


def _write_fake_zellij_with_live_session(
    bin_dir: Path, capture_file: Path, session_name: str
) -> None:
    script = bin_dir / "zellij"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'if [[ "${1:-}" == "ls" || "${1:-}" == "list-sessions" ]]; then',
                f'  printf "{session_name} (attached)\\n"',
                "  exit 0",
                "fi",
                "{",
                '  printf "%s\\n" "$@"',
                '  printf "ZELLIJ_CONFIG_DIR=%s\\n" "${ZELLIJ_CONFIG_DIR:-}"',
                '} > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    vc_frame = bin_dir / "vc-frame"
    vc_frame.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    vc_frame.chmod(0o755)


def _write_gc_zellij(bin_dir: Path, capture_file: Path, listing: str) -> None:
    script = bin_dir / "zellij"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                'capture = Path(os.environ["CAPTURE_FILE"])',
                'listing = os.environ.get("FAKE_ZELLIJ_LISTING", "")',
                'with capture.open("a", encoding="utf-8") as fh:',
                '    fh.write(" ".join(args) + "\\n")',
                'if args[:1] == ["list-sessions"]:',
                "    print(listing, end='')",
                "    sys.exit(0)",
                "sys.exit(0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    vc_frame = bin_dir / "vc-frame"
    vc_frame.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    vc_frame.chmod(0o755)


def _write_capture_script(script_path: Path, capture_file: Path) -> None:
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'printf "%s\\n" "$*" >> "{capture_file}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def _write_fake_python3(bin_dir: Path, capture_file: Path) -> None:
    script = bin_dir / "python3"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$*" >> "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _write_fake_curl(bin_dir: Path) -> None:
    script = bin_dir / "curl"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import json",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                "routes = json.loads(os.environ.get('FAKE_CURL_ROUTES', '{}'))",
                "capture = os.environ.get('CURL_CAPTURE_FILE')",
                "url = None",
                "output_path = None",
                "idx = 0",
                "while idx < len(args):",
                "    arg = args[idx]",
                "    if arg == '-o' and idx + 1 < len(args):",
                "        output_path = args[idx + 1]",
                "        idx += 2",
                "        continue",
                "    if not arg.startswith('-'):",
                "        url = arg",
                "    idx += 1",
                "if capture and url:",
                "    with Path(capture).open('a', encoding='utf-8') as fh:",
                "        fh.write(url + '\\n')",
                "if not url or url not in routes:",
                "    sys.exit(22)",
                "payload = routes[url]",
                "if output_path:",
                "    Path(output_path).write_text(payload, encoding='utf-8')",
                "else:",
                "    sys.stdout.write(payload)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _write_fake_marbles_spawn(script_path: Path) -> None:
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def _write_fake_helper(script_path: Path, spawn_script: Path) -> None:
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        "\n".join(
            [
                "_vetcoders_spawn_script() {",
                f'  printf "%s\\n" "{spawn_script}"',
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_generic_skill_helper(script_path: Path) -> None:
    script_path.parent.mkdir(parents=True, exist_ok=True)
    script_path.write_text(
        "\n".join(
            [
                "_vetcoders_skill_entry() {",
                '  printf "%s\\n" "$1" "$2" > "$CAPTURE_FILE"',
                "  shift 2",
                '  printf "%s\\n" "$@" >> "$CAPTURE_FILE"',
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )


def _write_stateful_zellij(
    bin_dir: Path, capture_file: Path, session_state_file: Path
) -> None:
    default_session = _expected_operator_session()
    script = bin_dir / "zellij"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                'capture = Path(os.environ["CAPTURE_FILE"])',
                'state_file = Path(os.environ["SESSION_STATE_FILE"])',
                'state = state_file.read_text(encoding="utf-8").strip() if state_file.exists() else "missing"',
                f'session = os.environ.get("FAKE_ZELLIJ_SESSION", "{default_session}")',
                'if "--session" in args:',
                '    idx = args.index("--session")',
                "    if idx + 1 < len(args):",
                "        session = args[idx + 1]",
                'elif args[:1] == ["attach"] and len(args) > 1:',
                "    session = args[-1]",
                'with capture.open("a", encoding="utf-8") as fh:',
                '    fh.write("ZELLIJ " + " ".join(args) + "\\n")',
                'if args[:1] == ["ls"]:',
                '    if state == "live":',
                '        print(f"{session} [Created 1m ago]")',
                '    elif state == "dead":',
                '        print(f"{session} [Created 1m ago] (EXITED - attach to resurrect)")',
                "    sys.exit(0)",
                'if args[:1] == ["attach"]:',
                '    if "--force-run-commands" in args:',
                '        state_file.write_text("live", encoding="utf-8")',
                "    sys.exit(0)",
                'if args[:1] == ["delete-session"]:',
                '    state_file.write_text("missing", encoding="utf-8")',
                "    sys.exit(0)",
                'if "--new-session-with-layout" in args:',
                '    state_file.write_text("live", encoding="utf-8")',
                "    sys.exit(0)",
                'if "action" in args and ("new-pane" in args or "new-tab" in args):',
                "    sys.exit(0)",
                "sys.exit(0)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    vc_frame = bin_dir / "vc-frame"
    vc_frame.write_text(script.read_text(encoding="utf-8"), encoding="utf-8")
    vc_frame.chmod(0o755)


def _write_fake_osascript(
    bin_dir: Path, capture_file: Path, session_state_file: Path
) -> None:
    script = bin_dir / "osascript"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "payload = sys.stdin.read()",
                'capture = Path(os.environ["CAPTURE_FILE"])',
                'state_file = Path(os.environ["SESSION_STATE_FILE"])',
                'with capture.open("a", encoding="utf-8") as fh:',
                '    fh.write("OSA " + payload.replace("\\n", "\\\\n") + "\\n")',
                'if "new-session-with-layout" in payload or "attach --force-run-commands" in payload:',
                '    state_file.write_text("live", encoding="utf-8")',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _spawned_command_script(capture_payload: str) -> Path:
    match = re.search(r"ZELLIJ .* action new-tab .* -- (\S+)", capture_payload)
    assert match, capture_payload
    return Path(match.group(1))


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def test_init_claude_uses_interactive_tab_without_print_mode(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)
    _write_fake_osascript(fake_bin, capture_file, session_state_file)
    _write_fake_agent(fake_bin, "claude", tmp_path / "unused-claude.txt")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["VIBECRAFTED_OSASCRIPT_BIN"] = str(fake_bin / "osascript")
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session()
    # Sanitize real zellij env to prevent leaks from the host session.
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "init", "claude"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    # When zellij operator session exists, spawn routes directly through zellij
    # without opening a new terminal via osascript.
    assert f"ZELLIJ --session {_expected_operator_session()} action new-tab" in payload

    command_script = _spawned_command_script(payload)
    script_body = command_script.read_text(encoding="utf-8")
    assert "claude --verbose --dangerously-skip-permissions " in script_body
    assert "/vc-init" in script_body
    assert " -p " not in script_body


def test_init_codex_uses_interactive_tab_without_exec_mode(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "capture.log"
    session_state_file = tmp_path / "session-state.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_stateful_zellij(fake_bin, capture_file, session_state_file)
    _write_fake_osascript(fake_bin, capture_file, session_state_file)
    _write_fake_agent(fake_bin, "codex", tmp_path / "unused-codex.txt")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["SESSION_STATE_FILE"] = str(session_state_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["VIBECRAFTED_OSASCRIPT_BIN"] = str(fake_bin / "osascript")
    env["XDG_CONFIG_HOME"] = str(tmp_path / "xdg")
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["FAKE_ZELLIJ_SESSION"] = _expected_operator_session()
    # Sanitize real zellij env to prevent leaks from the host session.
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "init", "codex"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8")
    # When zellij operator session exists, spawn routes directly through zellij
    # without opening a new terminal via osascript.
    assert f"ZELLIJ --session {_expected_operator_session()} action new-tab" in payload

    command_script = _spawned_command_script(payload)
    script_body = command_script.read_text(encoding="utf-8")
    assert "codex --dangerously-bypass-approvals-and-sandbox " in script_body
    assert "/vc-init" in script_body
    assert "codex exec" not in script_body


def test_vc_help_wrapper_symlink_renders_main_help(tmp_path: Path) -> None:
    wrapper = tmp_path / "vc-help"
    wrapper.symlink_to(LAUNCHER)

    result = subprocess.run(
        ["bash", str(wrapper)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." in result.stdout
    assert "Commands:" in result.stdout
    assert "Ship cycle:" in result.stdout
    assert "workflow → implement → marbles → review → dou → release" in result.stdout
    assert 'vibecrafted implement codex -p "Ship dark mode"' in result.stdout


def test_vc_help_wrapper_forwards_topic_help(tmp_path: Path) -> None:
    wrapper = tmp_path / "vc-help"
    wrapper.symlink_to(LAUNCHER)

    result = subprocess.run(
        ["bash", str(wrapper), "init"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "Start an interactive repository orientation session" in result.stdout
    assert "vc-init [claude|codex|gemini|agy|junie|grok]" in result.stdout
    assert "Ship cycle:" not in result.stdout


def test_dispatch_help_documents_async_lifecycle_contract() -> None:
    result = subprocess.run(
        ["bash", str(LAUNCHER), "help", "dispatch"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "vibecrafted.dispatch.v1 TOML plan" in result.stdout
    assert "vibecrafted dispatch <plan.dispatch.toml>" in result.stdout
    assert "--doctor validates only" in result.stdout
    assert "transcript capture" in result.stdout
    assert "artifact contract failed" in result.stdout


def test_dispatch_launcher_runs_async_lifecycle(tmp_path: Path) -> None:
    home = tmp_path / "home"
    report = tmp_path / "report.md"
    transcript = tmp_path / "trace.log"
    worker = tmp_path / "worker.py"
    worker.write_text(
        "from pathlib import Path\n"
        f"Path({str(report)!r}).write_text('---\\nstatus: completed\\n---\\nbody\\n', encoding='utf-8')\n"
        "print('launcher dispatcher hello')\n",
        encoding="utf-8",
    )
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")

    result = subprocess.run(
        [
            "bash",
            str(LAUNCHER),
            "dispatch",
            "run",
            "--run-id",
            "launcher-dispatch-test",
            "--root",
            str(tmp_path),
            "--report",
            str(report),
            "--transcript",
            str(transcript),
            "--require-transcript-output",
            "--json",
            "--",
            sys.executable,
            str(worker),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    assert payload["run_id"] == "launcher-dispatch-test"
    assert payload["artifact_ok"] is True
    assert payload["state"] == "report_validated"
    assert "process_spawned" in payload["states"]
    assert "first_output_seen" in payload["states"]
    assert "report_validated" in payload["states"]
    assert "launcher dispatcher hello" in transcript.read_text(encoding="utf-8")


def test_vetcoders_shell_entrypoint_stays_thin_facade() -> None:
    facade = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"
    lib_dir = facade.parent / "lib"
    body = facade.read_text(encoding="utf-8")

    assert len(body.splitlines()) <= 120
    assert lib_dir.is_dir()
    for module in [
        "core",
        "zellij",
        "prompts",
        "dispatch_core",
        "dispatch_wrappers",
        "marbles",
        "dispatch",
    ]:
        assert f"_vetcoders_source_shell_module {module}" in body
        assert (lib_dir / f"{module}.sh").is_file()

    runtime_root = facade.parent.parent
    for workflow, module in [
        ("vc-research", "research_prompts"),
        ("vc-research", "research"),
    ]:
        assert f"_vetcoders_source_workflow_module {workflow} {module}" in body
        assert (runtime_root / workflow / "shell" / f"{module}.sh").is_file()


def test_telemetry_wrapper_smokes_headless_marbles_runtime(tmp_path: Path) -> None:
    home = tmp_path / "home"
    wrapper = tmp_path / "telemetry"
    capture_file = tmp_path / "marbles-args.txt"
    isolated_root = tmp_path / "isolated-root"
    spawn_script = isolated_root / "runtime" / "scripts" / "marbles_spawn.sh"

    home.mkdir()
    wrapper.symlink_to(LAUNCHER)
    (isolated_root / "runtime" / "scripts").mkdir(parents=True)
    (isolated_root / "scripts").mkdir(parents=True)
    (isolated_root / "VERSION").write_text("0.0.0-test\n", encoding="utf-8")
    (isolated_root / "scripts" / "vibecrafted").write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )
    _write_fake_marbles_spawn(spawn_script)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_ROOT"] = str(isolated_root)
    env["VETCODERS_SPAWN_RUNTIME"] = "terminal"

    subprocess.run(
        ["bash", str(wrapper), "smoke", "--count", "1", "--no-watch"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--agent" in payload
    assert "codex" in payload
    assert "--runtime" in payload
    assert "headless" in payload
    assert "--count" in payload
    assert payload[payload.index("--count") + 1] == "1"
    assert "--no-watch" in payload
    assert "--root" in payload
    smoke_root = Path(payload[payload.index("--root") + 1])
    assert smoke_root.exists()
    assert smoke_root != REPO_ROOT
    assert (smoke_root / ".git").exists()
    assert "--file" in payload
    smoke_plan = Path(payload[payload.index("--file") + 1])
    assert smoke_plan.is_file()
    assert smoke_root in smoke_plan.parents
    plan_body = smoke_plan.read_text(encoding="utf-8")
    assert "SMOKE_OK.md" in plan_body
    assert "Do not run `telemetry smoke`" in plan_body
    assert "--prompt" not in payload


def test_telemetry_wrapper_clears_ambient_marbles_context(tmp_path: Path) -> None:
    home = tmp_path / "home"
    wrapper = tmp_path / "telemetry"
    capture_file = tmp_path / "marbles-env.txt"
    isolated_root = tmp_path / "isolated-root"
    spawn_script = isolated_root / "runtime" / "scripts" / "marbles_spawn.sh"

    home.mkdir()
    wrapper.symlink_to(LAUNCHER)
    (isolated_root / "runtime" / "scripts").mkdir(parents=True)
    (isolated_root / "scripts").mkdir(parents=True)
    (isolated_root / "VERSION").write_text("0.0.0-test\n", encoding="utf-8")
    (isolated_root / "scripts" / "vibecrafted").write_text(
        "#!/usr/bin/env bash\nexit 0\n",
        encoding="utf-8",
    )
    spawn_script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf "MARBLES_RUN_ID=%s\\n" "${VIBECRAFTED_MARBLES_RUN_ID:-}"',
                '  printf "RUN_ID=%s\\n" "${VIBECRAFTED_RUN_ID:-}"',
                '  printf "RUN_LOCK=%s\\n" "${VIBECRAFTED_RUN_LOCK:-}"',
                '  printf "SKILL_CODE=%s\\n" "${VIBECRAFTED_SKILL_CODE:-}"',
                '  printf "SKILL_NAME=%s\\n" "${VIBECRAFTED_SKILL_NAME:-}"',
                '  printf "OPERATOR_SESSION=%s\\n" "${VIBECRAFTED_OPERATOR_SESSION:-}"',
                '  printf "SPAWN_RUN_ID=%s\\n" "${SPAWN_RUN_ID:-}"',
                '  printf "SPAWN_SKILL_CODE=%s\\n" "${SPAWN_SKILL_CODE:-}"',
                '} > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    spawn_script.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VIBECRAFTED_ROOT"] = str(isolated_root)
    env["VETCODERS_SPAWN_RUNTIME"] = "terminal"
    env["VIBECRAFTED_MARBLES_RUN_ID"] = "marb-parent"
    env["VIBECRAFTED_RUN_ID"] = "marb-parent-003"
    env["VIBECRAFTED_RUN_LOCK"] = str(tmp_path / "parent.lock")
    env["VIBECRAFTED_SKILL_CODE"] = "impl"
    env["VIBECRAFTED_SKILL_NAME"] = "implement"
    env["VIBECRAFTED_OPERATOR_SESSION"] = "parent-session"
    env["SPAWN_RUN_ID"] = "stale-spawn"
    env["SPAWN_SKILL_CODE"] = "stale"

    subprocess.run(
        ["bash", str(wrapper), "smoke", "--count", "1", "--no-watch"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = dict(
        line.split("=", 1)
        for line in capture_file.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    assert payload["MARBLES_RUN_ID"] == ""
    assert payload["RUN_ID"] == ""
    assert payload["RUN_LOCK"] == ""
    assert payload["SKILL_CODE"] == ""
    assert payload["SKILL_NAME"] == ""
    assert payload["OPERATOR_SESSION"] == ""
    assert payload["SPAWN_RUN_ID"] == ""
    assert payload["SPAWN_SKILL_CODE"] == ""


def test_installed_launcher_prefers_current_control_plane_helper_over_home_store(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    installed_root = home / ".vibecrafted"
    runtime_root = home / ".local" / "share" / "vibecrafted"
    launcher = home / ".local" / "bin" / "vibecrafted"
    stale_capture = tmp_path / "stale-args.txt"
    fresh_capture = tmp_path / "fresh-args.txt"
    stale_spawn = installed_root / "runtime" / "scripts" / "marbles_spawn.sh"
    fresh_spawn = (
        runtime_root
        / "tools"
        / "vibecrafted-current"
        / "runtime"
        / "scripts"
        / "marbles_spawn.sh"
    )
    stale_helper = installed_root / "skills" / "runtime" / "shell" / "vetcoders.sh"
    fresh_helper = (
        runtime_root
        / "tools"
        / "vibecrafted-current"
        / "runtime"
        / "shell"
        / "vetcoders.sh"
    )

    home.mkdir(parents=True)
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    launcher.chmod(0o755)
    _write_fake_marbles_spawn(stale_spawn)
    _write_fake_marbles_spawn(fresh_spawn)
    _write_fake_helper(stale_helper, stale_spawn)
    _write_fake_helper(fresh_helper, fresh_spawn)

    stale_spawn.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'printf "%s\\n" "$@" > "{stale_capture}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    stale_spawn.chmod(0o755)
    fresh_spawn.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                f'printf "%s\\n" "$@" > "{fresh_capture}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fresh_spawn.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)

    subprocess.run(
        ["bash", str(launcher), "telemetry", "smoke", "--count", "1", "--no-watch"],
        check=True,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert fresh_capture.exists()
    assert not stale_capture.exists()


def test_repo_launcher_is_directly_executable() -> None:
    expected_version = (REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    result = subprocess.run(
        [str(LAUNCHER), "help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "𝚅𝚒𝚋𝚎𝚌𝚛𝚊𝚏𝚝𝚎𝚍." in result.stdout
    assert expected_version in result.stdout
    assert "Commands:" in result.stdout
    assert "vibecrafted init claude" in result.stdout
    # Bounded deck: plumbing stays out of first contact.
    assert "vibecrafted dashboard" not in result.stdout
    assert "telemetry smoke" not in result.stdout


def test_update_web_fallback_verifies_install_sh_against_sha256sums(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    wrapper = tmp_path / "vibecrafted"
    install_capture = tmp_path / "install-args.txt"
    curl_capture = tmp_path / "curl-urls.txt"

    home.mkdir()
    fake_bin.mkdir()
    wrapper.symlink_to(LAUNCHER)
    _write_fake_curl(fake_bin)

    install_body = (
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$INSTALL_CAPTURE"',
            ]
        )
        + "\n"
    )
    install_sha = hashlib.sha256(install_body.encode("utf-8")).hexdigest()
    routes = {
        "https://vibecrafted.io/channel/main.json": json.dumps(
            {
                "version": "9.9.9",
                "archive_url": "https://downloads.example/vibecrafted-9.9.9.tar.gz",
            }
        ),
        "https://downloads.example/install.sh": install_body,
        "https://downloads.example/SHA256SUMS": (
            f"{install_sha}  install.sh\ndeadbeef  vibecrafted-9.9.9.tar.gz\n"
        ),
    }

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["INSTALL_CAPTURE"] = str(install_capture)
    env["CURL_CAPTURE_FILE"] = str(curl_capture)
    env["FAKE_CURL_ROUTES"] = json.dumps(routes)

    result = subprocess.run(
        ["bash", str(wrapper), "update", "--ref", "main"],
        check=True,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert install_capture.read_text(encoding="utf-8").splitlines() == ["--ref", "main"]
    assert curl_capture.read_text(encoding="utf-8").splitlines() == [
        "https://vibecrafted.io/channel/main.json",
        "https://downloads.example/install.sh",
        "https://downloads.example/SHA256SUMS",
    ]
    assert "Verifying install.sh via SHA256SUMS" in (result.stdout + result.stderr)
    assert "SHA256" in (result.stdout + result.stderr)


def test_update_web_fallback_aborts_on_install_sh_sha256_mismatch(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    wrapper = tmp_path / "vibecrafted"
    install_capture = tmp_path / "install-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    wrapper.symlink_to(LAUNCHER)
    _write_fake_curl(fake_bin)

    install_body = (
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'printf "%s\\n" "$@" > "$INSTALL_CAPTURE"',
            ]
        )
        + "\n"
    )
    routes = {
        "https://vibecrafted.io/channel/main.json": json.dumps(
            {
                "version": "9.9.9",
                "archive_url": "https://downloads.example/vibecrafted-9.9.9.tar.gz",
            }
        ),
        "https://downloads.example/install.sh": install_body,
        "https://downloads.example/SHA256SUMS": (
            "0000000000000000000000000000000000000000000000000000000000000000  install.sh\n"
        ),
    }

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin:/usr/sbin:/sbin"
    env["INSTALL_CAPTURE"] = str(install_capture)
    env["FAKE_CURL_ROUTES"] = json.dumps(routes)

    result = subprocess.run(
        ["bash", str(wrapper), "update", "--ref", "main"],
        check=False,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert not install_capture.exists()
    assert "SHA256 mismatch for install.sh" in (result.stdout + result.stderr)


def test_installed_launcher_gui_uses_python_control_plane_surface(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    launcher = home / ".local" / "bin" / "vibecrafted"
    current_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "python3-calls.txt"

    home.mkdir(parents=True)
    fake_bin.mkdir()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    launcher.chmod(0o755)
    (current_root / "scripts").mkdir(parents=True, exist_ok=True)
    (current_root / "VERSION").write_text("0.0.0-test\n", encoding="utf-8")
    (current_root / "scripts" / "installer_gui.py").write_text(
        "#!/usr/bin/env python3\n", encoding="utf-8"
    )
    (current_root / "scripts" / "control_plane_state.py").write_text(
        "#!/usr/bin/env python3\n", encoding="utf-8"
    )
    _write_fake_python3(fake_bin, capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)

    result = subprocess.run(
        ["bash", str(launcher), "gui", "--no-open", "--port", "4173"],
        check=True,
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    payload = capture_file.read_text(encoding="utf-8")
    assert f"{current_root / 'scripts' / 'control_plane_state.py'} sync" in payload
    assert (
        f"{current_root / 'scripts' / 'installer_gui.py'} --source {current_root} --no-open --port 4173"
        in payload
    )
    assert "Listening URL: http://127.0.0.1:4173/" in result.stdout
    assert "Press Ctrl-C to stop." in result.stdout


def test_installed_launcher_tui_uses_shared_state_and_operator_binary(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    installed_root = home / ".vibecrafted"
    launcher = home / ".local" / "bin" / "vibecrafted"
    current_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    fake_bin = tmp_path / "bin"
    python_capture = tmp_path / "python3-calls.txt"
    tui_capture = tmp_path / "tui-calls.txt"

    home.mkdir(parents=True)
    fake_bin.mkdir()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    launcher.chmod(0o755)
    (current_root / "scripts").mkdir(parents=True, exist_ok=True)
    (current_root / "operator-tui" / "target" / "debug").mkdir(
        parents=True, exist_ok=True
    )
    (current_root / "operator-tui" / "Cargo.toml").write_text(
        '[package]\nname = "vibecrafted-operator"\nversion = "0.0.0"\nedition = "2021"\n',
        encoding="utf-8",
    )
    (current_root / "VERSION").write_text("0.0.0-test\n", encoding="utf-8")
    (current_root / "scripts" / "control_plane_state.py").write_text(
        "#!/usr/bin/env python3\n", encoding="utf-8"
    )
    (current_root / "scripts" / "vibecrafted").write_text(
        "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
    )
    _write_fake_python3(fake_bin, python_capture)
    _write_capture_script(
        current_root / "operator-tui" / "target" / "debug" / "vibecrafted-operator",
        tui_capture,
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(python_capture)

    subprocess.run(
        ["bash", str(launcher), "tui", "--tick-ms", "500"],
        check=True,
        cwd=tmp_path,
        env=env,
    )

    assert (
        f"{current_root / 'scripts' / 'control_plane_state.py'} sync"
        in python_capture.read_text(encoding="utf-8")
    )
    tui_args = tui_capture.read_text(encoding="utf-8")
    assert f"--state-root {installed_root / 'control_plane'}" in tui_args
    assert f"--deck {current_root / 'scripts' / 'vibecrafted'}" in tui_args
    assert "--tick-ms 500" in tui_args


def test_tui_uses_vc_operator_from_path_when_local_build_missing(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    launcher = home / ".local" / "bin" / "vibecrafted"
    current_root = (
        home / ".local" / "share" / "vibecrafted" / "tools" / "vibecrafted-current"
    )
    fake_bin = tmp_path / "bin"
    python_capture = tmp_path / "python3-calls.txt"
    tui_capture = tmp_path / "tui-calls.txt"

    home.mkdir(parents=True)
    fake_bin.mkdir()
    launcher.parent.mkdir(parents=True, exist_ok=True)
    launcher.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    launcher.chmod(0o755)
    (current_root / "scripts").mkdir(parents=True, exist_ok=True)
    (current_root / "operator-tui" / "target" / "debug").mkdir(
        parents=True, exist_ok=True
    )
    (current_root / "VERSION").write_text("0.0.0-test\n", encoding="utf-8")
    (current_root / "scripts" / "control_plane_state.py").write_text(
        "#!/usr/bin/env python3\n", encoding="utf-8"
    )
    (current_root / "scripts" / "vibecrafted").write_text(
        "#!/usr/bin/env bash\nexit 0\n", encoding="utf-8"
    )
    _write_fake_python3(fake_bin, python_capture)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(python_capture)
    _write_capture_script(fake_bin / "vc-operator", tui_capture)

    subprocess.run(
        ["bash", str(launcher), "tui", "--runtime", "headless"],
        check=True,
        cwd=tmp_path,
        env=env,
    )

    assert (
        f"{current_root / 'scripts' / 'control_plane_state.py'} sync"
        in python_capture.read_text(encoding="utf-8")
    )
    tui_args = tui_capture.read_text(encoding="utf-8")
    assert "--runtime headless" in tui_args
    assert f"--deck {current_root / 'scripts' / 'vibecrafted'}" in tui_args


def test_gui_help_exposes_local_server_flags() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "gui", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "--host <host>" in result.stdout
    assert "--port <port>" in result.stdout
    assert "--no-open" in result.stdout
    assert "--bundle-dir <path>" in result.stdout


@pytest.mark.parametrize(
    ("topic", "expected"),
    [
        ("init", "vc-init [claude|codex|gemini|agy|junie|grok]"),
        ("vc-init", "vc-init [claude|codex|gemini|agy|junie|grok]"),
        ("vc-review", 'vibecrafted review codex --prompt "Review PR #14"'),
        ("status", "vibecrafted stats"),
    ],
)
def test_help_topics_route_to_specific_command_or_skill_help(
    topic: str, expected: str
) -> None:
    result = subprocess.run(
        [str(LAUNCHER), "help", topic],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert expected in result.stdout
    assert "Ship cycle:" not in result.stdout


def test_status_empty_state_is_explicit_when_artifact_dirs_exist(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo = tmp_path / "repo"
    home_artifacts = home / ".vibecrafted" / "artifacts"
    local_reports = repo / ".vibecrafted" / "reports"

    home_artifacts.mkdir(parents=True)
    local_reports.mkdir(parents=True)

    env = os.environ.copy()
    env["HOME"] = str(home)

    result = subprocess.run(
        ["bash", str(LAUNCHER), "status"],
        check=True,
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
    )

    assert "No activity yet — run `vibecrafted init <agent>` to start." in result.stdout


def test_implement_help_is_the_canonical_autonomous_delivery_surface() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "implement", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "implement" in result.stdout
    assert "Autonomous end-to-end implementation" in result.stdout
    assert (
        "vibecrafted implement <claude|codex|gemini|agy|junie|grok> [flags]"
        in result.stdout
    )
    assert "vc-implement <claude|codex|gemini|agy|junie|grok> [flags]" in result.stdout
    assert (
        "Alias: vibecrafted justdo <claude|codex|gemini|agy|junie|grok> [flags]"
        in result.stdout
    )


def test_justdo_help_points_back_to_implement() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "justdo", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "justdo" in result.stdout
    assert "Convenient alias for vc-implement" in result.stdout
    assert (
        "vibecrafted implement <claude|codex|gemini|agy|junie|grok> [flags]"
        in result.stdout
    )
    assert "vc-implement <claude|codex|gemini|agy|junie|grok> [flags]" in result.stdout
    assert (
        "Alias: vibecrafted justdo <claude|codex|gemini|agy|junie|grok> [flags]"
        in result.stdout
    )


def test_compact_help_teaches_implement_before_alias() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert 'vibecrafted implement codex -p "Ship dark mode"' in result.stdout
    assert "justdo" not in result.stdout
    assert "leg" + "acy alias" not in result.stdout


def test_review_and_followup_help_separate_bounded_review_from_direction_audit() -> (
    None
):
    review = subprocess.run(
        [str(LAUNCHER), "review", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    followup = subprocess.run(
        [str(LAUNCHER), "followup", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    audit = subprocess.run(
        [str(LAUNCHER), "audit", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "version 1.0.0" in audit.stdout
    assert "READ-ONLY falsification of a completed plan" in audit.stdout
    assert "Bounded PR, branch, commit-range, or artifact-pack review" in review.stdout
    assert "version 2.0.0" in review.stdout
    assert 'vibecrafted review codex --prompt "Review PR #14"' in review.stdout
    assert "Post-implementation direction audit" in followup.stdout
    assert "version 2.2.0" in followup.stdout
    assert (
        'vibecrafted followup codex --prompt "Audit post-implementation direction"'
        in followup.stdout
    )


@pytest.mark.parametrize(
    ("wrapper_name", "skill", "description"),
    [
        ("vc-followup", "followup", "Post-implementation direction audit"),
        ("vc-audit", "audit", "READ-ONLY falsification of a completed plan"),
        ("vc-intents", "intents", "Plan-to-runtime truth audit"),
        (
            "vc-ownership",
            "ownership",
            "Full-spectrum operational ownership",
        ),
    ],
)
def test_skill_wrapper_help_is_human_readable_without_agent(
    tmp_path: Path, wrapper_name: str, skill: str, description: str
) -> None:
    wrapper = tmp_path / wrapper_name
    wrapper.symlink_to(LAUNCHER)

    result = subprocess.run(
        [str(wrapper), "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert skill in result.stdout
    assert description in result.stdout
    assert (
        f"{wrapper_name} <claude|codex|gemini|agy|junie|grok> [flags]" in result.stdout
    )


@pytest.mark.parametrize(
    ("skill", "prompt"),
    [
        ("intents", "Audit what from the plan really landed"),
        ("ownership", "Take the repo from diagnosis to finished surface"),
    ],
)
def test_generic_skill_fallback_routes_unwrapped_skills(
    tmp_path: Path, skill: str, prompt: str
) -> None:
    home = tmp_path / "home"
    wrapper = tmp_path / "vibecrafted"
    capture_file = tmp_path / "generic-skill-args.txt"
    helper = (
        home
        / ".local"
        / "share"
        / "vibecrafted"
        / "tools"
        / "vibecrafted-current"
        / "runtime"
        / "shell"
        / "vetcoders.sh"
    )

    home.mkdir()
    wrapper.symlink_to(LAUNCHER)
    _write_generic_skill_helper(helper)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        ["bash", str(wrapper), skill, "codex", "--prompt", prompt],
        check=True,
        cwd=tmp_path,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == ["codex", skill, "--prompt", prompt]


@pytest.mark.parametrize(
    ("wrapper_name", "skill", "prompt"),
    [
        ("vc-intents", "intents", "Audit what from the plan really landed"),
        (
            "vc-ownership",
            "ownership",
            "Take the repo from diagnosis to finished surface",
        ),
    ],
)
def test_generic_skill_fallback_routes_skill_wrappers(
    tmp_path: Path, wrapper_name: str, skill: str, prompt: str
) -> None:
    home = tmp_path / "home"
    wrapper = tmp_path / wrapper_name
    capture_file = tmp_path / "generic-wrapper-args.txt"
    helper = (
        home
        / ".local"
        / "share"
        / "vibecrafted"
        / "tools"
        / "vibecrafted-current"
        / "runtime"
        / "shell"
        / "vetcoders.sh"
    )

    home.mkdir()
    wrapper.symlink_to(LAUNCHER)
    _write_generic_skill_helper(helper)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        ["bash", str(wrapper), "codex", "--prompt", prompt],
        check=True,
        cwd=tmp_path,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == ["codex", skill, "--prompt", prompt]


def test_marbles_help_lists_delete_control_subcommand() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "marbles", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert (
        "vibecrafted marbles <pause|stop|resume|session|inspect|delete> [args]"
        in result.stdout
    )
    assert (
        "vc-marbles <pause|stop|resume|session|inspect|delete> [args]" in result.stdout
    )


def test_marbles_flags_without_agent_get_actionable_error() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "marbles", "--count", "8", "--depth", "10"],
        check=False,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Missing marbles agent before flags." in result.stderr
    assert "Try: vibecrafted marbles codex --count 8 --depth 10" in result.stderr
    assert "Unknown agent: --count" not in result.stderr


def test_generic_skill_entry_preserves_marbles_options_for_junie(
    tmp_path: Path,
) -> None:
    capture_file = tmp_path / "marbles-entry-args.txt"
    script = "\n".join(
        [
            "set -euo pipefail",
            f"source {REPO_ROOT / 'runtime' / 'shell' / 'vetcoders.sh'}",
            "_vetcoders_marbles() {",
            '  printf "%s\\n" "$@" > "$CAPTURE_FILE"',
            "}",
            "_vetcoders_skill_entry junie marbles --count 3 --file /tmp/plan.md",
        ]
    )
    env = os.environ.copy()
    env["HOME"] = str(tmp_path / "home")
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        ["bash", "-lc", script],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    assert capture_file.read_text(encoding="utf-8").splitlines() == [
        "junie",
        "--count",
        "3",
        "--file",
        "/tmp/plan.md",
    ]


def test_marbles_delete_control_subcommand_routes_to_helper(tmp_path: Path) -> None:
    home = tmp_path / "home"
    wrapper = tmp_path / "vibecrafted"
    capture_file = tmp_path / "marbles-delete-args.txt"
    helper = (
        home
        / ".local"
        / "share"
        / "vibecrafted"
        / "tools"
        / "vibecrafted-current"
        / "runtime"
        / "shell"
        / "vetcoders.sh"
    )

    home.mkdir()
    wrapper.symlink_to(LAUNCHER)
    helper.parent.mkdir(parents=True, exist_ok=True)
    helper.write_text(
        "\n".join(
            [
                "marbles-delete() {",
                '  printf "%s\\n" "$@" > "$CAPTURE_FILE"',
                "}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        ["bash", str(wrapper), "marbles", "delete", "marb-424242"],
        check=True,
        cwd=tmp_path,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == ["marb-424242"]


def test_loop_help_exposes_interactive_operator_runtime() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "loop", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "Interactive Agent-Operator continuation" in result.stdout
    assert "vibecrafted loop await-run --run-id" in result.stdout
    assert "vc-loop status" in result.stdout
    assert "<repo-root>/.vibecrafted/operator-loop.local.md" in result.stdout
    assert "Operator-approved argv command" in result.stdout


def test_loop_start_next_and_max_iteration_stop(tmp_path: Path) -> None:
    subprocess.run(
        [
            str(LAUNCHER),
            "loop",
            "start",
            "--prompt",
            "Keep conducting the dispatch",
            "--max-iterations",
            "2",
            "--completion-promise",
            "READY",
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    first_next = subprocess.run(
        [str(LAUNCHER), "loop", "next"],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert "CONTINUE: operator loop iteration 2" in first_next.stdout
    assert "Keep conducting the dispatch" in first_next.stdout
    assert "<promise>READY</promise>" in first_next.stdout

    second_next = subprocess.run(
        [str(LAUNCHER), "loop", "next"],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert "STOP: max iterations reached (2)." in second_next.stdout


def test_loop_state_defaults_to_git_root_from_subdirectory(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    nested = repo / "nested" / "dir"
    nested.mkdir(parents=True)
    subprocess.run(
        ["git", "init"], cwd=repo, check=True, capture_output=True, text=True
    )

    subprocess.run(
        [
            str(LAUNCHER),
            "loop",
            "start",
            "--prompt",
            "Keep conducting from a subdirectory",
            "--max-iterations",
            "2",
        ],
        check=True,
        cwd=nested,
        capture_output=True,
        text=True,
    )

    root_state = repo / ".vibecrafted" / "operator-loop.local.md"
    nested_state = nested / ".vibecrafted" / "operator-loop.local.md"
    assert root_state.exists()
    assert not nested_state.exists()

    result = subprocess.run(
        [str(LAUNCHER), "loop", "next"],
        check=True,
        cwd=nested,
        capture_output=True,
        text=True,
    )

    assert "CONTINUE: operator loop iteration 2" in result.stdout
    assert "Keep conducting from a subdirectory" in result.stdout


def test_loop_completion_promise_allows_colons(tmp_path: Path) -> None:
    subprocess.run(
        [
            str(LAUNCHER),
            "loop",
            "start",
            "--prompt",
            "Finish the cut",
            "--completion-promise",
            "READY: audited",
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            str(LAUNCHER),
            "loop",
            "complete",
            "--promise",
            "READY: audited",
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert (
        "Completed operator loop with <promise>READY: audited</promise>."
        in result.stdout
    )


def test_vc_loop_wrapper_routes_to_loop_command(tmp_path: Path) -> None:
    wrapper = tmp_path / "vc-loop"
    wrapper.symlink_to(LAUNCHER)

    result = subprocess.run(
        ["bash", str(wrapper), "--help"],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert "Interactive Agent-Operator continuation" in result.stdout


def test_agent_subcommand_help_lists_modes() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "codex", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "Plan-based helper modes for codex." in result.stdout
    assert "implement <plan.md>" in result.stdout
    assert "observe   --last" in result.stdout
    assert "await     --last" in result.stdout
    assert "stop      --run-id <id>" in result.stdout


def test_agent_stop_mode_routes_to_core_cli_help() -> None:
    result = subprocess.run(
        [str(LAUNCHER), "codex", "stop", "--help"],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )

    assert "Stop a run by launcher process group." in result.stdout
    assert "Usage: vibecrafted codex stop --run-id <id>" in result.stdout
    assert "Unknown mode: stop" not in result.stderr


def test_dashboard_subcommand_launches_repo_owned_zellij_layout(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env.pop("ZELLIJ_CONFIG_DIR", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "dashboard"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    # dashboard (default layout) uses the canonical operator session, no suffix.
    assert _expected_operator_session() in payload
    assert "--new-session-with-layout" in payload
    assert str(REPO_ROOT / "config" / "zellij" / "layouts" / "dashboard.kdl") in payload
    assert f"ZELLIJ_CONFIG_DIR={REPO_ROOT / 'config' / 'zellij'}" in payload


def test_start_subcommand_launches_operator_entrypoint_layout(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env.pop("ZELLIJ_CONFIG_DIR", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    subprocess.run(
        ["bash", str(LAUNCHER), "start"],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert _expected_operator_session() in payload
    assert "--new-session-with-layout" in payload
    assert str(REPO_ROOT / "config" / "zellij" / "layouts" / "operator.kdl") in payload
    assert f"ZELLIJ_CONFIG_DIR={REPO_ROOT / 'config' / 'zellij'}" in payload


def test_resume_subcommand_forwards_session_and_prompt_to_agent(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "codex-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_agent(fake_bin, "codex", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        [
            "bash",
            str(LAUNCHER),
            "resume",
            "codex",
            "--session",
            "resume-session-123",
            "--prompt",
            "Continue the fix",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == ["resume", "resume-session-123", "Continue the fix"]


def test_resume_subcommand_wraps_terminal_runtime_in_zellij_operator_session(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_zellij_with_live_session(fake_bin, capture_file, "operator-test")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_RUNTIME_BIN"] = str(fake_bin)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "terminal"
    env["VIBECRAFTED_OPERATOR_SESSION"] = "operator-test"
    env["CAPTURE_FILE"] = str(capture_file)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    env.pop("VIBECRAFTED_RUN_ID", None)
    env.pop("VIBECRAFTED_RUN_LOCK", None)
    env.pop("VIBECRAFTED_SKILL_CODE", None)
    env.pop("VIBECRAFTED_SKILL_NAME", None)

    subprocess.run(
        [
            "bash",
            str(LAUNCHER),
            "resume",
            "codex",
            "--session",
            "resume-session-789",
            "--prompt",
            "Continue inside zellij",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert "operator-test" in payload
    assert "action" in payload
    assert "new-tab" in payload
    assert "--name" in payload
    assert "resume-codex" in payload
    assert "--cwd" in payload
    assert str(REPO_ROOT) in payload


def test_resume_wrapper_symlink_forwards_session_and_prompt_to_agent(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "codex-args.txt"
    wrapper = tmp_path / "vc-resume"

    home.mkdir()
    fake_bin.mkdir()
    wrapper.symlink_to(LAUNCHER)
    _write_fake_agent(fake_bin, "codex", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["CAPTURE_FILE"] = str(capture_file)

    subprocess.run(
        [
            "bash",
            str(wrapper),
            "codex",
            "--session",
            "resume-session-456",
            "--prompt",
            "Continue from wrapper",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert payload == ["resume", "resume-session-456", "Continue from wrapper"]


def test_vc_dashboard_wrapper_dispatches_to_dashboard(tmp_path: Path) -> None:
    """vc-dashboard wrapper (symlink) reaches cmd_dashboard, not run_skill."""
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"
    wrapper = tmp_path / "vc-dashboard"

    home.mkdir()
    fake_bin.mkdir()
    wrapper.symlink_to(LAUNCHER)
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    result = subprocess.run(
        ["bash", str(wrapper)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "--session" in payload
    assert "--new-session-with-layout" in payload


def test_dashboard_ls_delegates_to_zellij_list_sessions(tmp_path: Path) -> None:
    """vibecrafted dashboard ls calls zellij list-sessions, not layout load."""
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    result = subprocess.run(
        ["bash", str(LAUNCHER), "dashboard", "ls"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "list-sessions" in payload


def test_dashboard_switch_inside_zellij_uses_switch_session(tmp_path: Path) -> None:
    """dashboard switch from inside Zellij uses 'action switch-session', not attach."""
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    # Simulate being inside Zellij
    env["ZELLIJ"] = "0"
    env["ZELLIJ_PANE_ID"] = "1"
    env["ZELLIJ_SESSION_NAME"] = "existing-session"

    result = subprocess.run(
        ["bash", str(LAUNCHER), "dashboard", "switch", "target-session"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "action" in payload
    assert "switch-session" in payload
    assert "target-session" in payload
    # Must NOT use 'attach' when inside Zellij
    assert "attach" not in payload


def test_dashboard_attach_inside_zellij_uses_switch_session(tmp_path: Path) -> None:
    """dashboard attach from inside Zellij falls through to switch-session."""
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["ZELLIJ"] = "0"
    env["ZELLIJ_PANE_ID"] = "1"
    env["ZELLIJ_SESSION_NAME"] = "existing-session"

    result = subprocess.run(
        ["bash", str(LAUNCHER), "dashboard", "attach", "other-session"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "action" in payload
    assert "switch-session" in payload
    assert "other-session" in payload
    assert "attach" not in payload


def test_dashboard_switch_outside_zellij_uses_attach(tmp_path: Path) -> None:
    """dashboard switch from outside Zellij falls through to attach."""
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_fake_command(fake_bin, "zellij", capture_file)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)

    result = subprocess.run(
        ["bash", str(LAUNCHER), "dashboard", "switch", "target-session"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8").splitlines()
    assert "attach" in payload
    assert "target-session" in payload


def test_dashboard_gc_prunes_dead_sessions(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_gc_zellij(
        fake_bin,
        capture_file,
        "\n".join(
            [
                "vc-runtime [Created 144h ago]",
                "joyous-hill [Created 72h ago] (EXITED - attach to resurrect)",
                "didactic-cactus [Created 5h ago] (EXITED - attach to resurrect)",
                "",
            ]
        ),
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["FAKE_ZELLIJ_LISTING"] = "\n".join(
        [
            "vc-runtime [Created 144h ago]",
            "joyous-hill [Created 72h ago] (EXITED - attach to resurrect)",
            "didactic-cactus [Created 5h ago] (EXITED - attach to resurrect)",
            "",
        ]
    )

    result = subprocess.run(
        ["bash", str(LAUNCHER), "dashboard", "gc", "--apply"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8")
    assert "list-sessions" in payload
    assert "kill-session joyous-hill" in payload
    assert "kill-session didactic-cactus" in payload
    assert "kill-session vc-runtime" not in payload


def test_dashboard_gc_include_live_prunes_only_stale_detached_sessions(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    capture_file = tmp_path / "zellij-args.txt"

    home.mkdir()
    fake_bin.mkdir()
    _write_gc_zellij(
        fake_bin,
        capture_file,
        "\n".join(
            [
                "active-one [Created 72h ago] (current)",
                "stale-live [Created 72h ago]",
                "fresh-live [Created 2h ago]",
                "",
            ]
        ),
    )

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["CAPTURE_FILE"] = str(capture_file)
    env["FAKE_ZELLIJ_LISTING"] = "\n".join(
        [
            "active-one [Created 72h ago] (current)",
            "stale-live [Created 72h ago]",
            "fresh-live [Created 2h ago]",
            "",
        ]
    )

    result = subprocess.run(
        [
            "bash",
            str(LAUNCHER),
            "dashboard",
            "gc",
            "--apply",
            "--include-live",
            "--max-age-hours",
            "24",
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = capture_file.read_text(encoding="utf-8")
    assert "kill-session stale-live" in payload
    assert "kill-session fresh-live" not in payload
    assert "kill-session active-one" not in payload


def test_run_helper_blocks_self_looping_path_resolution(tmp_path: Path) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    launcher_copy = tmp_path / "vibecrafted"

    home.mkdir()
    fake_bin.mkdir()
    _write_trimmed_launcher(launcher_copy)
    (fake_bin / "vc-loop").symlink_to(launcher_copy)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"

    result = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{launcher_copy}"; _run_helper vc-loop --file /tmp/demo.md',
        ],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "resolved back to vibecrafted itself" in result.stderr
    assert "missing function definition to vetcoders.sh" in result.stderr


def _write_fake_claude_stream_agent(bin_dir: Path, final_message: str) -> None:
    script = bin_dir / "claude"
    stream = "\n".join(
        [
            "Claude CLI banner that should be ignored by the JSON filter",
            json.dumps(
                {
                    "type": "system",
                    "subtype": "init",
                    "session_id": "claude-fixture-session",
                }
            ),
            json.dumps(
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {
                                "type": "text",
                                "text": "Intermediate assistant text is transcript-only.",
                            }
                        ]
                    },
                }
            ),
            json.dumps({"type": "result", "result": final_message}),
        ]
    )
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "cat <<'JSONL'",
                stream,
                "JSONL",
                'exit "${FAKE_CLAUDE_EXIT:-0}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _write_fake_codex_last_message_agent(bin_dir: Path, final_message: str) -> None:
    script = bin_dir / "codex"
    script.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                'last_message=""',
                "while [[ $# -gt 0 ]]; do",
                '  if [[ "$1" == "--output-last-message" ]]; then',
                "    shift",
                '    last_message="${1:-}"',
                "  fi",
                "  shift || true",
                "done",
                'if [[ -n "$last_message" ]]; then',
                '  printf "%s\\n" "$FAKE_CODEX_LAST_MESSAGE" > "$last_message"',
                "fi",
                'printf "%s\\n" \'{"type":"thread.started","thread_id":"codex-fixture-session"}\'',
                'printf "%s\\n" \'{"type":"item.completed","item":{"type":"agent_message","text":"Codex stream body."}}\'',
                'exit "${FAKE_CODEX_EXIT:-0}"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script.chmod(0o755)


def _strip_ansi(payload: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", payload)


def _generate_and_run_spawn_launcher(
    tmp_path: Path,
    agent: str,
    env: dict[str, str],
) -> tuple[subprocess.CompletedProcess[str], Path, Path, Path]:
    plan = tmp_path / f"{agent}-plan.md"
    root = tmp_path / f"{agent}-root"
    plan.write_text("Hermetic launcher salvage fixture.\n", encoding="utf-8")
    root.mkdir()

    spawn_script = REPO_ROOT / "runtime" / "scripts" / f"{agent}_spawn.sh"
    dry_run = subprocess.run(
        [
            "bash",
            str(spawn_script),
            "--runtime",
            "headless",
            "--root",
            str(root),
            "--dry-run",
            str(plan),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    clean_stdout = _strip_ansi(dry_run.stdout)
    launcher_match = re.search(r"launcher generated only: (.+)", clean_stdout)
    report_match = re.search(r"report:\s+(.+)", clean_stdout)
    assert launcher_match, clean_stdout
    assert report_match, clean_stdout
    launcher = Path(launcher_match.group(1).strip())
    report = Path(report_match.group(1).strip())
    transcript = report.with_suffix(".transcript.log")
    last_message = Path(str(transcript).removesuffix(".log") + ".last-message.md")

    result = subprocess.run(
        ["bash", str(launcher)],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    return result, report, transcript, last_message


def test_codex_and_claude_launchers_salvage_last_message_on_missing_report(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    home.mkdir()
    fake_bin.mkdir()

    claude_final = "# Claude final message\n\nSalvaged from result JSONL."
    codex_final = "# Codex final message\n\nSalvaged from --output-last-message."
    _write_fake_claude_stream_agent(fake_bin, claude_final)
    _write_fake_codex_last_message_agent(fake_bin, codex_final)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_RUNTIME_BIN"] = str(fake_bin)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_INLINE_STARTUP_WATCH"] = "0"
    env["FAKE_CODEX_LAST_MESSAGE"] = codex_final

    claude_result, claude_report, _, claude_last_message = (
        _generate_and_run_spawn_launcher(tmp_path, "claude", env)
    )
    codex_result, codex_report, _, codex_last_message = (
        _generate_and_run_spawn_launcher(tmp_path, "codex", env)
    )

    assert claude_result.returncode == 0, claude_result.stderr
    assert codex_result.returncode == 0, codex_result.stderr
    claude_body = claude_report.read_text(encoding="utf-8")
    codex_body = codex_report.read_text(encoding="utf-8")
    assert "status: completed" in claude_body
    assert "status: completed" in codex_body
    assert claude_final in claude_body
    assert codex_final in codex_body
    assert "no final message was captured" not in claude_body
    assert claude_last_message.read_text(encoding="utf-8").strip() == claude_final
    assert codex_last_message.read_text(encoding="utf-8").strip() == codex_final


def test_claude_launcher_salvages_final_message_on_failure(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_bin = tmp_path / "bin"
    home.mkdir()
    fake_bin.mkdir()

    final_message = (
        "# Claude failed final message\n\nThe useful failure report survived."
    )
    _write_fake_claude_stream_agent(fake_bin, final_message)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_RUNTIME_BIN"] = str(fake_bin)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_INLINE_STARTUP_WATCH"] = "0"
    env["FAKE_CLAUDE_EXIT"] = "7"

    result, report, _, last_message = _generate_and_run_spawn_launcher(
        tmp_path,
        "claude",
        env,
    )

    assert result.returncode == 7
    body = report.read_text(encoding="utf-8")
    assert "status: failed" in body
    assert final_message in body
    assert "no final message was captured" not in body
    assert last_message.read_text(encoding="utf-8").strip() == final_message


def _fake_agent_script(agent: str, final_message: str, stream_json: bool) -> str:
    env_prefix = agent.upper()
    lines = [
        "#!/usr/bin/env bash",
        "set -euo pipefail",
        'prompt_file=""',
        'task_text=""',
        "while [[ $# -gt 0 ]]; do",
        '  case "$1" in',
        "    --prompt-file)",
        "      shift",
        '      prompt_file="${1:-}"',
        "      ;;",
        "    --prompt-file=*)",
        '      prompt_file="${1#--prompt-file=}"',
        "      ;;",
        "    --task=*)",
        '      task_text="${1#--task=}"',
        "      ;;",
        "    --task)",
        "      shift",
        '      task_text="${1:-}"',
        "      ;;",
        "  esac",
        "  shift || true",
        "done",
        'if [[ -n "$prompt_file" ]]; then',
        '  prompt_text="$(cat "$prompt_file")"',
        'elif [[ -n "$task_text" ]]; then',
        '  prompt_text="$task_text"',
        "else",
        '  prompt_text="$(cat)"',
        "fi",
        'report_path="$(printf "%s\\n" "$prompt_text" | awk -F": " \'/^Report path: / { print $2; exit }\')"',
        'if [[ "${FAKE_WRITE_REPORT:-0}" == "1" && -n "$report_path" ]]; then',
        '  mkdir -p "$(dirname "$report_path")"',
        "  cat > \"$report_path\" <<'REPORT'",
        "---",
        f"agent: {agent}",
        "status: completed",
        "---",
        "",
        f"{agent} worker-authored report survived.",
        "REPORT",
        "fi",
    ]
    if stream_json:
        stream = "\n".join(
            [
                f"{agent} CLI banner ignored by grep",
                json.dumps(
                    {
                        "type": "message",
                        "role": "assistant",
                        "content": final_message,
                    }
                ),
                json.dumps({"type": "result", "status": "done"}),
            ]
        )
        lines.extend(["cat <<'JSONL'", stream, "JSONL"])
    else:
        lines.extend(["cat <<'TXT'", final_message, "TXT"])
    lines.append(f'exit "${{FAKE_{env_prefix}_EXIT:-0}}"')
    return "\n".join(lines) + "\n"


def _write_fake_salvage_agent(
    bin_dir: Path,
    agent: str,
    final_message: str,
    *,
    stream_json: bool = False,
) -> None:
    script = bin_dir / agent
    script.write_text(
        _fake_agent_script(agent, final_message, stream_json),
        encoding="utf-8",
    )
    script.chmod(0o755)


def _fleet_salvage_env(tmp_path: Path, fake_bin: Path) -> dict[str, str]:
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_RUNTIME_BIN"] = str(fake_bin)
    env["VIBECRAFTED_HOME"] = str(home / ".vibecrafted")
    env["VIBECRAFTED_INLINE_STARTUP_WATCH"] = "0"
    return env


@pytest.mark.parametrize(
    ("agent", "stream_json"),
    [
        ("gemini", True),
        ("agy", False),
        ("grok", False),
        ("junie", False),
    ],
)
def test_remaining_launchers_salvage_final_message_on_missing_report_success(
    tmp_path: Path,
    agent: str,
    stream_json: bool,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    final_message = f"# {agent} final message\n\nSalvaged from captured stdout."
    _write_fake_salvage_agent(
        fake_bin,
        agent,
        final_message,
        stream_json=stream_json,
    )
    env = _fleet_salvage_env(tmp_path, fake_bin)

    result, report, _, last_message = _generate_and_run_spawn_launcher(
        tmp_path,
        agent,
        env,
    )

    assert result.returncode == 0, result.stderr
    body = report.read_text(encoding="utf-8")
    assert "status: completed" in body
    assert final_message in body
    assert "no final message was captured" not in body
    assert final_message in last_message.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("agent", "stream_json", "exit_code"),
    [
        ("gemini", True, "11"),
        ("agy", False, "12"),
        ("grok", False, "13"),
        ("junie", False, "14"),
    ],
)
def test_remaining_launchers_salvage_final_message_on_missing_report_failure(
    tmp_path: Path,
    agent: str,
    stream_json: bool,
    exit_code: str,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    final_message = f"# {agent} failed final message\n\nFailure details survived."
    _write_fake_salvage_agent(
        fake_bin,
        agent,
        final_message,
        stream_json=stream_json,
    )
    env = _fleet_salvage_env(tmp_path, fake_bin)
    env[f"FAKE_{agent.upper()}_EXIT"] = exit_code

    result, report, _, last_message = _generate_and_run_spawn_launcher(
        tmp_path,
        agent,
        env,
    )

    assert result.returncode == int(exit_code)
    body = report.read_text(encoding="utf-8")
    assert "status: failed" in body
    assert final_message in body
    assert "no final message was captured" not in body
    assert final_message in last_message.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("agent", "stream_json"),
    [
        ("gemini", True),
        ("agy", False),
        ("grok", False),
        ("junie", False),
    ],
)
def test_remaining_launchers_do_not_overwrite_worker_authored_reports(
    tmp_path: Path,
    agent: str,
    stream_json: bool,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    final_message = f"# {agent} stdout final message\n\nThis stays out of the report."
    _write_fake_salvage_agent(
        fake_bin,
        agent,
        final_message,
        stream_json=stream_json,
    )
    env = _fleet_salvage_env(tmp_path, fake_bin)
    env["FAKE_WRITE_REPORT"] = "1"

    result, report, _, last_message = _generate_and_run_spawn_launcher(
        tmp_path,
        agent,
        env,
    )

    assert result.returncode == 0, result.stderr
    body = report.read_text(encoding="utf-8")
    assert f"{agent} worker-authored report survived." in body
    assert final_message not in body
    assert final_message in last_message.read_text(encoding="utf-8")
