# Tools Reference

Every tool returns a JSON object. On success the shape varies by tool; on error the shape is consistently `{"error": "<message>", "model": "<resolved-model>"}` (or `{"status": "error", ...}` for video tools). No tool raises an exception to the MCP transport.

Every tool that talks to a model accepts a `model` parameter. Resolution order is: per-call `model` > `GEMINI_DEFAULT_MODEL` env var > built-in default. See `docs/configuration.md` for details.

## `gemini_list_models`

**Signature:** `gemini_list_models() -> list[dict] | dict`

Lists models the current API key can access.

**Parameters:** none.

**Success response (excerpt):**

```json
[
  {
    "name": "gemini-2.5-pro",
    "supported_actions": ["generateContent", "countTokens"],
    "input_token_limit": 1048576,
    "output_token_limit": 65536
  }
]
```

**Error response:**

```json
{"error": "<message>", "model": "n/a"}
```

**Notes:** No `model` parameter because this call does not target a specific model.

---

## `gemini_generate`

**Signature:**
```python
gemini_generate(
    prompt: str,
    system_instruction: str | None = None,
    temperature: float = 0.7,
    max_output_tokens: int | None = None,
    model: str | None = None,
) -> dict
```

Single-turn text generation.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | User prompt |
| `system_instruction` | str\|None | None | Optional system prompt |
| `temperature` | float | 0.7 | Sampling temperature |
| `max_output_tokens` | int\|None | None | Cap on response length |
| `model` | str\|None | None | Resolves to `gemini-3.1-pro-preview` when unset |

**Success response:**

```json
{"text": "<answer>", "tokens_used": 1234, "model": "gemini-3.1-pro-preview"}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-3.1-pro-preview"}
```

---

## `gemini_generate_image`

**Signature:**
```python
gemini_generate_image(
    prompt: str,
    output_dir: str = "/tmp/gemini-images",
    count: int = 1,
    model: str | None = None,
) -> dict
```

Native Gemini image generation. Writes PNG files to `output_dir` and returns absolute paths. Powered by Gemini's Nano Banana models. Pass `model="gemini-3-pro-image-preview"` for Nano Banana Pro.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Text description |
| `output_dir` | str | `/tmp/gemini-images` | Created if missing |
| `count` | int | 1 | Number of candidates |
| `model` | str\|None | None | Resolves to `gemini-3.1-flash-image-preview` when unset |

**Success response:**

```json
{
  "paths": ["/tmp/gemini-images/gemini-1713380000-a1b2c3d4.png"],
  "model": "gemini-3.1-flash-image-preview"
}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-3.1-flash-image-preview"}
```

---

## `gemini_generate_image_imagen`

**Signature:**
```python
gemini_generate_image_imagen(
    prompt: str,
    output_dir: str = "/tmp/gemini-images",
    count: int = 1,
    aspect_ratio: str = "1:1",
    model: str | None = None,
) -> dict
```

**DEPRECATED.** The Imagen 4 model IDs this tool used sunset on 2026-08-17 (404 after). It now redirects to the Gemini flash-image path (`gemini-3.1-flash-image-preview`). Use `gemini_generate_image` for new code.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Text description |
| `output_dir` | str | `/tmp/gemini-images` | Created if missing |
| `count` | int | 1 | Must be 1 to 4 inclusive |
| `aspect_ratio` | str | `"1:1"` | One of: `"1:1"`, `"16:9"`, `"9:16"`, `"4:3"`, `"3:4"` |
| `model` | str\|None | None | Resolves to `gemini-3.1-flash-image-preview`; `imagen-4.0-*` IDs are redirected to it |

**Success response:**

```json
{
  "paths": ["/tmp/gemini-images/imagen-1776443000-ab12cd34.png"],
  "model": "gemini-3.1-flash-image-preview",
  "deprecated": true,
  "deprecation": "gemini_generate_image_imagen is deprecated; Imagen 4 models sunset 2026-08-17. This call was served by gemini-3.1-flash-image-preview. Use gemini_generate_image."
}
```

**Error response:**

```json
{"error": "count must be between 1 and 4", "model": "gemini-3.1-flash-image-preview", "deprecated": true}
```

**Notes:** This tool no longer calls Imagen. `aspect_ratio` is translated into a prompt instruction (the flash-image path has no aspect-ratio config knob), and `count` maps to `candidate_count`. Aspect ratio is therefore prompt-steered, not a hard crop.

---

## `gemini_code_execute`

**Signature:**
```python
gemini_code_execute(prompt: str, model: str | None = None) -> dict
```

Gemini writes Python, runs it in its sandbox, and returns the result.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Question or task |
| `model` | str\|None | None | Resolves to `gemini-3.1-pro-preview-customtools` when unset |

