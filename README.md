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
