"""Gemini MCP server.

Exposes Google Gemini (via Google AI Studio) as MCP tools.
Run with: uvx --from "fastmcp[cli]" fastmcp run server.py
"""
from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from google import genai

mcp = FastMCP("gemini")

_sessions: dict[str, Any] = {}
_client: genai.Client | None = None


def _build_client() -> genai.Client:
    """Construct a google-genai Client from env. Raises if API key is missing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is required but not set."
        )
    return genai.Client(api_key=api_key)


def _resolve_model(default: str) -> str:
    """Return the caller's default unless GEMINI_DEFAULT_MODEL overrides globally."""
    return os.environ.get("GEMINI_DEFAULT_MODEL") or default


def _ensure_client() -> genai.Client:
    """Lazy-init the module-level client. Safe to call multiple times."""
    global _client
    if _client is None:
        _client = _build_client()
    return _client


if __name__ == "__main__":
    _ensure_client()
    mcp.run()
