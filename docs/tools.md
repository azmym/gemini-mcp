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
| `model` | str\|None | None | Resolves to `gemini-2.5-pro` when unset |

**Success response:**

```json
{"text": "<answer>", "tokens_used": 1234, "model": "gemini-2.5-pro"}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-2.5-pro"}
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
| `model` | str\|None | None | Resolves to `gemini-2.5-flash-image` when unset |

**Success response:**

```json
{
  "paths": ["/tmp/gemini-images/gemini-1713380000-a1b2c3d4.png"],
  "model": "gemini-2.5-flash-image"
}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-2.5-flash-image"}
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

Image generation with Imagen 4 (text-to-image, PNG output).

**Parameters:**

| Param | Type | Default | Notes |
|---|---|---|---|
| `prompt` | str | required | Text description |
| `output_dir` | str | `/tmp/gemini-images` | Created if missing |
| `count` | int | 1 | Must be 1 to 4 inclusive |
| `aspect_ratio` | str | `"1:1"` | One of: `"1:1"`, `"16:9"`, `"9:16"`, `"4:3"`, `"3:4"` |
| `model` | str\|None | None | Resolves to `imagen-4.0-generate-001` when unset |

**Success response:**

```json
{
  "paths": ["/tmp/gemini-images/imagen-1776443000-ab12cd34.png"],
  "model": "imagen-4.0-generate-001"
}
```

**Error response:**

```json
{"error": "count must be between 1 and 4", "model": "imagen-4.0-generate-001"}
```

**Notes:** Imagen 4 uses a different SDK entry point (`client.models.generate_images`) from `gemini_generate_image`.

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
| `model` | str\|None | None | Resolves to `gemini-2.5-pro` when unset |

**Success response:**

```json
{
  "answer": "The 100th Fibonacci number is 354224848179261915075.",
  "code": "def fib(n): ...",
  "stdout": "354224848179261915075\n",
  "model": "gemini-2.5-pro"
}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-2.5-pro"}
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
| `model` | str\|None | None | Resolves to `gemini-2.5-flash` when unset |

**Success response:**

```json
{
  "answer": "<answer>",
  "citations": [
    {"url": "https://example.com/a", "title": "Example A"}
  ],
  "model": "gemini-2.5-flash"
}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-2.5-flash"}
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
| `model` | str\|None | None | Resolves to `gemini-2.5-pro` when unset |

**Success response:**

```json
{
  "answer": "<answer>",
  "file_uri": "files/abc123",
  "model": "gemini-2.5-pro"
}
```

**Error response:**

```json
{"error": "File not found: /bad/path", "model": "gemini-2.5-pro"}
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
| `model` | str\|None | None | Resolves to `gemini-2.5-flash` when unset; only used when creating a new session |

**Success response:**

```json
{"response": "<reply>", "turn": 3, "model": "gemini-2.5-flash"}
```

**Error response:**

```json
{"error": "<message>", "model": "gemini-2.5-flash"}
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
| `duration_seconds` | int | 5 | Veo 3 accepts roughly 4 to 8 seconds |
| `image_path` | str\|None | None | If set, image-to-video mode; must be a local file |
| `model` | str\|None | None | Resolves to `veo-3.0-generate-001` when unset (sunset 2026-06-30, see [migration guide](migration-veo-3.1.md)) |

> **Note:** `veo-3.0-*` and `veo-2.0-*` IDs will return `404 Not Found` after 2026-06-30. Pass `model="veo-3.1-generate-preview"` (or set `GEMINI_DEFAULT_MODEL`) to switch today. See [Migrating to Veo 3.1](migration-veo-3.1.md).

**Success response:**

```json
{
  "operation_id": "a1b2c3d4e5f6",
  "model": "veo-3.0-generate-001",
  "message": "Video generation started. Poll with gemini_get_video."
}
```

**Error response:**

```json
{"error": "File not found: /path/to/image.png", "model": "veo-3.0-generate-001"}
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
