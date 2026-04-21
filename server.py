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
_video_ops: dict[str, Any] = {}
_client: genai.Client | None = None


def _build_client() -> genai.Client:
    """Construct a google-genai Client from env. Raises if API key is missing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is required but not set."
        )
    return genai.Client(api_key=api_key)


def _resolve_model(explicit: str | None, builtin: str) -> str:
    """Resolve the model to use for a tool call.

    Priority (highest first):
    1. Explicit per-call argument (caller passed `model=...`)
    2. GEMINI_DEFAULT_MODEL environment variable
    3. Built-in default for the tool
    """
    if explicit:
        return explicit
    return os.environ.get("GEMINI_DEFAULT_MODEL") or builtin


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
        return {"error": str(exc), "model": "n/a"}


@mcp.tool()
def gemini_generate(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.7,
    max_output_tokens: int | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Single-turn text generation with optional system prompt and sampling controls."""
    chosen = _resolve_model(model, "gemini-2.5-pro")
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
    model: str | None = None,
) -> dict[str, Any]:
    """Generate images from a text prompt using a Gemini native image model.

    Writes PNG files to `output_dir` and returns their absolute paths.
    """
    chosen = _resolve_model(model, "gemini-2.5-flash-image")
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
def gemini_generate_image_imagen(
    prompt: str,
    output_dir: str = "/tmp/gemini-images",
    count: int = 1,
    aspect_ratio: str = "1:1",
    model: str | None = None,
) -> dict[str, Any]:
    """Generate images with Imagen 4 (text-to-image, PNG output).

    Uses `client.models.generate_images()`. Supported aspect ratios:
    "1:1", "16:9", "9:16", "4:3", "3:4". Count must be 1 to 4.
    """
    chosen = _resolve_model(model, "imagen-4.0-generate-001")
    if count < 1 or count > 4:
        return {"error": "count must be between 1 and 4", "model": chosen}
    try:
        client = _ensure_client()
        out_path = Path(output_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        config = genai_types.GenerateImagesConfig(
            number_of_images=count,
            aspect_ratio=aspect_ratio,
            output_mime_type="image/png",
        )
        response = client.models.generate_images(
            model=chosen,
            prompt=prompt,
            config=config,
        )

        paths: list[str] = []
        stamp = int(time.time())
        for generated in response.generated_images or []:
            data = getattr(getattr(generated, "image", None), "image_bytes", None)
            if not data:
                continue
            fname = f"imagen-{stamp}-{uuid.uuid4().hex[:8]}.png"
            fpath = out_path / fname
            fpath.write_bytes(data)
            paths.append(str(fpath))

        return {"paths": paths, "model": chosen}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_code_execute(
    prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Ask Gemini to write and run Python code in its sandbox.

    Returns the final answer plus the code and stdout.
    """
    chosen = _resolve_model(model, "gemini-2.5-pro")
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
    model: str | None = None,
) -> dict[str, Any]:
    """Text generation grounded with Google Search. Returns answer and citations."""
    chosen = _resolve_model(model, "gemini-2.5-flash")
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


@mcp.tool()
def gemini_analyze_file(
    file_path: str,
    prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Upload a local file (PDF, image, audio, video) and ask Gemini about it."""
    chosen = _resolve_model(model, "gemini-2.5-pro")
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return {"error": f"File not found: {file_path}", "model": chosen}

    try:
        client = _ensure_client()
        uploaded = client.files.upload(file=str(path))
        response = client.models.generate_content(
            model=chosen,
            contents=[prompt, uploaded],
        )
        return {
            "answer": (response.text or "").strip(),
            "file_uri": getattr(uploaded, "uri", "") or getattr(uploaded, "name", ""),
            "model": chosen,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_chat(
    session_id: str,
    message: str,
    system_instruction: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Multi-turn chat keyed by session_id. State lives in memory for server lifetime."""
    chosen = _resolve_model(model, "gemini-2.5-flash")
    try:
        client = _ensure_client()
        session = _sessions.get(session_id)
        if session is None:
            config = genai_types.GenerateContentConfig(system_instruction=system_instruction)
            chat = client.chats.create(model=chosen, config=config)
            session = {"chat": chat, "turn": 0}
            _sessions[session_id] = session

        session["turn"] += 1
        response = session["chat"].send_message(message)
        return {
            "response": (response.text or "").strip(),
            "turn": session["turn"],
            "model": chosen,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_start_video(
    prompt: str,
    aspect_ratio: str = "16:9",
    duration_seconds: int = 5,
    image_path: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Start a Veo video generation. Returns an operation_id to poll with gemini_get_video.

    Aspect ratio is "16:9" or "9:16". Duration is 4 to 8 seconds for Veo 3.
    When image_path is set, runs image-to-video mode.
    """
    chosen = _resolve_model(model, "veo-3.0-generate-001")
    image = None
    if image_path:
        p = Path(image_path).expanduser().resolve()
        if not p.is_file():
            return {"error": f"File not found: {image_path}", "model": chosen}
        mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
        try:
            image = genai_types.Image(image_bytes=p.read_bytes(), mime_type=mime)
        except Exception as exc:  # noqa: BLE001
            return {"error": f"Failed to read image: {exc}", "model": chosen}

    try:
        client = _ensure_client()
        config = genai_types.GenerateVideosConfig(
            number_of_videos=1,
            duration_seconds=duration_seconds,
            aspect_ratio=aspect_ratio,
        )
        operation = client.models.generate_videos(
            model=chosen,
            prompt=prompt,
            config=config,
            image=image,
        )
        op_id = uuid.uuid4().hex[:12]
        _video_ops[op_id] = operation
        return {
            "operation_id": op_id,
            "model": chosen,
            "message": "Video generation started. Poll with gemini_get_video.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_get_video(
    operation_id: str,
    output_dir: str = "/tmp/gemini-videos",
) -> dict[str, Any]:
    """Poll a Veo operation started by gemini_start_video.

    Returns status "running", "done" (with path), "error", or "unknown".
    """
    op = _video_ops.get(operation_id)
    if op is None:
        return {"status": "unknown", "error": "operation_id not found"}

    try:
        client = _ensure_client()
        op = client.operations.get(op)
        _video_ops[operation_id] = op
    except Exception as exc:  # noqa: BLE001
        _video_ops.pop(operation_id, None)
        return {"status": "error", "error": str(exc), "operation_id": operation_id}

    if not getattr(op, "done", False):
        return {"status": "running", "operation_id": operation_id}

    try:
        video = op.result.generated_videos[0].video
        video_bytes = getattr(video, "video_bytes", None)
        if not video_bytes:
            video_bytes = client.files.download(file=video)
        out = Path(output_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        fname = f"veo-{int(time.time())}-{uuid.uuid4().hex[:8]}.mp4"
        fpath = out / fname
        fpath.write_bytes(video_bytes)
        _video_ops.pop(operation_id, None)
        return {"status": "done", "path": str(fpath), "operation_id": operation_id}
    except Exception as exc:  # noqa: BLE001
        _video_ops.pop(operation_id, None)
        return {"status": "error", "error": str(exc), "operation_id": operation_id}


def main() -> None:
    """CLI entry point. Registered in pyproject.toml as `gemini-mcp`."""
    _ensure_client()
    mcp.run()


if __name__ == "__main__":
    main()
