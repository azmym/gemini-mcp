"""Tests for server startup configuration."""
from __future__ import annotations

import importlib

import pytest
from google import genai


def test_server_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import server

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        server._build_client()


def test_build_client_accepts_authorization_key_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI Studio Authorization keys ("AQ."-prefixed) build a client like legacy
    "AIza" keys; the server must never reject keys on their format."""
    monkeypatch.setenv("GEMINI_API_KEY", "AQ.Ab-test-key-not-real")
    import server

    assert isinstance(server._build_client(), genai.Client)


def test_resolve_uses_explicit_model_when_provided(monkeypatch: pytest.MonkeyPatch) -> None:
    """An explicit per-call model wins over every other source."""
    monkeypatch.setenv("GEMINI_DEFAULT_MODEL", "env-model")
    import server
    importlib.reload(server)

    assert server._resolve_model("caller-explicit", "builtin") == "caller-explicit"


def test_resolve_uses_env_var_when_no_explicit_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the caller passes None, the env var overrides the built-in default."""
    monkeypatch.setenv("GEMINI_DEFAULT_MODEL", "env-model")
    import server
    importlib.reload(server)

    assert server._resolve_model(None, "builtin") == "env-model"


def test_resolve_falls_back_to_builtin_when_nothing_else_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When nothing is set, the built-in default is used."""
    monkeypatch.delenv("GEMINI_DEFAULT_MODEL", raising=False)
    import server
    importlib.reload(server)

    assert server._resolve_model(None, "builtin") == "builtin"


def test_video_ops_dict_exists() -> None:
    """The module-level _video_ops dict must exist for video operation tracking."""
    import server

    assert hasattr(server, "_video_ops")
    assert isinstance(server._video_ops, dict)
