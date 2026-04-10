from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"


def _write_fake_marbles_spawn(script_path: Path) -> None:
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


def _write_replaying_zellij(script_path: Path) -> None:
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "import os",
                "import shutil",
                "import subprocess",
                "import sys",
                "from pathlib import Path",
                "",
                "args = sys.argv[1:]",
                'Path(os.environ["ZELLIJ_CAPTURE_FILE"]).write_text("\\n".join(args) + "\\n", encoding="utf-8")',
                "if args:",
                "    shell = shutil.which('zsh') or shutil.which('bash') or '/bin/sh'",
                "    subprocess.run([shell, '-lc', args[-1]], check=True, env=os.environ.copy())",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def _prepare_fake_marbles_bundle(tmp_path: Path) -> tuple[Path, Path]:
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir()
    shutil.copytree(REPO_ROOT / "skills/vc-agents/scripts/lib", scripts_dir / "lib")

    for name in (
        "common.sh",
        "marbles_spawn.sh",
        "marbles_watcher.sh",
        "marbles_next.sh",
    ):
        source = REPO_ROOT / "skills" / "vc-agents" / "scripts" / name
        target = scripts_dir / name
        shutil.copy2(source, target)
        target.chmod(0o755)

    capture_file = tmp_path / "spawn-events.jsonl"
    fake_spawn = textwrap.dedent(
        r"""
        #!/usr/bin/env bash
        set -euo pipefail

        SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
        # shellcheck source=common.sh
        source "$SCRIPT_DIR/common.sh"

        agent="$(basename "${BASH_SOURCE[0]}" _spawn.sh)"
        mode="implement"
        runtime="terminal"
        model=""
        root=""
        success_hook=""
        failure_hook=""
        plan_file=""

        while [[ $# -gt 0 ]]; do
          case "$1" in
            --mode) shift; mode="$1" ;;
            --runtime) shift; runtime="$1" ;;
            --root) shift; root="$1" ;;
            --model) shift; model="$1" ;;
            --success-hook) shift; success_hook="$1" ;;
            --failure-hook) shift; failure_hook="$1" ;;
            *)
              [[ -z "$plan_file" ]] || { echo "unexpected arg: $1" >&2; exit 1; }
              plan_file="$1"
              ;;
          esac
          shift
        done

        spawn_prepare_paths "$agent" "$plan_file" "$root" "$mode"
        if [[ -n "${MARBLES_TEST_FAIL_BEFORE_META_LOOP:-}" && "${SPAWN_LOOP_NR:-0}" == "${MARBLES_TEST_FAIL_BEFORE_META_LOOP}" ]]; then
          printf 'synthetic pre-meta failure for loop %s\n' "${SPAWN_LOOP_NR:-0}" >&2
          exit 42
        fi
        spawn_write_meta "$SPAWN_META" "launching" "$agent" "$mode" "$SPAWN_ROOT" "$SPAWN_PLAN" "$SPAWN_REPORT" "$SPAWN_TRANSCRIPT" "$0" "$model"

        python3 - "$MARBLES_SPAWN_CAPTURE" "$SPAWN_PLAN" "$SPAWN_REPORT" "$success_hook" "$failure_hook" "$agent" "$model" "$SPAWN_RUN_ID" "$SPAWN_LOOP_NR" <<'PY'
        import json
        import pathlib
        import sys

        capture, plan, report, success_hook, failure_hook, agent, model, run_id, loop_nr = sys.argv[1:10]
        payload = {
            "plan": plan,
            "report": report,
            "success_hook": success_hook,
            "failure_hook": failure_hook,
            "agent": agent,
            "model": model,
            "run_id": run_id,
            "loop": int(loop_nr or "0"),
        }
        capture_path = pathlib.Path(capture)
        capture_path.parent.mkdir(parents=True, exist_ok=True)
        with capture_path.open("a", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
            handle.write("\n")
        PY

        cat > "$SPAWN_TRANSCRIPT" <<EOF
        ---
        run_id: ${SPAWN_RUN_ID}
        prompt_id: ${SPAWN_PROMPT_ID}
        agent: ${SPAWN_AGENT}
        skill: marb
        model: ${model:-unknown}
        status: transcript
        ---

        session: fake-${agent}-${SPAWN_LOOP_NR}
        working...
        EOF

        if [[ "${SPAWN_LOOP_NR:-0}" == "1" ]]; then
          p0=1
        else
          p0=0
        fi

        cat > "$SPAWN_REPORT" <<EOF
        ---
        run_id: ${SPAWN_RUN_ID}
        prompt_id: ${SPAWN_PROMPT_ID}
        agent: ${SPAWN_AGENT}
        skill: marb
        model: ${model:-unknown}
        status: completed
        ---

        P0: ${p0}
        P1: 0
        P2: 0
        EOF

        cp "$SPAWN_REPORT" "${SPAWN_REPORT%.md}_verified.md"

        if [[ "${MARBLES_TEST_EDIT_ANCESTOR:-}" == "1" && "${SPAWN_LOOP_NR:-0}" == "1" ]]; then
          base_run_id="${SPAWN_RUN_ID%-???}"
          ancestor_path="$(spawn_marbles_state_dir "$base_run_id")/ancestor.md"
          cat > "$ancestor_path" <<'EOF_ANCESTOR'
        ---
        agent: gemini
        focus: accessibility
        priority: P0
        model: gemini-2.5-pro
        ---

        Steer the next loop toward accessibility.
        EOF_ANCESTOR
        fi

        spawn_finish_meta "$SPAWN_META" "completed" "0"

        if [[ -n "$success_hook" ]]; then
          bash -lc "$success_hook"
        fi
        """
    ).lstrip()

    for agent in ("claude", "codex", "gemini"):
        script = scripts_dir / f"{agent}_spawn.sh"
        script.write_text(fake_spawn, encoding="utf-8")
        script.chmod(0o755)

    return scripts_dir, capture_file


