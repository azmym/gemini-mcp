"""Shared pytest fixtures for gemini-mcp tests."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_genai_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch google.genai.Client with a MagicMock and return it.

    Tests configure return values on this mock to simulate API responses.
    """
    client = MagicMock()
    monkeypatch.setattr("server._client", client)
    return client


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test runs with a fake API key so server imports cleanly."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")


@pytest.fixture
def reset_chat_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the in-memory chat session dict between tests."""
    import server

    monkeypatch.setattr(server, "_sessions", {})
