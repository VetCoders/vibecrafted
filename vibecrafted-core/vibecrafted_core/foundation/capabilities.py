from __future__ import annotations

import ast
import re
import subprocess
import tomllib
from pathlib import PurePosixPath, Path
from typing import Mapping

from .model import CapabilityClassification, CapabilityDelta


def _git_lines(root: Path, *args: str) -> tuple[str, ...]:
    result = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            (result.stderr or result.stdout).strip() or "git inventory failed"
        )
    return tuple(line for line in result.stdout.splitlines() if line)


def capability_kind(path: str) -> str | None:
    name = PurePosixPath(path).name
    if path.startswith("bin/") or name.startswith("vc-"):
        return "command"
    if "/tests/" in f"/{path}" or name.startswith("test_"):
        return "test"
    if name.endswith(".schema.json") or "/schemas/" in f"/{path}":
        return "schema"
    if name.endswith("_RULE.md"):
        return "rule"
    if name in {"Makefile", "install.sh", "install.ps1", "install.toml"}:
        return "release"
    if name in {"pyproject.toml", "vibecrafted.toml"}:
        return "config"
    return None


def _source_capabilities(path: str, source: str) -> dict[str, str]:
    capabilities: dict[str, str] = {}
    if path.endswith(".py"):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return {f"{path}::parse_error": "unknown"}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if isinstance(node, ast.ClassDef) or not node.name.startswith("_"):
                    capabilities[f"{path}::public_symbol:{node.name}"] = "public_symbol"
                if node.name.startswith("test_"):
                    capabilities[f"{path}::test:{node.name}"] = "test"
            if not isinstance(node, ast.Call) or not isinstance(
                node.func, ast.Attribute
            ):
                continue
            if node.func.attr != "add_parser" or not node.args:
                continue
            argument = node.args[0]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                capabilities[f"{path}::command:{argument.value}"] = "command"
    if PurePosixPath(path).name == "Makefile":
        for target in re.findall(r"^([A-Za-z0-9_.-]+)\s*:(?!=)", source, re.MULTILINE):
            if not target.startswith("."):
                capabilities[f"{path}::release:{target}"] = "release"
    if path.endswith(".toml"):
        try:
            parsed = tomllib.loads(source)
        except tomllib.TOMLDecodeError:
            return {**capabilities, f"{path}::parse_error": "unknown"}

        def walk(prefix: str, value: object) -> None:
            if isinstance(value, dict):
                for key, child in value.items():
                    walk(f"{prefix}.{key}" if prefix else str(key), child)
            else:
                capabilities[f"{path}::config:{prefix}"] = "config"

        walk("", parsed)
    if path.endswith((".sh", ".zsh")):
        for name in re.findall(
            r"^([A-Za-z_][A-Za-z0-9_-]*)\s*\(\)\s*\{", source, re.MULTILINE
        ):
            if not name.startswith("_"):
                capabilities[f"{path}::command:{name}"] = "command"
    return capabilities


def inventory_tree(root: str | Path, ref: str) -> dict[str, str]:
    repo = Path(root).resolve()
    paths = _git_lines(repo, "ls-tree", "-r", "--name-only", ref)
    inventory = {
        path: kind for path in paths if (kind := capability_kind(path)) is not None
    }
    for path in paths:
        if (
            not path.endswith((".py", ".toml", ".sh", ".zsh"))
            and PurePosixPath(path).name != "Makefile"
        ):
            continue
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            inventory.update(_source_capabilities(path, result.stdout))
    return inventory


def inventory_live(root: str | Path) -> dict[str, str]:
    repo = Path(root).resolve()
    paths = _git_lines(repo, "ls-files")
    inventory = {
        path: kind for path in paths if (kind := capability_kind(path)) is not None
    }
    for path in paths:
        if (
            not path.endswith((".py", ".toml", ".sh", ".zsh"))
            and PurePosixPath(path).name != "Makefile"
        ):
            continue
        target = repo / path
        try:
            source = target.read_text(encoding="utf-8")
        except OSError:
            continue
        inventory.update(_source_capabilities(path, source))
    return inventory


def capability_delta(
    root: str | Path,
    authority_ref: str,
    *,
    classifications: Mapping[str, Mapping[str, str]] | None = None,
) -> tuple[CapabilityDelta, ...]:
    authority = inventory_tree(root, authority_ref)
    live = inventory_live(root)
    provided = classifications or {}
    losses: list[CapabilityDelta] = []
    for identity, kind in sorted(authority.items()):
        if identity in live:
            continue
        declaration = provided.get(identity, {})
        raw_classification = str(declaration.get("classification") or "unknown")
        try:
            classification = CapabilityClassification(raw_classification)
        except ValueError:
            classification = CapabilityClassification.UNKNOWN
        losses.append(
            CapabilityDelta(
                kind=kind,
                identity=identity,
                authority_evidence=f"{authority_ref}:{identity}",
                classification=classification,
                classification_evidence=str(declaration.get("evidence") or ""),
            )
        )
    return tuple(losses)


def public_python_symbols(source: str) -> tuple[str, ...]:
    """Small, deterministic v1 inventory for exported top-level definitions."""
    pattern = re.compile(r"^(?:class|def)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
    return tuple(
        sorted(name for name in pattern.findall(source) if not name.startswith("_"))
    )
