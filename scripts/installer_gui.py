#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from textwrap import dedent
from typing import Any
from urllib.parse import urlparse

try:
    from installer_brand import PRODUCT_LINE, TAGLINE, VAPOR_HEADER
    from installer_tui import (
        CATEGORY_LABELS,
        helper_layer_path,
        read_framework_version,
        run_diagnostics,
        start_here_path,
        summarize_diagnostics,
    )
    from runtime_paths import vibecrafted_home
except ModuleNotFoundError:  # pragma: no cover - depends on entrypoint
    from scripts.installer_brand import PRODUCT_LINE, TAGLINE, VAPOR_HEADER
    from scripts.installer_tui import (
        CATEGORY_LABELS,
        helper_layer_path,
        read_framework_version,
        run_diagnostics,
        start_here_path,
        summarize_diagnostics,
    )
    from scripts.runtime_paths import vibecrafted_home


OUTPUT_TAIL_LIMIT = 120


def default_source_dir() -> str:
    return str(Path(__file__).resolve().parent.parent)


def installer_script_path(source_dir: str) -> Path:
    return Path(source_dir).resolve() / "scripts" / "vetcoders_install.py"


def foundations_script_path(source_dir: str) -> Path:
    return Path(source_dir).resolve() / "scripts" / "install-foundations.sh"


def build_install_command(source_dir: str, *, with_shell: bool) -> list[str]:
    installer_path = installer_script_path(source_dir)
    if not installer_path.exists():
        raise FileNotFoundError(f"Installer not found at {installer_path}")
    command = [
        sys.executable,
        str(installer_path),
        "install",
        "--source",
        str(Path(source_dir).resolve()),
        "--compact",
        "--non-interactive",
    ]
    if with_shell:
        command.append("--with-shell")
    return command


@dataclass(frozen=True)
class InstallStep:
    label: str
    command: list[str]


def build_install_steps(source_dir: str, *, with_shell: bool) -> list[InstallStep]:
    steps: list[InstallStep] = []
    foundations_path = foundations_script_path(source_dir)
    if foundations_path.exists():
        steps.append(
            InstallStep(
                label="Bootstrap foundations",
                command=["bash", str(foundations_path)],
            )
        )

    steps.append(
        InstallStep(
            label="Install Vibecrafted",
            command=build_install_command(source_dir, with_shell=with_shell),
        )
    )
    return steps


