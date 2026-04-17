"""Tests for gemini_generate tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_response(text: str, total_tokens: int = 42) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(total_token_count=total_tokens),
    )


def test_generate_returns_text_and_tokens(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_response("hello world", 11)

    import server

    result = server.gemini_generate.fn(prompt="hi")

    assert result["text"] == "hello world"
    assert result["tokens_used"] == 11
    assert result["model"] == "gemini-2.5-pro"


def test_generate_respects_model_parameter(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_response("ok")

    import server

    result = server.gemini_generate.fn(prompt="hi", model="gemini-2.5-flash")

    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.5-flash"
    assert result["model"] == "gemini-2.5-flash"


def test_generate_passes_system_instruction_and_temperature(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_response("ok")

    import server

    server.gemini_generate.fn(
        prompt="hi",
        system_instruction="be terse",
        temperature=0.2,
        max_output_tokens=100,
    )

    config = mock_genai_client.models.generate_content.call_args.kwargs["config"]
    assert config.system_instruction == "be terse"
    assert config.temperature == 0.2
    assert config.max_output_tokens == 100


def test_generate_wraps_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("quota")

    import server

    result = server.gemini_generate.fn(prompt="hi")

    assert result == {"error": "quota", "model": "gemini-2.5-pro"}
