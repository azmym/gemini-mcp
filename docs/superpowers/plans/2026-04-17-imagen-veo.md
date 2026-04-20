# Imagen + Veo Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 3 new MCP tools to gemini-mcp: `gemini_generate_image_imagen` (sync Imagen 4 image generation), `gemini_start_video` (starts Veo long-running operation, returns operation_id), and `gemini_get_video` (polls operation, saves MP4 when done).

**Architecture:** Append three `@mcp.tool()` functions to `server.py`. Add a module-level dict `_video_ops: dict[str, Any] = {}` for in-memory storage of in-flight Veo operations keyed by a short UUID. Follow the existing server pattern: `_resolve_model` for model selection, structured `{error, model}` returns, no exceptions crossing the stdio boundary.

**Tech Stack:** Python 3.11+, FastMCP 3.x, google-genai SDK (`client.models.generate_images`, `client.models.generate_videos`, `client.operations.get`), pytest, uv.

---

## File Structure

```
~/workspace/gemini-mcp/
├── server.py                           # Append 3 tools + _video_ops dict
├── tests/
│   ├── conftest.py                     # Add reset_video_ops fixture
│   ├── test_generate_image_imagen.py   # NEW
│   ├── test_start_video.py             # NEW
│   └── test_get_video.py               # NEW
├── README.md                           # Update Features table + usage example + test count
└── docs/superpowers/
    ├── specs/2026-04-17-imagen-veo-design.md
    └── plans/2026-04-17-imagen-veo.md
```

One new state dict in `server.py`. One new fixture in `conftest.py`. Three new test files. README updates in a final commit.

---

## Task 1: Feature branch + fixtures foundation

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Create feature branch**

```bash
cd /Users/mahmoud.ibrahim/workspace/gemini-mcp
git checkout main
git pull origin main
git checkout -b feat/imagen-veo
```

- [ ] **Step 2: Add `reset_video_ops` fixture to `tests/conftest.py`**

Open `tests/conftest.py`. Append after the existing `reset_chat_sessions` fixture:

```python
@pytest.fixture
def reset_video_ops(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clear the in-memory Veo operations dict between tests."""
    import server

    monkeypatch.setattr(server, "_video_ops", {})
```

- [ ] **Step 3: Verify existing suite still passes**

Run: `cd /Users/mahmoud.ibrahim/workspace/gemini-mcp && uv run pytest -v`
Expected: `31 passed`.

- [ ] **Step 4: Commit**

```bash
cd /Users/mahmoud.ibrahim/workspace/gemini-mcp
git add tests/conftest.py
git commit -m "test: add reset_video_ops fixture"
```

---

## Task 2: Add `_video_ops` module state

**Files:**
- Modify: `server.py` (near existing `_sessions`)

- [ ] **Step 1: Add failing smoke test**

Append to `tests/test_config.py`:

```python
def test_video_ops_dict_exists() -> None:
    """The module-level _video_ops dict must exist for video operation tracking."""
    import server

    assert hasattr(server, "_video_ops")
    assert isinstance(server._video_ops, dict)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mahmoud.ibrahim/workspace/gemini-mcp && uv run pytest tests/test_config.py::test_video_ops_dict_exists -v`
Expected: FAIL with `AttributeError: module 'server' has no attribute '_video_ops'`.

- [ ] **Step 3: Add `_video_ops` to `server.py`**

Find the line `_sessions: dict[str, Any] = {}` in `server.py`. Add a new line directly below it:

```python
_video_ops: dict[str, Any] = {}
```

The two lines together should look like:

```python
_sessions: dict[str, Any] = {}
_video_ops: dict[str, Any] = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py::test_video_ops_dict_exists -v`
Expected: PASS.

- [ ] **Step 5: Run full suite**

Run: `uv run pytest -v`
Expected: 32 passed.

- [ ] **Step 6: Commit**

```bash
git add server.py tests/test_config.py
git commit -m "feat: add _video_ops module state for Veo operations"
```

---

## Task 3: Add imports required by later tools

**Files:**
- Modify: `server.py` (top imports)

- [ ] **Step 1: Check current imports**

Run: `cd /Users/mahmoud.ibrahim/workspace/gemini-mcp && head -20 server.py`
Expected: Confirms `time`, `uuid`, `Path`, `os`, `Any`, `FastMCP`, `genai`, `genai_types` are already present (all were added in previous tasks).

- [ ] **Step 2: No new imports needed**

