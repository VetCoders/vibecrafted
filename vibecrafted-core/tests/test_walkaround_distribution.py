from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = REPO_ROOT / "vibecrafted-core"
EXPECTED_SPKI = "521ed59d3c446c540afe1557c2dbc39c9c190775f99896b2b65206c32814b25b"


def _run(
    command: list[str], *, cwd: Path = REPO_ROOT
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def test_packaged_public_key_matches_release_lineage() -> None:
    key = PROJECT_ROOT / "vibecrafted_core/trust/vibecrafted-signing-v1.pub"
    result = subprocess.run(
        ["openssl", "pkey", "-pubin", "-in", str(key), "-outform", "DER"],
        check=True,
        capture_output=True,
    )

    assert hashlib.sha256(result.stdout).hexdigest() == EXPECTED_SPKI


@pytest.mark.skipif(
    os.environ.get("VIBECRAFTED_REQUIRE_RELEASE_CREDENTIALS") != "1",
    reason="operator-gated production trust probe",
)
def test_noneditable_wheel_trust_probe_accepts_release_key_and_rejects_attacker(
    tmp_path: Path,
) -> None:
    signing_key = Path.home() / ".keys/vibecrafted-signing.key"
    if not signing_key.is_file():
        pytest.fail("operator-gated release signing key is unavailable")
    uv = shutil.which("uv")
    openssl = shutil.which("openssl")
    assert uv is not None and openssl is not None
    dist = tmp_path / "dist"
    built = _run([uv, "build", "--wheel", "--out-dir", str(dist)], cwd=PROJECT_ROOT)
    assert built.returncode == 0, built.stderr
    wheel = next(dist.glob("vibecrafted-*.whl"))
    venv = tmp_path / "venv"
    created = _run([uv, "venv", str(venv)])
    assert created.returncode == 0, created.stderr
    python = venv / "bin/python"
    installed = _run([uv, "pip", "install", "--python", str(python), str(wheel)])
    assert installed.returncode == 0, installed.stderr
    runner = venv / "bin/verify-vibecrafted-walkaround"
    assert runner.is_file()

    challenge = tmp_path / "challenge.json"
    challenge.write_text(
        json.dumps(
            {
                "domain": "io.vetcoders.vibecrafted.release-trust-probe.v1",
                "nonce": "installed-wheel-authorized",
                "schema": "io.vetcoders.vibecrafted.trust-probe.v1",
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    authorized_signature = tmp_path / "authorized.sig"
    authorized = _run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-sign",
            str(signing_key),
            "-out",
            str(authorized_signature),
            str(challenge),
        ]
    )
    assert authorized.returncode == 0, authorized.stderr
    accepted = _run(
        [str(runner), "trust-probe", str(challenge), str(authorized_signature)]
    )
    assert accepted.returncode == 0, accepted.stderr

    attacker_key = tmp_path / "attacker.pem"
    attacker_signature = tmp_path / "attacker.sig"
    generated = _run(
        [openssl, "genpkey", "-algorithm", "RSA", "-out", str(attacker_key)]
    )
    assert generated.returncode == 0, generated.stderr
    forged = _run(
        [
            openssl,
            "dgst",
            "-sha256",
            "-sign",
            str(attacker_key),
            "-out",
            str(attacker_signature),
            str(challenge),
        ]
    )
    assert forged.returncode == 0, forged.stderr
    rejected = _run(
        [str(runner), "trust-probe", str(challenge), str(attacker_signature)]
    )
    assert rejected.returncode == 33
    assert "VCPC033" in rejected.stderr
