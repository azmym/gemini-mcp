# gemini-mcp

An MCP server that exposes Google Gemini capabilities to Claude Code and other MCP clients via the Google AI Studio API.

![Python](https://img.shields.io/badge/python-3.11%2B-blue?logo=python&logoColor=white)
![License](https://img.shields.io/badge/license-MIT-green)

## Overview

`gemini-mcp` wraps the Google AI Studio API as a set of MCP tools, making Gemini models directly callable from within Claude Code (or any MCP-compatible client). It supports single-turn text generation, image generation, Python code execution in Gemini's sandbox, Google Search-grounded responses, multi-modal file analysis, and persistent multi-turn chat sessions. No Vertex AI account or Anthropic API key is required.

## Features

| Tool | Default model | Purpose |
|---|---|---|
| `gemini_list_models` | n/a | Lists available Gemini models with capabilities and token limits |
| `gemini_generate` | `gemini-2.5-pro` | Single-turn text generation with optional system prompt and sampling controls |
| `gemini_generate_image` | `gemini-2.5-flash-image` | Native image generation; writes PNG files to a local output directory |
| `gemini_code_execute` | `gemini-2.5-pro` | Gemini writes and runs Python in its sandbox; returns answer, code, and stdout |
| `gemini_search_grounded` | `gemini-2.5-flash` | Text generation grounded with Google Search; returns answer and citations |
| `gemini_analyze_file` | `gemini-2.5-pro` | Uploads a local file (PDF, image, audio, video) via the Files API and answers a question about it |
| `gemini_chat` | `gemini-2.5-flash` | Multi-turn chat keyed by `session_id`; state is held in memory for the server lifetime |

Every tool accepts a `model` parameter to override the default for that call. Set `GEMINI_DEFAULT_MODEL` to override every tool's default globally.

## Requirements

- Python 3.11 or later
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A Google AI Studio API key from https://aistudio.google.com/app/apikey

## Installation

Pick the approach that matches how you plan to use the server. Options A and B register the `gemini` MCP server with Claude Code; Option C is a manual standalone run for verification.

### Option A: install directly from GitHub (no local clone)

Best for most users. `uvx` fetches the repository, installs dependencies into an isolated cache, and runs the `gemini-mcp` entry point registered in `pyproject.toml`. Replace `<your-key>` with your Google AI Studio API key.

```bash
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -- uvx --from git+https://github.com/azmym/gemini-mcp gemini-mcp
```

On first invocation `uvx` clones the repo and installs `fastmcp` and `google-genai` (roughly 5 to 15 seconds cold start); subsequent calls are instant thanks to the uv cache. To upgrade to the latest `main`, run:

```bash
uvx --from git+https://github.com/azmym/gemini-mcp --refresh gemini-mcp --help
```

You can also pin to a specific tag or commit by appending `@<ref>`, for example `git+https://github.com/azmym/gemini-mcp@v0.1.0`.

### Option B: run from a local clone (best for development)

Use this when you want to edit the code and iterate quickly. Replace `/path/to/gemini-mcp` with the absolute path where you cloned the repository.

```bash
git clone https://github.com/azmym/gemini-mcp
cd gemini-mcp
uv sync

claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -- uv --directory /path/to/gemini-mcp run python server.py
```

Changes to `server.py` take effect the next time Claude Code restarts the MCP server.

### Option C: standalone manual run (testing without Claude Code)

Launch the server directly to verify the environment is correct. The process speaks the MCP stdio transport and waits for a client to connect.

```bash
cd /path/to/gemini-mcp
GEMINI_API_KEY=<your-key> uv run python server.py
```

After registering with Option A or B, verify the connection:

```bash
claude mcp list
# Expected: gemini: ... - ✓ Connected
```

## Configuration

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key (https://aistudio.google.com/app/apikey) |
| `GEMINI_DEFAULT_MODEL` | No | Overrides the default model for every tool globally |

## Model selection

Every tool accepts a `model` parameter, so you can pick a different Gemini model for each call without changing any configuration. This is the recommended way to work with the server: defaults are tuned for the common case, and you override them only when a specific task benefits from a different model.

Resolution order, from highest to lowest priority:

1. The `model` argument on the individual tool call.
2. The `GEMINI_DEFAULT_MODEL` environment variable, if set.
3. The tool's built-in default (see the Features table above).

### Choosing per call

Pass `model` explicitly when you want a specific model for that call. The defaults stay untouched.

```text
Tool: gemini_generate
  prompt: "Explain CAP theorem in two paragraphs."
  model: "gemini-3.1-pro-preview"
```

```text
Tool: gemini_generate_image
  prompt: "Product photo of a wireless headset on a studio backdrop"
  model: "gemini-3-pro-image-preview"
```

Call `gemini_list_models` to see every model your API key can access:

```text
Tool: gemini_list_models
```

### Common choices

| Goal | Model |
|---|---|
| Fast, cheap chat or short answers | `gemini-2.5-flash` |
| Strongest stable reasoning, code, analysis | `gemini-2.5-pro` |
| Latest preview, advanced reasoning | `gemini-3.1-pro-preview` |
| Fast preview variant | `gemini-3-flash-preview` |
| Stable image generation | `gemini-2.5-flash-image` |
| Preview image generation | `gemini-3-pro-image-preview` or `gemini-3.1-flash-image-preview` |
| Grounded answers with citations | `gemini-2.5-flash` (fast) or `gemini-2.5-pro` (thorough) |

Preview models can change behavior or availability without notice. Stick to the stable models for workflows you rely on; use previews for experimentation.

### Changing the global default

If you want one model everywhere without passing it on every call, set `GEMINI_DEFAULT_MODEL` on the MCP server entry. For Claude Code users, re-add the server with the extra env flag:

```bash
claude mcp remove gemini -s user
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -e GEMINI_DEFAULT_MODEL=gemini-3-flash-preview \
  -- uvx --from git+https://github.com/azmym/gemini-mcp gemini-mcp
```

Explicit `model` arguments on individual tool calls still win over the env var.

## Usage examples

### Analyze a PDF

Ask Gemini to read a local PDF and summarize it:

```text
Tool: gemini_analyze_file
  file_path: "/home/user/docs/report.pdf"
  prompt: "Summarize the key findings in three bullet points."
  model: "gemini-2.5-pro"
```

Example response:

```json
{
  "answer": "1. Revenue grew 18% year-on-year...\n2. Operational costs declined...\n3. Outlook for next quarter...",
  "file_uri": "files/abc123",
  "model": "gemini-2.5-pro"
}
```

Files uploaded via the Files API expire automatically on Google's servers after 48 hours.

### Generate image variations

Generate three product image variations from a prompt:

```text
Tool: gemini_generate_image
  prompt: "A minimalist product shot of a ceramic coffee mug on a white surface, soft natural light"
  output_dir: "/tmp/gemini-images"
  count: 3
```

Example response:

```json
{
  "paths": [
    "/tmp/gemini-images/gemini-1713380000-a1b2c3d4.png",
    "/tmp/gemini-images/gemini-1713380000-e5f6a7b8.png",
    "/tmp/gemini-images/gemini-1713380000-c9d0e1f2.png"
  ],
  "model": "gemini-2.5-flash-image"
}
```

### Search-grounded query with citations

Ask a question that benefits from up-to-date web data:

```text
Tool: gemini_search_grounded
  prompt: "What is the latest stable release of Python?"
```

Example response:

```json
{
  "answer": "As of April 2025, the latest stable Python release is 3.13.3...",
  "citations": [
    {"url": "https://www.python.org/downloads/", "title": "Download Python"},
    {"url": "https://docs.python.org/3/whatsnew/3.13.html", "title": "What's New in Python 3.13"}
  ],
  "model": "gemini-2.5-flash"
}
```

## Available Gemini models

Call `gemini_list_models` to retrieve the full list of models your API key can access, along with supported actions and token limits:

```text
Tool: gemini_list_models
```

The server can use any model string accepted by the Google AI Studio API. At the time of writing, this includes Gemini 3 preview models (such as `gemini-3.1-pro-preview`), Imagen 4 for image generation, and Veo 3 for video generation. Pass the model name explicitly in any tool call to use a non-default model.

## Development

### Setup

```bash
git clone https://github.com/azmym/gemini-mcp
cd gemini-mcp
uv sync --extra dev
```

### Running tests

Tests are fully offline: `google.genai` is mocked at the client boundary so no API key is needed.

```bash
uv run pytest
```

All 31 unit tests should pass. The test suite sets `FASTMCP_DECORATOR_MODE=object` via `tests/conftest.py` (see Known limitations below).

## Project structure

```text
gemini-mcp/
├── server.py          # All MCP tool definitions and the `main()` entry point
├── pyproject.toml     # Project metadata, dependencies, and `gemini-mcp` script
├── tests/             # 31 unit tests (offline, mocked)
└── docs/
    └── superpowers/
        ├── specs/     # Design specification
        └── plans/     # Implementation plan
```

The `gemini-mcp` console script is registered under `[project.scripts]` in `pyproject.toml` and points to `server:main`. This is what makes Option A above work: `uvx` installs the package, exposes the `gemini-mcp` command, and runs it.

## Known limitations

- **Chat session state is in-memory.** All `gemini_chat` sessions are lost when the server process restarts. There is no persistence layer.
- **`gemini_list_models` has no `model` parameter.** On API error it returns `{"error": "...", "model": "n/a"}` rather than a model name, because no model is involved in the call.
- **Tests require `FASTMCP_DECORATOR_MODE=object`.** This environment variable (set in `tests/conftest.py`) enables a FastMCP v2 compatibility mode (deprecated in FastMCP 3.x) that allows tests to access `.fn` on decorated tool functions. This is a test-only concern and does not affect production behavior.
- **Google AI Studio only.** This server does not support Vertex AI. The `GEMINI_API_KEY` must be a Google AI Studio key.

## Contributing

Issues and pull requests are welcome. If you find a bug or want to propose a new tool, open an issue first to discuss the approach. For code changes, fork the repository, create a feature branch, and open a PR against `main`. Please include or update tests as appropriate.

## License

MIT. See the LICENSE file for details.
