"""Tests for gemini_chat tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_chat_creates_session_on_first_call(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.return_value = SimpleNamespace(text="hello back")
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    result = server.gemini_chat.fn(session_id="s1", message="hi")

    mock_genai_client.chats.create.assert_called_once()
    assert result["response"] == "hello back"
    assert result["turn"] == 1
    assert "s1" in server._sessions


def test_chat_reuses_existing_session(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.side_effect = [
        SimpleNamespace(text="reply 1"),
        SimpleNamespace(text="reply 2"),
    ]
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    server.gemini_chat.fn(session_id="s2", message="msg 1")
    result2 = server.gemini_chat.fn(session_id="s2", message="msg 2")

    assert mock_genai_client.chats.create.call_count == 1
    assert chat_mock.send_message.call_count == 2
    assert result2["response"] == "reply 2"
    assert result2["turn"] == 2


def test_chat_passes_system_instruction_on_first_turn(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.return_value = SimpleNamespace(text="ok")
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    server.gemini_chat.fn(
        session_id="s3", message="hi", system_instruction="be formal"
    )

    create_kwargs = mock_genai_client.chats.create.call_args.kwargs
    config = create_kwargs["config"]
    assert config.system_instruction == "be formal"


def test_chat_wraps_errors(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.side_effect = RuntimeError("chat down")
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    result = server.gemini_chat.fn(session_id="s4", message="hi")

    assert result == {"error": "chat down", "model": "gemini-3.8-flash"}
