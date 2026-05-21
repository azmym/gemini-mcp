"""Tests for gemini_generate_music tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_audio_response(data: bytes = b"RIFF\x00\x00\x00\x00WAVEfake") -> SimpleNamespace:
    """Build a fake response shaped like generate_content with an AUDIO part."""
    part = SimpleNamespace(
        inline_data=SimpleNamespace(data=data, mime_type="audio/wav"),
        text=None,
    )
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    return SimpleNamespace(candidates=[candidate], text=None)


def test_generate_music_writes_wav(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_audio_response()

    import server

    result = server.gemini_generate_music.fn(
        prompt="lo-fi piano loop",
        output_dir=str(tmp_path),
    )

    written = Path(result["path"])
    assert written.exists()
    assert written.read_bytes().startswith(b"RIFF")
    assert written.name.startswith("lyria-")
    assert written.suffix == ".wav"
    assert result["model"] == "lyria-3-pro-preview"


def test_generate_music_creates_output_dir(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_audio_response()
    nested = tmp_path / "nested" / "music"

    import server

    result = server.gemini_generate_music.fn(
        prompt="ambient pad",
        output_dir=str(nested),
    )

    assert nested.exists()
    assert Path(result["path"]).parent == nested


def test_generate_music_rejects_bad_duration(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    import server

    result = server.gemini_generate_music.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        duration_seconds=0,
    )

    assert "error" in result
    assert "duration_seconds" in result["error"]
    mock_genai_client.models.generate_content.assert_not_called()


def test_generate_music_wraps_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("lyria down")

    import server

    result = server.gemini_generate_music.fn(
        prompt="hi",
        output_dir=str(tmp_path),
    )

    assert result == {"error": "lyria down", "model": "lyria-3-pro-preview"}


def test_generate_music_model_override(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_audio_response()

    import server

    result = server.gemini_generate_music.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        model="lyria-3-clip-preview",
    )

    assert result["model"] == "lyria-3-clip-preview"
    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "lyria-3-clip-preview"
