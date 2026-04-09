from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "skills" / "vc-agents" / "shell" / "vetcoders.sh"


def _org_repo() -> str:
    remote = subprocess.check_output(
        ["git", "remote", "get-url", "origin"],
        cwd=REPO_ROOT,
        text=True,
    ).strip()
    match = re.search(r"[:/]([^/]+)/([^/.]+?)(?:\.git)?$", remote)
    assert match is not None
    return f"{match.group(1)}/{match.group(2)}"


def _write_fake_spawn(script_path: Path) -> None:
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf "RUN_ID=%s\\n" "${VIBECRAFTED_RUN_ID:-}"',
                '  printf "SKILL_CODE=%s\\n" "${VIBECRAFTED_SKILL_CODE:-}"',
                '  printf "SKILL_NAME=%s\\n" "${VIBECRAFTED_SKILL_NAME:-}"',
                '  printf "RUN_LOCK=%s\\n" "${VIBECRAFTED_RUN_LOCK:-}"',
                '  printf "ARGS=%s\\n" "$*"',
                '} > "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    script_path.chmod(0o755)


def _run_helper(
    tmp_path: Path,
    helper: str,
    args: list[str],
) -> dict[str, str]:
    home = tmp_path / "home"
    fake_spawn = tmp_path / "fake_spawn.sh"
    capture_file = tmp_path / f"{helper}.log"

    home.mkdir(parents=True)
    _write_fake_spawn(fake_spawn)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)

    quoted_args = " ".join(shlex.quote(arg) for arg in args)
    subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{HELPER_SCRIPT}"',
                    "_vetcoders_spawn_script() {",
                    f'  printf "%s\\n" "{fake_spawn}"',
                    "}",
                    f"{helper} {quoted_args}".rstrip(),
                ]
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload: dict[str, str] = {}
    for line in capture_file.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        payload[key] = value
    return payload


def _run_prompt_capture(
    tmp_path: Path,
    helper: str,
    args: list[str],
) -> dict[str, str]:
    home = tmp_path / "home"
    capture_file = tmp_path / f"{helper}-prompt.log"

    home.mkdir(parents=True)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)

    quoted_args = " ".join(shlex.quote(arg) for arg in args)
    subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{HELPER_SCRIPT}"',
                    "_vetcoders_prompt_text() {",
                    '  local tool="$1"',
                    '  local mode="$2"',
                    "  {",
                    '    printf "TOOL=%s\\n" "$tool"',
                    '    printf "MODE=%s\\n" "$mode"',
                    '    printf "RUN_ID=%s\\n" "${VIBECRAFTED_RUN_ID:-}"',
                    '    printf "SKILL_CODE=%s\\n" "${VIBECRAFTED_SKILL_CODE:-}"',
                    '    printf "SKILL_NAME=%s\\n" "${VIBECRAFTED_SKILL_NAME:-}"',
                    '    printf "RUN_LOCK=%s\\n" "${VIBECRAFTED_RUN_LOCK:-}"',
                    '  } > "$CAPTURE_FILE"',
                    "}",
                    f"{helper} {quoted_args}".rstrip(),
                ]
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload: dict[str, str] = {}
    for line in capture_file.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        payload[key] = value
    return payload


