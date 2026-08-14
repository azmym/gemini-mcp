"""Tests for gemini_analyze_file tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _fake_text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, usage_metadata=None)


def test_analyze_file_sends_small_file_inline(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    """Small files go inline: Gemini 3.x 403s on Files API references."""
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    mock_genai_client.models.generate_content.return_value = _fake_text_response("summary here")

    import server

    result = server.gemini_analyze_file.fn(file_path=str(pdf), prompt="summarize")

    # The Files API path is what triggers the 403 on 3.x models; it must not be used.
    mock_genai_client.files.upload.assert_not_called()

    contents = mock_genai_client.models.generate_content.call_args.kwargs["contents"]
    assert contents[0] == "summarize"
    part = contents[1]
    assert part.inline_data.data == b"%PDF-1.4 fake"
    assert part.inline_data.mime_type == "application/pdf"

    assert result["answer"] == "summary here"
    assert result["inline"] is True
    assert result["file_uri"] == ""
    assert result["model"] == "gemini-3.1-pro-preview"


def test_analyze_file_falls_back_to_upload_for_large_file(
    tmp_path: Path, mock_genai_client: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Files too large to inline still use the Files API."""
    import server

    monkeypatch.setattr(server, "_INLINE_MAX_BYTES", 8)

    big = tmp_path / "big.pdf"
    big.write_bytes(b"%PDF-1.4 this is longer than eight bytes")

    uploaded = SimpleNamespace(
        uri="files/abc123", name="files/abc123", mime_type="application/pdf"
    )
    mock_genai_client.files.upload.return_value = uploaded
    mock_genai_client.models.generate_content.return_value = _fake_text_response("big summary")

    result = server.gemini_analyze_file.fn(file_path=str(big), prompt="summarize")

    mock_genai_client.files.upload.assert_called_once()
    upload_kwargs = mock_genai_client.files.upload.call_args.kwargs
    assert (upload_kwargs.get("file") or upload_kwargs.get("path")) == str(big)

    contents = mock_genai_client.models.generate_content.call_args.kwargs["contents"]
    assert contents[1] is uploaded

    assert result["answer"] == "big summary"
    assert result["inline"] is False
    assert result["file_uri"] == "files/abc123"


def test_analyze_file_guesses_mime_type_from_extension(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    png = tmp_path / "shot.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n fake")
    mock_genai_client.models.generate_content.return_value = _fake_text_response("a picture")

    import server

    server.gemini_analyze_file.fn(file_path=str(png), prompt="describe")

    part = mock_genai_client.models.generate_content.call_args.kwargs["contents"][1]
    assert part.inline_data.mime_type == "image/png"


def test_analyze_file_defaults_mime_type_when_unknown(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    """An unguessable extension must not crash; fall back to octet-stream."""
    blob = tmp_path / "data.weirdext"
    blob.write_bytes(b"\x00\x01\x02")
    mock_genai_client.models.generate_content.return_value = _fake_text_response("bytes")

    import server

    server.gemini_analyze_file.fn(file_path=str(blob), prompt="what is this")

    part = mock_genai_client.models.generate_content.call_args.kwargs["contents"][1]
    assert part.inline_data.mime_type == "application/octet-stream"


def test_analyze_file_returns_error_when_file_missing(mock_genai_client: MagicMock) -> None:
    import server

    result = server.gemini_analyze_file.fn(
        file_path="/tmp/does-not-exist-abcxyz.pdf", prompt="x"
    )

    assert "error" in result
    assert "not found" in result["error"].lower()
    mock_genai_client.files.upload.assert_not_called()


def test_analyze_file_wraps_sdk_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_genai_client.models.generate_content.side_effect = RuntimeError("model down")

    import server

    result = server.gemini_analyze_file.fn(file_path=str(pdf), prompt="x")

    assert result == {"error": "model down", "model": "gemini-3.1-pro-preview"}
