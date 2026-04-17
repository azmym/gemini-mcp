"""Tests for gemini_analyze_file tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, usage_metadata=None)


def test_analyze_file_uploads_and_asks(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    uploaded = SimpleNamespace(uri="files/abc123", name="files/abc123", mime_type="application/pdf")
    mock_genai_client.files.upload.return_value = uploaded
    mock_genai_client.models.generate_content.return_value = _fake_text_response("summary here")

    import server

    result = server.gemini_analyze_file.fn(
        file_path=str(pdf), prompt="summarize"
    )

    mock_genai_client.files.upload.assert_called_once()
    upload_kwargs = mock_genai_client.files.upload.call_args.kwargs
    actual_path = upload_kwargs.get("file") or upload_kwargs.get("path")
    assert actual_path == str(pdf)
    assert result["answer"] == "summary here"
    assert result["file_uri"] == "files/abc123"
    assert result["model"] == "gemini-2.5-pro"


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
    mock_genai_client.files.upload.side_effect = RuntimeError("upload failed")

    import server

    result = server.gemini_analyze_file.fn(
        file_path=str(pdf), prompt="x"
    )

    assert result == {"error": "upload failed", "model": "gemini-2.5-pro"}
