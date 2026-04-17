"""Tests for gemini_list_models tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def test_list_models_returns_entries_with_capabilities(mock_genai_client: MagicMock) -> None:
    fake_model = SimpleNamespace(
        name="models/gemini-2.5-flash",
        supported_actions=["generateContent", "countTokens"],
        input_token_limit=1_000_000,
        output_token_limit=8_192,
    )
    mock_genai_client.models.list.return_value = [fake_model]

    import server

    result = server.gemini_list_models.fn()

    assert isinstance(result, list)
    assert result[0]["name"] == "gemini-2.5-flash"
    assert result[0]["input_token_limit"] == 1_000_000
    assert result[0]["output_token_limit"] == 8_192


def test_list_models_strips_models_prefix(mock_genai_client: MagicMock) -> None:
    fake_model = SimpleNamespace(
        name="models/gemini-3-flash-preview",
        supported_actions=[],
        input_token_limit=0,
        output_token_limit=0,
    )
    mock_genai_client.models.list.return_value = [fake_model]

    import server

    result = server.gemini_list_models.fn()

    assert result[0]["name"] == "gemini-3-flash-preview"


def test_list_models_wraps_sdk_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.list.side_effect = RuntimeError("api down")

    import server

    result = server.gemini_list_models.fn()

    assert isinstance(result, dict)
    assert "error" in result
    assert "api down" in result["error"]
