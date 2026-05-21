"""Tests for gemini_tts tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_audio_response(data: bytes = b"RIFF\x00\x00\x00\x00WAVEtts") -> SimpleNamespace:
    part = SimpleNamespace(
        inline_data=SimpleNamespace(data=data, mime_type="audio/wav"),
        text=None,
    )
    candidate = SimpleNamespace(content=SimpleNamespace(parts=[part]))
    return SimpleNamespace(candidates=[candidate], text=None)


def test_tts_single_voice_writes_wav(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_audio_response()

    import server

    result = server.gemini_tts.fn(
        text="Hello, world.",
        output_dir=str(tmp_path),
    )

    written = Path(result["path"])
    assert written.exists()
    assert written.read_bytes().startswith(b"RIFF")
    assert written.name.startswith("tts-")
    assert written.suffix == ".wav"
    assert result["model"] == "gemini-3.1-flash-tts-preview"


def test_tts_single_voice_passes_voice_name(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_audio_response()

    import server

    server.gemini_tts.fn(
        text="hello",
        output_dir=str(tmp_path),
        voice="Charon",
    )

    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    config = call_kwargs["config"]
    voice_config = config.speech_config.voice_config
    assert voice_config.prebuilt_voice_config.voice_name == "Charon"


def test_tts_multi_speaker_passes_speaker_configs(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_audio_response()

    import server

    server.gemini_tts.fn(
        text="Alice: hello\nBob: hi",
        output_dir=str(tmp_path),
        speakers=[
            {"name": "Alice", "voice": "Kore"},
            {"name": "Bob", "voice": "Charon"},
        ],
    )

    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    config = call_kwargs["config"]
    multi = config.speech_config.multi_speaker_voice_config
    assert len(multi.speaker_voice_configs) == 2
    assert multi.speaker_voice_configs[0].speaker == "Alice"
    assert multi.speaker_voice_configs[0].voice_config.prebuilt_voice_config.voice_name == "Kore"
    assert multi.speaker_voice_configs[1].speaker == "Bob"


def test_tts_rejects_malformed_speakers(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    import server

    result = server.gemini_tts.fn(
        text="hi",
        output_dir=str(tmp_path),
        speakers=[{"name": "Alice"}],  # missing "voice"
    )

    assert "error" in result
    assert "speakers" in result["error"]
    mock_genai_client.models.generate_content.assert_not_called()


def test_tts_wraps_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("tts down")

    import server

    result = server.gemini_tts.fn(
        text="hi",
        output_dir=str(tmp_path),
    )

    assert result == {"error": "tts down", "model": "gemini-3.1-flash-tts-preview"}


def test_tts_model_override(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_audio_response()

    import server

    result = server.gemini_tts.fn(
        text="hi",
        output_dir=str(tmp_path),
        model="gemini-2.5-flash-preview-tts",
    )

    assert result["model"] == "gemini-2.5-flash-preview-tts"
    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.5-flash-preview-tts"
