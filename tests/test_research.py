"""Tests for gemini_start_research and gemini_get_research_report tools."""
from __future__ import annotations

import concurrent.futures
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_response(
    text: str = "# Report\n\nFindings.",
    citations: list[dict] | None = None,
) -> SimpleNamespace:
    """Build a fake GenerateContentResponse with text and grounding metadata."""
    grounding_chunks = []
    for c in citations or []:
        web = SimpleNamespace(uri=c["url"], title=c.get("title", ""))
        grounding_chunks.append(SimpleNamespace(web=web))
    grounding_metadata = SimpleNamespace(grounding_chunks=grounding_chunks)
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=text)]),
        grounding_metadata=grounding_metadata,
    )
    return SimpleNamespace(candidates=[candidate], text=text)


def _completed_future(value=None, exc: Exception | None = None) -> concurrent.futures.Future:
    """Build a Future that is already finished."""
    fut: concurrent.futures.Future = concurrent.futures.Future()
    if exc is not None:
        fut.set_exception(exc)
    else:
        fut.set_result(value)
    return fut


def _running_future() -> concurrent.futures.Future:
    """Build a Future that has not finished yet."""
    return concurrent.futures.Future()


def test_start_research_submits_to_executor(
    mock_genai_client: MagicMock, reset_research_ops: None, monkeypatch
) -> None:
    submitted = {}

    class FakeExecutor:
        def submit(self, fn, *args, **kwargs):
            submitted["fn"] = fn
            submitted["kwargs"] = kwargs
            return _completed_future(value=_fake_response())

    import server

    monkeypatch.setattr(server, "_ensure_research_executor", lambda: FakeExecutor())

    result = server.gemini_start_research.fn(prompt="What is X?")

    assert "operation_id" in result
    op_id = result["operation_id"]
    assert isinstance(op_id, str) and len(op_id) >= 8
    assert result["model"] == "deep-research-max-preview-04-2026"
    assert "gemini_get_research_report" in result.get("message", "")
    assert op_id in server._research_ops
    assert submitted["fn"] is mock_genai_client.models.generate_content
    assert submitted["kwargs"]["model"] == "deep-research-max-preview-04-2026"
    assert submitted["kwargs"]["contents"] == "What is X?"


def test_start_research_wraps_executor_errors(
    mock_genai_client: MagicMock, reset_research_ops: None, monkeypatch
) -> None:
    class BoomExecutor:
        def submit(self, fn, *args, **kwargs):
            raise RuntimeError("dr down")

    import server

    monkeypatch.setattr(server, "_ensure_research_executor", lambda: BoomExecutor())

    result = server.gemini_start_research.fn(prompt="hi")

    assert result == {"error": "dr down", "model": "deep-research-max-preview-04-2026"}
    assert server._research_ops == {}


def test_start_research_model_override(
    mock_genai_client: MagicMock, reset_research_ops: None, monkeypatch
) -> None:
    submitted = {}

    class FakeExecutor:
        def submit(self, fn, *args, **kwargs):
            submitted["kwargs"] = kwargs
            return _completed_future(value=_fake_response())

    import server

    monkeypatch.setattr(server, "_ensure_research_executor", lambda: FakeExecutor())

    result = server.gemini_start_research.fn(
        prompt="hi", model="deep-research-pro-preview-12-2025"
    )

    assert result["model"] == "deep-research-pro-preview-12-2025"
    assert submitted["kwargs"]["model"] == "deep-research-pro-preview-12-2025"


def test_get_research_report_unknown_id(
    reset_research_ops: None,
) -> None:
    import server

    result = server.gemini_get_research_report.fn(operation_id="nope")

    assert result == {"status": "unknown", "error": "operation_id not found"}


def test_get_research_report_running(
    reset_research_ops: None,
) -> None:
    import server

    server._research_ops["op1"] = _running_future()

    result = server.gemini_get_research_report.fn(operation_id="op1")

    assert result["status"] == "running"
    assert result["operation_id"] == "op1"
    assert "op1" in server._research_ops


def test_get_research_report_done_writes_markdown(
    tmp_path: Path,
    reset_research_ops: None,
) -> None:
    response = _fake_response(
        text="# Big Report\n\nContent.",
        citations=[
            {"url": "https://a.example", "title": "A"},
            {"url": "https://b.example", "title": "B"},
        ],
    )

    import server

    server._research_ops["op2"] = _completed_future(value=response)

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
    assert written.read_text(encoding="utf-8") == "# Big Report\n\nContent."
    assert written.name.startswith("research-")
    assert written.suffix == ".md"
    assert "op2" not in server._research_ops


def test_get_research_report_future_raised(
    reset_research_ops: None,
) -> None:
    import server

    server._research_ops["op3"] = _completed_future(exc=RuntimeError("synthesis failed"))

    result = server.gemini_get_research_report.fn(operation_id="op3")

    assert result["status"] == "error"
    assert "synthesis failed" in result["error"]
    assert "op3" not in server._research_ops


def test_get_research_report_empty_text_is_error(
    tmp_path: Path,
    reset_research_ops: None,
) -> None:
    response = SimpleNamespace(candidates=[], text="")

    import server

    server._research_ops["op4"] = _completed_future(value=response)

    result = server.gemini_get_research_report.fn(
        operation_id="op4", output_dir=str(tmp_path)
    )

    assert result["status"] == "error"
    assert "no text" in result["error"].lower()
    assert "op4" not in server._research_ops