def _load_spawn_events(capture_file: Path) -> list[dict[str, object]]:
    return [
        json.loads(line)
        for line in capture_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _expected_operator_session(run_id: str | None = None) -> str:
    base = (
        re.sub(r"[^a-z0-9]+", "-", REPO_ROOT.name.lower()).strip("-") or "vibecrafted"
    )
    return f"{base}-{run_id}" if run_id else base


def _run_marbles_prompt(
    tmp_path: Path, *, inside_zellij: bool
) -> tuple[list[str], list[str]]:
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    fake_bin = tmp_path / "bin"
    tmpdir_root = tmp_path / "tmpdir"
    capture_file = tmp_path / "marbles-args.txt"
    zellij_capture_file = tmp_path / "zellij-args.txt"
    spawn_script = (
        crafted_home / "skills" / "vc-agents" / "scripts" / "marbles_spawn.sh"
    )

    home.mkdir()
    fake_bin.mkdir()
    tmpdir_root.mkdir()
    spawn_script.parent.mkdir(parents=True)
    _write_fake_marbles_spawn(spawn_script)
    _write_replaying_zellij(fake_bin / "zellij")

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["ZELLIJ_CAPTURE_FILE"] = str(zellij_capture_file)
    env["TMPDIR"] = f"{tmpdir_root}/"
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    env["VIBECRAFTED_RUN_ID"] = "marb-014520"
    operator_session = _expected_operator_session(env["VIBECRAFTED_RUN_ID"])

    if inside_zellij:
        env["ZELLIJ"] = "operator"
        env["ZELLIJ_PANE_ID"] = "terminal_7"
        env["ZELLIJ_SESSION_NAME"] = operator_session
    else:
        env["VIBECRAFTED_OPERATOR_SESSION"] = operator_session

    subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                'claude-marbles --count 1 --prompt "weź i vc-justdo wszystko co marbles znajdzie"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    return (
        capture_file.read_text(encoding="utf-8").splitlines(),
        zellij_capture_file.read_text(encoding="utf-8").splitlines(),
    )


def test_vc_marbles_preserves_prompt_as_single_argument_inside_zellij(
    tmp_path: Path,
) -> None:
    payload, zellij_payload = _run_marbles_prompt(tmp_path, inside_zellij=True)

    assert "--agent" in payload
    assert "claude" in payload
    assert "--count" in payload
    assert "1" in payload
    assert "--prompt" in payload
    assert "weź i vc-justdo wszystko co marbles znajdzie" in payload
    assert "new-tab" in zellij_payload
    assert any("vibecrafted-marbles." in line for line in zellij_payload)
    assert not any("//vibecrafted-marbles." in line for line in zellij_payload)
    assert not any(
        "weź i vc-justdo wszystko co marbles znajdzie" in line
        for line in zellij_payload
    )