def test_workflow_skill_helpers_reuse_one_run_id_from_prompt_to_spawn(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    fake_spawn = tmp_path / "fake_spawn.sh"
    capture_file = tmp_path / "run-trace.log"
    counter_file = tmp_path / "run-id-counter.txt"

    home.mkdir(parents=True)
    fake_spawn.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "{",
                '  printf "SPAWN_RUN_ID=%s\\n" "${VIBECRAFTED_RUN_ID:-}"',
                '  printf "SPAWN_RUN_LOCK=%s\\n" "${VIBECRAFTED_RUN_LOCK:-}"',
                '} >> "$CAPTURE_FILE"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    fake_spawn.chmod(0o755)

    env = os.environ.copy()
    env["HOME"] = str(home)
    env["CAPTURE_FILE"] = str(capture_file)
    env["VETCODERS_SPAWN_RUNTIME"] = "headless"
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["RUN_ID_COUNTER_FILE"] = str(counter_file)

    subprocess.run(
        [
            "bash",
            "-lc",
            "\n".join(
                [
                    "set -euo pipefail",
                    f'source "{HELPER_SCRIPT}"',
                    "_vetcoders_generate_run_id() {",
                    '  local prefix="$1"',
                    "  local counter=0",
                    '  if [[ -f "$RUN_ID_COUNTER_FILE" ]]; then',
                    '    counter="$(cat "$RUN_ID_COUNTER_FILE")"',
                    "  fi",
                    '  counter="$((counter + 1))"',
                    '  printf "%s" "$counter" > "$RUN_ID_COUNTER_FILE"',
                    '  if [[ "$counter" == "1" ]]; then',
                    '    printf "%s-111111\\n" "$prefix"',
                    "  else",
                    '    printf "%s-222222\\n" "$prefix"',
                    "  fi",
                    "}",
                    "_vetcoders_spawn_script() {",
                    f'  printf "%s\\n" "{fake_spawn}"',
                    "}",
                    "_vetcoders_prompt_text() {",
                    '  local tool="$1"',
                    '  local mode="$2"',
                    '  local prompt_text="$3"',
                    "  {",
                    '    printf "PROMPT_RUN_ID=%s\\n" "${VIBECRAFTED_RUN_ID:-}"',
                    '    printf "PROMPT_RUN_LOCK=%s\\n" "${VIBECRAFTED_RUN_LOCK:-}"',
                    '  } > "$CAPTURE_FILE"',
                    "  shift 3",
                    '  _vetcoders_spawn_plan "$tool" "$mode" /dev/null "$@"',
                    "}",
                    'codex-followup --prompt "Check runtime"',
                ]
            ),
        ],
        check=True,
        cwd=REPO_ROOT,
        env=env,
    )

    payload: dict[str, str] = {}
    for line in capture_file.read_text(encoding="utf-8").splitlines():
        key, value = line.split("=", 1)
        payload[key] = value

    assert payload["PROMPT_RUN_ID"] == "fwup-111111"
    assert payload["SPAWN_RUN_ID"] == "fwup-111111"
    assert payload["PROMPT_RUN_LOCK"] == payload["SPAWN_RUN_LOCK"]
    assert counter_file.read_text(encoding="utf-8") == "1"


def test_workflow_skill_helpers_create_run_context_before_prompt_text(
    tmp_path: Path,
) -> None:
    org_repo = _org_repo()
    cases = [
        ("codex-skill-workflow", "workflow", "wflw"),
        ("codex-followup", "followup", "fwup"),
        ("codex-dou", "dou", "vdou"),
    ]

    for index, (helper, skill_name, prefix) in enumerate(cases, start=1):
        payload = _run_prompt_capture(
            tmp_path / f"prompt-case-{index}",
            helper,
            ["--prompt", f"{skill_name} prompt capture"],
        )
        run_id = payload["RUN_ID"]
        assert payload["TOOL"] == "codex"
        assert payload["MODE"] == "implement"
        assert re.fullmatch(rf"{prefix}-\d{{6}}", run_id)
        assert payload["SKILL_CODE"] == prefix
        assert payload["SKILL_NAME"] == skill_name

        lock_path = Path(payload["RUN_LOCK"])
        expected_lock = (
            tmp_path
            / f"prompt-case-{index}"
            / "home"
            / ".vibecrafted"
            / "locks"
            / Path(org_repo)
            / f"{run_id}.lock"
        )
        assert lock_path == expected_lock
        assert lock_path.read_text(encoding="utf-8").splitlines()[:4] == [
            f"run_id={run_id}",
            "agent=codex",
            f"skill={skill_name}",
            f"root={REPO_ROOT}",
        ]


def test_workflow_skill_helpers_export_registered_run_ids_and_locks(
    tmp_path: Path,
) -> None:
    org_repo = _org_repo()
    cases = [
        ("codex-skill-workflow", "workflow", "wflw"),
        ("codex-followup", "followup", "fwup"),
        ("codex-dou", "dou", "vdou"),
        ("codex-justdo", "justdo", "just"),
    ]

    for index, (helper, skill_name, prefix) in enumerate(cases, start=1):
        payload = _run_helper(
            tmp_path / f"case-{index}",
            helper,
            ["--prompt", f"{skill_name} telemetry smoke"],
        )
        run_id = payload["RUN_ID"]
        assert re.fullmatch(rf"{prefix}-\d{{6}}", run_id)
        assert payload["SKILL_CODE"] == prefix
        assert payload["SKILL_NAME"] == skill_name

        lock_path = Path(payload["RUN_LOCK"])
        expected_lock = (
            tmp_path
            / f"case-{index}"
            / "home"
            / ".vibecrafted"
            / "locks"
            / Path(org_repo)
            / f"{run_id}.lock"
        )
        assert lock_path == expected_lock
        assert lock_path.read_text(encoding="utf-8").splitlines()[:4] == [
            f"run_id={run_id}",
            "agent=codex",
            f"skill={skill_name}",
            f"root={REPO_ROOT}",
        ]


def test_legacy_review_helper_generates_real_run_id_and_lock(tmp_path: Path) -> None:
    org_repo = _org_repo()
    plan_file = tmp_path / "review-plan.md"
    plan_file.write_text("# Review plan\n", encoding="utf-8")

    payload = _run_helper(tmp_path, "codex-review", [str(plan_file)])
    run_id = payload["RUN_ID"]

    assert re.fullmatch(r"rvew-\d{6}", run_id)
    assert payload["SKILL_CODE"] == "rvew"
    assert payload["SKILL_NAME"] == "review"

    lock_path = Path(payload["RUN_LOCK"])
    expected_lock = (
        tmp_path / "home" / ".vibecrafted" / "locks" / Path(org_repo) / f"{run_id}.lock"
    )
    assert lock_path == expected_lock
    assert "skill=review" in lock_path.read_text(encoding="utf-8")
