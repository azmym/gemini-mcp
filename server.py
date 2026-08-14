"""Gemini MCP server.

Exposes Google Gemini (via Google AI Studio) as MCP tools.
Run with: uvx --from "fastmcp[cli]" fastmcp run server.py
"""
from __future__ import annotations

import mimetypes
import os
import re
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

_ALLOWED_ASPECT_RATIOS: frozenset[str] = frozenset({"1:1", "16:9", "9:16", "4:3", "3:4"})

# Gemini 3.x models reject Files API references with 403 PERMISSION_DENIED
# ("The caller does not have permission") even for a file the same key just
# uploaded successfully; only gemini-2.5-* accepts them. Inline bytes work on
# every model, so gemini_analyze_file inlines by default and only falls back to
# the Files API for payloads too large to inline.
# The API's own inline request ceiling is 20MB; 15MB leaves room for the prompt
# and encoding overhead. Verified inline at 5MB; an 18MB text payload fails on
# the 1,048,576-token context limit rather than on request size.
_INLINE_MAX_BYTES: int = 15 * 1024 * 1024

# Interaction states that mean "not finished yet" (see InteractionStatus in the
# google-genai SDK). Anything else that is not "completed" is terminal-bad.
_RESEARCH_PENDING: frozenset[str] = frozenset(
    {"in_progress", "queued", "requires_action"}
)

# Cited sources come back as markdown links inside output_text; the Interactions
# response has no structured citations field.
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")


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
    chosen = _resolve_model(model, "gemini-3.1-flash-image")
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
    redirects to gemini-3.1-flash-image (the same path as
    gemini_generate_image). Imagen-only knobs are translated: aspect_ratio is
    appended to the prompt as an instruction; count maps to candidate_count.
    Prefer gemini_generate_image for new code.
    """
    deprecation = (
        "gemini_generate_image_imagen is deprecated; Imagen 4 models sunset "
        "2026-08-17. This call was served by gemini-3.1-flash-image. "
        "Use gemini_generate_image."
    )
    # Redirect the no-model default and any explicit imagen-* pin to flash-image;
    # honor any other explicit model (and GEMINI_DEFAULT_MODEL) as before.
    effective = None if (model is None or model.startswith("imagen-")) else model
    chosen = _resolve_model(effective, "gemini-3.1-flash-image")
    # Post-resolve guard: GEMINI_DEFAULT_MODEL may itself be set to an imagen-*
    # ID, which the pre-resolve nullification above cannot catch.
    if chosen.startswith("imagen-"):
        chosen = "gemini-3.1-flash-image"
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
    chosen = _resolve_model(model, "gemini-3.7-flash")
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
    """Send a local file (PDF, image, audio, video) to Gemini and ask about it.

    Files at or under `_INLINE_MAX_BYTES` are sent inline as bytes. Larger files
    fall back to the Files API, which only works on Gemini 2.5-era models (see
    `_INLINE_MAX_BYTES`).
    """
    chosen = _resolve_model(model, "gemini-3.1-pro-preview")
    path = Path(file_path).expanduser().resolve()
    if not path.is_file():
        return {"error": f"File not found: {file_path}", "model": chosen}

    try:
        client = _ensure_client()
        if path.stat().st_size <= _INLINE_MAX_BYTES:
            mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            part = genai_types.Part.from_bytes(
                data=path.read_bytes(),
                mime_type=mime_type,
            )
            response = client.models.generate_content(
                model=chosen,
                contents=[prompt, part],
            )
            return {
                "answer": (response.text or "").strip(),
                "file_uri": "",
                "inline": True,
                "model": chosen,
            }

        uploaded = client.files.upload(file=str(path))
        response = client.models.generate_content(
            model=chosen,
            contents=[prompt, uploaded],
        )
        return {
            "answer": (response.text or "").strip(),
            "file_uri": getattr(uploaded, "uri", "") or getattr(uploaded, "name", ""),
            "inline": False,
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
    chosen = _resolve_model(model, "gemini-3.7-flash")
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

    Deep Research models are served ONLY by the Interactions API: calling
    models.generate_content on them returns 400 "This model only supports
    Interactions API". The model ID is an *agent*, so it goes in the `agent`
    field (the `model` field is rejected for it), and `background=True` is
    mandatory for agent interactions. Interactions are natively asynchronous,
    so the API's own interaction ID is the operation handle: no local thread
    pool is needed, and the handle stays valid across a server restart.
    """
    chosen = _resolve_model(model, "deep-research-max-preview-04-2026")
    try:
        client = _ensure_client()
        interaction = client.interactions.create(
            agent=chosen,
            input=prompt,
            background=True,
        )
        return {
            "operation_id": interaction.id,
            "model": chosen,
            "message": "Research started. Poll with gemini_get_research_report.",
        }
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc), "model": chosen}


def _research_citations(report: str) -> list[dict[str, str]]:
    """Extract cited sources from a Deep Research report.

    The Interactions response carries no structured citations field; sources
    are rendered as markdown links in output_text. Deduplicated, order kept.
    """
    citations: list[dict[str, str]] = []
    seen: set[str] = set()
    for title, url in _MD_LINK_RE.findall(report):
        if url in seen:
            continue
        seen.add(url)
        citations.append({"url": url, "title": title})
    return citations


@mcp.tool()
def gemini_get_research_report(
    operation_id: str,
    output_dir: str = "/tmp/gemini-research",
) -> dict[str, Any]:
    """Poll a Deep Research operation started by gemini_start_research.

    Returns status "running", "done" (with path and inline report), or "error".
    """
    try:
        interaction = _ensure_client().interactions.get(operation_id)
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "operation_id": operation_id}

    status = str(getattr(interaction, "status", "") or "")
    if status in _RESEARCH_PENDING:
        return {"status": "running", "operation_id": operation_id}

    if status != "completed":
        errors = getattr(interaction, "errors", None) or []
        detail = "; ".join(
            str(getattr(e, "message", None) or e) for e in errors
        )
        return {
            "status": "error",
            "error": f"Deep Research interaction {status}"
            + (f": {detail}" if detail else ""),
            "operation_id": operation_id,
        }

    try:
        report = (getattr(interaction, "output_text", "") or "").strip()
        if not report:
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
        return {
            "status": "done",
            "path": str(fpath),
            "report": report,
            "citations": _research_citations(report),
            "operation_id": operation_id,
        }
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc), "operation_id": operation_id}


def main() -> None:
    """CLI entry point. Registered in pyproject.toml as `gemini-mcp`."""
    _ensure_client()
    mcp.run()


if __name__ == "__main__":
    main()
