# Imagen + Veo Tools: Design

**Date:** 2026-04-17
**Status:** Approved (pending user review)
**Depends on:** 2026-04-17-gemini-mcp-design.md (baseline server)

## Problem

The existing gemini-mcp server exposes only `generateContent`-based models. Google AI Studio also publishes Imagen 4 (image) and Veo 2/3 (video) model families that use different SDK entry points: `client.models.generate_images()` and `client.models.generate_videos()` respectively. The second is a long-running operation (LRO) that polls. Today users of the MCP server can't reach these models at all.

## Goals

1. Expose Imagen 4 image generation as a new synchronous MCP tool.
2. Expose Veo video generation as a pair of MCP tools (start + poll) so the stdio server is never blocked for minutes.
3. Fit the existing server structure: single `server.py`, FastMCP decorators, `_resolve_model` for model selection, structured error returns, `.fn` accessible tests.
4. Keep scope tight: one prompt in, file path(s) out, no advanced parameter surface.

## Non-Goals

- Imagen editing (`client.models.edit_image`), upscaling (`upscale_image`), recontext, or segmentation.
- Vertex AI path (this server is AI-Studio-only).
- Persistent video operation storage. Operations live in memory only; server restart clears them.
- Exposing every `GenerateImagesConfig` / `GenerateVideosConfig` field. We ship the minimal useful surface and add more if callers ask.
- Audio/TTS, Lyria (music), embeddings. Each is a separate future proposal.
- Imagen image-to-image editing or masking. Imagen tool is text-to-image only.

## Architecture

```
Claude Code ─stdio─► gemini-mcp ─HTTPS─► Google AI Studio
                        │
                        ├─ gemini_generate_image_imagen (sync)
                        ├─ gemini_start_video        (returns operation_id)
                        └─ gemini_get_video          (polls + saves MP4)
                                │
                                └─ _video_ops: dict[operation_id -> Operation]
                                     (in-memory, cleared on server restart)
```

