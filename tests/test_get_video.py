"""Tests for gemini_get_video tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_get_video_running(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    op = MagicMock()
    op.done = False

    import server

    server._video_ops["op123abc"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_video.fn(operation_id="op123abc")

    assert result["status"] == "running"
    assert result["operation_id"] == "op123abc"
    assert "op123abc" in server._video_ops
    mock_genai_client.operations.get.assert_called_once_with(op)
