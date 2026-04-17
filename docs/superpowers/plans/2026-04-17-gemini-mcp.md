# Gemini MCP Server Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a FastMCP-based Gemini MCP server exposing 7 tools (list_models, generate, generate_image, code_execute, search_grounded, analyze_file, chat) with per-call model selection, backed by Google AI Studio via `google-genai`.

**Architecture:** Single Python file (`server.py`) using FastMCP decorators to register tools. Each tool wraps a `google-genai` SDK call. Chat state lives in a module-level dict. Run via `uvx` so users do not need to manage a virtualenv. Configuration via `GEMINI_API_KEY` and optional `GEMINI_DEFAULT_MODEL` env vars.

**Tech Stack:** Python 3.11+, FastMCP 2.x, google-genai SDK, uv/uvx for dependency management, pytest for tests.

---

## File Structure

```
~/workspace/gemini-mcp/
├── server.py                              # All tools (~250 lines)
├── pyproject.toml                         # uv-managed deps
├── README.md                              # Setup and tool reference
├── .gitignore                             # Python standard ignores
├── .python-version                        # 3.11
├── tests/
│   ├── __init__.py
│   ├── conftest.py                        # Shared fixtures
│   ├── test_config.py                     # Config loading tests
│   ├── test_list_models.py                # Model listing tool
│   ├── test_generate.py                   # Text generation tool
│   ├── test_generate_image.py             # Image generation tool
│   ├── test_code_execute.py               # Code execution tool
│   ├── test_search_grounded.py            # Search grounding tool
│   ├── test_analyze_file.py               # File analysis tool
│   └── test_chat.py                       # Chat tool
└── docs/
    └── superpowers/
        ├── specs/2026-04-17-gemini-mcp-design.md
        └── plans/2026-04-17-gemini-mcp.md
```

Each `test_*.py` exercises one tool. `server.py` is split into clearly separated sections (config, client bootstrap, one function per tool, and `mcp.run()` entry point) but kept in one file because each tool is small and the total stays under ~300 lines.

---

## Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.python-version`
- Create: `.gitignore`
- Create: `README.md`

- [ ] **Step 1: Create `.python-version`**

```
3.11
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "gemini-mcp"
version = "0.1.0"
description = "MCP server exposing Google Gemini capabilities via Google AI Studio"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "fastmcp>=2.0.0",
    "google-genai>=0.3.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["."]
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.py[cod]
*.egg-info/
.venv/
.pytest_cache/
dist/
build/
.env
uv.lock
/tmp/gemini-images/
```

- [ ] **Step 4: Create minimal `README.md`**

````markdown
# gemini-mcp

MCP server exposing Google Gemini capabilities (text, image, code execution, search grounding, file analysis, chat) to Claude Code via Google AI Studio.

## Setup

1. Get a key at https://ai.google.dev
2. Register with Claude Code:

```bash
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -- uvx --from "fastmcp[cli]" fastmcp run ~/workspace/gemini-mcp/server.py
```

## Configuration

| Env var | Required | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key |
| `GEMINI_DEFAULT_MODEL` | No | Overrides every tool's default model |

## Tools

See `docs/superpowers/specs/2026-04-17-gemini-mcp-design.md` for the full tool reference.
````

- [ ] **Step 5: Install dependencies**

Run: `cd ~/workspace/gemini-mcp && uv sync --extra dev`
Expected: Creates `.venv/` and lockfile. Exit 0.

- [ ] **Step 6: Commit**

```bash
cd ~/workspace/gemini-mcp
git add pyproject.toml .python-version .gitignore README.md
git commit -m "chore: scaffold gemini-mcp project"
```

---

## Task 2: Test Fixtures (`conftest.py`)

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`

- [ ] **Step 1: Create `tests/__init__.py`**

Empty file. Just needed so pytest treats `tests/` as a package.

```python
```

- [ ] **Step 2: Create `tests/conftest.py`**

```python
"""Shared pytest fixtures for gemini-mcp tests."""
from __future__ import annotations