All SDK types (`genai_types.GenerateImagesConfig`, `genai_types.GenerateVideosConfig`, `genai_types.Image`) are already accessible through `genai_types`. All stdlib imports are present. Skip to Task 4.

---

## Task 4: `gemini_generate_image_imagen` - success path test

**Files:**
- Create: `tests/test_generate_image_imagen.py`

- [ ] **Step 1: Create test file with first failing test**

Create `tests/test_generate_image_imagen.py`:

```python
"""Tests for gemini_generate_image_imagen tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def _fake_images_response(num: int = 1) -> SimpleNamespace:
    png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32
    images = [
        SimpleNamespace(image=SimpleNamespace(image_bytes=png))
        for _ in range(num)
    ]
    return SimpleNamespace(generated_images=images)


def test_imagen_writes_png(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=1)

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="a cat",
        output_dir=str(tmp_path),
        count=1,
    )

    assert len(result["paths"]) == 1
    written = Path(result["paths"][0])
    assert written.exists()
    assert written.read_bytes().startswith(b"\x89PNG")
    assert written.name.startswith("imagen-")
    assert result["model"] == "imagen-4.0-generate-001"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd /Users/mahmoud.ibrahim/workspace/gemini-mcp && uv run pytest tests/test_generate_image_imagen.py::test_imagen_writes_png -v`
Expected: FAIL with `AttributeError: module 'server' has no attribute 'gemini_generate_image_imagen'`.

- [ ] **Step 3: Add the tool to `server.py`**

In `server.py`, find the `gemini_generate_image` tool (the existing one). Directly after its closing brace (the line with `return {"error": str(exc), "model": chosen}` followed by a blank line), append the new tool:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_generate_image_imagen.py::test_imagen_writes_png -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_generate_image_imagen.py
git commit -m "feat: add gemini_generate_image_imagen tool"
```

---

## Task 5: `gemini_generate_image_imagen` - config and error paths

**Files:**
- Modify: `tests/test_generate_image_imagen.py`

- [ ] **Step 1: Append four more tests**

Append to `tests/test_generate_image_imagen.py`:

```python
def test_imagen_passes_count_and_aspect_ratio(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=3)

    import server

    server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=3,
        aspect_ratio="16:9",
    )

    call_kwargs = mock_genai_client.models.generate_images.call_args.kwargs
    config = call_kwargs["config"]
    assert config.number_of_images == 3
    assert config.aspect_ratio == "16:9"
    assert config.output_mime_type == "image/png"


def test_imagen_creates_output_dir(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=1)
    nested = tmp_path / "nested" / "imagen"

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(nested),
        count=1,
    )

    assert nested.exists()
    assert Path(result["paths"][0]).parent == nested


def test_imagen_rejects_bad_count(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=5,
    )

    assert "error" in result
    assert "count must be between 1 and 4" in result["error"]
    mock_genai_client.models.generate_images.assert_not_called()


def test_imagen_wraps_errors(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.side_effect = RuntimeError("quota exceeded")

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=1,
    )

    assert result == {"error": "quota exceeded", "model": "imagen-4.0-generate-001"}


def test_imagen_model_override(
    tmp_path: Path, mock_genai_client: MagicMock
) -> None:
    mock_genai_client.models.generate_images.return_value = _fake_images_response(num=1)

    import server

    result = server.gemini_generate_image_imagen.fn(
        prompt="hi",
        output_dir=str(tmp_path),
        count=1,
        model="imagen-4.0-ultra-generate-001",
    )

    assert result["model"] == "imagen-4.0-ultra-generate-001"
    call_kwargs = mock_genai_client.models.generate_images.call_args.kwargs
    assert call_kwargs["model"] == "imagen-4.0-ultra-generate-001"
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/test_generate_image_imagen.py -v`
Expected: 5 passed (1 from Task 4 + 4 from this task).

- [ ] **Step 3: Run full suite**

Run: `uv run pytest -v`
Expected: 37 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_generate_image_imagen.py
git commit -m "test: cover Imagen config, error, and model-override paths"
```

---

## Task 6: `gemini_start_video` - success path test

**Files:**
- Create: `tests/test_start_video.py`

- [ ] **Step 1: Create test file with first failing test**

Create `tests/test_start_video.py`:

