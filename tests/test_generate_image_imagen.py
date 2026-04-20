"""Tests for gemini_generate_image_imagen tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_images_response(num: int = 1) -> SimpleNamespace:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    images = [
        SimpleNamespace(image=SimpleNamespace(image_bytes=png))
        for _ in range(num)
    ]
    return SimpleNamespace(generated_images=images)


def test_imagen_writes_png(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=1)

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="a cat",
        output_dir=str(tmp_path),
        count=1,
    )

    assert len(result["paths"]) == 1
    written = Path(result["paths"][0])
    assert written.exists()
    assert written.read_bytes().startswith(b"\x89PNG")
    assert written.name.startswith("imagen-")
    assert result["model"] == "imagen-4.0-generate-001"
