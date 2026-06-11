from __future__ import annotations

import json
import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from vibecrafted_core.dispatch.model import (
    STATE_FAILED,
    STATE_PENDING,
    STATE_UNKNOWN,
    STATE_VERIFIED,
    Dispatch,
)
from vibecrafted_core.dispatch.schema import parse_dispatch
from vibecrafted_core.dispatch.supervisor import (
    CellRun,
    DispatchSupervisor,
    run_dispatch,
)

FAST_AWAIT = "await = { poll_s = 0.02, timeout_min = 1.0 }"


@dataclass
class FakeCell:
    """Echo-script work cell: bash side effects + a literal report body."""

    bash: str = ""
    report: str = "worker done"
    write_report: bool = True


@dataclass
class FakeCells:
    """Launcher double that spawns real bash processes instead of LLM cells,
    so the supervisor's process-handle await path is exercised for real."""

    reports_dir: Path
    cells: dict[tuple[str, str], FakeCell] = field(default_factory=dict)
    launches: list[tuple[str, str]] = field(default_factory=list)
    prompts: dict[tuple[str, str], str] = field(default_factory=dict)

    def __call__(self, cut, prompt: str, kind: str) -> CellRun:
        self.launches.append((cut.id, kind))
        self.prompts[(cut.id, kind)] = prompt
        cell = self.cells.get((cut.id, kind), FakeCell())
        report_path = self.reports_dir / f"{cut.id}_{kind}_report.md"
        script = cell.bash or "true"
        if cell.write_report:
            script += (
                f"\nprintf '%s\\n' {shlex.quote(cell.report)}"
                f" > {shlex.quote(str(report_path))}"
            )
        proc = subprocess.Popen(["bash", "-c", script])
        return CellRun(
            cut_id=cut.id,
            kind=kind,
            accepted=True,
            run_id=f"fake-{cut.id}-{kind}",
            pid=proc.pid,
            report_path=str(report_path),
            proc=proc,
        )


def build_dispatch(
    tmp_path: Path, cuts_toml: str, *, repo: Path | None = None, policy: str = ""
) -> tuple[Dispatch, Path, Path]:
    repo_dir = repo if repo is not None else tmp_path / "repo"
    repo_dir.mkdir(exist_ok=True)
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir(exist_ok=True)
    artifacts_dir = tmp_path / "artifacts"
    policy_text = policy or "repair_rounds = 0"
    if "await" not in policy_text:
        policy_text += f"\n{FAST_AWAIT}"
    text = f"""
schema = "vibecrafted.dispatch.v1"

[meta]
name = "fake-dispatch"
repo = "{repo_dir}"
reports_dir = "{reports_dir}"

[policy]
{policy_text}

{cuts_toml}
"""
    return parse_dispatch(text, base_dir=tmp_path), reports_dir, artifacts_dir


def init_git_repo(path: Path) -> None:
    path.mkdir(exist_ok=True)
    for args in (
        ["init", "-q"],
        ["config", "user.email", "agents@vetcoders.io"],
        ["config", "user.name", "fake"],
    ):
        subprocess.run(["git", *args], cwd=path, check=True, capture_output=True)
    (path / "seed.txt").write_text("seed\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-q", "-m", "seed"],
        cwd=path,
        check=True,
        capture_output=True,
    )


def test_passing_cuts_flip_to_verified_and_emit_artifacts(tmp_path: Path) -> None:
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "c1"
agent = "claude"
workflow = "implement"
prompt = "do thing one"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }

[[cuts]]
id = "c2"
agent = "codex"
workflow = "implement"
prompt = "do thing two"
  [[cuts.verify]]
  run = "echo also ok"
  expect = { contains = "ok", exit_code = 0 }
