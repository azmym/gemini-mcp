"""Tests for gemini_start_research and gemini_get_research_report tools.

Deep Research models are served ONLY by the Interactions API. They reject
`models.generate_content` with 400 "This model only supports Interactions API",
and the interaction ID belongs in the `agent` field (not `model`) with
`background=True`. These tests pin that contract.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _interaction(
    status: str = "in_progress",
    output_text: str = "",
    id: str = "v1_abc123",
    errors: list | None = None,
) -> SimpleNamespace:
    """Build a fake Interaction as returned by client.interactions.create/get."""
    return SimpleNamespace(
        id=id,
        status=status,
        output_text=output_text,
        errors=errors,
    )


def test_start_research_uses_interactions_agent_field(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    """Regression: deep-research IDs go to interactions.create(agent=...),
    never models.generate_content(model=...), which returns 400."""
    mock_genai_client.interactions.create.return_value = _interaction()

    import server

    result = server.gemini_start_research.fn(prompt="What is X?")

    mock_genai_client.models.generate_content.assert_not_called()
    mock_genai_client.interactions.create.assert_called_once()
    kwargs = mock_genai_client.interactions.create.call_args.kwargs
    assert kwargs["agent"] == "deep-research-max-preview-04-2026"
    assert kwargs["input"] == "What is X?"
    assert kwargs["background"] is True
    assert "model" not in kwargs

    assert result["operation_id"] == "v1_abc123"
    assert result["model"] == "deep-research-max-preview-04-2026"
    assert "gemini_get_research_report" in result.get("message", "")


def test_start_research_returns_api_interaction_id(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    """The operation_id must be the API's interaction id so it survives a
    server restart, unlike the old locally-generated uuid."""
    mock_genai_client.interactions.create.return_value = _interaction(id="v1_zzz999")

    import server

    result = server.gemini_start_research.fn(prompt="hi")

    assert result["operation_id"] == "v1_zzz999"


def test_start_research_model_override(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    mock_genai_client.interactions.create.return_value = _interaction()

    import server

    result = server.gemini_start_research.fn(
        prompt="hi", model="deep-research-pro-preview-12-2025"
    )

    assert result["model"] == "deep-research-pro-preview-12-2025"
    kwargs = mock_genai_client.interactions.create.call_args.kwargs
    assert kwargs["agent"] == "deep-research-pro-preview-12-2025"


def test_start_research_wraps_api_errors(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    mock_genai_client.interactions.create.side_effect = RuntimeError("dr down")

    import server

    result = server.gemini_start_research.fn(prompt="hi")

    assert result == {"error": "dr down", "model": "deep-research-max-preview-04-2026"}


def test_get_research_report_running(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    mock_genai_client.interactions.get.return_value = _interaction(status="in_progress")

    import server

    result = server.gemini_get_research_report.fn(operation_id="v1_abc123")

    assert result["status"] == "running"
    assert result["operation_id"] == "v1_abc123"


def test_get_research_report_queued_is_running(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    """queued is a pre-completion state and must not read as done or error."""
    mock_genai_client.interactions.get.return_value = _interaction(status="queued")

    import server

    result = server.gemini_get_research_report.fn(operation_id="v1_abc123")

    assert result["status"] == "running"


def test_get_research_report_done_writes_markdown(
    mock_genai_client: MagicMock, reset_research_ops: None, tmp_path: Path
) -> None:
    report = "# Big Report\n\nParis is the capital [1]."
    mock_genai_client.interactions.get.return_value = _interaction(
        status="completed", output_text=report
    )

    import server

    result = server.gemini_get_research_report.fn(
        operation_id="v1_abc123", output_dir=str(tmp_path)
    )

    assert result["status"] == "done"
    assert result["report"] == report
    written = Path(result["path"])
    assert written.exists()
    assert written.read_text(encoding="utf-8") == report
    assert written.name.startswith("research-")
    assert written.suffix == ".md"


def test_get_research_report_extracts_inline_citations(
    mock_genai_client: MagicMock, reset_research_ops: None, tmp_path: Path
) -> None:
    """Interactions returns no structured citations field; the cited sources
    arrive as markdown links inside output_text."""
    report = (
        "Findings.\n\n**Sources:**\n"
        "1. [depaul.edu](https://example.com/a)\n"
        "2. [wikipedia.org](https://example.com/b)\n"
    )
    mock_genai_client.interactions.get.return_value = _interaction(
        status="completed", output_text=report
    )

    import server

    result = server.gemini_get_research_report.fn(
        operation_id="v1_abc123", output_dir=str(tmp_path)
    )

    assert result["citations"] == [
        {"url": "https://example.com/a", "title": "depaul.edu"},
        {"url": "https://example.com/b", "title": "wikipedia.org"},
    ]


def test_get_research_report_failed_status_is_error(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    mock_genai_client.interactions.get.return_value = _interaction(
        status="failed", errors=[SimpleNamespace(message="synthesis failed")]
    )

    import server

    result = server.gemini_get_research_report.fn(operation_id="v1_abc123")

    assert result["status"] == "error"
    assert "failed" in result["error"].lower()


def test_get_research_report_budget_exceeded_is_error(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    mock_genai_client.interactions.get.return_value = _interaction(
        status="budget_exceeded"
    )

    import server

    result = server.gemini_get_research_report.fn(operation_id="v1_abc123")

    assert result["status"] == "error"
    assert "budget_exceeded" in result["error"]


def test_get_research_report_completed_but_empty_is_error(
    mock_genai_client: MagicMock, reset_research_ops: None, tmp_path: Path
) -> None:
    mock_genai_client.interactions.get.return_value = _interaction(
        status="completed", output_text=""
    )

    import server

    result = server.gemini_get_research_report.fn(
        operation_id="v1_abc123", output_dir=str(tmp_path)
    )

    assert result["status"] == "error"
    assert "no text" in result["error"].lower()


def test_get_research_report_wraps_api_errors(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    mock_genai_client.interactions.get.side_effect = RuntimeError("404 not found")

    import server

    result = server.gemini_get_research_report.fn(operation_id="nope")

    assert result["status"] == "error"
    assert "404 not found" in result["error"]
