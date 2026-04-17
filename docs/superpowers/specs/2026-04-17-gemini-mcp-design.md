# Gemini MCP Server: Design

**Date:** 2026-04-17
**Status:** Approved

## Problem

Claude Code users need a way to call Google Gemini models directly as MCP tools, with per-call model selection so they can choose the right Gemini model (Flash, Pro, Gemini 3 preview, image, etc.) for each task. No existing MCP server in the user's setup exposes the full range of Gemini capabilities, and the existing `gemini-image` skill only covers image generation through shell-invoked scripts.

## Goals

1. Expose the major Google AI Studio Gemini capabilities as MCP tools: text generation, native image generation, code execution, Google Search grounding, file/document analysis, multi-turn chat.
2. Let the caller pick the model per tool call via a `model` parameter, with sensible stable defaults and an env var override.
3. Keep the project small: a single Python file using FastMCP and the `google-genai` SDK.
4. Run as a stdio MCP server integrated with Claude Code via `claude mcp add`.

## Non-Goals

- Vertex AI support. This server targets Google AI Studio only, authenticated by `GEMINI_API_KEY`.
- Imagen API wrapper. Use Gemini native image models (`gemini-2.5-flash-image`, `gemini-3.1-flash-image-preview`) instead.
- Persisting chat sessions to disk. Sessions live in memory for the lifetime of the server process.
- Publishing to PyPI or a Claude Code marketplace. This is a standalone project in `~/workspace/gemini-mcp/` for personal use.

## Architecture

```
┌──────────────┐         stdio          ┌──────────────────────┐
│ Claude Code  │ <────── JSON-RPC ────> │ gemini-mcp server    │
└──────────────┘                         │  (FastMCP, Python)   │
                                         └──────────┬───────────┘
                                                    │ HTTPS
                                                    ▼
                                         ┌──────────────────────┐
                                         │ Google AI Studio API │
                                         └──────────────────────┘
```

The MCP server is a single Python process launched by Claude Code over stdio. It calls `google-genai` SDK methods against Google AI Studio using the `GEMINI_API_KEY` env var.

## Project Layout

```
~/workspace/gemini-mcp/
├── server.py              # All MCP tools in one file (~250 lines)
├── pyproject.toml         # Deps: fastmcp, google-genai
├── README.md              # Setup, configuration, tool reference
├── .gitignore             # Standard Python
└── docs/
    └── superpowers/
        └── specs/
            └── 2026-04-17-gemini-mcp-design.md
```

## Tools

Each tool returns a structured dict so Claude can cleanly surface the output. All tools accept `model: str` with a default; `GEMINI_DEFAULT_MODEL` overrides all defaults globally.

### `gemini_list_models`

- **Purpose:** List available Gemini models with their supported capabilities.
- **Inputs:** (none)
- **Output:** `[{name: str, input_modalities: [str], output_modalities: [str], supports_code_execution: bool, supports_search_grounding: bool}, ...]`
- **Default model:** n/a (always hits the `list_models` endpoint).

### `gemini_generate`

- **Purpose:** Single-turn text generation.
- **Inputs:** `prompt: str`, `system_instruction: str | None = None`, `temperature: float = 0.7`, `max_output_tokens: int | None = None`, `model: str = "gemini-2.5-pro"`.
- **Output:** `{text: str, model: str, tokens_used: int}`.

### `gemini_generate_image`

- **Purpose:** Generate one or more images from a text prompt using a Gemini native image model.
- **Inputs:** `prompt: str`, `output_dir: str = "/tmp/gemini-images"`, `count: int = 1`, `model: str = "gemini-2.5-flash-image"`.
- **Output:** `{paths: [str], model: str}` (local file paths of saved PNGs).

### `gemini_code_execute`

- **Purpose:** Ask Gemini to write and run Python code in its sandbox to answer the prompt. Returns the final answer plus executed code and stdout.
- **Inputs:** `prompt: str`, `model: str = "gemini-2.5-pro"`.
- **Output:** `{answer: str, code: str, stdout: str, model: str}`.

### `gemini_search_grounded`

- **Purpose:** Text generation grounded with Google Search. Returns the answer plus citations.
- **Inputs:** `prompt: str`, `model: str = "gemini-2.5-flash"`.
- **Output:** `{answer: str, citations: [{url: str, title: str}], model: str}`.

### `gemini_analyze_file`

- **Purpose:** Upload a local file (PDF, image, audio, video) via the Files API and ask Gemini a question about it.
- **Inputs:** `file_path: str`, `prompt: str`, `model: str = "gemini-2.5-pro"`.
- **Output:** `{answer: str, file_uri: str, model: str}`.
- **Notes:** Files auto-expire in 48h on Google's side. The server does not delete them explicitly.

### `gemini_chat`

- **Purpose:** Multi-turn conversation keyed by `session_id`.
- **Inputs:** `session_id: str`, `message: str`, `system_instruction: str | None = None` (set once on first turn), `model: str = "gemini-2.5-flash"`.
- **Output:** `{response: str, turn: int, model: str}`.
- **State:** In-memory dict `sessions: dict[str, Chat]`. Cleared on server restart.

## Configuration

| Env var | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `GEMINI_DEFAULT_MODEL` | No | Overrides every tool's default model |

The server reads these at startup via `os.environ`. If `GEMINI_API_KEY` is missing, the server fails fast with a clear error before accepting any tool calls.

## Installation and Invocation

**Install dependencies (for development):**

```bash
cd ~/workspace/gemini-mcp
uv sync
```

**Register with Claude Code:**

```bash
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -- uvx --from "fastmcp[cli]" fastmcp run ~/workspace/gemini-mcp/server.py
```

This uses `uvx` so there's no virtualenv to maintain. The command Claude Code runs will fetch FastMCP and its deps on first invocation and cache them.

## Error Handling

- SDK exceptions are caught per tool and returned as `{error: str, model: str}` rather than raised. A raised exception would crash the stdio server and disconnect Claude.
- Unknown model names surface the Google API's error message verbatim so the user can correct the `model` argument.
- `gemini_analyze_file` validates the file exists locally before uploading and returns a clear error if not.

## Testing

- Manual smoke tests after implementation:
  1. `gemini_list_models` returns at least one `gemini-2.5-*` entry.
  2. `gemini_generate` with a trivial prompt returns text.
  3. `gemini_generate_image` writes a PNG to the output dir.
  4. `gemini_code_execute` returns executed code and stdout for a math question.
  5. `gemini_search_grounded` returns citations for a current-events query.
  6. `gemini_analyze_file` answers a question about a sample PDF.
  7. `gemini_chat` with the same `session_id` across two calls maintains context.
- No automated test suite for v1. Future work if the server gains shared users.

## Open Questions

None at time of approval.

## Out of Scope Future Work

- Audio output (TTS via Gemini): not yet in stable API.
- Streaming responses: FastMCP supports it; defer until a tool actually benefits.
- Cost/token reporting beyond what each tool already returns.
- Rate limit handling beyond the SDK's built-in retries.