```python
"""Tests for gemini_start_video tool."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock


def test_start_video_stores_operation(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    operation = MagicMock(name="operation")
    mock_genai_client.models.generate_videos.return_value = operation

    import server

    result = server.gemini_start_video.fn(
        prompt="a sunset timelapse",
    )

    assert "operation_id" in result
    op_id = result["operation_id"]
    assert isinstance(op_id, str) and len(op_id) >= 8
    assert result["model"] == "veo-3.0-generate-001"
    assert "gemini_get_video" in result.get("message", "")
    assert server._video_ops[op_id] is operation
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_start_video.py::test_start_video_stores_operation -v`
Expected: FAIL with `AttributeError: module 'server' has no attribute 'gemini_start_video'`.

- [ ] **Step 3: Add the tool to `server.py`**

In `server.py`, append after the new `gemini_generate_image_imagen` tool you added in Task 4:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_start_video.py::test_start_video_stores_operation -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_start_video.py
git commit -m "feat: add gemini_start_video tool"
```

---

## Task 7: `gemini_start_video` - config, image, and error paths

**Files:**
- Modify: `tests/test_start_video.py`

- [ ] **Step 1: Append four more tests**

Append to `tests/test_start_video.py`:

```python
def test_start_video_passes_config(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    mock_genai_client.models.generate_videos.return_value = MagicMock()

    import server

    server.gemini_start_video.fn(
        prompt="hi",
        aspect_ratio="9:16",
        duration_seconds=7,
    )

    call_kwargs = mock_genai_client.models.generate_videos.call_args.kwargs
    config = call_kwargs["config"]
    assert config.aspect_ratio == "9:16"
    assert config.duration_seconds == 7
    assert config.number_of_videos == 1


def test_start_video_with_image_path(
    tmp_path: Path, mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    png = tmp_path / "seed.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")
    mock_genai_client.models.generate_videos.return_value = MagicMock()

    import server

    server.gemini_start_video.fn(
        prompt="animate this",
        image_path=str(png),
    )

    call_kwargs = mock_genai_client.models.generate_videos.call_args.kwargs
    assert call_kwargs["image"] is not None
    assert call_kwargs["image"].image_bytes == png.read_bytes()
    assert call_kwargs["image"].mime_type == "image/png"


def test_start_video_missing_image_file(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    import server

    result = server.gemini_start_video.fn(
        prompt="hi",
        image_path="/tmp/does-not-exist-xyz.png",
    )

    assert "error" in result
    assert "not found" in result["error"].lower()
    mock_genai_client.models.generate_videos.assert_not_called()


def test_start_video_wraps_sdk_errors(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    mock_genai_client.models.generate_videos.side_effect = RuntimeError("veo down")

    import server

    result = server.gemini_start_video.fn(prompt="hi")

    assert result == {"error": "veo down", "model": "veo-3.0-generate-001"}
    assert server._video_ops == {}
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/test_start_video.py -v`
Expected: 5 passed.

- [ ] **Step 3: Run full suite**

Run: `uv run pytest -v`
Expected: 42 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_start_video.py
git commit -m "test: cover start_video config, image, and error paths"
```

---

## Task 8: `gemini_get_video` - running state

**Files:**
- Create: `tests/test_get_video.py`

- [ ] **Step 1: Create test file with first failing test**

Create `tests/test_get_video.py`:

```python
"""Tests for gemini_get_video tool."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock


def test_get_video_running(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    op = MagicMock()
    op.done = False

    import server

    server._video_ops["op123abc"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_video.fn(operation_id="op123abc")

    assert result["status"] == "running"
    assert result["operation_id"] == "op123abc"
    assert "op123abc" in server._video_ops
    mock_genai_client.operations.get.assert_called_once_with(op)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_get_video.py::test_get_video_running -v`
Expected: FAIL with `AttributeError: module 'server' has no attribute 'gemini_get_video'`.

- [ ] **Step 3: Add the tool to `server.py`**

In `server.py`, append after `gemini_start_video`:

```python
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
        videos = op.result.generated_videos
        video_bytes = videos[0].video.video_bytes
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_get_video.py::test_get_video_running -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add server.py tests/test_get_video.py
git commit -m "feat: add gemini_get_video tool with running-state path"
```

---

## Task 9: `gemini_get_video` - done, unknown, and error states

**Files:**
- Modify: `tests/test_get_video.py`

- [ ] **Step 1: Append four more tests**

Append to `tests/test_get_video.py`:

```python
def test_get_video_done_writes_mp4(
    tmp_path: Path, mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    fake_bytes = b"fake-mp4-content"
    video = SimpleNamespace(video=SimpleNamespace(video_bytes=fake_bytes))
    result_obj = SimpleNamespace(generated_videos=[video])
    op = MagicMock()
    op.done = True
    op.result = result_obj

    import server

    server._video_ops["op456def"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_video.fn(
        operation_id="op456def",
        output_dir=str(tmp_path),
    )

    assert result["status"] == "done"
    assert result["operation_id"] == "op456def"
    written = Path(result["path"])
    assert written.exists()
    assert written.read_bytes() == fake_bytes
    assert written.name.startswith("veo-")
    assert written.suffix == ".mp4"
    assert "op456def" not in server._video_ops


def test_get_video_unknown_id(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    import server

    result = server.gemini_get_video.fn(operation_id="does-not-exist")

    assert result == {"status": "unknown", "error": "operation_id not found"}
    mock_genai_client.operations.get.assert_not_called()


def test_get_video_done_missing_video_bytes(
    tmp_path: Path, mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    result_obj = SimpleNamespace(generated_videos=[])
    op = MagicMock()
    op.done = True
    op.result = result_obj

    import server

    server._video_ops["opempty"] = op
    mock_genai_client.operations.get.return_value = op

    result = server.gemini_get_video.fn(
        operation_id="opempty",
        output_dir=str(tmp_path),
    )

    assert result["status"] == "error"
    assert "opempty" not in server._video_ops


def test_get_video_refresh_raises(
    mock_genai_client: MagicMock, reset_video_ops: None
) -> None:
    op = MagicMock()

    import server

    server._video_ops["oprun"] = op
    mock_genai_client.operations.get.side_effect = RuntimeError("refresh failed")

    result = server.gemini_get_video.fn(operation_id="oprun")

    assert result["status"] == "error"
    assert "refresh failed" in result["error"]
    assert "oprun" not in server._video_ops
```

- [ ] **Step 2: Run the new tests**

Run: `uv run pytest tests/test_get_video.py -v`
Expected: 5 passed.

- [ ] **Step 3: Run full suite**

Run: `uv run pytest -v`
Expected: 47 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/test_get_video.py
git commit -m "test: cover get_video done, unknown, and error states"
```

---

## Task 10: Verify tool discovery and smoke test

**Files:** (no changes)

- [ ] **Step 1: Verify every tool is registered**

Run: `cd /Users/mahmoud.ibrahim/workspace/gemini-mcp && GEMINI_API_KEY=dummy uv run python -c "import server; tools = sorted(t for t in dir(server) if t.startswith('gemini_')); print(len(tools), 'tools:', tools)"`

Expected output (10 tools):
```
10 tools: ['gemini_analyze_file', 'gemini_chat', 'gemini_code_execute', 'gemini_generate', 'gemini_generate_image', 'gemini_generate_image_imagen', 'gemini_get_video', 'gemini_list_models', 'gemini_search_grounded', 'gemini_start_video']
```

- [ ] **Step 2: Run full suite**

Run: `uv run pytest -v`
Expected: 47 passed.

- [ ] **Step 3: Start server standalone (sanity check)**

Run: `GEMINI_API_KEY=dummy timeout 5 uv run python server.py < /dev/null 2>&1 | grep -E "Starting MCP server|gemini" | head -3`
Expected output includes: `Starting MCP server 'gemini' with ...`

- [ ] **Step 4: No commit needed if everything passes**

Only commit if a file was modified:
```bash
git status
# If clean, skip. If modified, investigate.
```

---

## Task 11: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update the Features table**

In `README.md`, find the Features table and add three rows after `gemini_chat`:

```markdown
| `gemini_generate_image_imagen` | `imagen-4.0-generate-001` | Image generation with Imagen 4; writes PNG files to a local output directory |
| `gemini_start_video` | `veo-3.0-generate-001` | Kicks off a Veo video generation; returns an `operation_id` for polling |
| `gemini_get_video` | n/a | Polls a Veo operation started by `gemini_start_video`; writes the MP4 when done |
```

- [ ] **Step 2: Add a new Usage example for async video**

In `README.md`, find the section "### Search-grounded query with citations" and add a new subsection directly after it (before "## Available Gemini models"):

```markdown
### Asynchronous video generation

Video generation takes 30 seconds to a few minutes. The server exposes a start-then-poll pattern so Claude can work on other tasks while waiting.

Step 1: start the operation.

```text
Tool: gemini_start_video
  prompt: "A calm drone shot of waves meeting a sandy beach at sunset"
  aspect_ratio: "16:9"
  duration_seconds: 5
```

Response:

```json
{"operation_id": "a1b2c3d4e5f6", "model": "veo-3.0-generate-001", "message": "Video generation started. Poll with gemini_get_video."}
```

Step 2: poll until the status is `done`.

```text
Tool: gemini_get_video
  operation_id: "a1b2c3d4e5f6"
```

While running:

```json
{"status": "running", "operation_id": "a1b2c3d4e5f6"}
```

When complete:

```json
{"status": "done", "path": "/tmp/gemini-videos/veo-1776443060-ab12cd34.mp4", "operation_id": "a1b2c3d4e5f6"}
```

Poll every 10 to 15 seconds. Operation state is held in memory, so restarting the server invalidates any in-flight `operation_id` values.
```

- [ ] **Step 3: Update test count (two occurrences)**

Find these two lines in `README.md` and update each:

```markdown
All 31 unit tests should pass.
```
becomes:
```markdown
All 47 unit tests should pass.
```

And:
```markdown
├── tests/             # 31 unit tests (offline, mocked)
```
becomes:
```markdown
├── tests/             # 47 unit tests (offline, mocked)
```

- [ ] **Step 4: Update Known limitations**

Find the Known limitations section in `README.md`. Add two new bullets at the end:

```markdown
- **Video operation state is in-memory.** `operation_id` values returned by `gemini_start_video` are invalidated when the server process restarts. Poll within a single server lifetime.
- **Image-to-video requires local files.** `gemini_start_video`'s `image_path` must point to a file readable by the server process.
```

- [ ] **Step 5: Verify README still has no em/en dashes**

Run: `grep -nE "—|–" /Users/mahmoud.ibrahim/workspace/gemini-mcp/README.md && echo "FOUND" || echo "clean"`
Expected: `clean`.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: document Imagen and Veo tools in README"
```

---

## Task 12: Merge and push

**Files:** (no changes)

- [ ] **Step 1: Run full suite one more time**

Run: `cd /Users/mahmoud.ibrahim/workspace/gemini-mcp && uv run pytest -v`
Expected: 47 passed.

- [ ] **Step 2: Merge into main**

```bash
git checkout main
git merge --no-ff feat/imagen-veo -m "Merge feat/imagen-veo: Imagen 4 + Veo 3 tools"
git branch -d feat/imagen-veo
```

- [ ] **Step 3: Push to GitHub**

```bash
git push origin main
```

Expected output last line: `<old-sha>..<new-sha>  main -> main`.

- [ ] **Step 4: Verify remote**

Run: `git rev-parse HEAD && gh api repos/azmym/gemini-mcp/commits/main --jq '.sha'`
Expected: both SHAs match.

---

## Self-Review

**Spec coverage:**
- `gemini_generate_image_imagen`: Tasks 4-5 (signature, success, count bounds, aspect ratio, output dir creation, error wrap, model override) ✓
- `gemini_start_video`: Tasks 6-7 (signature, operation storage, config passthrough, image-to-video, missing file error, SDK error wrap) ✓
- `gemini_get_video`: Tasks 8-9 (running, done-writes-mp4, unknown id, done-with-missing-bytes, refresh failure) ✓
- `_video_ops` module state: Task 2 ✓
- `reset_video_ops` fixture: Task 1 ✓
- No new deps: Task 3 verified ✓
- README updates (Features table, async video example, test count, Known limitations): Task 11 ✓
- Test count target 44 in spec; plan delivers 47 due to a config smoke test and 5 tests per get_video subgroup. Higher-than-spec is fine.

**Placeholder scan:** No TBDs, TODOs, or "similar to Task N" references. Every code block is complete.

**Type consistency:**
- `_video_ops: dict[str, Any]` consistent across Tasks 1, 2, 6, 7, 8, 9.
- `_resolve_model(model, "imagen-4.0-generate-001")` and `_resolve_model(model, "veo-3.0-generate-001")` consistent with existing tool pattern.
- SDK method names verified against the installed `google-genai` SDK: `client.models.generate_images`, `client.models.generate_videos`, `client.operations.get`.
- Response attribute names: `response.generated_images[i].image.image_bytes` (Imagen), `op.result.generated_videos[i].video.video_bytes` (Veo). Matches SDK types inspected during brainstorming.