**Success response:**

```json
{
  "answer": "The 100th Fibonacci number is 354224848179261915075.",
  "code": "def fib(n): ...",
  "stdout": "354224848179261915075\n",
  "model": "gemini-3.1-pro-preview-customtools"
}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-3.1-pro-preview-customtools"}
```

---

## `gemini_search_grounded`

**Signature:**
```python
gemini_search_grounded(prompt: str, model: str | None = None) -> dict
```

Text generation grounded with Google Search. Returns answer plus source citations.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Question |
| `model` | str\|None | None | Resolves to `gemini-3.5-flash` when unset |

**Success response:**

```json
{
  "answer": "<answer>",
  "citations": [
    {"url": "https://example.com/a", "title": "Example A"}
  ],
  "model": "gemini-3.5-flash"
}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-3.5-flash"}
```

---

## `gemini_analyze_file`

**Signature:**
```python
gemini_analyze_file(
    file_path: str,
    prompt: str,
    model: str | None = None,
) -> dict
```

Uploads a local file (PDF, image, audio, video) via the Files API and answers a question about it.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `file_path` | str | required | Absolute path to a local file |
| `prompt` | str | required | Question about the file |
| `model` | str\|None | None | Resolves to `gemini-3.1-pro-preview` when unset |

**Success response:**

```json
{
  "answer": "<answer>",
  "file_uri": "files/abc123",
  "model": "gemini-3.1-pro-preview"
}
```

**Error response:**

```json
{"error": "File not found: /bad/path", "model": "gemini-3.1-pro-preview"}
```

**Notes:** Files uploaded to the Files API expire on Google's servers after 48 hours.

---

## `gemini_chat`

**Signature:**
```python
gemini_chat(
    session_id: str,
    message: str,
    system_instruction: str | None = None,
    model: str | None = None,
) -> dict
```

Multi-turn chat keyed by `session_id`. State is held in memory for the server lifetime.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `session_id` | str | required | Arbitrary caller-chosen string; identifies the chat |
| `message` | str | required | Next user message |
| `system_instruction` | str\|None | None | Applied only on first turn; ignored on subsequent calls |
| `model` | str\|None | None | Resolves to `gemini-3.5-flash` when unset; only used when creating a new session |

**Success response:**

```json
{"response": "<reply>", "turn": 3, "model": "gemini-3.5-flash"}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-3.5-flash"}
```

**Notes:** Sessions do not persist across server restarts. There is no way to list or delete sessions; they live until the process exits.

---

## `gemini_start_video`

**Signature:**
```python
gemini_start_video(
    prompt: str,
    aspect_ratio: str = "16:9",
    duration_seconds: int = 5,
    image_path: str | None = None,
    model: str | None = None,
) -> dict
```

Kicks off a Veo video generation. Returns an `operation_id` to poll with `gemini_get_video`.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Text description |
| `aspect_ratio` | str | `"16:9"` | `"16:9"` or `"9:16"` |
| `duration_seconds` | int | 5 | Veo 3.1 accepts roughly 4 to 8 seconds |
| `image_path` | str\|None | None | If set, image-to-video mode; must be a local file |
| `model` | str\|None | None | Resolves to `veo-3.1-generate-preview` when unset (Veo 3.0 IDs sunset 2026-06-30; see [migration guide](migration-v0.2.md)) |

**Success response:**

```json
{
  "operation_id": "a1b2c3d4e5f6",
  "model": "veo-3.1-generate-preview",
  "message": "Video generation started. Poll with gemini_get_video."
}
```

**Error response:**

```json
{"error": "File not found: /path/to/image.png", "model": "veo-3.1-generate-preview"}
```

**Notes:** `operation_id` is invalidated when the server process restarts.

---

## `gemini_get_video`

**Signature:**
```python
gemini_get_video(
    operation_id: str,
    output_dir: str = "/tmp/gemini-videos",
) -> dict
```

Polls a Veo operation. When done, writes the MP4 and returns its path.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `operation_id` | str | required | Returned by `gemini_start_video` |
| `output_dir` | str | `/tmp/gemini-videos` | Created if missing |

**Success responses (one of):**

```json
{"status": "running", "operation_id": "a1b2c3d4e5f6"}
```

```json
{
  "status": "done",
  "path": "/tmp/gemini-videos/veo-1776443060-ab12cd34.mp4",
  "operation_id": "a1b2c3d4e5f6"
}
```

**Error responses (one of):**

```json
{"status": "error", "error": "<message>", "operation_id": "a1b2c3d4e5f6"}
```

```json
{"status": "unknown", "error": "operation_id not found"}
```

**Notes:** Recommended poll interval: 10 to 15 seconds. Total wall time is typically 30 seconds to 3 minutes. The completed operation is popped from memory after the MP4 is saved.