Three new `@mcp.tool()` functions are appended to `server.py`. A new module-level dict `_video_ops: dict[str, Any] = {}` holds in-flight Veo operations, keyed by a short opaque ID the server generates (not the SDK's `operation.name`, so we have a stable handle even if the SDK formats change).

## Tool Specifications

### `gemini_generate_image_imagen`

Synchronous image generation using an Imagen 4 model.

**Signature:**

```python
def gemini_generate_image_imagen(
    prompt: str,
    output_dir: str = "/tmp/gemini-images",
    count: int = 1,
    aspect_ratio: str = "1:1",
    model: str | None = None,
) -> dict[str, Any]
```

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Text description |
| `output_dir` | str | `/tmp/gemini-images` | Created if missing |
| `count` | int | 1 | 1 to 4 inclusive. Values outside range return an error |
| `aspect_ratio` | str | `"1:1"` | One of: `"1:1"`, `"16:9"`, `"9:16"`, `"4:3"`, `"3:4"` |
| `model` | str | None | Defaults via `_resolve_model` to `imagen-4.0-generate-001` |

**Success output:**

```json
{"paths": ["/tmp/gemini-images/imagen-1776443000-ab12cd34.png"], "model": "imagen-4.0-generate-001"}
```

**Error output:**

```json
{"error": "...", "model": "imagen-4.0-generate-001"}
```

**Internals:**

```python
from google.genai import types as genai_types

config = genai_types.GenerateImagesConfig(
    number_of_images=count,
    aspect_ratio=aspect_ratio,
    output_mime_type="image/png",
)
response = client.models.generate_images(model=chosen, prompt=prompt, config=config)

for g in response.generated_images or []:
    data = g.image.image_bytes
    path = out / f"imagen-{stamp}-{uuid4().hex[:8]}.png"
    path.write_bytes(data)
    paths.append(str(path))
```

### `gemini_start_video`

Kicks off a Veo video generation and returns an operation ID immediately.

**Signature:**

```python
def gemini_start_video(
    prompt: str,
    aspect_ratio: str = "16:9",
    duration_seconds: int = 5,
    image_path: str | None = None,
    model: str | None = None,
) -> dict[str, Any]
```

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Text description |
| `aspect_ratio` | str | `"16:9"` | `"16:9"` or `"9:16"` |
| `duration_seconds` | int | 5 | Veo 3 accepts roughly 4 to 8 seconds |
| `image_path` | str\|None | None | If set, image-to-video mode. Must be a local file |
| `model` | str | None | Defaults via `_resolve_model` to `veo-3.0-generate-001` |

**Success output:**

```json
{"operation_id": "a1b2c3d4e5f6", "model": "veo-3.0-generate-001", "message": "Video generation started. Poll with gemini_get_video."}
```

**Error output:**

```json
{"error": "File not found: /path/to/image.png", "model": "veo-3.0-generate-001"}
```

**Internals:**

```python
image = None
if image_path:
    p = Path(image_path).expanduser().resolve()
    if not p.is_file():
        return {"error": f"File not found: {image_path}", "model": chosen}
    mime = "image/png" if p.suffix.lower() == ".png" else "image/jpeg"
    image = genai_types.Image(image_bytes=p.read_bytes(), mime_type=mime)

config = genai_types.GenerateVideosConfig(
    number_of_videos=1,
    duration_seconds=duration_seconds,
    aspect_ratio=aspect_ratio,
)
operation = client.models.generate_videos(
    model=chosen, prompt=prompt, config=config, image=image
)

op_id = uuid.uuid4().hex[:12]
_video_ops[op_id] = operation
return {"operation_id": op_id, "model": chosen, "message": "Video generation started. Poll with gemini_get_video."}
```

### `gemini_get_video`

Refreshes a Veo operation and, when complete, saves the video to disk.

**Signature:**

```python
def gemini_get_video(
    operation_id: str,
    output_dir: str = "/tmp/gemini-videos",
) -> dict[str, Any]
```

**Success outputs (one of):**

```json
{"status": "running", "operation_id": "a1b2c3d4e5f6"}
```
```json
{"status": "done", "path": "/tmp/gemini-videos/veo-1776443060-ab12cd34.mp4", "operation_id": "a1b2c3d4e5f6"}
```

**Error outputs (one of):**

```json
{"status": "error", "error": "<message>", "operation_id": "a1b2c3d4e5f6"}
```
```json
{"status": "unknown", "error": "operation_id not found"}
```

**Internals:**

```python
op = _video_ops.get(operation_id)
if op is None:
    return {"status": "unknown", "error": "operation_id not found"}

client = _ensure_client()
op = client.operations.get(op)
_video_ops[operation_id] = op

if not op.done:
    return {"status": "running", "operation_id": operation_id}

try:
    videos = op.result.generated_videos
    video_bytes = videos[0].video.video_bytes
    out = Path(output_dir).expanduser().resolve()
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"veo-{int(time.time())}-{uuid.uuid4().hex[:8]}.mp4"
    path.write_bytes(video_bytes)
    _video_ops.pop(operation_id, None)
    return {"status": "done", "path": str(path), "operation_id": operation_id}
except Exception as exc:  # noqa: BLE001
    _video_ops.pop(operation_id, None)
    return {"status": "error", "error": str(exc), "operation_id": operation_id}
```

Recommended client poll interval: 10 to 15 seconds. Total wall time: 30 seconds to 3 minutes typical.

## Module-Level State

```python
_video_ops: dict[str, Any] = {}
```

Added alongside the existing `_sessions` dict. Cleared implicitly on server restart. Not persisted.

## Configuration

No new environment variables. `GEMINI_API_KEY` and `GEMINI_DEFAULT_MODEL` already handle auth and model selection. `_resolve_model(model, builtin)` applies the same priority: explicit > env > built-in.

## Error Handling

All three tools follow the existing convention: catch `Exception`, return a structured dict. Nothing raises to the stdio layer. The two exceptions:

1. `gemini_start_video` with a missing `image_path` returns before hitting the SDK.
2. `gemini_get_video` with an unknown `operation_id` returns `status: unknown` rather than raising.

Dead operations (errored after polling) are popped from `_video_ops` so stale entries don't accumulate.

## Testing Strategy

Three new test files, all offline (mocks on `server._client`):

### `tests/test_generate_image_imagen.py`

- `test_imagen_writes_png(tmp_path, mock_genai_client)`: mock `generate_images` returns two `GeneratedImage`s with fake PNG bytes; verify two files written, `paths` matches, model is `imagen-4.0-generate-001`.
- `test_imagen_respects_count_and_aspect_ratio`: mock returns 3; verify `config.number_of_images == 3` and `config.aspect_ratio == "16:9"` on the call.
- `test_imagen_creates_output_dir(tmp_path)`: nested non-existent dir created.
- `test_imagen_wraps_errors`: SDK raises, tool returns `{error, model}`.
- `test_imagen_model_override`: per-call `model="imagen-4.0-ultra-generate-001"` wins over built-in.

### `tests/test_start_video.py`

- `test_start_video_stores_operation(mock_genai_client, reset_video_ops)`: mock `generate_videos` returns an op; assert `operation_id` in result, operation stored in `server._video_ops`.
- `test_start_video_passes_config`: assert `config.aspect_ratio == "9:16"` and `config.duration_seconds == 7`.
- `test_start_video_with_image_path(tmp_path)`: create a fake PNG, call with `image_path=...`, assert `image` kwarg passed to SDK and bytes match.
- `test_start_video_missing_image_file`: non-existent path returns `{error: "File not found: ...", model}`, SDK never called.
- `test_start_video_wraps_sdk_errors`: SDK raises, structured error returned.

### `tests/test_get_video.py`

- `test_get_video_running(mock_genai_client, reset_video_ops)`: pre-seed `_video_ops` with a mock op where `done=False`; assert `status: "running"`.
- `test_get_video_done_writes_mp4(tmp_path)`: pre-seed with `done=True`, `result.generated_videos[0].video.video_bytes = b"fake-mp4"`; assert file written, op popped from dict, `status: "done"`, `path` correct.
- `test_get_video_refresh_called`: verify `client.operations.get(op)` was called.
- `test_get_video_unknown_id`: bad id returns `{status: "unknown", error: "operation_id not found"}`.
- `test_get_video_wraps_errors`: done=True but video bytes missing -> `status: "error"` and op popped.

### `conftest.py` addition

```python
@pytest.fixture
def reset_video_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    import server
    monkeypatch.setattr(server, "_video_ops", {})
```

Target total: +13 tests, bringing the suite from 31 to 44.

## Dependencies

No new dependencies. `google-genai` already includes `generate_images`, `generate_videos`, and `operations.get`.

## README Updates

After implementation:

1. Add three rows to the Features table.
2. Add an "Asynchronous video generation" subsection under Usage examples showing the start/poll pattern with a loop.
3. Update Known limitations: note that `_video_ops` is in-memory and that image-to-video requires local file read.
4. Update the test count in Development and Project structure from 31 to 44.

## Migration Notes for Existing Users

- No breaking changes to existing tools.
- Users on `uvx --from git+...@v0.1.0` stay locked. New functionality requires updating (next-version tag, or `--refresh`).

## Out of Scope Future Work

- Imagen edit/upscale/recontext tools.
- Audio output (TTS, Lyria music).
- Veo reference-images workflow (up to 3 style refs).
- Webhook-based completion (`GenerateVideosConfig.webhook_config`).
- Persistent operation storage so `operation_id` survives server restart.
- Resume-downloading partial videos.
