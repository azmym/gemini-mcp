# Installation

This guide covers installing and registering the `gemini-mcp` server with Claude Code (or any MCP-compatible client).

## Prerequisites

- **Python 3.11 or later.** Check with `python3 --version`.
- **[`uv`](https://docs.astral.sh/uv/).** Install with `curl -LsSf https://astral.sh/uv/install.sh | sh` (or `brew install uv` on macOS).
- **A Google AI Studio API key.** Create one at https://aistudio.google.com/app/apikey. This is a Google AI Studio key, not a Vertex AI service account. Newly created keys start with `AQ.` (the Authorization key format); legacy `AIza` keys also work. No configuration difference — both go in `GEMINI_API_KEY`.
- **Claude Code** (for Options A and B). Other MCP clients work too; the `claude mcp add` commands below are Claude-Code-specific.

## Option A: install directly from GitHub

Best for most users. `uvx` fetches the repository, installs dependencies into an isolated cache, and runs the `gemini-mcp` console script.

```bash
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -- uvx --from git+https://github.com/azmym/gemini-mcp gemini-mcp
```

Replace `<your-key>` with your Google AI Studio API key. The first invocation clones the repo and installs `fastmcp` and `google-genai` (roughly 5 to 15 seconds cold start). Subsequent calls are instant thanks to the uv cache.

### Pinning a version

Append `@<ref>` to pin a tag, branch, or commit:

```bash
uvx --from git+https://github.com/azmym/gemini-mcp@v0.1.0 gemini-mcp
```

### Upgrading

Force `uvx` to refetch the latest commit from `main`:

```bash
uvx --from git+https://github.com/azmym/gemini-mcp --refresh gemini-mcp --help
```

Then restart Claude Code to pick up the new version.

To pin to a specific release instead of tracking `main`, re-register the server with the tag appended:

```bash
claude mcp remove gemini -s user
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -- uvx --from git+https://github.com/azmym/gemini-mcp@v0.2.0 gemini-mcp
```

### Upgrading from v0.1.x to v0.2.0

v0.2.0 changes the built-in default model for every tool. If any of your workflows relied on the old defaults (e.g. `gemini-2.5-pro` for text generation or `veo-3.0-generate-001` for video), read [docs/migration-v0.2.md](migration-v0.2.md) for the full list and per-tool pin recipes before upgrading.

The upgrade itself is a one-liner:

```bash
uvx --from git+https://github.com/azmym/gemini-mcp --refresh gemini-mcp --help
```

Then restart Claude Code.

## Option B: run from a local clone

Use this when you want to edit the code and iterate quickly.

```bash
git clone https://github.com/azmym/gemini-mcp
cd gemini-mcp
uv sync

claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -- uv --directory /absolute/path/to/gemini-mcp run python server.py
```

Replace `/absolute/path/to/gemini-mcp` with the absolute path where you cloned the repository. Changes to `server.py` take effect the next time Claude Code restarts the MCP server.

## Option C: standalone manual run

Launch the server directly to verify your environment. The process speaks the MCP stdio transport and waits for a client to connect.

```bash
cd /path/to/gemini-mcp
GEMINI_API_KEY=<your-key> uv run python server.py
```

Use this for smoke testing; production use should go through Option A or B.

## Verifying the connection

After registering with Option A or B:

```bash
claude mcp list
```

Expected output contains a line like:
```
gemini: uvx --from git+https://github.com/azmym/gemini-mcp gemini-mcp - ✓ Connected
```

If it shows `✗ Failed to connect`, run `claude mcp get gemini` to inspect the configuration, and check that `GEMINI_API_KEY` is set and valid.

## Removing the server

```bash
claude mcp remove gemini -s user
```