import os
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def mock_genai_client(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    """Patch google.genai.Client with a MagicMock and return it.

    Tests configure return values on this mock to simulate API responses.
    """
    client = MagicMock()
    monkeypatch.setattr("server._client", client)
    return client


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure every test runs with a fake API key so server imports cleanly."""
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")


@pytest.fixture
def reset_chat_sessions(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the in-memory chat session dict between tests."""
    import server

    monkeypatch.setattr(server, "_sessions", {})
```

- [ ] **Step 3: Commit**

```bash
git add tests/__init__.py tests/conftest.py
git commit -m "test: add shared pytest fixtures"
```

---

## Task 3: Server Module Skeleton and Config Loading

**Files:**
- Create: `server.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write failing test for missing API key**

Create `tests/test_config.py`:

```python
"""Tests for server startup configuration."""
from __future__ import annotations

import importlib

import pytest


def test_server_raises_when_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import server

    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        server._build_client()


def test_default_model_env_overrides_all_tools(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_DEFAULT_MODEL", "gemini-3-flash-preview")
    import server
    importlib.reload(server)

    assert server._resolve_model("gemini-2.5-flash") == "gemini-3-flash-preview"


def test_default_model_env_absent_returns_caller_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GEMINI_DEFAULT_MODEL", raising=False)
    import server
    importlib.reload(server)

    assert server._resolve_model("gemini-2.5-flash") == "gemini-2.5-flash"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd ~/workspace/gemini-mcp && uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'server'`.

- [ ] **Step 3: Create `server.py` skeleton**

```python
"""Gemini MCP server.

Exposes Google Gemini (via Google AI Studio) as MCP tools.
Run with: uvx --from "fastmcp[cli]" fastmcp run server.py
"""
from __future__ import annotations

import os
from typing import Any

from fastmcp import FastMCP
from google import genai

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


if __name__ == "__main__":
    _ensure_client()
    mcp.run()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd ~/workspace/gemini-mcp && uv run pytest tests/test_config.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_config.py
git commit -m "feat: add server skeleton with config loading"
```

---

## Task 4: `gemini_list_models` Tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_list_models.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_list_models.py`:

```python
"""Tests for gemini_list_models tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def test_list_models_returns_entries_with_capabilities(mock_genai_client: MagicMock) -> None:
    fake_model = SimpleNamespace(
        name="models/gemini-2.5-flash",
        supported_actions=["generateContent", "countTokens"],
        input_token_limit=1_000_000,
        output_token_limit=8_192,
    )
    mock_genai_client.models.list.return_value = [fake_model]

    import server

    result = server.gemini_list_models.fn()

    assert isinstance(result, list)
    assert result[0]["name"] == "gemini-2.5-flash"
    assert result[0]["input_token_limit"] == 1_000_000
    assert result[0]["output_token_limit"] == 8_192


def test_list_models_strips_models_prefix(mock_genai_client: MagicMock) -> None:
    fake_model = SimpleNamespace(
        name="models/gemini-3-flash-preview",
        supported_actions=[],
        input_token_limit=0,
        output_token_limit=0,
    )
    mock_genai_client.models.list.return_value = [fake_model]

    import server

    result = server.gemini_list_models.fn()

    assert result[0]["name"] == "gemini-3-flash-preview"


def test_list_models_wraps_sdk_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.list.side_effect = RuntimeError("api down")

    import server

    result = server.gemini_list_models.fn()

    assert isinstance(result, dict)
    assert "error" in result
    assert "api down" in result["error"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_list_models.py -v`
Expected: FAIL with `AttributeError: module 'server' has no attribute 'gemini_list_models'`.

- [ ] **Step 3: Add tool to `server.py` (append after `_ensure_client`)**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_list_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_list_models.py
git commit -m "feat: add gemini_list_models tool"
```

---

## Task 5: `gemini_generate` Tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_generate.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_generate.py`:

```python
"""Tests for gemini_generate tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_response(text: str, total_tokens: int = 42) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        usage_metadata=SimpleNamespace(total_token_count=total_tokens),
    )


def test_generate_returns_text_and_tokens(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_response("hello world", 11)

    import server

    result = server.gemini_generate.fn(prompt="hi")

    assert result["text"] == "hello world"
    assert result["tokens_used"] == 11
    assert result["model"] == "gemini-2.5-pro"


def test_generate_respects_model_parameter(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_response("ok")

    import server

    result = server.gemini_generate.fn(prompt="hi", model="gemini-2.5-flash")

    call_kwargs = mock_genai_client.models.generate_content.call_args.kwargs
    assert call_kwargs["model"] == "gemini-2.5-flash"
    assert result["model"] == "gemini-2.5-flash"


def test_generate_passes_system_instruction_and_temperature(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_response("ok")

    import server

    server.gemini_generate.fn(
        prompt="hi",
        system_instruction="be terse",
        temperature=0.2,
        max_output_tokens=100,
    )

    config = mock_genai_client.models.generate_content.call_args.kwargs["config"]
    assert config.system_instruction == "be terse"
    assert config.temperature == 0.2
    assert config.max_output_tokens == 100


def test_generate_wraps_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("quota")

    import server

    result = server.gemini_generate.fn(prompt="hi")

    assert result == {"error": "quota", "model": "gemini-2.5-pro"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generate.py -v`
Expected: FAIL with missing attribute.

- [ ] **Step 3: Add tool to `server.py`**

```python
from google.genai import types as genai_types


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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_generate.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_generate.py
git commit -m "feat: add gemini_generate tool"
```

---

## Task 6: `gemini_generate_image` Tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_generate_image.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_generate_image.py`:

```python
"""Tests for gemini_generate_image tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_image_response(num_images: int = 1) -> SimpleNamespace:
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    parts = [
        SimpleNamespace(inline_data=SimpleNamespace(data=png_bytes, mime_type="image/png"))
        for _ in range(num_images)
    ]
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts))
    return SimpleNamespace(candidates=[candidate])


def test_generate_image_writes_png(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response()

    import server

    result = server.gemini_generate_image.fn(
        prompt="a cat", output_dir=str(tmp_path), count=1
    )

    assert len(result["paths"]) == 1
    assert Path(result["paths"][0]).exists()
    assert Path(result["paths"][0]).read_bytes().startswith(b"\x89PNG")
    assert result["model"] == "gemini-2.5-flash-image"


def test_generate_image_count_multiple(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response(num_images=3)

    import server

    result = server.gemini_generate_image.fn(
        prompt="cats", output_dir=str(tmp_path), count=3
    )

    assert len(result["paths"]) == 3
    for p in result["paths"]:
        assert Path(p).exists()


def test_generate_image_creates_output_dir(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_image_response()
    nested = tmp_path / "nested" / "dir"

    import server

    result = server.gemini_generate_image.fn(
        prompt="a cat", output_dir=str(nested), count=1
    )

    assert nested.exists()
    assert Path(result["paths"][0]).parent == nested


def test_generate_image_wraps_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("no image")

    import server

    result = server.gemini_generate_image.fn(
        prompt="x", output_dir=str(tmp_path), count=1
    )

    assert result == {"error": "no image", "model": "gemini-2.5-flash-image"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_generate_image.py -v`
Expected: FAIL with missing attribute.

- [ ] **Step 3: Add tool to `server.py`**

Add these imports at the top (near existing imports):

```python
import time
import uuid
from pathlib import Path
```

Append the tool:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_generate_image.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_generate_image.py
git commit -m "feat: add gemini_generate_image tool"
```

---

## Task 7: `gemini_code_execute` Tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_code_execute.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_code_execute.py`:

```python
"""Tests for gemini_code_execute tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_code_response(answer: str, code: str, stdout: str) -> SimpleNamespace:
    parts = [
        SimpleNamespace(text=None, executable_code=SimpleNamespace(code=code), code_execution_result=None),
        SimpleNamespace(text=None, executable_code=None, code_execution_result=SimpleNamespace(output=stdout)),
        SimpleNamespace(text=answer, executable_code=None, code_execution_result=None),
    ]
    candidate = SimpleNamespace(content=SimpleNamespace(parts=parts))
    return SimpleNamespace(candidates=[candidate], text=answer)


def test_code_execute_extracts_code_stdout_and_answer(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_code_response(
        answer="The answer is 42.",
        code="print(21 * 2)",
        stdout="42",
    )

    import server

    result = server.gemini_code_execute.fn(prompt="what is 21*2?")

    assert result["answer"] == "The answer is 42."
    assert "21 * 2" in result["code"]
    assert result["stdout"] == "42"
    assert result["model"] == "gemini-2.5-pro"


def test_code_execute_enables_code_execution_tool(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_code_response("ans", "code", "out")

    import server

    server.gemini_code_execute.fn(prompt="hi")

    config = mock_genai_client.models.generate_content.call_args.kwargs["config"]
    assert config.tools  # at least one tool
    assert any(getattr(t, "code_execution", None) is not None for t in config.tools)


def test_code_execute_wraps_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("nope")

    import server

    result = server.gemini_code_execute.fn(prompt="hi")

    assert result == {"error": "nope", "model": "gemini-2.5-pro"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_code_execute.py -v`
Expected: FAIL with missing attribute.

- [ ] **Step 3: Add tool to `server.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_code_execute.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_code_execute.py
git commit -m "feat: add gemini_code_execute tool"
```

---

## Task 8: `gemini_search_grounded` Tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_search_grounded.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_search_grounded.py`:

```python
"""Tests for gemini_search_grounded tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_grounded_response(answer: str, urls: list[tuple[str, str]]) -> SimpleNamespace:
    chunks = [
        SimpleNamespace(web=SimpleNamespace(uri=u, title=t))
        for u, t in urls
    ]
    grounding_metadata = SimpleNamespace(grounding_chunks=chunks)
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text=answer)]),
        grounding_metadata=grounding_metadata,
    )
    return SimpleNamespace(candidates=[candidate], text=answer)


def test_search_grounded_returns_answer_and_citations(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_grounded_response(
        answer="Paris is the capital of France.",
        urls=[("https://example.com/a", "Example A"), ("https://example.com/b", "Example B")],
    )

    import server

    result = server.gemini_search_grounded.fn(prompt="capital of France?")

    assert result["answer"] == "Paris is the capital of France."
    assert result["citations"] == [
        {"url": "https://example.com/a", "title": "Example A"},
        {"url": "https://example.com/b", "title": "Example B"},
    ]
    assert result["model"] == "gemini-2.5-flash"


def test_search_grounded_enables_search_tool(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.return_value = _fake_grounded_response("ok", [])

    import server

    server.gemini_search_grounded.fn(prompt="hi")

    config = mock_genai_client.models.generate_content.call_args.kwargs["config"]
    assert any(getattr(t, "google_search", None) is not None for t in config.tools)


def test_search_grounded_handles_missing_metadata(mock_genai_client: MagicMock) -> None:
    candidate = SimpleNamespace(
        content=SimpleNamespace(parts=[SimpleNamespace(text="ok")]),
        grounding_metadata=None,
    )
    mock_genai_client.models.generate_content.return_value = SimpleNamespace(
        candidates=[candidate], text="ok"
    )

    import server

    result = server.gemini_search_grounded.fn(prompt="hi")

    assert result["citations"] == []


def test_search_grounded_wraps_errors(mock_genai_client: MagicMock) -> None:
    mock_genai_client.models.generate_content.side_effect = RuntimeError("search down")

    import server

    result = server.gemini_search_grounded.fn(prompt="hi")

    assert result == {"error": "search down", "model": "gemini-2.5-flash"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_search_grounded.py -v`
Expected: FAIL with missing attribute.

- [ ] **Step 3: Add tool to `server.py`**

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_search_grounded.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_search_grounded.py
git commit -m "feat: add gemini_search_grounded tool"
```

---

## Task 9: `gemini_analyze_file` Tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_analyze_file.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_analyze_file.py`:

```python
"""Tests for gemini_analyze_file tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_text_response(text: str) -> SimpleNamespace:
    return SimpleNamespace(text=text, usage_metadata=None)


def test_analyze_file_uploads_and_asks(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")

    uploaded = SimpleNamespace(uri="files/abc123", name="files/abc123", mime_type="application/pdf")
    mock_genai_client.files.upload.return_value = uploaded
    mock_genai_client.models.generate_content.return_value = _fake_text_response("summary here")

    import server

    result = server.gemini_analyze_file.fn(
        file_path=str(pdf), prompt="summarize"
    )

    mock_genai_client.files.upload.assert_called_once()
    upload_kwargs = mock_genai_client.files.upload.call_args.kwargs
    assert str(pdf) == upload_kwargs.get("file") or upload_kwargs.get("path")
    assert result["answer"] == "summary here"
    assert result["file_uri"] == "files/abc123"
    assert result["model"] == "gemini-2.5-pro"


def test_analyze_file_returns_error_when_file_missing(mock_genai_client: MagicMock) -> None:
    import server

    result = server.gemini_analyze_file.fn(
        file_path="/tmp/does-not-exist-abcxyz.pdf", prompt="x"
    )

    assert "error" in result
    assert "not found" in result["error"].lower()
    mock_genai_client.files.upload.assert_not_called()


def test_analyze_file_wraps_sdk_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    pdf = tmp_path / "doc.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    mock_genai_client.files.upload.side_effect = RuntimeError("upload failed")

    import server

    result = server.gemini_analyze_file.fn(
        file_path=str(pdf), prompt="x"
    )

    assert result == {"error": "upload failed", "model": "gemini-2.5-pro"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analyze_file.py -v`
Expected: FAIL with missing attribute.

- [ ] **Step 3: Add tool to `server.py`**

```python
@mcp.tool()
def gemini_analyze_file(
    file_path: str,
    prompt: str,
    model: str = "gemini-2.5-pro",
) -> dict[str, Any]:
    """Upload a local file (PDF, image, audio, video) and ask Gemini about it."""
    chosen = _resolve_model(model)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_analyze_file.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_analyze_file.py
git commit -m "feat: add gemini_analyze_file tool"
```

---

## Task 10: `gemini_chat` Tool

**Files:**
- Modify: `server.py`
- Create: `tests/test_chat.py`

- [ ] **Step 1: Write failing test**

Create `tests/test_chat.py`:

```python
"""Tests for gemini_chat tool."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def test_chat_creates_session_on_first_call(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.return_value = SimpleNamespace(text="hello back")
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    result = server.gemini_chat.fn(session_id="s1", message="hi")

    mock_genai_client.chats.create.assert_called_once()
    assert result["response"] == "hello back"
    assert result["turn"] == 1
    assert "s1" in server._sessions


def test_chat_reuses_existing_session(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.side_effect = [
        SimpleNamespace(text="reply 1"),
        SimpleNamespace(text="reply 2"),
    ]
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    server.gemini_chat.fn(session_id="s2", message="msg 1")
    result2 = server.gemini_chat.fn(session_id="s2", message="msg 2")

    assert mock_genai_client.chats.create.call_count == 1
    assert chat_mock.send_message.call_count == 2
    assert result2["response"] == "reply 2"
    assert result2["turn"] == 2


def test_chat_passes_system_instruction_on_first_turn(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.return_value = SimpleNamespace(text="ok")
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    server.gemini_chat.fn(
        session_id="s3", message="hi", system_instruction="be formal"
    )

    create_kwargs = mock_genai_client.chats.create.call_args.kwargs
    config = create_kwargs["config"]
    assert config.system_instruction == "be formal"


def test_chat_wraps_errors(
    mock_genai_client: MagicMock, reset_chat_sessions: None
) -> None:
    chat_mock = MagicMock()
    chat_mock.send_message.side_effect = RuntimeError("chat down")
    mock_genai_client.chats.create.return_value = chat_mock

    import server

    result = server.gemini_chat.fn(session_id="s4", message="hi")

    assert result == {"error": "chat down", "model": "gemini-2.5-flash"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_chat.py -v`
Expected: FAIL with missing attribute.

- [ ] **Step 3: Add tool to `server.py`**

```python
@mcp.tool()
def gemini_chat(
    session_id: str,
    message: str,
    system_instruction: str | None = None,
    model: str = "gemini-2.5-flash",
) -> dict[str, Any]:
    """Multi-turn chat keyed by session_id. State lives in memory for server lifetime."""
    chosen = _resolve_model(model)
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_chat.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_chat.py
git commit -m "feat: add gemini_chat tool"
```

---

## Task 11: Full Test Suite Verification

**Files:** (no changes)

- [ ] **Step 1: Run the whole suite**

Run: `cd ~/workspace/gemini-mcp && uv run pytest -v`
Expected: All tests pass (~22 tests total across 7 files plus config).

- [ ] **Step 2: Verify the server imports cleanly**

Run: `cd ~/workspace/gemini-mcp && GEMINI_API_KEY=dummy uv run python -c "import server; print(sorted(t for t in dir(server) if t.startswith('gemini_')))"`
Expected output:
```
['gemini_analyze_file', 'gemini_chat', 'gemini_code_execute', 'gemini_generate', 'gemini_generate_image', 'gemini_list_models', 'gemini_search_grounded']
```

- [ ] **Step 3: Commit any formatting tweaks if needed**

```bash
git status
# If clean: skip this step
```

---

## Task 12: Manual Smoke Test Checklist

Run these with a real `GEMINI_API_KEY` in the shell. These are not automated; they verify the server actually talks to Gemini.

**Files:** (no changes)

- [ ] **Step 1: Start the server standalone**

Run: `cd ~/workspace/gemini-mcp && GEMINI_API_KEY=<real-key> uv run fastmcp run server.py --transport stdio < /dev/null`
Expected: Server starts, reads no stdin, exits cleanly on EOF.

- [ ] **Step 2: Register with Claude Code**

```bash
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<real-key> \
  -- uvx --from "fastmcp[cli]" fastmcp run ~/workspace/gemini-mcp/server.py
```
Expected: "Added stdio MCP server gemini ..."

- [ ] **Step 3: Verify connection**

Run: `claude mcp list`
Expected: `gemini: uvx --from "fastmcp[cli]" fastmcp run ~/workspace/gemini-mcp/server.py - ✓ Connected`

- [ ] **Step 4: Smoke-test each tool from within Claude Code**

In a Claude Code session, ask Claude to call each tool once:

1. Call `gemini_list_models` - expect a list containing `gemini-2.5-flash`.
2. Call `gemini_generate` with prompt "say hi" - expect non-empty `text`.
3. Call `gemini_generate_image` with prompt "a red apple on a white background" - expect a PNG at the returned path.
4. Call `gemini_code_execute` with prompt "what is 17 * 23?" - expect `stdout` containing "391".
5. Call `gemini_search_grounded` with prompt "who won Wimbledon men's singles in 2024?" - expect `citations` with at least one URL.
6. Call `gemini_analyze_file` with a local PDF path and prompt "summarize in one sentence" - expect non-empty `answer`.
7. Call `gemini_chat` twice with `session_id="smoke"`, second call referencing the first - expect coherent follow-up.

- [ ] **Step 5: If all 7 tools return expected results, final commit**

```bash
cd ~/workspace/gemini-mcp
git log --oneline | head -15
# Confirm commit history is clean.
```

---

## Self-Review Notes

Spec coverage confirmed: every tool listed in the spec has a matching task. Configuration (both env vars), error handling (structured `{error, model}` returns), in-memory chat sessions, and installation command all covered. No placeholders, no TBDs, consistent naming (`_resolve_model`, `_ensure_client`, `_sessions`, `_client` used the same way across tasks). Tests mock the `google.genai` SDK at the `server._client` boundary so the suite runs offline.
