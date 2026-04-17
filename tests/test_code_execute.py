"""Tests for gemini_code_execute tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_code_response(answer: str, code: str, stdout: str) -> SimpleNamespace:
    parts = [
        SimpleNamespace(text=None, executable_code=SimpleNamespace(code=code), code_execution_result=None),
        SimpleNamespace(text=None, executable_code=None, code_execution_result=SimpleNamespace(output=stdout)),
        SimpleNamespace(text=answer, executable_code=None, code_execution_result=None),
    ]
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts))
    return SimpleNamespace(candidates=[candidate], text=answer)


def test_code_execute_extracts_code_stdout_and_answer(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_code_response(
        answer="The answer is 42.",
        code="print(21 * 2)",
        stdout="42",
    )

    import server

    result = server.gemini_code_execute.fn(prompt="what is 21*2?")

    assert result["answer"] == "The answer is 42."
    assert "21 * 2" in result["code"]
    assert result["stdout"] == "42"
    assert result["model"] == "gemini-2.5-pro"


def test_code_execute_enables_code_execution_tool(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_code_response("ans", "code", "out")

    import server

    server.gemini_code_execute.fn(prompt="hi")

    config = mock_genai_client.models.generate_content.call_args.kwargs["config"]
    assert config.tools  # at least one tool
    assert any(getattr(t, "code_execution", None) is not None for t in config.tools)


def test_code_execute_wraps_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("nope")

    import server

    result = server.gemini_code_execute.fn(prompt="hi")

    assert result == {"error": "nope", "model": "gemini-2.5-pro"}