---

## `gemini_generate_music`

**Signature:**
```python
gemini_generate_music(
    prompt: str,
    output_dir: str = "/tmp/gemini-music",
    duration_seconds: int = 30,
    model: str | None = None,
) -> dict
```

Generates music from a text prompt with Lyria 3. Writes a WAV file to `output_dir` and returns its absolute path.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Text description of the desired music |
| `output_dir` | str | `/tmp/gemini-music` | Created if missing |
| `duration_seconds` | int | 30 | Must be > 0. Validated client-side; the model enforces its own upper bound. Currently advisory; the SDK does not yet expose a duration parameter for AUDIO modality, so the model uses prompt-conditioned defaults. |
| `model` | str\|None | None | Resolves to `lyria-3-pro-preview` when unset. Pass `lyria-3-clip-preview` for short loops. |

**Success response:**

```json
{
  "path": "/tmp/gemini-music/lyria-1776443100-ab12cd34.wav",
  "model": "lyria-3-pro-preview"
}
```

**Error responses:**

```json
{"error": "duration_seconds must be > 0", "model": "lyria-3-pro-preview"}
```

```json
{"error": "<sdk message>", "model": "lyria-3-pro-preview"}
```


---

## `gemini_tts`

**Signature:**
```python
gemini_tts(
    text: str,
    output_dir: str = "/tmp/gemini-tts",
    voice: str = "Kore",
    speakers: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> dict
```

Synthesizes speech from text. Single-voice mode by default; pass `speakers` for multi-speaker output.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `text` | str | required | The text to speak. In multi-speaker mode, prefix lines with the speaker name (`"Alice: ...\nBob: ..."`). |
| `output_dir` | str | `/tmp/gemini-tts` | Created if missing |
| `voice` | str | `"Kore"` | Voice name (single-voice mode only). See Google's voice catalog for the full list. |
| `speakers` | list[dict]\|None | None | Multi-speaker mode. Each item is `{"name": "<speaker label>", "voice": "<voice name>"}`. When set, `voice` is ignored. |
| `model` | str\|None | None | Resolves to `gemini-3.1-flash-tts-preview` when unset |

**Success response:**

```json
{
  "path": "/tmp/gemini-tts/tts-1776443200-cd34ef56.wav",
  "model": "gemini-3.1-flash-tts-preview"
}
```

**Error responses:**

```json
{"error": "speakers must be a list of {name, voice} dicts", "model": "gemini-3.1-flash-tts-preview"}
```

```json
{"error": "<sdk message>", "model": "gemini-3.1-flash-tts-preview"}
```


---

## `gemini_start_research`

**Signature:**
```python
gemini_start_research(
    prompt: str,
    model: str | None = None,
) -> dict
```

Starts a Deep Research synthesis. Returns an `operation_id` to poll with `gemini_get_research_report`. Long-running operation; expect minutes, not seconds.

Deep Research runs on the Interactions API, not `generateContent`. The model IDs are *agents*: the server sends them in the `agent` field with `background=True`, because calling `generateContent` on them returns `400 This model only supports Interactions API`. This requires `google-genai>=2.0.0`.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Research question |
| `model` | str\|None | None | Resolves to `deep-research-max-preview-04-2026` when unset. Alternatives: `deep-research-pro-preview-12-2025`, `deep-research-preview-04-2026`. |

**Success response:**

```json
{
  "operation_id": "a1b2c3d4e5f6",
  "model": "deep-research-max-preview-04-2026",
  "message": "Research started. Poll with gemini_get_research_report."
}
```

**Error response:**

```json
{"error": "<message>", "model": "deep-research-max-preview-04-2026"}
```

**Notes:** `operation_id` is the API-side interaction ID, so it stays valid across a server restart.

---

## `gemini_get_research_report`

**Signature:**
```python
gemini_get_research_report(
    operation_id: str,
    output_dir: str = "/tmp/gemini-research",
) -> dict
```

Polls a Deep Research operation. When done, writes the report markdown to disk and returns its path plus the inline text and citations.

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `operation_id` | str | required | Returned by `gemini_start_research` |
| `output_dir` | str | `/tmp/gemini-research` | Created if missing |

**Success responses (one of):**

```json
{"status": "running", "operation_id": "a1b2c3d4e5f6"}
```

```json
{
  "status": "done",
  "path": "/tmp/gemini-research/research-1776443300-ef56ab12.md",
  "report": "# Findings\n\n...",
  "citations": [
    {"url": "https://example.com/a", "title": "Example A"}
  ],
  "operation_id": "a1b2c3d4e5f6"
}
```

**Error responses (one of):**

```json
{"status": "error", "error": "<message>", "operation_id": "a1b2c3d4e5f6"}
```

