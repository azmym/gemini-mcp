"""Tests for gemini_search_grounded tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_grounded_response(answer: str, urls: list[tuple[str, str]]) -> SimpleNamespace:
    chunks = [
        SimpleNamespace(web=SimpleNamespace(uri=u, title=t))
        for u, t in urls
    ]
    grounding_metadata = SimpleNamespace(grounding_chunks=chunks)
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=answer)]),
        grounding_metadata=grounding_metadata,
    )
    return SimpleNamespace(candidates=[candidate], text=answer)


def test_search_grounded_returns_answer_and_citations(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_grounded_response(
        answer="Paris is the capital of France.",
        urls=[("https://example.com/a", "Example A"), ("https://example.com/b", "Example B")],
    )

    import server

    result = server.gemini_search_grounded.fn(prompt="capital of France?")

    assert result["answer"] == "Paris is the capital of France."
    assert result["citations"] == [
        {"url": "https://example.com/a", "title": "Example A"},
        {"url": "https://example.com/b", "title": "Example B"},
    ]
    assert result["model"] == "gemini-3.5-flash"


def test_search_grounded_enables_search_tool(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_grounded_response("ok", [])

    import server

    server.gemini_search_grounded.fn(prompt="hi")

    config = mock_genai_client.models.generate_content.call_args.kwargs["config"]
    assert any(getattr(t, "google_search", None) is not None for t in config.tools)


def test_search_grounded_handles_missing_metadata(mock_genai_client: MagicMock) -> None:
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text="ok")]),
        grounding_metadata=None,
    )
    mock_genai_client.models.generate_content.return_value = SimpleNamespace(
        candidates=[candidate], text="ok"
    )

    import server

    result = server.gemini_search_grounded.fn(prompt="hi")

    assert result["citations"] == []


def test_search_grounded_wraps_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("search down")

    import server

    result = server.gemini_search_grounded.fn(prompt="hi")

    assert result == {"error": "search down", "model": "gemini-3.5-flash"}
