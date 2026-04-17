"""Gemini MCP server.

Exposes Google Gemini (via Google AI Studio) as MCP tools.
Run with: uvx --from "fastmcp[cli]" fastmcp run server.py
"""
from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from google import genai
from google.genai import types as genai_types

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


@mcp.tool()
def gemini_list_models() -> list[dict[str, Any]] | dict[str, str]:
    """List available Gemini models with their capabilities and token limits."""
    try:
        client = _ensure_client()
        out: list[dict[str, Any]] = []
        for m in client.models.list():
            name = m.name.removeprefix("models/") if m.name else ""
            out.append(
                {
                    "name": name,
                    "supported_actions": list(getattr(m, "supported_actions", []) or []),
                    "input_token_limit": getattr(m, "input_token_limit", 0) or 0,
                    "output_token_limit": getattr(m, "output_token_limit", 0) or 0,
                }
            )
        return out
    except Exception as exc:  # noqa: BLE001 - surface as structured error
        return {"error": str(exc)}


@mcp.tool()
def gemini_generate(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.7,
    max_output_tokens: int | None = None,
    model: str = "gemini-2.5-pro",
) -> dict[str, Any]:
    """Single-turn text generation with optional system prompt and sampling controls."""
    chosen = _resolve_model(model)
    try:
        client = _ensure_client()
        config = genai_types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        response = client.models.generate_content(
            model=chosen,
            contents=prompt,
            config=config,
        )
        tokens = getattr(getattr(response, "usage_metadata", None), "total_token_count", 0) or 0
        return {"text": response.text or "", "tokens_used": tokens, "model": chosen}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


if __name__ == "__main__":
    _ensure_client()
    mcp.run()
