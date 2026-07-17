from __future__ import annotations

import json
import subprocess
from types import SimpleNamespace
from pathlib import Path

import pytest

from vibecrafted_core import git as git_module
from vibecrafted_core import workflow
from vibecrafted_core.foundation.data_authority import inventory_sources
from vibecrafted_core.foundation.lease import lease_budget_hash, validate_diff_text
from vibecrafted_core.foundation.model import DestructiveChangeLease, FoundationStatus
from vibecrafted_core.foundation.service import (
    FoundationError,
    load_receipt,
    preflight_launch,
    seal_repository,
    verify_receipt,
)
from vibecrafted_core.package_resources import resource_path
from vibecrafted_core.workflow import WorkflowLaunchSpec


def _git(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=path, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def _commit(path: Path, name: str, content: str) -> str:
    target = path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    _git(path, "add", name)
    _git(path, "commit", "-q", "-m", f"add {name}")
    return _git(path, "rev-parse", "HEAD")


def _authority_repo(tmp_path: Path) -> tuple[Path, Path, Path]:
    bare = tmp_path / "authority.git"
    subprocess.run(["git", "init", "-q", "--bare", str(bare)], check=True)
    seed = tmp_path / "seed"
    subprocess.run(["git", "init", "-q", "-b", "main", str(seed)], check=True)
    _git(seed, "config", "user.email", "test@example.com")
    _git(seed, "config", "user.name", "tester")
    _git(seed, "remote", "add", "origin", str(bare))
    _commit(seed, "README.md", "base\n")
    config = seed / "vibecrafted.toml"
    config.write_text(
        '[vibecrafted.foundation]\nrequired = true\nauthority = "origin/main"\n'
        "normative_sources = []\nnormative_discovery_globs = []\npremises = []\n",
        encoding="utf-8",
    )
    _git(seed, "add", "vibecrafted.toml")
    _git(seed, "commit", "-q", "-m", "configure foundation")
    _git(seed, "push", "-q", "-u", "origin", "main")
    live = tmp_path / "live"
    subprocess.run(
        ["git", "clone", "-q", "--branch", "main", str(bare), str(live)], check=True
    )
    _git(live, "config", "user.email", "test@example.com")
    _git(live, "config", "user.name", "tester")
    return bare, seed, live


def test_foundation_schema_and_rule_are_packaged() -> None:
    schema = json.loads(
        resource_path("schemas", "foundation.schema.v1.json").read_text(
            encoding="utf-8"
        )
    )
    assert schema["$id"] == "vibecrafted.foundation.v1"
    assert set(schema["properties"]["status"]["enum"]) == {
        "SEALED",
        "BLOCKED",
        "OPERATOR_WAIVER_REQUIRED",
    }
    assert resource_path("skills", "FOUNDATION_RULE.md").is_file()


def test_repo_full_missing_upstream_is_unknown_not_zero(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")
    _commit(repo, "README.md", "hello\n")

    payload = git_module.repo_full(repo)

    assert payload["upstream"] == ""
    assert payload["ahead"] is None
    assert payload["behind"] is None
    assert payload["ahead_behind_state"] == "unknown"


def test_stale_but_green_branch_blocks_seven_missing_commits_without_mutation(
    tmp_path: Path,
) -> None:
    _bare, seed, live = _authority_repo(tmp_path)
    _git(live, "switch", "-q", "-c", "feature")
    _git(live, "push", "-q", "-u", "origin", "feature")
    for index in range(7):
        _commit(seed, f"authority/capability_{index}.py", f"CAPABILITY = {index}\n")
    _git(seed, "push", "-q", "origin", "main")
    before = (_git(live, "rev-parse", "HEAD"), _git(live, "status", "--porcelain=v1"))

    receipt, path = seal_repository(
        live, run_id="incident-stale", output=tmp_path / "blocked.json"
    )
    after = (_git(live, "rev-parse", "HEAD"), _git(live, "status", "--porcelain=v1"))
    decision = preflight_launch(
        root=live,
        workflow="implement",
        can_modify_code=True,
        receipt_path=path,
    )

    assert receipt.status is FoundationStatus.BLOCKED
    assert len(receipt.repository.authority_only_commits) == 7
    assert decision["allowed"] is False
    assert before == after


def test_synthetic_oracle_cannot_hide_unbound_live_truth(tmp_path: Path) -> None:
    (tmp_path / "fixtures").mkdir()
    (tmp_path / "fixtures" / "synthetic.json").write_text("{}\n", encoding="utf-8")
    (tmp_path / "sessions").mkdir()
    (tmp_path / "sessions" / "real.json").write_text(
        '{"real": true}\n', encoding="utf-8"
    )

    sources, unbound = inventory_sources(
        tmp_path,
        [
            {
                "identity": "synthetic",
                "path": "fixtures/synthetic.json",
                "provenance": "synthetic",
            }
        ],
        discovery_globs=["sessions/*.json"],
    )

    assert sources[0].provenance == "synthetic"
    assert unbound == (str((tmp_path / "sessions" / "real.json").resolve()),)


def test_legitimate_seal_plan_binding_and_normative_drift(tmp_path: Path) -> None:
    _bare, seed, live = _authority_repo(tmp_path)
    normative = seed / "oracle.json"
    normative.write_text('{"schema": 1}\n', encoding="utf-8")
    config = seed / "vibecrafted.toml"
    config.write_text(
        '[vibecrafted.foundation]\nrequired = true\nauthority = "origin/main"\n'
        'normative_discovery_globs = ["oracle*.json"]\npremises = []\n'
        '[[vibecrafted.foundation.normative_sources]]\nidentity = "oracle"\npath = "oracle.json"\n'
        'provenance = "real"\nrequired_provenance = "real"\n',
        encoding="utf-8",
    )
    _git(seed, "add", "oracle.json", "vibecrafted.toml")
    _git(seed, "commit", "-q", "-m", "bind normative oracle")
    _git(seed, "push", "-q", "origin", "main")
    _git(live, "pull", "-q", "--ff-only")

    receipt, path = seal_repository(live, output=tmp_path / "sealed.json")
    plan = tmp_path / "plan.md"
    plan.write_text(
        "---\n"
        f"foundation_receipt_path: {path}\n"
        f"foundation_receipt_hash: {receipt.receipt_hash}\n"
        f"foundation_authority_ref: {receipt.repository.authority_ref}\n"
        f"foundation_authority_sha: {receipt.repository.authority_sha.value}\n"
        f"foundation_premise_set_hash: {receipt.bindings['premise_set_hash']}\n"
        "---\n",
        encoding="utf-8",
    )

    assert receipt.status is FoundationStatus.SEALED
    assert verify_receipt(path, root=live, plan_path=plan)["allowed"] is True
    (live / "oracle.json").write_text('{"schema": 2}\n', encoding="utf-8")
    drift = verify_receipt(path, root=live, plan_path=plan)
    assert drift["allowed"] is False
    assert "normative source drifted: oracle" in drift["reasons"]


def test_destructive_lease_rejects_path_and_budget_overrun() -> None:
    budget_hash = lease_budget_hash(
        allowed_paths=("src/parser/**",),
        max_deleted_files=1,
        max_deleted_loc=100,
        expected_deleted_symbols=("LegacyParser",),
        risk_class="destructive",
        approved_by="operator",
    )
    lease = DestructiveChangeLease(
        allowed_paths=("src/parser/**",),
        max_deleted_files=1,
        max_deleted_loc=100,
        expected_deleted_symbols=("LegacyParser",),
        risk_class="destructive",
        approved_budget_hash=budget_hash,
        approved_by="operator",
        recovery_checkpoint_ref="refs/vibecrafted/checkpoints/run/cut",
        dirty_snapshot_hash="abc",
    )

    result = validate_diff_text(
        lease,
        name_status="D\tsrc/parser/old.py\nD\tsecrets.txt\n",
        numstat="0\t90\tsrc/parser/old.py\n0\t50\tsecrets.txt\n",
        deleted_symbols=("LegacyParser", "HiddenParser"),
    )

    assert result.allowed is False
    assert len(result.violations) == 4


def test_receipt_hash_tampering_blocks(tmp_path: Path) -> None:
    _bare, _seed, live = _authority_repo(tmp_path)
    receipt, path = seal_repository(live, output=tmp_path / "sealed.json")
    assert receipt.status is FoundationStatus.SEALED
    payload = load_receipt(path)
    payload["created_by"] = "attacker"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert verify_receipt(path, root=live)["allowed"] is False


def test_remote_advance_and_offline_refresh_invalidate_seal(tmp_path: Path) -> None:
    bare, seed, live = _authority_repo(tmp_path)
    receipt, path = seal_repository(live, output=tmp_path / "sealed.json")
    assert receipt.status is FoundationStatus.SEALED
    _commit(seed, "new_capability.py", "VALUE = 1\n")
    _git(seed, "push", "-q", "origin", "main")
    advanced = verify_receipt(path, root=live)
    assert advanced["allowed"] is False
    assert "authority ref drifted from receipt" in advanced["reasons"]

    offline = tmp_path / "authority-offline.git"
    bare.rename(offline)
    unavailable = verify_receipt(path, root=live)
    assert unavailable["allowed"] is False
    assert any(
        reason.startswith("authority refresh failed:")
        for reason in unavailable["reasons"]
    )


def test_detached_and_unrelated_histories_block(tmp_path: Path) -> None:
    _bare, _seed, live = _authority_repo(tmp_path)
    _git(live, "checkout", "-q", "--detach", "HEAD")
    detached, _path = seal_repository(live, output=tmp_path / "detached.json")
    assert detached.status is FoundationStatus.BLOCKED
    assert detached.repository.detached.value is True

    unrelated = tmp_path / "unrelated"
    subprocess.run(["git", "init", "-q", "-b", "main", str(unrelated)], check=True)
    _git(unrelated, "config", "user.email", "test@example.com")
    _git(unrelated, "config", "user.name", "tester")
    _commit(unrelated, "local.txt", "unrelated\n")
    _git(unrelated, "remote", "add", "origin", str(_bare))
    (unrelated / "vibecrafted.toml").write_text(
        '[vibecrafted.foundation]\nrequired = true\nauthority = "origin/main"\n',
        encoding="utf-8",
    )
    unrelated_receipt, _ = seal_repository(
        unrelated, output=tmp_path / "unrelated.json"
    )
    assert unrelated_receipt.status is FoundationStatus.BLOCKED
    assert unrelated_receipt.repository.relation.value == "unrelated"


def test_ambiguous_authority_is_never_guessed(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "tester")
    _commit(repo, "README.md", "hello\n")
    _git(repo, "remote", "add", "one", str(tmp_path / "one.git"))
    _git(repo, "remote", "add", "two", str(tmp_path / "two.git"))

    with pytest.raises(FoundationError, match="explicit authority is required"):
        seal_repository(repo, output=tmp_path / "ambiguous.json")
    preflight = preflight_launch(
        root=repo,
        workflow="implement",
        can_modify_code=True,
    )
    assert preflight["allowed"] is False


def test_workflow_launch_blocks_before_popen_and_sealed_path_launches_once(
    tmp_path: Path, monkeypatch
) -> None:
    _bare, seed, live = _authority_repo(tmp_path)
    monkeypatch.setenv("VIBECRAFTED_HOME", str(tmp_path / "state"))
    for index in range(2):
        _commit(seed, f"missing_{index}.py", f"VALUE = {index}\n")
    _git(seed, "push", "-q", "origin", "main")
    blocked, blocked_path = seal_repository(live, output=tmp_path / "blocked.json")
    calls: list[list[str]] = []

    class FakeProcess:
        pid = 4242

    def fake_popen(command, **_kwargs):
        calls.append(list(command))
        return FakeProcess()

    monkeypatch.setattr(
        workflow,
        "subprocess",
        SimpleNamespace(
            Popen=fake_popen,
            STDOUT=subprocess.STDOUT,
            SubprocessError=subprocess.SubprocessError,
            run=subprocess.run,
        ),
    )
    spec = WorkflowLaunchSpec(
        agent="codex",
        mode="implement",
        skill="implement",
        prompt="do not mutate",
        file="",
        runtime="headless",
        root=str(live),
        foundation_receipt_path=str(blocked_path),
    )
    refused = workflow.launch_workflow(spec, tmp_path)
    assert blocked.status is FoundationStatus.BLOCKED
    assert refused["accepted"] is False
    assert refused["worker_launches"] == 0
    assert calls == []

    _git(live, "pull", "-q", "--ff-only")
    sealed, sealed_path = seal_repository(live, output=tmp_path / "sealed-launch.json")
    assert sealed.status is FoundationStatus.SEALED
    allowed_spec = replace_spec = WorkflowLaunchSpec(
        agent="codex",
        mode="implement",
        skill="implement",
        prompt="bounded work",
        file="",
        runtime="headless",
        root=str(live),
        foundation_receipt_path=str(sealed_path),
    )
    launched = workflow.launch_workflow(allowed_spec, tmp_path)
    assert replace_spec is allowed_spec
    assert launched["accepted"] is True
    assert launched["foundation"]["status"] == "SEALED"
    assert len(calls) == 1
