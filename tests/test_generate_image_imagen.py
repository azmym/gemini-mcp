"""Tests for the deprecated gemini_generate_image_imagen tool (redirects to flash-image)."""
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


def test_imagen_writes_png_via_flash_image(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=1)

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
    assert result["model"] == "gemini-3.1-flash-image-preview"
    assert result["deprecated"] is True
    assert "deprecated" in result["deprecation"]


def test_imagen_maps_count_to_candidate_count(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=3)

    import server

    server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=3,
        aspect_ratio="16:9",
    )

    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    config = call_kwargs["config"]
    assert config.candidate_count == 3
    assert config.response_modalities == ["IMAGE"]


def test_imagen_aspect_ratio_appended_to_prompt(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=1)

    import server

    server.gemini_generate_image_imagen.fn(
        prompt="a dog",
        output_dir=str(tmp_path),
        count=1,
        aspect_ratio="16:9",
    )

    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert "16:9 aspect ratio" in call_kwargs["contents"]


def test_imagen_square_aspect_ratio_no_suffix(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=1)

    import server

    server.gemini_generate_image_imagen.fn(
        prompt="a dog",
        output_dir=str(tmp_path),
        count=1,
        aspect_ratio="1:1",
    )

    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["contents"] == "a dog"


def test_imagen_creates_output_dir(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=1)
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
    assert result["deprecated"] is True
    mock_genai_client.models.generate_content.assert_not_called()


def test_imagen_wraps_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("quota exceeded")

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=1,
    )

    assert result == {
        "error": "quota exceeded",
        "model": "gemini-3.1-flash-image-preview",
        "deprecated": True,
    }


def test_imagen_explicit_imagen_id_is_redirected(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=1)

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=1,
        model="imagen-4.0-ultra-generate-001",
    )

    assert result["model"] == "gemini-3.1-flash-image-preview"
    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3.1-flash-image-preview"


def test_imagen_non_imagen_model_is_honored(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=1)

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=1,
        model="gemini-3-pro-image-preview",
    )

    assert result["model"] == "gemini-3-pro-image-preview"
    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-3-pro-image-preview"
