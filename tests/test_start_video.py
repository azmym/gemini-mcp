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
    assert result["model"] == "veo-3.1-generate-preview"
    assert "gemini_get_video" in result.get("message", "")
    assert server._video_ops[op_id] is operation


def test_start_video_passes_config(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    mock_genai_client.models.generate_videos.return_value = MagicMock()

    import server

    server.gemini_start_video.fn(
        prompt="hi",
        aspect_ratio="9:16",
        duration_seconds=7,
    )

    call_kwargs = mock_genai_client.models.generate_videos.call_args.kwargs
    config = call_kwargs["config"]
    assert config.aspect_ratio == "9:16"
    assert config.duration_seconds == 7
    assert config.number_of_videos == 1


def test_start_video_with_image_path(
    tmp_path: Path, mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    png = tmp_path / "seed.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")
    mock_genai_client.models.generate_videos.return_value = MagicMock()

    import server

    server.gemini_start_video.fn(
        prompt="animate this",
        image_path=str(png),
    )

    call_kwargs = mock_genai_client.models.generate_videos.call_args.kwargs
    assert call_kwargs["image"] is not None
    assert call_kwargs["image"].image_bytes == png.read_bytes()
    assert call_kwargs["image"].mime_type == "image/png"


def test_start_video_missing_image_file(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    import server

    result = server.gemini_start_video.fn(
        prompt="hi",
        image_path="/tmp/does-not-exist-xyz.png",
    )

    assert "error" in result
    assert "not found" in result["error"].lower()
    mock_genai_client.models.generate_videos.assert_not_called()


def test_start_video_wraps_sdk_errors(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    mock_genai_client.models.generate_videos.side_effect = RuntimeError("veo down")

    import server

    result = server.gemini_start_video.fn(prompt="hi")

    assert result == {"error": "veo down", "model": "veo-3.1-generate-preview"}
    assert server._video_ops == {}