""",
    )
    launcher = FakeCells(reports_dir=reports_dir)

    result = run_dispatch(dispatch, launcher=launcher, artifacts_dir=artifacts_dir)

    assert result.states == {"c1": STATE_VERIFIED, "c2": STATE_VERIFIED}
    assert result.line_broken is False
    assert launcher.launches == [("c1", "initial"), ("c2", "initial")]

    tracker = (artifacts_dir / "tracker.md").read_text(encoding="utf-8")
    assert tracker.count("[x]") == 2
    journal = (artifacts_dir / "journal.md").read_text(encoding="utf-8")
    assert "dispatch start" in journal and "dispatch end" in journal
    handoff = (artifacts_dir / "handoff.md").read_text(encoding="utf-8")
    assert "dou_index: 2/2" in handoff
    payload = json.loads(
        (artifacts_dir / "dispatch-result.json").read_text(encoding="utf-8")
    )
    assert payload["schema"] == "vibecrafted.dispatch-result.v1"
    assert payload["baton"]["dou_index"]["verified"] == 2
    assert [entry["id"] for entry in payload["cuts"]] == ["c1", "c2"]
    assert payload["cuts"][0]["state"] == STATE_VERIFIED
    assert payload["cuts"][1]["state"] == STATE_VERIFIED


def test_baton_flows_from_verified_cut_into_next_prompt(tmp_path: Path) -> None:
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "c1"
agent = "claude"
workflow = "implement"
prompt = "first"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }

[[cuts]]
id = "c2"
agent = "claude"
workflow = "implement"
prompt = "second consumes {baton}"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
    )
    launcher = FakeCells(reports_dir=reports_dir)

    run_dispatch(dispatch, launcher=launcher, artifacts_dir=artifacts_dir)

    second_prompt = launcher.prompts[("c2", "initial")]
    assert '"cut_id": "c1"' in second_prompt
    assert '"state": "[x]"' in second_prompt


def test_failed_verify_launches_repair_then_verifies(tmp_path: Path) -> None:
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "c1"
agent = "claude"
workflow = "implement"
prompt = "create the marker"
  [[cuts.verify]]
  run = "cat marker.txt"
  expect = { contains = "fixed" }
""",
        policy="repair_rounds = 1",
    )
    repo_dir = Path(dispatch.meta.repo)
    launcher = FakeCells(reports_dir=reports_dir)
    launcher.cells[("c1", "initial")] = FakeCell(bash="true")
    launcher.cells[("c1", "repair1")] = FakeCell(
        bash=f"echo fixed > {shlex.quote(str(repo_dir / 'marker.txt'))}"
    )

    result = run_dispatch(dispatch, launcher=launcher, artifacts_dir=artifacts_dir)

    assert result.states == {"c1": STATE_VERIFIED}
    assert launcher.launches == [("c1", "initial"), ("c1", "repair1")]
    assert result.baton.last is not None
    assert result.baton.last.repair_attempts == 1
    repair_prompt = launcher.prompts[("c1", "repair1")]
    assert "REPAIR ROUND" in repair_prompt
    assert "marker.txt" in repair_prompt


def test_critical_failure_breaks_line_and_skips_downstream(tmp_path: Path) -> None:
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "c1"
critical = true
agent = "claude"
workflow = "implement"
prompt = "doomed"
  [[cuts.verify]]
  run = "echo broken"
  expect = { contains = "never-there" }

[[cuts]]
id = "c2"
agent = "codex"
workflow = "implement"
prompt = "never runs"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
    )
    launcher = FakeCells(reports_dir=reports_dir)

    result = run_dispatch(dispatch, launcher=launcher, artifacts_dir=artifacts_dir)

    assert result.states == {"c1": STATE_FAILED, "c2": STATE_PENDING}
    assert result.line_broken is True
    assert launcher.launches == [("c1", "initial")]
    assert [(entry["id"], entry["state"]) for entry in result.cuts] == [
        ("c1", STATE_FAILED),
        ("c2", STATE_PENDING),
    ]
    tracker = (artifacts_dir / "tracker.md").read_text(encoding="utf-8")
    assert "skipped: line broken upstream" in tracker
    journal = (artifacts_dir / "journal.md").read_text(encoding="utf-8")
    assert "breaking the dispatch line" in journal


def test_read_cut_mutation_is_refuted_despite_green_verify(tmp_path: Path) -> None:
    repo_dir = tmp_path / "repo"
    init_git_repo(repo_dir)
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "audit"
agent = "gemini"
workflow = "review"
mode = "read"
mutation = "forbid"
prompt = "look but do not touch"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
        repo=repo_dir,
    )
    launcher = FakeCells(reports_dir=reports_dir)
    launcher.cells[("audit", "initial")] = FakeCell(
        bash=f"echo dirty > {shlex.quote(str(repo_dir / 'mutated.txt'))}"
    )

    result = run_dispatch(dispatch, launcher=launcher, artifacts_dir=artifacts_dir)

    assert result.states == {"audit": STATE_FAILED}
    assert result.baton.last is not None
    assert any("mutated" in f or "mutation" in f for f in result.baton.last.failures)
    journal = (artifacts_dir / "journal.md").read_text(encoding="utf-8")
    assert "READ cut mutated the repository" in journal


def test_substrate_failure_in_report_refutes_cut(tmp_path: Path) -> None:
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "c1"
agent = "claude"
workflow = "implement"
prompt = "poisoned tree"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
    )
    launcher = FakeCells(reports_dir=reports_dir)
    launcher.cells[("c1", "initial")] = FakeCell(
        report="SUBSTRATE_FAILURE: tree poisoned by concurrent reset"
    )

    result = run_dispatch(dispatch, launcher=launcher, artifacts_dir=artifacts_dir)

    assert result.states == {"c1": STATE_FAILED}
    assert result.baton.last is not None
    assert any("SUBSTRATE_FAILURE" in f for f in result.baton.last.failures)


