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


def test_get_video_done_writes_mp4(
    tmp_path: Path, mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    fake_bytes = b"fake-mp4-content"
    video = SimpleNamespace(video=SimpleNamespace(video_bytes=fake_bytes))
    result_obj = SimpleNamespace(generated_videos=[video])
    op = MagicMock()
    op.done = True
    op.result = result_obj

    import server

    server._video_ops["op456def"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_video.fn(
        operation_id="op456def",
        output_dir=str(tmp_path),
    )

    assert result["status"] == "done"
    assert result["operation_id"] == "op456def"
    written = Path(result["path"])
    assert written.exists()
    assert written.read_bytes() == fake_bytes
    assert written.name.startswith("veo-")
    assert written.suffix == ".mp4"
    assert "op456def" not in server._video_ops


def test_get_video_unknown_id(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    import server

    result = server.gemini_get_video.fn(operation_id="does-not-exist")

    assert result == {"status": "unknown", "error": "operation_id not found"}
    mock_genai_client.operations.get.assert_not_called()


def test_get_video_done_missing_video_bytes(
    tmp_path: Path, mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    result_obj = SimpleNamespace(generated_videos=[])
    op = MagicMock()
    op.done = True
    op.result = result_obj

    import server

    server._video_ops["opempty"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_video.fn(
        operation_id="opempty",
        output_dir=str(tmp_path),
    )

    assert result["status"] == "error"
    assert "opempty" not in server._video_ops


def test_get_video_refresh_raises(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    op = MagicMock()

    import server

    server._video_ops["oprun"] = op
    mock_genai_client.operations.get.side_effect = RuntimeError("refresh failed")

    result = server.gemini_get_video.fn(operation_id="oprun")

    assert result["status"] == "error"
    assert "refresh failed" in result["error"]
    assert "oprun" not in server._video_ops