def test_vc_marbles_preserves_prompt_as_single_argument_in_operator_session(
    tmp_path: Path,
) -> None:
    payload, zellij_payload = _run_marbles_prompt(tmp_path, inside_zellij=False)

    assert "--agent" in payload
    assert "claude" in payload
    assert "--count" in payload
    assert "1" in payload
    assert "--prompt" in payload
    assert "weź i vc-justdo wszystko co marbles znajdzie" in payload
    assert "new-tab" in zellij_payload
    assert any("vc-spawn-cmd." in line for line in zellij_payload)
    assert not any("//vc-spawn-cmd." in line for line in zellij_payload)
    assert not any(
        "weź i vc-justdo wszystko co marbles znajdzie" in line
        for line in zellij_payload
    )


def test_vetcoders_shell_quote_join_stays_utf8_clean_for_multiline_prompt(
    tmp_path: Path,
) -> None:
    env = os.environ.copy()
    env["PROMPT_PAYLOAD"] = (
        "Siemka! weź i zażółć gęślą jaźń.\n"
        "_Run inside zellij - if there is any open window attach to it._\n"
        "Don't drop UTF-8 on the floor."
    )

    quoted = subprocess.run(
        [
            "bash",
            "-lc",
            f'source "{HELPER_SCRIPT}"; _vetcoders_shell_quote_join "$PROMPT_PAYLOAD"',
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
    ).stdout.decode("utf-8")

    roundtrip_script = tmp_path / "roundtrip.sh"
    roundtrip_script.write_text(
        f"#!/usr/bin/env bash\nprintf %s {quoted}\n",
        encoding="utf-8",
    )
    roundtrip_script.chmod(0o755)

    roundtrip = subprocess.run(
        ["bash", str(roundtrip_script)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
    ).stdout.decode("utf-8")

    assert roundtrip == env["PROMPT_PAYLOAD"]


def test_parse_contract_treats_everything_after_prompt_as_prompt_block() -> None:
    env = os.environ.copy()
    env["PROMPT_HEAD"] = "Portable musi działać."

    payload = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f'source "{HELPER_SCRIPT}"; '
                '_vetcoders_parse_contract --count 8 --prompt "$PROMPT_HEAD" '
                "--runtime headless --depth 99; "
                'printf "COUNT=%s\\n" "$_vetcoders_contract_count"; '
                'printf "RUNTIME=%s\\n" "$_vetcoders_contract_runtime"; '
                'printf "DEPTH=%s\\n" "$_vetcoders_contract_depth"; '
                'printf "PROMPT=%s\\n" "$_vetcoders_contract_prompt"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    ).stdout

    lines = dict(line.split("=", 1) for line in payload.strip().splitlines())
    assert lines["COUNT"] == "8"
    assert lines["RUNTIME"] == ""
    assert lines["DEPTH"] == ""
    assert lines["PROMPT"] == "Portable musi działać. --runtime headless --depth 99"


def test_write_command_script_falls_back_to_bash_when_zsh_missing(
    tmp_path: Path,
) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "bash").symlink_to(Path("/bin/bash"))
    (fake_bin / "chmod").symlink_to(Path("/bin/chmod"))

    command_script = tmp_path / "spawn-cmd"
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:/usr/bin"

    subprocess.run(
        [
            "/bin/bash",
            "-c",
            (
                f'source "{HELPER_SCRIPT}"; '
                f'_vetcoders_write_command_script "{command_script}" "printf %s fallback-ok"'
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    script_body = command_script.read_text(encoding="utf-8")
    assert str(fake_bin / "bash") in script_body
    assert "zsh" not in script_body

    result = subprocess.run(
        [str(command_script)],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.stdout == "fallback-ok"
    assert not command_script.exists()


def test_marbles_runtime_steers_next_loop_from_ancestor_frontmatter(
    tmp_path: Path,
) -> None:
    scripts_dir, capture_file = _prepare_fake_marbles_bundle(tmp_path)
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["MARBLES_SPAWN_CAPTURE"] = str(capture_file)
    env["MARBLES_TEST_EDIT_ANCESTOR"] = "1"
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)

    subprocess.run(
        [
            "bash",
            str(scripts_dir / "marbles_spawn.sh"),
            "--agent",
            "codex",
            "--count",
            "2",
            "--runtime",
            "headless",
            "--prompt",
            "Fix installer drift end to end",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    state_dirs = list((crafted_home / "marbles").iterdir())
    assert len(state_dirs) == 1
    state_dir = state_dirs[0]
    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))

    assert state["god_plan"] == str(state_dir / "god.md")
    assert state["ancestor_plan"] == str(state_dir / "ancestor.md")
    assert state["plan"] == str(state_dir / "ancestor.md")
    assert [loop["agent"] for loop in state["loops"][:2]] == ["codex", "gemini"]
    assert state["loops"][1]["focus"] == "accessibility"
    assert state["loops"][1]["model"] == "gemini-2.5-pro"

    god_plan = state_dir / "god.md"
    ancestor_plan = state_dir / "ancestor.md"
    assert god_plan.read_text(encoding="utf-8").startswith("---\nkind: god\n")
    assert oct(god_plan.stat().st_mode & 0o777) == "0o444"
    assert ancestor_plan.read_text(encoding="utf-8").startswith("---\nagent: gemini\n")

    events = _load_spawn_events(capture_file)
    assert [event["agent"] for event in events] == ["codex", "gemini"]
    assert str(state_dir) in str(events[0]["success_hook"])
    assert str(events[0]["plan"]).endswith("marbles-ancestor_L1.md")
    assert str(events[1]["plan"]).endswith("marbles-ancestor_L2.md")
    assert str(events[0]["plan"]) not in str(events[0]["success_hook"])
    assert events[1]["model"] == "gemini-2.5-pro"


def test_marbles_no_watch_still_creates_god_and_ancestor_contract(
    tmp_path: Path,
) -> None:
    scripts_dir, capture_file = _prepare_fake_marbles_bundle(tmp_path)
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["MARBLES_SPAWN_CAPTURE"] = str(capture_file)
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)

    subprocess.run(
        [
            "bash",
            str(scripts_dir / "marbles_spawn.sh"),
            "--agent",
            "claude",
            "--count",
            "1",
            "--runtime",
            "headless",
            "--no-watch",
            "--prompt",
            "Harden the installer quick path",
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    state_dirs = list((crafted_home / "marbles").iterdir())
    assert len(state_dirs) == 1
    state_dir = state_dirs[0]
    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))

    assert state["status"] == "initialized"
    assert state["god_plan"] == str(state_dir / "god.md")
    assert state["ancestor_plan"] == str(state_dir / "ancestor.md")
    assert (state_dir / "god.md").exists()
    assert (state_dir / "ancestor.md").exists()

    events = _load_spawn_events(capture_file)
    assert len(events) == 1
    assert str(state_dir) in str(events[0]["success_hook"])
    assert str(events[0]["plan"]).endswith("marbles-ancestor_L1.md")


def test_marbles_materializes_failed_loop_when_child_spawn_dies_before_meta(
    tmp_path: Path,
) -> None:
    scripts_dir, capture_file = _prepare_fake_marbles_bundle(tmp_path)
    home = tmp_path / "home"
    crafted_home = home / ".vibecrafted"
    home.mkdir()

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["MARBLES_SPAWN_CAPTURE"] = str(capture_file)
    env["MARBLES_TEST_FAIL_BEFORE_META_LOOP"] = "2"
    env["VIBECRAFTED_MARBLES_META_TIMEOUT_S"] = "2"
    env["VIBECRAFTED_MARBLES_REPORT_TIMEOUT_S"] = "2"
    env.pop("ZELLIJ", None)
    env.pop("ZELLIJ_PANE_ID", None)
    env.pop("ZELLIJ_SESSION_NAME", None)
    env.pop("VIBECRAFTED_OPERATOR_SESSION", None)

    result = subprocess.run(
        [
            "bash",
            str(scripts_dir / "marbles_spawn.sh"),
            "--agent",
            "codex",
            "--count",
            "2",
            "--runtime",
            "headless",
            "--prompt",
            "Stabilize runtime truth",
        ],
        check=False,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
    )

    state_dirs = list((crafted_home / "marbles").iterdir())
    assert len(state_dirs) == 1
    state_dir = state_dirs[0]
    state = json.loads((state_dir / "state.json").read_text(encoding="utf-8"))

    assert state["status"] == "failed"
    assert [loop["status"] for loop in state["loops"]] == ["done", "failed"]
    failed_loop = state["loops"][1]
    assert failed_loop["failure_reason"] == "spawn-failed"
    assert failed_loop["loop"] == 2
    assert failed_loop["report"]
    assert Path(failed_loop["report"]).exists()
    assert "failed before loop 2 could launch" in Path(failed_loop["report"]).read_text(
        encoding="utf-8"
    )

    meta_records = subprocess.run(
        [
            "bash",
            "-lc",
            (
                f"find '{crafted_home / 'artifacts'}' -type f -name '*.meta.json' -print0 "
                f"| xargs -0 jq -r 'select(.run_id==\"{state['run_id']}-002\") | .status'"
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert "failed" in meta_records.stdout.splitlines()
    assert "no meta.json within" not in result.stdout
