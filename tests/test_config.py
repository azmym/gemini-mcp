"""Tests for server startup configuration."""
from __future__ import annotations

import importlib

import pytest


def test_server_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import server

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        server._build_client()


def test_default_model_env_overrides_all_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_DEFAULT_MODEL", "gemini-3-flash-preview")
    import server
    importlib.reload(server)

    assert server._resolve_model("gemini-2.5-flash") == "gemini-3-flash-preview"


def test_default_model_env_absent_returns_caller_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_DEFAULT_MODEL", raising=False)
    import server
    importlib.reload(server)

    assert server._resolve_model("gemini-2.5-flash") == "gemini-2.5-flash"
