"""Tests for gemini_start_video tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def test_start_video_stores_operation(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    operation = MagicMock(name="operation")
    mock_genai_client.models.generate_videos.return_value = operation

    import server

    result = server.gemini_start_video.fn(
        prompt="a sunset timelapse",
    )

    assert "operation_id" in result
    op_id = result["operation_id"]
    assert isinstance(op_id, str) and len(op_id) >= 8
    assert result["model"] == "veo-3.0-generate-001"
    assert "gemini_get_video" in result.get("message", "")
    assert server._video_ops[op_id] is operation
