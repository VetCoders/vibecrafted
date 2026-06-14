from __future__ import annotations

from vibecrafted_core.agent_stream import AgentStreamParser, resolve_default_model


def test_agent_stream_parser_extracts_claude_session_usage_cost_and_text() -> None:
    parser = AgentStreamParser("claude")

    rendered = [
        parser.feed_line(
            b'{"type":"system","subtype":"init","session_id":"claude-sess",'
            b'"model":"claude-opus-4-8"}\n'
        ),
        parser.feed_line(
            b'{"type":"stream_event","event":{"type":"content_block_delta",'
            b'"delta":{"type":"text_delta","text":"hello"}}}\n'
        ),
        parser.feed_line(
            b'{"type":"result","result":"done","usage":{"input_tokens":10,'
            b'"cache_read_input_tokens":3,"output_tokens":5},'
            b'"total_cost_usd":0.0123}\n'
        ),
    ]

    assert "session: claude-sess" in "".join(rendered)
    assert "model: claude-opus-4-8" in "".join(rendered)
    assert "hello" in "".join(rendered)
    assert parser.session_id == "claude-sess"
    assert parser.model_id == "claude-opus-4-8"
    assert parser.tokens_input == 10
    assert parser.tokens_cached_input == 3
    assert parser.tokens_output == 5
    assert parser.cost_usd == 0.0123


def test_agent_stream_parser_extracts_codex_thread_usage_and_text() -> None:
    parser = AgentStreamParser("codex")
    parser.model_id = "gpt-5.3-codex"

    rendered = [
        parser.feed_line(b'{"type":"thread.started","thread_id":"codex-thread"}\n'),
        parser.feed_line(
            b'{"type":"item.completed","item":{"type":"agent_message",'
            b'"text":"codex body"}}\n'
        ),
        parser.feed_line(
            b'{"type":"turn.completed","usage":{"input_tokens":11,'
            b'"cached_input_tokens":4,"output_tokens":6}}\n'
        ),
    ]

    text = "".join(rendered)
    assert "session: codex-thread" in text
    assert "model: gpt-5.3-codex" in text
    assert "codex body" in text
    assert parser.session_id == "codex-thread"
    assert parser.model_id == "gpt-5.3-codex"
    assert parser.tokens_input == 11
    assert parser.tokens_cached_input == 4
    assert parser.tokens_output == 6


def test_agent_stream_parser_extracts_gemini_session_stats_and_text() -> None:
    parser = AgentStreamParser("gemini")

    rendered = [
        parser.feed_line(
            b'{"type":"init","session_id":"gem-sess","model":"gemini-pro"}\n'
        ),
        parser.feed_line(b'{"type":"gemini","content":"gemini body"}\n'),
        parser.feed_line(
            b'{"type":"result","status":"done","stats":{"input_tokens":12,'
            b'"output_tokens":7,"duration_ms":42}}\n'
        ),
    ]

    text = "".join(rendered)
    assert "session: gem-sess" in text
    assert "model: gemini-pro" in text
    assert "gemini body" in text
    assert parser.session_id == "gem-sess"
    assert parser.model_id == "gemini-pro"
    assert parser.tokens_input == 12
    assert parser.tokens_output == 7


def test_agent_stream_parser_treats_agy_as_claude_family_text_stream() -> None:
    parser = AgentStreamParser("agy")

    assert parser.feed_line(b"[12:00:00] session: agy-sess\n") == (
        "[12:00:00] session: agy-sess\n"
    )
    assert parser.feed_line(b"[12:00:00] model: agy-pro\n") == (
        "[12:00:00] model: agy-pro\n"
    )
    assert parser.feed_line(b"[12:00:01] tokens: 20 in (8 cached) / 9 out\n") == (
        "[12:00:01] tokens: 20 in (8 cached) / 9 out\n"
    )
    assert parser.session_id == "agy-sess"
    assert parser.model_id == "agy-pro"
    assert parser.resume_command("/repo") == "cd /repo && agy --conversation agy-sess"
    assert parser.tokens_input == 20
    assert parser.tokens_cached_input == 8
    assert parser.tokens_output == 9


def test_resolve_default_model_reads_codex_config(tmp_path, monkeypatch) -> None:
    codex_home = tmp_path / ".codex"
    codex_home.mkdir()
    (codex_home / "config.toml").write_text('model = "gpt-5.5"\n', encoding="utf-8")
    monkeypatch.delenv("CODEX_MODEL", raising=False)

    assert (
        resolve_default_model("codex", env={"CODEX_HOME": str(codex_home)}) == "gpt-5.5"
    )
    assert (
        resolve_default_model(
            "codex",
            command=["codex", "exec", "--model", "gpt-5.3-codex", "-"],
            env={"CODEX_HOME": str(codex_home)},
        )
        == "gpt-5.3-codex"
    )
