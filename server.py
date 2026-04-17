"""Gemini MCP server.

Exposes Google Gemini (via Google AI Studio) as MCP tools.
Run with: uvx --from "fastmcp[cli]" fastmcp run server.py
"""
from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
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


@mcp.tool()
def gemini_generate_image(
    prompt: str,
    output_dir: str = "/tmp/gemini-images",
    count: int = 1,
    model: str = "gemini-2.5-flash-image",
) -> dict[str, Any]:
    """Generate images from a text prompt using a Gemini native image model.

    Writes PNG files to `output_dir` and returns their absolute paths.
    """
    chosen = _resolve_model(model)
    try:
        client = _ensure_client()
        out_path = Path(output_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        config = genai_types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            candidate_count=count,
        )
        response = client.models.generate_content(
            model=chosen,
            contents=prompt,
            config=config,
        )

        paths: list[str] = []
        stamp = int(time.time())
        for candidate in response.candidates or []:
            for part in getattr(candidate.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline is None or not inline.data:
                    continue
                fname = f"gemini-{stamp}-{uuid.uuid4().hex[:8]}.png"
                fpath = out_path / fname
                fpath.write_bytes(inline.data)
                paths.append(str(fpath))

        return {"paths": paths, "model": chosen}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_code_execute(
    prompt: str,
    model: str = "gemini-2.5-pro",
) -> dict[str, Any]:
    """Ask Gemini to write and run Python code in its sandbox.

    Returns the final answer plus the code and stdout.
    """
    chosen = _resolve_model(model)
    try:
        client = _ensure_client()
        config = genai_types.GenerateContentConfig(
            tools=[genai_types.Tool(code_execution=genai_types.ToolCodeExecution())],
        )
        response = client.models.generate_content(
            model=chosen,
            contents=prompt,
            config=config,
        )

        code_parts: list[str] = []
        stdout_parts: list[str] = []
        answer_parts: list[str] = []
        for candidate in response.candidates or []:
            for part in getattr(candidate.content, "parts", []) or []:
                if getattr(part, "executable_code", None):
                    code_parts.append(part.executable_code.code or "")
                elif getattr(part, "code_execution_result", None):
                    stdout_parts.append(part.code_execution_result.output or "")
                elif getattr(part, "text", None):
                    answer_parts.append(part.text)

        return {
            "answer": "\n".join(answer_parts).strip() or (response.text or ""),
            "code": "\n".join(code_parts),
            "stdout": "\n".join(stdout_parts),
            "model": chosen,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_search_grounded(
    prompt: str,
    model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    """Text generation grounded with Google Search. Returns answer and citations."""
    chosen = _resolve_model(model)
    try:
        client = _ensure_client()
        config = genai_types.GenerateContentConfig(
            tools=[genai_types.Tool(google_search=genai_types.GoogleSearch())],
        )
        response = client.models.generate_content(
            model=chosen,
            contents=prompt,
            config=config,
        )

        text_parts: list[str] = []
        citations: list[dict[str, str]] = []
        for candidate in response.candidates or []:
            for part in getattr(candidate.content, "parts", []) or []:
                if getattr(part, "text", None):
                    text_parts.append(part.text)
            metadata = getattr(candidate, "grounding_metadata", None)
            if metadata is None:
                continue
            for chunk in getattr(metadata, "grounding_chunks", []) or []:
                web = getattr(chunk, "web", None)
                if web and getattr(web, "uri", None):
                    citations.append({"url": web.uri, "title": getattr(web, "title", "") or ""})

        return {
            "answer": "\n".join(text_parts).strip() or (response.text or ""),
            "citations": citations,
            "model": chosen,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


if __name__ == "__main__":
    _ensure_client()
    mcp.run()
