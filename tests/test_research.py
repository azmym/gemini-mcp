"""Tests for gemini_start_research and gemini_get_research_report tools."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_research_op(
    done: bool = True,
    text: str = "# Report\n\nFindings.",
    citations: list[dict] | None = None,
) -> MagicMock:
    """Build a fake Deep Research long-running operation object."""
    op = MagicMock()
    op.done = done
    if not done:
        op.result = None
        return op

    grounding_chunks = []
    for c in citations or []:
        web = SimpleNamespace(uri=c["url"], title=c.get("title", ""))
        grounding_chunks.append(SimpleNamespace(web=web))
    grounding_metadata = SimpleNamespace(grounding_chunks=grounding_chunks)
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
        grounding_metadata=grounding_metadata,
    )
    op.result = SimpleNamespace(candidates=[candidate], text=text)
    return op


def test_start_research_stores_operation(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    operation = MagicMock(name="lro")
    mock_genai_client.models.generate_content.return_value = operation

    import server

    result = server.gemini_start_research.fn(prompt="What is X?")

    assert "operation_id" in result
    op_id = result["operation_id"]
    assert isinstance(op_id, str) and len(op_id) >= 8
    assert result["model"] == "deep-research-max-preview-04-2026"
    assert "gemini_get_research_report" in result.get("message", "")
    assert server._research_ops[op_id] is operation


def test_start_research_wraps_sdk_errors(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("dr down")

    import server

    result = server.gemini_start_research.fn(prompt="hi")

    assert result == {"error": "dr down", "model": "deep-research-max-preview-04-2026"}
    assert server._research_ops == {}


def test_start_research_model_override(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    operation = MagicMock(name="lro")
    mock_genai_client.models.generate_content.return_value = operation

    import server

    result = server.gemini_start_research.fn(
        prompt="hi", model="deep-research-pro-preview-12-2025"
    )

    assert result["model"] == "deep-research-pro-preview-12-2025"
    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "deep-research-pro-preview-12-2025"


def test_get_research_report_unknown_id(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    import server

    result = server.gemini_get_research_report.fn(operation_id="nope")

    assert result == {"status": "unknown", "error": "operation_id not found"}
    mock_genai_client.operations.get.assert_not_called()


def test_get_research_report_running(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    op = _fake_research_op(done=False)

    import server

    server._research_ops["op1"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_research_report.fn(operation_id="op1")

    assert result["status"] == "running"
    assert result["operation_id"] == "op1"
    assert "op1" in server._research_ops
    mock_genai_client.operations.get.assert_called_once_with(op)


def test_get_research_report_done_writes_markdown(
    tmp_path: Path,
    mock_genai_client: MagicMock,
    reset_research_ops: None,
) -> None:
    op = _fake_research_op(
        done=True,
        text="# Big Report\n\nContent.",
        citations=[
            {"url": "https://a.example", "title": "A"},
            {"url": "https://b.example", "title": "B"},
        ],
    )

    import server

    server._research_ops["op2"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_research_report.fn(
        operation_id="op2", output_dir=str(tmp_path)
    )

    assert result["status"] == "done"
    assert result["operation_id"] == "op2"
    assert result["report"] == "# Big Report\n\nContent."
    assert result["citations"] == [
        {"url": "https://a.example", "title": "A"},
        {"url": "https://b.example", "title": "B"},
    ]
    written = Path(result["path"])
    assert written.exists()
    assert written.read_text() == "# Big Report\n\nContent."
    assert written.name.startswith("research-")
    assert written.suffix == ".md"
    assert "op2" not in server._research_ops


def test_get_research_report_refresh_raises(
    mock_genai_client: MagicMock, reset_research_ops: None
) -> None:
    op = _fake_research_op(done=False)

    import server

    server._research_ops["op3"] = op
    mock_genai_client.operations.get.side_effect = RuntimeError("refresh failed")

    result = server.gemini_get_research_report.fn(operation_id="op3")

    assert result["status"] == "error"
    assert "refresh failed" in result["error"]
    assert "op3" not in server._research_ops
