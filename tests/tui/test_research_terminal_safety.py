from __future__ import annotations

import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
HELPER_SCRIPT = REPO_ROOT / "runtime" / "shell" / "vetcoders.sh"

sys.path.insert(0, str(REPO_ROOT / "vibecrafted-core"))

from vibecrafted_core.wrappers import _launcher_paths  # noqa: E402

BLOCKING_ZELLIJ_VERBS = ("attach", "--new-session-with-layout", "switch-session")


def _stub_zellij(bin_dir: Path, log: Path) -> None:
    # Records every invocation; reports no sessions. Lets the test prove that
    # vc-research never starts a blocking zellij client in the calling shell.
    bin_dir.mkdir(parents=True, exist_ok=True)
    stub = bin_dir / "zellij"
    stub.write_text(
        "#!/usr/bin/env bash\n"
        f'echo "$@" >> "{log}"\n'
        'case "${1:-}" in list-sessions|ls) exit 0 ;; esac\n'
        "exit 0\n",
        encoding="utf-8",
    )
    stub.chmod(stub.stat().st_mode | stat.S_IEXEC)


def test_vc_research_terminal_without_session_degrades_to_headless(
    tmp_path: Path,
) -> None:
    # VC-vbcr-stabilize-033 (operator-reported terminal kill): with terminal
    # runtime and no live zellij session, vc-research used to hand the calling
    # terminal to a blocking zellij client. It must degrade to headless, leave
    # the shell alive, and never invoke a blocking zellij verb.
    root = tmp_path / "repo"
    root.mkdir()
    crafted_home = tmp_path / "home" / ".vibecrafted"
    stub_bin = tmp_path / "stub-bin"
    zellij_log = tmp_path / "zellij-invocations.log"
    _stub_zellij(stub_bin, zellij_log)

    env = os.environ.copy()
    env["VIBECRAFTED_HOME"] = str(crafted_home)
    env["VIBECRAFTED_ROOT"] = str(REPO_ROOT)
    env["VETCODERS_SPAWN_RUNTIME"] = "terminal"
    for ambient in (
        "ZELLIJ",
        "ZELLIJ_PANE_ID",
        "ZELLIJ_SESSION_NAME",
        "VIBECRAFTED_OPERATOR_SESSION",
        "VIBECRAFTED_RUN_ID",
        "VIBECRAFTED_RUN_LOCK",
    ):
        env.pop(ambient, None)

    result = subprocess.run(
        [
            "bash",
            "-c",
            (
                f'export PATH="{stub_bin}:$PATH"; '
                f'source "{HELPER_SCRIPT}"; '
                f'vc-research --root "{root}" --prompt "probe terminal safety"; '
                'rc=$?; echo "SHELL-ALIVE rc=$rc"; exit $rc'
            ),
        ],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert "SHELL-ALIVE rc=0" in result.stdout, (
        f"calling shell did not survive: rc={result.returncode}\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert "Degrading to headless" in result.stderr
    assert "Research swarm prepared" in result.stdout
    assert "Launchers:" in result.stdout

    if zellij_log.exists():
        calls = zellij_log.read_text(encoding="utf-8")
        for verb in BLOCKING_ZELLIJ_VERBS:
            assert verb not in calls, f"blocking zellij verb invoked: {verb}\n{calls}"


def test_launcher_paths_recognise_every_supported_agent() -> None:
    # The old regex matched only claude|codex|gemini while the default swarm
    # is claude+codex+junie — the venv vc-research entrypoint could never
    # collect its own launchers and always exited 1 before spawning.
    output = "\n".join(
        [
            "Launchers:",
            "  claude: /tmp/claude_launch.sh",
            "  codex: /tmp/codex_launch.sh",
            "  junie: /tmp/junie_launch.sh",
            "  agy: /tmp/agy_launch.sh",
            "  grok: /tmp/grok_launch.sh",
            "  gemini: /tmp/gemini_launch.sh",
        ]
    )
    launchers = _launcher_paths(output)
    assert sorted(launchers) == ["agy", "claude", "codex", "gemini", "grok", "junie"]
    assert launchers["junie"] == Path("/tmp/junie_launch.sh")