def install_runtime_env(base_env: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(os.environ if base_env is None else base_env)
    path_entries = env.get("PATH", "").split(os.pathsep) if env.get("PATH") else []

    candidates = [
        vibecrafted_home() / "bin",
        vibecrafted_home() / "tools" / "node" / "bin",
        Path.home() / ".cargo" / "bin",
    ]
    for candidate in candidates:
        candidate_str = str(candidate)
        if candidate.is_dir() and candidate_str not in path_entries:
            path_entries.insert(0, candidate_str)

    env["PATH"] = os.pathsep.join(path_entries)
    return env


def _trim_home(value: str) -> str:
    home = str(Path.home())
    if value.startswith(home):
        return value.replace(home, "~", 1)
    return value


def _open_target(target: str) -> bool:
    if sys.platform == "darwin" and shutil.which("open"):
        subprocess.Popen(
            ["open", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    if sys.platform.startswith("linux") and shutil.which("xdg-open"):
        subprocess.Popen(
            ["xdg-open", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    return webbrowser.open(target)


@dataclass
class InstallRun:
    command: list[str] = field(default_factory=list)
    plan: list[list[str]] = field(default_factory=list)
    output: list[str] = field(default_factory=list)
    with_shell: bool = True
    running: bool = False
    completed: bool = False
    exit_code: int | None = None
    error: str | None = None
    current_stage: str | None = None
    started_at: float | None = None
    finished_at: float | None = None


class InstallController:
    def __init__(self, source_dir: str) -> None:
        self.source_dir = str(Path(source_dir).resolve())
        self.version = read_framework_version(self.source_dir)
        self.diagnostics = run_diagnostics()
        self.found_items, self.missing_items, self.needs_install = (
            summarize_diagnostics(self.diagnostics)
        )
        self._lock = threading.Lock()
        self._run = InstallRun()

    def _category_cards(self) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        for key, label in CATEGORY_LABELS.items():
            entries = []
            present = 0
            for name, entry in self.diagnostics.get(key, {}).items():
                found = bool(entry.get("found"))
                if found:
                    present += 1
                entries.append(
                    {
                        "name": name,
                        "label": entry.get("label", name),
                        "found": found,
                        "detail": entry.get("detail", ""),
                    }
                )
            cards.append(
                {
                    "key": key,
                    "label": label,
                    "present": present,
                    "total": len(entries),
                    "items": entries,
                }
            )
        return cards

    def preflight_payload(self) -> dict[str, Any]:
        return {
            "brand": {
                "header": VAPOR_HEADER,
                "tagline": TAGLINE,
                "product_line": PRODUCT_LINE,
            },
            "version": self.version,
            "source_dir": self.source_dir,
            "source_dir_display": _trim_home(self.source_dir),
            "guide_path": str(start_here_path()),
            "guide_path_display": _trim_home(str(start_here_path())),
            "helper_path": str(helper_layer_path()),
            "helper_path_display": _trim_home(str(helper_layer_path())),
            "found_count": len(self.found_items),
            "missing_count": len(self.missing_items),
            "needs_install": self.needs_install,
            "categories": self._category_cards(),
            "status": self.status_payload(),
        }

    def status_payload(self) -> dict[str, Any]:
        with self._lock:
            output_tail = self._run.output[-OUTPUT_TAIL_LIMIT:]
            plan = self._run.plan or ([self._run.command] if self._run.command else [])
            return {
                "command": self._run.command,
                "plan": plan,
                "command_display": " && ".join(" ".join(step) for step in plan),
                "with_shell": self._run.with_shell,
                "running": self._run.running,
                "completed": self._run.completed,
                "exit_code": self._run.exit_code,
                "error": self._run.error,
                "current_stage": self._run.current_stage,
                "output": output_tail,
                "output_line_count": len(self._run.output),
                "started_at": self._run.started_at,
                "finished_at": self._run.finished_at,
            }

    def start(self, *, with_shell: bool) -> tuple[bool, str]:
        try:
            steps = build_install_steps(self.source_dir, with_shell=with_shell)
        except FileNotFoundError as exc:
            with self._lock:
                self._run = InstallRun(
                    command=[],
                    plan=[],
                    with_shell=with_shell,
                    running=False,
                    completed=True,
                    exit_code=-1,
                    error=str(exc),
                    current_stage=None,
                    finished_at=time.time(),
                )
            return False, str(exc)

        with self._lock:
            if self._run.running:
                return False, "Installation is already running."
            self._run = InstallRun(
                command=steps[-1].command,
                plan=[step.command for step in steps],
                with_shell=with_shell,
                running=True,
                completed=False,
                exit_code=None,
                error=None,
                output=[],
                current_stage=steps[0].label,
                started_at=time.time(),
            )

        worker = threading.Thread(
            target=self._worker,
            args=(steps,),
            daemon=True,
            name="installer-gui-worker",
        )
        worker.start()
        return True, "Installer started."

    def _append_output(self, line: str) -> None:
        with self._lock:
            self._run.output.append(line)

    def _worker(self, steps: list[InstallStep]) -> None:
        exit_code = 0
        error: str | None = None
        env = install_runtime_env()
        try:
            for step in steps:
                with self._lock:
                    self._run.current_stage = step.label
                self._append_output(f"[stage] {step.label}")
                self._append_output(f"$ {' '.join(step.command)}")
                process = subprocess.Popen(
                    step.command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    env=env,
                )
                assert process.stdout is not None
                for raw_line in process.stdout:
                    self._append_output(raw_line.rstrip("\n"))
                exit_code = process.wait()
                if exit_code != 0:
                    break
                env = install_runtime_env(env)
        except Exception as exc:  # pragma: no cover - defensive path
            error = str(exc)
            exit_code = -1

        with self._lock:
            self._run.running = False
            self._run.completed = True
            self._run.exit_code = exit_code
            self._run.error = error
            self._run.finished_at = time.time()

    def open_start_here(self) -> tuple[bool, str]:
        guide = start_here_path()
        if not guide.exists():
            return False, f"Guide not found at {guide}"
        if not _open_target(str(guide)):
            return False, f"Could not open {guide}"
        return True, f"Opened {_trim_home(str(guide))}"


class InstallerHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        controller: InstallController,
    ) -> None:
        super().__init__(server_address, InstallerRequestHandler)
        self.controller = controller


class InstallerRequestHandler(BaseHTTPRequestHandler):
    server: InstallerHTTPServer

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send_html(build_html(self.server.controller.preflight_payload()))
            return
        if parsed.path == "/api/preflight":
            self._send_json(self.server.controller.preflight_payload())
            return
        if parsed.path == "/api/install/status":
            self._send_json(self.server.controller.status_payload())
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/install":
            payload = self._read_json()
            accepted, message = self.server.controller.start(
                with_shell=bool(payload.get("with_shell", True))
            )
            status_payload = self.server.controller.status_payload()
            status_payload["accepted"] = accepted
            status_payload["message"] = message
            status = HTTPStatus.ACCEPTED if accepted else HTTPStatus.CONFLICT
            if status_payload.get("error") and not status_payload.get("running"):
                status = HTTPStatus.BAD_REQUEST
            self._send_json(status_payload, status=status)
            return
        if parsed.path == "/api/open-start-here":
            ok, message = self.server.controller.open_start_here()
            self._send_json(
                {"ok": ok, "message": message},
                status=HTTPStatus.OK if ok else HTTPStatus.BAD_REQUEST,
            )
            return
        self._send_json({"error": "Not found"}, status=HTTPStatus.NOT_FOUND)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length)
        if not raw:
            return {}
        return json.loads(raw.decode("utf-8"))

    def _send_html(self, payload: str, *, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = payload.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_json(
        self, payload: dict[str, Any], *, status: HTTPStatus = HTTPStatus.OK
    ) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def build_html(preflight: dict[str, Any]) -> str:
    boot_json = json.dumps(preflight).replace("</", "<\\/")
    template = dedent(
        """\
        <!doctype html>
        <html lang="en">
          <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <title>Vibecrafted Guided Installer</title>
            <style>
              :root {
                --bg: #0f1318;
                --bg-glow: rgba(196, 140, 95, 0.24);
                --panel: rgba(18, 24, 31, 0.88);
                --panel-strong: rgba(25, 32, 41, 0.96);
                --border: rgba(196, 140, 95, 0.26);
                --copper: #d79a63;
                --patina: #88a2a0;
                --text: #eef2f3;
                --muted: #9fb0b5;
                --ok: #84d59a;
                --warn: #f0c36e;
                --fail: #f48c7f;
                --shadow: 0 28px 80px rgba(0, 0, 0, 0.35);
              }

              * { box-sizing: border-box; }

              body {
                margin: 0;
                min-height: 100vh;
                background:
                  radial-gradient(circle at top, var(--bg-glow), transparent 38%),
                  linear-gradient(180deg, #10161d 0%, #0b1015 100%);
                color: var(--text);
                font-family: "SF Mono", "JetBrains Mono", "IBM Plex Mono", monospace;
              }

              a {
                color: inherit;
              }

              .shell {
                width: min(1180px, calc(100vw - 32px));
                margin: 24px auto;
                padding: 28px;
                border: 1px solid rgba(255, 255, 255, 0.06);
                border-radius: 28px;
                background: rgba(8, 11, 16, 0.76);
                box-shadow: var(--shadow);
                backdrop-filter: blur(18px);
              }

              .hero {
                display: grid;
                gap: 18px;
                grid-template-columns: minmax(0, 1.4fr) minmax(280px, 0.9fr);
                align-items: stretch;
                margin-bottom: 24px;
              }

              .hero-copy,
              .hero-side,
              .panel {
                padding: 24px;
                border: 1px solid var(--border);
                border-radius: 24px;
                background: var(--panel);
              }

              .eyebrow {
                color: var(--patina);
                letter-spacing: 0.14em;
                text-transform: uppercase;
                font-size: 12px;
              }

              h1 {
                margin: 10px 0 14px;
                font-size: clamp(34px, 6vw, 58px);
                line-height: 0.92;
                letter-spacing: -0.06em;
              }

              .hero-brand {
                color: var(--copper);
                display: block;
                font-size: clamp(18px, 3vw, 24px);
                letter-spacing: 0.08em;
                text-transform: uppercase;
              }

              .hero-lead {
                margin: 0;
                font-size: 17px;
                line-height: 1.65;
                color: var(--muted);
                max-width: 58ch;
              }

              .hero-list,
              .stats,
              .category-items,
              .steps,
              .next-steps {
                margin: 0;
                padding: 0;
                list-style: none;
              }

              .hero-list {
                display: grid;
                gap: 8px;
                margin-top: 18px;
              }

              .hero-list li::before,
              .next-steps li::before {
                content: ">";
                color: var(--copper);
                margin-right: 10px;
              }

              .hero-side {
                display: grid;
                gap: 16px;
                align-content: start;
                background:
                  linear-gradient(180deg, rgba(196, 140, 95, 0.11), transparent 70%),
                  var(--panel-strong);
              }

              .stats {
                display: grid;
                gap: 12px;
              }

              .stats li {
                display: flex;
                justify-content: space-between;
                gap: 16px;
                padding-bottom: 12px;
                border-bottom: 1px solid rgba(255, 255, 255, 0.08);
                color: var(--muted);
              }

              .stats strong {
                color: var(--text);
                font-size: 19px;
              }

              .page-grid {
                display: grid;
                gap: 20px;
                grid-template-columns: minmax(0, 1.35fr) minmax(320px, 0.95fr);
              }

              .section-title {
                margin: 0 0 8px;
                font-size: 20px;
              }

              .section-copy,
              .status-text,
              .guide-feedback,
              .panel-copy {
                color: var(--muted);
                line-height: 1.6;
                margin: 0;
              }

              .steps {
                display: grid;
                gap: 14px;
                margin-top: 18px;
              }

              .steps li {
                padding: 14px 16px;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.07);
                background: rgba(255, 255, 255, 0.02);
              }

              .steps strong {
                display: block;
                color: var(--text);
                margin-bottom: 6px;
              }

              .category-grid {
                display: grid;
                gap: 14px;
                margin-top: 18px;
              }

              .category-card {
                border: 1px solid rgba(255, 255, 255, 0.07);
                border-radius: 18px;
                padding: 16px;
                background: rgba(255, 255, 255, 0.02);
              }

              .category-head {
                display: flex;
                justify-content: space-between;
                gap: 16px;
                align-items: baseline;
                margin-bottom: 10px;
              }

              .category-head span:last-child {
                color: var(--patina);
              }

              .category-items {
                display: grid;
                gap: 8px;
              }

              .category-items li {
                display: grid;
                gap: 4px;
                padding: 10px 12px;
                border-radius: 14px;
                background: rgba(0, 0, 0, 0.16);
              }

              .item-line {
                display: flex;
                justify-content: space-between;
                gap: 12px;
              }

              .item-detail {
                color: var(--muted);
                font-size: 13px;
                word-break: break-word;
              }

              .chip {
                display: inline-flex;
                align-items: center;
                gap: 8px;
                border-radius: 999px;
                padding: 8px 12px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                color: var(--muted);
                background: rgba(255, 255, 255, 0.03);
              }

              .chip.ok { color: var(--ok); }
              .chip.warn { color: var(--warn); }
              .chip.fail { color: var(--fail); }

              .install-form {
                display: grid;
                gap: 14px;
                margin-top: 18px;
              }

              .toggle {
                display: flex;
                gap: 12px;
                align-items: flex-start;
                padding: 14px 16px;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.07);
                background: rgba(255, 255, 255, 0.02);
              }

              .toggle input {
                margin-top: 2px;
              }

              .button-row {
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
              }

              button {
                border: 0;
                border-radius: 999px;
                padding: 12px 18px;
                font: inherit;
                cursor: pointer;
                transition: transform 120ms ease, opacity 120ms ease;
              }

              button:hover {
                transform: translateY(-1px);
              }

              button:disabled {
                cursor: not-allowed;
                opacity: 0.65;
                transform: none;
              }

              .primary {
                background: linear-gradient(135deg, #d79a63 0%, #e8b98d 100%);
                color: #21160e;
                font-weight: 700;
              }

              .secondary {
                background: rgba(255, 255, 255, 0.06);
                color: var(--text);
                border: 1px solid rgba(255, 255, 255, 0.1);
              }

              .status-block {
                display: grid;
                gap: 12px;
              }

              .command-box,
              .log-box {
                margin-top: 14px;
                padding: 16px;
                border-radius: 18px;
                border: 1px solid rgba(255, 255, 255, 0.07);
                background: rgba(6, 9, 13, 0.82);
                color: var(--muted);
                overflow: auto;
              }

              .command-box code,
              .log-box code,
              .log-box pre {
                margin: 0;
                white-space: pre-wrap;
                word-break: break-word;
                font: inherit;
              }

              .log-meta {
                display: flex;
                justify-content: space-between;
                gap: 12px;
                align-items: center;
                margin-top: 14px;
                color: var(--muted);
                font-size: 13px;
              }

              .success-panel {
                margin-top: 16px;
                padding: 18px;
                border-radius: 18px;
                border: 1px solid rgba(132, 213, 154, 0.28);
                background: rgba(132, 213, 154, 0.08);
              }

              .success-panel[hidden] {
                display: none;
              }

              .next-steps {
                display: grid;
                gap: 8px;
                margin-top: 12px;
              }

              .footer-note {
                margin-top: 24px;
                padding-top: 16px;
                border-top: 1px solid rgba(255, 255, 255, 0.08);
                color: var(--muted);
                font-size: 13px;
              }

              @media (max-width: 960px) {
                .hero,
                .page-grid {
                  grid-template-columns: 1fr;
                }
              }
            </style>
          </head>
          <body>
            <div class="shell">
              <section class="hero">
                <article class="hero-copy">
                  <div class="eyebrow">Guided install</div>
                  <h1>
                    <span class="hero-brand">%%HEADER%%</span>
                    Ship AI-built software without the vibe hangover
                  </h1>
                  <p class="hero-lead">
                    The release engine for AI-built software. This guided installer keeps the real install
                    contract intact, but gives founders and operators a calmer front door than raw terminal prompts.
                  </p>
                  <ul class="hero-list">
                    <li>See the runtime truth before touching the machine.</li>
                    <li>Bootstrap required foundations, then run the same compact installer used by automation.</li>
                    <li>Leave with a readable START_HERE guide and a clean command deck.</li>
                  </ul>
                </article>
                <aside class="hero-side">
                  <div class="eyebrow">Current surface</div>
                  <ul class="stats">
                    <li><span>Framework</span><strong id="version-value"></strong></li>
                    <li><span>Source</span><strong id="source-value"></strong></li>
                    <li><span>Guide</span><strong id="guide-value"></strong></li>
                    <li><span>Helpers</span><strong id="helper-value"></strong></li>
                  </ul>
                  <p class="panel-copy">%%TAGLINE%%</p>
                  <p class="panel-copy">%%PRODUCT_LINE%%</p>
                </aside>
              </section>

              <section class="page-grid">
                <article class="panel">
                  <h2 class="section-title">What this path does</h2>
                  <p class="section-copy">
                    This GUI is intentionally thin. It does not invent a parallel installer; it wraps the repo-owned
                    foundation bootstrap plus the compact flow, streams the real log, and keeps the launch-ready
                    onboarding surface aligned with what the product actually promises.
                  </p>
                  <ol class="steps">
                    <li>
                      <strong>1. Inspect the machine</strong>
                      Framework views, required foundations, toolchains, and agent CLIs are checked before install.
                    </li>
                    <li>
                      <strong>2. Choose the helper surface</strong>
                      Shell helpers stay optional. The core `vibecrafted ...` command deck works either way.
                    </li>
                    <li>
                      <strong>3. Bootstrap foundations</strong>
                      The browser path installs the repo-owned foundation layer first, so aicx, loctree, and friends are not skipped.
                    </li>
                    <li>
                      <strong>4. Run the same install truth</strong>
                      The browser path then launches `vetcoders_install.py --compact --non-interactive` and streams its output.
                    </li>
                  </ol>

                  <div class="category-grid" id="category-grid"></div>
                </article>

                <article class="panel">
                  <h2 class="section-title">Start install</h2>
                  <p class="section-copy">
                    Recommended for onboarding founders, PMs, or teammates who should trust the path before they start
                    memorizing commands.
                  </p>
                  <form class="install-form" id="install-form">
                    <label class="toggle" for="with-shell">
                      <input checked id="with-shell" name="with-shell" type="checkbox">
                      <span>
                        <strong>Install shell helpers</strong><br>
                        Add the optional helper layer so `vc-*` wrappers and the command deck are available in future sessions.
                      </span>
                    </label>
                    <div class="button-row">
                      <button class="primary" id="install-button" type="submit">Launch guided install</button>
                      <button class="secondary" id="open-guide-button" type="button">Open START_HERE</button>
                    </div>
                  </form>
                  <div class="status-block">
                    <div class="chip" id="status-chip">Waiting for approval</div>
                    <p class="status-text" id="status-text">
                      Review the preflight cards, then start the install when the machine shape looks right.
                    </p>
                    <p class="guide-feedback" id="guide-feedback"></p>
                  </div>

                  <div class="command-box">
                    <code id="command-line">Install command will appear here.</code>
                  </div>

                  <div class="log-box">
                    <pre id="log-output">No install has run yet.</pre>
                  </div>

                  <div class="log-meta">
                    <span id="log-lines">0 lines captured</span>
                    <span id="status-meta">Compact mode, repo-owned installer truth.</span>
                  </div>

                  <section class="success-panel" hidden id="success-panel">
                    <strong>Install finished.</strong>
                    <p class="panel-copy">
                      Use the guide for the plain-language onboarding path, then run the command deck where the real work begins.
                    </p>
                    <ul class="next-steps">
                      <li><code>vibecrafted help</code></li>
                      <li><code>vibecrafted doctor</code></li>
                      <li><code>vibecrafted init claude</code></li>
                    </ul>
                  </section>
                </article>
              </section>

              <p class="footer-note">
                Browser surface by design. If you are scripting installs or running CI, stay on the direct terminal path.
              </p>
            </div>

            <script>
              window.__BOOT__ = %%BOOT%%;
            </script>
            <script>
              const boot = window.__BOOT__;
              const dom = {
                version: document.getElementById('version-value'),
                source: document.getElementById('source-value'),
                guide: document.getElementById('guide-value'),
                helper: document.getElementById('helper-value'),
                categoryGrid: document.getElementById('category-grid'),
                installForm: document.getElementById('install-form'),
                withShell: document.getElementById('with-shell'),
                installButton: document.getElementById('install-button'),
                openGuideButton: document.getElementById('open-guide-button'),
                statusChip: document.getElementById('status-chip'),
                statusText: document.getElementById('status-text'),
                guideFeedback: document.getElementById('guide-feedback'),
                commandLine: document.getElementById('command-line'),
                logOutput: document.getElementById('log-output'),
                logLines: document.getElementById('log-lines'),
                statusMeta: document.getElementById('status-meta'),
                successPanel: document.getElementById('success-panel'),
              };

              let pollTimer = null;

              function escapeHtml(value) {
                return String(value)
                  .replaceAll('&', '&amp;')
                  .replaceAll('<', '&lt;')
                  .replaceAll('>', '&gt;')
                  .replaceAll('"', '&quot;')
                  .replaceAll("'", '&#39;');
              }

              function statusClass(found) {
                if (found) return 'chip ok';
                return 'chip warn';
              }

              function renderBoot() {
                dom.version.textContent = boot.version;
                dom.source.textContent = boot.source_dir_display;
                dom.guide.textContent = boot.guide_path_display;
                dom.helper.textContent = boot.helper_path_display;
                dom.openGuideButton.disabled = false;

                dom.categoryGrid.innerHTML = boot.categories.map((category) => {
                  const items = category.items.map((item) => `
                    <li>
                      <div class="item-line">
                        <span>${escapeHtml(item.label)}</span>
                        <span class="${statusClass(item.found)}">${item.found ? 'ready' : 'missing'}</span>
                      </div>
                      <div class="item-detail">${escapeHtml(item.detail)}</div>
                    </li>
                  `).join('');
                  return `
                    <section class="category-card">
                      <div class="category-head">
                        <strong>${escapeHtml(category.label)}</strong>
                        <span>${category.present}/${category.total}</span>
                      </div>
                      <ul class="category-items">${items}</ul>
                    </section>
                  `;
                }).join('');

                renderStatus(boot.status);
              }

              function renderStatus(status) {
                const commandDisplay = status.command_display || 'Install command will appear here.';
                dom.commandLine.textContent = commandDisplay;
                dom.logOutput.textContent = status.output && status.output.length
                  ? status.output.join('\\n')
                  : 'No install has run yet.';
                dom.logLines.textContent = `${status.output_line_count || 0} lines captured`;

                if (status.running) {
                  dom.installButton.disabled = true;
                  dom.withShell.disabled = true;
                  dom.statusChip.className = 'chip warn';
                  dom.statusChip.textContent = 'Installing';
                  const stage = status.current_stage ? `${status.current_stage} is running now.` : 'The guided install is running now.';
                  dom.statusText.textContent = `${stage} You can leave this window open and watch the live log.`;
                  dom.statusMeta.textContent = 'Streaming repo-owned foundations + compact installer output.';
                  dom.successPanel.hidden = true;
                  return;
                }

                dom.installButton.disabled = false;
                dom.withShell.disabled = false;

                if (status.completed && status.exit_code === 0) {
                  dom.statusChip.className = 'chip ok';
                  dom.statusChip.textContent = 'Install complete';
                  dom.statusText.textContent = 'The guided path finished cleanly. Use START_HERE for the plain-language path, then switch to the command deck.';
                  dom.statusMeta.textContent = 'Foundations and installer exited cleanly.';
                  dom.successPanel.hidden = false;
                  return;
                }

                if (status.completed) {
                  dom.statusChip.className = 'chip fail';
                  dom.statusChip.textContent = 'Needs attention';
                  dom.statusText.textContent = status.error || `Installer exited with code ${status.exit_code}. Review the log above before retrying.`;
                  dom.statusMeta.textContent = 'The guided shell stayed up so you can inspect the failure.';
                  dom.successPanel.hidden = true;
                  return;
                }

                dom.statusChip.className = 'chip';
                dom.statusChip.textContent = 'Waiting for approval';
                dom.statusText.textContent = 'Review the preflight cards, then start the install when the machine shape looks right.';
                dom.statusMeta.textContent = 'Guided foundations + compact mode, repo-owned installer truth.';
                dom.successPanel.hidden = true;
              }

              async function fetchStatus() {
                const response = await fetch('/api/install/status', { cache: 'no-store' });
                if (!response.ok) {
                  throw new Error('Could not fetch install status');
                }
                return response.json();
              }

              async function pollStatus() {
                try {
                  const status = await fetchStatus();
                  renderStatus(status);
                  if (status.running) {
                    pollTimer = window.setTimeout(pollStatus, 700);
                  }
                } catch (error) {
                  dom.statusChip.className = 'chip fail';
                  dom.statusChip.textContent = 'Connection issue';
                  dom.statusText.textContent = error.message;
                }
              }

              dom.installForm.addEventListener('submit', async (event) => {
                event.preventDefault();
                if (pollTimer) {
                  window.clearTimeout(pollTimer);
                }
                dom.guideFeedback.textContent = '';
                const response = await fetch('/api/install', {
                  method: 'POST',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ with_shell: dom.withShell.checked }),
                });
                const payload = await response.json();
                renderStatus(payload);
                if (payload.message) {
                  dom.guideFeedback.textContent = payload.message;
                }
                if (payload.running) {
                  pollStatus();
                }
              });

              dom.openGuideButton.addEventListener('click', async () => {
                const response = await fetch('/api/open-start-here', { method: 'POST' });
                const payload = await response.json();
                dom.guideFeedback.textContent = payload.message || '';
              });

              renderBoot();
              pollStatus();
            </script>
          </body>
        </html>
        """
    )
    return (
        template.replace("%%BOOT%%", boot_json)
        .replace("%%HEADER%%", VAPOR_HEADER)
        .replace("%%TAGLINE%%", TAGLINE)
        .replace("%%PRODUCT_LINE%%", PRODUCT_LINE)
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Launch the browser-based guided installer for Vibecrafted."
    )
    parser.add_argument(
        "--source",
        default=default_source_dir(),
        help="Framework source directory to stage from.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind.")
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="Port to bind. Use 0 for an ephemeral free port.",
    )
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="Start the local server without opening a browser tab.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    controller = InstallController(args.source)
    server = InstallerHTTPServer((args.host, args.port), controller)
    host, port = server.server_address[:2]
    url = f"http://{host}:{port}/"

    print(f"Guided installer ready at {url}")
    print("Press Ctrl-C to stop the local server.")
    if not args.no_open:
        _open_target(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping guided installer.")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    raise SystemExit(main())
