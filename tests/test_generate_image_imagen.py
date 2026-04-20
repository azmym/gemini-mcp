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


def test_imagen_passes_count_and_aspect_ratio(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=3)

    import server

    server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=3,
        aspect_ratio="16:9",
    )

    call_kwargs = mock_genai_client.models.generate_images.call_args.kwargs
    config = call_kwargs["config"]
    assert config.number_of_images == 3
    assert config.aspect_ratio == "16:9"
    assert config.output_mime_type == "image/png"


def test_imagen_creates_output_dir(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=1)
    nested = tmp_path / "nested" / "imagen"

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(nested),
        count=1,
    )

    assert nested.exists()
    assert Path(result["paths"][0]).parent == nested


def test_imagen_rejects_bad_count(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=5,
    )

    assert "error" in result
    assert "count must be between 1 and 4" in result["error"]
    mock_genai_client.models.generate_images.assert_not_called()


def test_imagen_wraps_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.side_effect = RuntimeError("quota exceeded")

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=1,
    )

    assert result == {"error": "quota exceeded", "model": "imagen-4.0-generate-001"}


def test_imagen_model_override(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=1)

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=1,
        model="imagen-4.0-ultra-generate-001",
    )

    assert result["model"] == "imagen-4.0-ultra-generate-001"
    call_kwargs = mock_genai_client.models.generate_images.call_args.kwargs
    assert call_kwargs["model"] == "imagen-4.0-ultra-generate-001"
