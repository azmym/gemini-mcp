"""Gemini MCP server.

Exposes Google Gemini (via Google AI Studio) as MCP tools.
Run with: uvx --from "fastmcp[cli]" fastmcp run server.py
"""
from __future__ import annotations

import os
import time
import concurrent.futures
import uuid
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from google import genai
from google.genai import types as genai_types

mcp = FastMCP("gemini")

_sessions: dict[str, Any] = {}
_video_ops: dict[str, Any] = {}
_research_ops: dict[str, Any] = {}
_client: genai.Client | None = None
_research_executor: concurrent.futures.ThreadPoolExecutor | None = None

_ALLOWED_ASPECT_RATIOS: frozenset[str] = frozenset({"1:1", "16:9", "9:16", "4:3", "3:4"})


def _ensure_research_executor() -> concurrent.futures.ThreadPoolExecutor:
    """Lazy-init thread pool for Deep Research synchronous calls.

    Deep Research models use the synchronous generateContent endpoint but can
    take minutes. A background thread keeps the MCP server responsive and
    makes the polling pair pattern work.
    """
    global _research_executor
    if _research_executor is None:
        _research_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=4, thread_name_prefix="gemini-research"
        )
    return _research_executor


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
    chosen = _resolve_model(model, "gemini-3.1-pro-preview")
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
    chosen = _resolve_model(model, "gemini-3.1-flash-image-preview")
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
    """DEPRECATED: generate images via the Gemini flash-image path.

    The Imagen 4 model IDs this tool used (imagen-4.0-*) are discontinued by
    Google on 2026-08-17 and return 404 after that date. This tool now
    redirects to gemini-3.1-flash-image-preview (the same path as
    gemini_generate_image). Imagen-only knobs are translated: aspect_ratio is
    appended to the prompt as an instruction; count maps to candidate_count.
    Prefer gemini_generate_image for new code.
    """
    deprecation = (
        "gemini_generate_image_imagen is deprecated; Imagen 4 models sunset "
        "2026-08-17. This call was served by gemini-3.1-flash-image-preview. "
        "Use gemini_generate_image."
    )
    # Redirect the no-model default and any imagen-* pin to flash-image;
    # honor any other explicit model (and GEMINI_DEFAULT_MODEL) as before.
    effective = None if (model is None or model.startswith("imagen-")) else model
    chosen = _resolve_model(effective, "gemini-3.1-flash-image-preview")
    if chosen.startswith("imagen-"):
        chosen = "gemini-3.1-flash-image-preview"
    if count < 1 or count > 4:
        return {
            "error": "count must be between 1 and 4",
            "model": chosen,
            "deprecated": True,
        }
    if aspect_ratio not in _ALLOWED_ASPECT_RATIOS:
        return {
            "error": f"aspect_ratio must be one of: {', '.join(sorted(_ALLOWED_ASPECT_RATIOS))}",
            "model": chosen,
            "deprecated": True,
        }
    try:
        client = _ensure_client()
        out_path = Path(output_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        contents = prompt
        if aspect_ratio != "1:1":
            contents = (
                f"{prompt}\n\nGenerate the image with a "
                f"{aspect_ratio} aspect ratio."
            )

        config = genai_types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            candidate_count=count,
        )
        response = client.models.generate_content(
            model=chosen,
            contents=contents,
            config=config,
        )

        paths: list[str] = []
        stamp = int(time.time())
        for candidate in response.candidates or []:
            for part in getattr(candidate.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline is None or not inline.data:
                    continue
                fname = f"imagen-{stamp}-{uuid.uuid4().hex[:8]}.png"
                fpath = out_path / fname
                fpath.write_bytes(inline.data)
                paths.append(str(fpath))

        return {
            "paths": paths,
            "model": chosen,
            "deprecated": True,
            "deprecation": deprecation,
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen, "deprecated": True}


@mcp.tool()
def gemini_generate_music(
    prompt: str,
    output_dir: str = "/tmp/gemini-music",
    duration_seconds: int = 30,
    model: str | None = None,
) -> dict[str, Any]:
    """Generate music from a text prompt with Lyria 3.

    Writes a WAV file to `output_dir` and returns its absolute path.
    `duration_seconds` is currently validated client-side (`> 0`) but NOT
    forwarded to the SDK: `GenerateContentConfig` does not yet accept a
    duration field for AUDIO modality. Encode duration hints in the prompt
    until the SDK exposes it.
    """
    chosen = _resolve_model(model, "lyria-3-pro-preview")
    if duration_seconds <= 0:
        return {"error": "duration_seconds must be > 0", "model": chosen}
    try:
        client = _ensure_client()
        out_path = Path(output_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        config = genai_types.GenerateContentConfig(
            response_modalities=["AUDIO"],
        )
        response = client.models.generate_content(
            model=chosen,
            contents=prompt,
            config=config,
        )

        for candidate in response.candidates or []:
            for part in getattr(candidate.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline is None or not inline.data:
                    continue
                stamp = int(time.time())
                fname = f"lyria-{stamp}-{uuid.uuid4().hex[:8]}.wav"
                fpath = out_path / fname
                fpath.write_bytes(inline.data)
                return {"path": str(fpath), "model": chosen}

        return {"error": "no audio returned", "model": chosen}
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_tts(
    text: str,
    output_dir: str = "/tmp/gemini-tts",
    voice: str = "Kore",
    speakers: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Synthesize speech from text using Gemini 3.1 TTS.

    Single-voice mode: pass `text` and optionally `voice`.
    Multi-speaker mode: pass `speakers=[{"name": "Alice", "voice": "Kore"}, ...]`
    and write `text` as "Alice: ...\\nBob: ..." with the speaker name as a prefix.
    """
    chosen = _resolve_model(model, "gemini-3.1-flash-tts-preview")

    if speakers is not None:
        if not isinstance(speakers, list) or not all(
            isinstance(s, dict) and "name" in s and "voice" in s
            and isinstance(s["name"], str) and isinstance(s["voice"], str)
            for s in speakers
        ):
            return {
                "error": "speakers must be a list of {name, voice} dicts",
                "model": chosen,
            }

    try:
        client = _ensure_client()
        out_path = Path(output_dir).expanduser().resolve()
        out_path.mkdir(parents=True, exist_ok=True)

        if speakers is None:
            speech_config = genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=voice,
                    ),
                ),
            )
        else:
            speech_config = genai_types.SpeechConfig(
                multi_speaker_voice_config=genai_types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        genai_types.SpeakerVoiceConfig(
                            speaker=s["name"],
                            voice_config=genai_types.VoiceConfig(
                                prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                                    voice_name=s["voice"],
                                ),
                            ),
                        )
                        for s in speakers
                    ],
                ),
            )

        config = genai_types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=speech_config,
        )
        response = client.models.generate_content(
            model=chosen,
            contents=text,
            config=config,
        )

        for candidate in response.candidates or []:
            for part in getattr(candidate.content, "parts", []) or []:
                inline = getattr(part, "inline_data", None)
                if inline is None or not inline.data:
                    continue
                stamp = int(time.time())
                fname = f"tts-{stamp}-{uuid.uuid4().hex[:8]}.wav"
                fpath = out_path / fname
                fpath.write_bytes(inline.data)
                return {"path": str(fpath), "model": chosen}

        return {"error": "no audio returned", "model": chosen}
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
    chosen = _resolve_model(model, "gemini-3.1-pro-preview-customtools")
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
    chosen = _resolve_model(model, "gemini-3.5-flash")
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
    chosen = _resolve_model(model, "gemini-3.1-pro-preview")
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
    chosen = _resolve_model(model, "gemini-3.5-flash")
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

    Aspect ratio is "16:9" or "9:16". Duration is 4 to 8 seconds for Veo 3.1.
    When image_path is set, runs image-to-video mode.
    """
    chosen = _resolve_model(model, "veo-3.1-generate-preview")
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


@mcp.tool()
def gemini_start_research(
    prompt: str,
    model: str | None = None,
) -> dict[str, Any]:
    """Start a Deep Research synthesis. Returns operation_id; poll with gemini_get_research_report.

    Deep Research is a synchronous SDK call that can take minutes. This tool
    runs it in a background thread so the MCP server stays responsive.
    """
    chosen = _resolve_model(model, "deep-research-max-preview-04-2026")
    try:
        client = _ensure_client()
        executor = _ensure_research_executor()
        future = executor.submit(
            client.models.generate_content,
            model=chosen,
            contents=prompt,
        )
        op_id = uuid.uuid4().hex[:12]
        _research_ops[op_id] = future
        return {
            "operation_id": op_id,
            "model": chosen,
            "message": "Research started. Poll with gemini_get_research_report.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


@mcp.tool()
def gemini_get_research_report(
    operation_id: str,
    output_dir: str = "/tmp/gemini-research",
) -> dict[str, Any]:
    """Poll a Deep Research operation started by gemini_start_research.

    Returns status "running", "done" (with path and inline report), "error", or "unknown".
    """
    future = _research_ops.get(operation_id)
    if future is None:
        return {"status": "unknown", "error": "operation_id not found"}

    if not future.done():
        return {"status": "running", "operation_id": operation_id}

    try:
        response = future.result()
    except Exception as exc:  # noqa: BLE001
        _research_ops.pop(operation_id, None)
        return {"status": "error", "error": str(exc), "operation_id": operation_id}

    try:
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
                    citations.append(
                        {"url": web.uri, "title": getattr(web, "title", "") or ""}
                    )

        report = "\n".join(text_parts).strip() or (getattr(response, "text", "") or "")
        if not report:
            _research_ops.pop(operation_id, None)
            return {
                "status": "error",
                "error": "Deep Research returned no text",
                "operation_id": operation_id,
            }
        out = Path(output_dir).expanduser().resolve()
        out.mkdir(parents=True, exist_ok=True)
        stamp = int(time.time())
        fname = f"research-{stamp}-{uuid.uuid4().hex[:8]}.md"
        fpath = out / fname
        fpath.write_text(report, encoding="utf-8")
        _research_ops.pop(operation_id, None)
        return {
            "status": "done",
            "path": str(fpath),
            "report": report,
            "citations": citations,
            "operation_id": operation_id,
        }
    except Exception as exc:  # noqa: BLE001
        _research_ops.pop(operation_id, None)
        return {"status": "error", "error": str(exc), "operation_id": operation_id}


def main() -> None:
    """CLI entry point. Registered in pyproject.toml as `gemini-mcp`."""
    _ensure_client()
    mcp.run()


if __name__ == "__main__":
    main()
