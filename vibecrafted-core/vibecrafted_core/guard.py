"""vc-guard — in-flight enforcer sibling of vc-trust.

Trust judges after the fact. Guard enforces at the gate. Guard never invents
settlement letters: it only consumes trust journal verdicts (and inventories
existing gates). Fail-closed with mandatory remedium text.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from . import trust

# Gate inventory — naming what already exists (coverage, not reimplementation).
GATE_INVENTORY: tuple[dict[str, str], ...] = (
    {
        "id": "commit-msg",
        "path": "scripts/hooks/commit-msg",
        "enforces": "subject [<agent>/<runtime>] type, Authored-By, session_id, time, runtime, body; bans vendor Co-Authored-By",
        "phase": "commit",
        "mode": "hard",
    },
    {
        "id": "prepare-commit-msg",
        "path": "scripts/hooks/prepare-commit-msg",
        "enforces": "fills Authored-By/session_id/time/runtime trailers when subject is legal",
        "phase": "commit",
        "mode": "helper",
    },
    {
        "id": "pre-commit",
        "path": "scripts/hooks/pre-commit (or core.hooksPath)",
        "enforces": "ruff/prettier/semgrep family quality gates before commit",
        "phase": "commit",
        "mode": "hard",
    },
    {
        "id": "pre-push",
        "path": "scripts/hooks/pre-push (or core.hooksPath)",
        "enforces": "push-time quality/security gates",
        "phase": "push",
        "mode": "hard",
    },
    {
        "id": "loctree-first",
        "path": "agent doctrine + tools/hooks (loctree-first)",
        "enforces": "structural map before structural grep; rejects blind rummaging",
        "phase": "agent",
        "mode": "policy",
    },
    {
        "id": "classifier-hard-stops",
        "path": "vc-operator AUTONOMY.md + charter hard-stops",
        "enforces": "push/merge/deploy/secrets require operator button",
        "phase": "dispatch",
        "mode": "policy",
    },
    {
        "id": "commit-msg-diff-advisory",
        "path": "tools/hooks/lib/commit-msg-diff-gate.sh (seed)",
        "enforces": "advisory claim-vs-staged pack checks (e.g. 5-file pack)",
        "phase": "commit",
        "mode": "advisory",
    },
    {
        "id": "trust-block-dispatch",
        "path": "vibecrafted_core.guard.enforce_continuation",
        "enforces": "refuse workflow continuation when HEAD (or line) has trust verdict block",
        "phase": "dispatch",
        "mode": "hard",
    },
)

COVERAGE_GAPS: tuple[str, ...] = (
    "No fleet-wide guarantee that every sibling repo has seeded commit-msg hooks.",
    "commit-msg-diff-gate remains advisory until operator elevates it to hard.",
    "PATH/install drift (source green, installed deck stale) is not yet a guard gate.",
    "Trust block refuse covers HEAD-by-default; per-branch line policy is opt-in via --sha.",
)


@dataclass(frozen=True)
class GuardDecision:
    allowed: bool
    reason: str
    remedium: str
    blocking_sha: str = ""
    blocking_verdict: str = ""
    journal: str = ""

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


def inventory() -> dict[str, Any]:
    return {
        "schema": "vibecrafted.guard-inventory.v1",
        "role": "enforcer",
        "sibling": "vc-trust (judge; never blocks dispatch)",
        "gates": list(GATE_INVENTORY),
        "coverage_gaps": list(COVERAGE_GAPS),
        "doctrine": {
            "fail_closed": True,
            "remedium_required": True,
            "non_interactive_safe": True,
            "settlement_authority": "vc-trust note only; guard never invents f/x/n letters",
            "agent_fairness": (
                "commit-msg enforces Authored-By shape; trust falsifies fairness "
                "truth; guard may refuse when trust has blocked the line"
            ),
        },
    }


def _repo_root(path: Path | None = None) -> Path:
    return trust._repo_root(path)


def _head_sha(repo: Path) -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo),
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise ValueError(proc.stderr.strip() or "cannot resolve HEAD")
    return proc.stdout.strip()


def latest_trust_verdict(
    *,
    repo: Path,
    journal: Path,
    sha: str = "",
) -> dict[str, Any] | None:
    """Latest append-only trust journal record for repo+sha (default HEAD)."""
    resolved_repo = _repo_root(repo)
    target = sha or _head_sha(resolved_repo)
    full = trust._resolve_commit(resolved_repo, target)
    roots = {str(resolved_repo), str(repo), str(Path(repo).resolve())}
    latest: dict[str, Any] | None = None
    for record in trust._read_journal(journal):
        if str(record.get("repo_root") or "") not in roots:
            # Also accept if both resolve to the same path (macOS /var).
            try:
                if Path(str(record.get("repo_root"))).resolve() != resolved_repo:
                    continue
            except OSError:
                continue
        if str(record.get("sha") or "") != full:
            continue
        latest = dict(record)
    return latest


def enforce_continuation(
    *,
    repo: Path | None = None,
    journal: Path | None = None,
    sha: str = "",
    skill: str = "",
) -> GuardDecision:
    """Refuse continuation when trust has recorded block for the target commit.

    Does not invent settlement. Does not re-judge claims. Fail-closed on
    unreadable journals only when an explicit block cannot be ruled out? —
    No: missing journal means no trust block yet → allow (trust is opt-in
    judge; guard only acts on recorded block).
    """
    # Guard must never refuse its own inventory / trust workflows circularly
    # in a way that prevents remediation. trust and guard themselves always pass.
    if skill in {"trust", "guard", "init"}:
        return GuardDecision(
            allowed=True,
            reason="meta_skill_exempt",
            remedium="",
            journal=str(journal or trust.default_journal_path()),
        )

    resolved_repo = _repo_root(repo)
    resolved_journal = (journal or trust.default_journal_path()).expanduser()
    if not resolved_journal.is_file():
        return GuardDecision(
            allowed=True,
            reason="no_trust_journal",
            remedium="",
            journal=str(resolved_journal),
        )

    record = latest_trust_verdict(repo=resolved_repo, journal=resolved_journal, sha=sha)
    if record is None:
        return GuardDecision(
            allowed=True,
            reason="no_trust_verdict_for_target",
            remedium="",
            journal=str(resolved_journal),
        )

    verdict = str(record.get("verdict") or "")
    blocking_sha = str(record.get("sha") or "")
    if verdict != "block":
        return GuardDecision(
            allowed=True,
            reason=f"trust_verdict_{verdict or 'empty'}",
            remedium="",
            blocking_sha=blocking_sha,
            blocking_verdict=verdict,
            journal=str(resolved_journal),
        )

    claims = record.get("claims") or []
    claim_lines = []
    if isinstance(claims, list):
        for item in claims[:6]:
            if isinstance(item, Mapping):
                claim_lines.append(f"  - {item.get('claim')}: {item.get('evidence')}")
    remedium = (
        f"vc-guard: refuse continuation — trust recorded block on {blocking_sha[:12]}.\n"
        f"Remedium:\n"
        f"  1. Read journal entry: {resolved_journal}\n"
        f"  2. Fix the falsified claims (agent fairness, completeness, runtime).\n"
        f"  3. Commit the fix with legal Authored-By matching the executor.\n"
        f"  4. Re-run: python -m vibecrafted_core.trust inspect <new-sha>\n"
        f"  5. Explicitly note a new verdict (pass/pass-with-gaps) — never imply pass.\n"
        f"Blocked claims:\n"
        + ("\n".join(claim_lines) if claim_lines else "  (see journal)")
    )
    return GuardDecision(
        allowed=False,
        reason="trust_block",
        remedium=remedium,
        blocking_sha=blocking_sha,
        blocking_verdict="block",
        journal=str(resolved_journal),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m vibecrafted_core.guard",
        description="vc-guard inventory and trust-block enforcement helper.",
    )
    parser.add_argument("--journal", type=Path, default=None)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inventory", help="List named gates and coverage gaps")
    check = commands.add_parser(
        "check",
        help="Allow/refuse continuation based on trust journal block for HEAD/sha",
    )
    check.add_argument("--sha", default="")
    check.add_argument("--skill", default="")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inventory":
            print(json.dumps(inventory(), indent=2, ensure_ascii=False))
            return 0
        decision = enforce_continuation(
            repo=args.repo,
            journal=args.journal,
            sha=args.sha,
            skill=args.skill,
        )
        print(json.dumps(decision.to_payload(), indent=2, ensure_ascii=False))
        if decision.allowed:
            return 0
        print(decision.remedium, file=sys.stderr)
        return 1
    except (OSError, ValueError) as exc:
        print(f"vc-guard: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