def test_launcher_exception_still_emits_result_and_handoff(tmp_path: Path) -> None:
    dispatch, _reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "boom"
critical = true
agent = "codex"
workflow = "implement"
prompt = "launcher crashes"
  [[cuts.verify]]
  run = "echo should-not-run"
  expect = { contains = "should-not-run" }

[[cuts]]
id = "downstream"
agent = "codex"
workflow = "implement"
prompt = "skipped after critical crash"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
    )

    def crashing_launcher(_cut, _prompt: str, _kind: str) -> CellRun:
        raise RuntimeError("launcher exploded before accepting the cell")

    result = run_dispatch(
        dispatch, launcher=crashing_launcher, artifacts_dir=artifacts_dir
    )

    assert result.line_broken is True
    assert result.states == {"boom": STATE_FAILED, "downstream": STATE_PENDING}
    payload = json.loads(
        (artifacts_dir / "dispatch-result.json").read_text(encoding="utf-8")
    )
    assert [(entry["id"], entry["state"]) for entry in payload["cuts"]] == [
        ("boom", STATE_FAILED),
        ("downstream", STATE_PENDING),
    ]
    handoff = (artifacts_dir / "handoff.md").read_text(encoding="utf-8")
    assert "launcher exploded before accepting the cell" in handoff
    journal = (artifacts_dir / "journal.md").read_text(encoding="utf-8")
    assert "dispatch end" in journal


def test_timeout_continue_marks_unknown_and_journals(tmp_path: Path) -> None:
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "slow"
agent = "claude"
workflow = "implement"
prompt = "sleeps forever"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
        policy=(
            "repair_rounds = 0\n"
            'on_timeout = "continue"\n'
            "await = { poll_s = 0.02, timeout_min = 0.005 }"
        ),
    )
    launcher = FakeCells(reports_dir=reports_dir)
    launcher.cells[("slow", "initial")] = FakeCell(bash="sleep 10", write_report=False)

    result = run_dispatch(dispatch, launcher=launcher, artifacts_dir=artifacts_dir)

    assert result.states == {"slow": STATE_UNKNOWN}
    journal = (artifacts_dir / "journal.md").read_text(encoding="utf-8")
    assert "timed out" in journal
    assert "process terminated" in journal


def test_broken_announced_report_recovers_by_mtime(tmp_path: Path) -> None:
    dispatch, reports_dir, artifacts_dir = build_dispatch(
        tmp_path,
        """
[[cuts]]
id = "c1"
agent = "claude"
workflow = "implement"
prompt = "writes report elsewhere"
  [[cuts.verify]]
  run = "echo ok"
  expect = { contains = "ok" }
""",
    )
    stray_report = reports_dir / "stray_actual_report.md"

    def broken_path_launcher(cut, prompt: str, kind: str) -> CellRun:
        proc = subprocess.Popen(
            [
                "bash",
                "-c",
                f"printf 'real report\\n' > {shlex.quote(str(stray_report))}",
            ]
        )
        return CellRun(
            cut_id=cut.id,
            kind=kind,
            accepted=True,
            run_id="fake-broken",
            pid=proc.pid,
            report_path=str(tmp_path / "announced" / "never_written.md"),
            proc=proc,
        )

    result = run_dispatch(
        dispatch, launcher=broken_path_launcher, artifacts_dir=artifacts_dir
    )

    assert result.states == {"c1": STATE_VERIFIED}
    assert result.baton.last is not None
    assert result.baton.last.report == str(stray_report)
    journal = (artifacts_dir / "journal.md").read_text(encoding="utf-8")
    assert "recovered by mtime" in journal


def test_supervisor_default_artifacts_follow_tracker_path(tmp_path: Path) -> None:
    plans_dir = tmp_path / "plans"
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    reports_dir = tmp_path / "reports"
    reports_dir.mkdir()
    text = f"""
schema = "vibecrafted.dispatch.v1"

[meta]
name = "tracker-located"
repo = "{repo_dir}"
reports_dir = "{reports_dir}"
tracker = "{plans_dir / "tracker.md"}"

[policy]
repair_rounds = 0
{FAST_AWAIT}

[[cuts]]
id = "c1"
agent = "claude"
workflow = "implement"
prompt = "noop"
  [[cuts.verify]]
  run = "echo ok"
  expect = {{ contains = "ok" }}
"""
    dispatch = parse_dispatch(text, base_dir=tmp_path)
    launcher = FakeCells(reports_dir=reports_dir)
    supervisor = DispatchSupervisor(dispatch, launcher=launcher)

    result = supervisor.run()

    assert result.states == {"c1": STATE_VERIFIED}
    assert (plans_dir / "tracker.md").is_file()
    assert (plans_dir / "journal.md").is_file()
    assert (plans_dir / "dispatch-result.json").is_file()
