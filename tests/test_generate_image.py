"""Tests for gemini_generate_image tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_image_response(num_images: int = 1) -> SimpleNamespace:
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    parts = [
        SimpleNamespace(inline_data=SimpleNamespace(data=png_bytes, mime_type="image/png"))
        for _ in range(num_images)
    ]
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts))
    return SimpleNamespace(candidates=[candidate])


def test_generate_image_writes_png(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response()

    import server

    result = server.gemini_generate_image.fn(
        prompt="a cat", output_dir=str(tmp_path), count=1
    )

    assert len(result["paths"]) == 1
    assert Path(result["paths"][0]).exists()
    assert Path(result["paths"][0]).read_bytes().startswith(b"\x89PNG")
    assert result["model"] == "gemini-2.5-flash-image"


def test_generate_image_count_multiple(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=3)

    import server

    result = server.gemini_generate_image.fn(
        prompt="cats", output_dir=str(tmp_path), count=3
    )

    assert len(result["paths"]) == 3
    for p in result["paths"]:
        assert Path(p).exists()


def test_generate_image_creates_output_dir(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response()
    nested = tmp_path / "nested" / "dir"

    import server

    result = server.gemini_generate_image.fn(
        prompt="a cat", output_dir=str(nested), count=1
    )

    assert nested.exists()
    assert Path(result["paths"][0]).parent == nested


def test_generate_image_wraps_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("no image")

    import server

    result = server.gemini_generate_image.fn(
        prompt="x", output_dir=str(tmp_path), count=1
    )

    assert result == {"error": "no image", "model": "gemini-2.5-flash-image"}
