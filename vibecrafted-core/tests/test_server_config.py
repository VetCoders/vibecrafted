from __future__ import annotations

import stat
from pathlib import Path

import pytest
from vibecrafted_core.server_config import (
    ServerConfig,
    ServerConfigError,
    load_server_config,
    seed_server_config,
)


def test_server_config_defaults_when_file_is_absent(tmp_path: Path) -> None:
    config = load_server_config(tmp_path / "missing.toml")

    assert config.bind_host == "127.0.0.1"
    assert config.port == 3024
    assert config.public_url == "http://127.0.0.1:3024"


def test_seed_server_config_preserves_other_tables_and_existing_owner(
    tmp_path: Path,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text('[runtime]\nhorse = "wezterm"\n', encoding="utf-8")
    path.chmod(0o640)
    tailnet = ServerConfig(
        bind_host="100.82.232.70",
        port=3025,
        public_url="http://100.82.232.70:3025",
    )

    seeded, created = seed_server_config(tailnet, path)
    retained, replaced = seed_server_config(ServerConfig(), path)

    assert created
    assert not replaced
    assert seeded == tailnet
    assert retained == tailnet
    assert '[runtime]\nhorse = "wezterm"' in path.read_text(encoding="utf-8")
    assert stat.S_IMODE(path.stat().st_mode) == 0o640


def test_server_config_keeps_bind_and_public_origin_distinct(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "[server]\n"
        'bind_host = "0.0.0.0"\n'
        "port = 3025\n"
        'public_url = "https://observer.tailnet.example"\n',
        encoding="utf-8",
    )

    config = load_server_config(path)

    assert config.bind_addr == "0.0.0.0:3025"
    assert config.public_url == "https://observer.tailnet.example"


@pytest.mark.parametrize(
    "body, message",
    [
        ("[server]\nport = 0\n", "between 1 and 65535"),
        ("[server]\nport = true\n", "must be an integer"),
        (
            '[server]\npublic_url = "http://user:secret@example.com/path"\n',
            "must be an HTTP",
        ),
        ("[server]\nunknown = 1\n", r"unsupported \[server\] key"),
    ],
)
def test_server_config_rejects_invalid_contract(
    tmp_path: Path,
    body: str,
    message: str,
) -> None:
    path = tmp_path / "config.toml"
    path.write_text(body, encoding="utf-8")

    with pytest.raises(ServerConfigError, match=message):
        load_server_config(path)
