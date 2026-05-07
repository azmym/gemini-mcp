# Migrating to Veo 3.1

Google AI Studio announced on 2026-05-07 that Veo 2 and Veo 3.0 model IDs will be discontinued on **2026-06-30**. After that date, requests to the affected IDs return `404 Not Found`. This guide explains what to change and when the server's built-in default will move.

## Why this matters

If your workflow relies on `veo-3.0-generate-001`, `veo-3.0-fast-generate-001`, or `veo-2.0-generate-001`, your `gemini_start_video` calls will start failing on 2026-06-30 unless you point them at a Veo 3.1 model first. The server's built-in default is still `veo-3.0-generate-001` today (see "Server default timeline" below), so you must opt in to 3.1 in the meantime.

## What's affected

These model IDs will be removed:

- `veo-2.0-generate-001`
- `veo-3.0-generate-001`
- `veo-3.0-fast-generate-001`

## Old to new ID mapping

| Old (sunset 2026-06-30) | New (AI Studio) | New (Vertex GA) |
|---|---|---|
| `veo-3.0-generate-001` | `veo-3.1-generate-preview` | `veo-3.1-generate-00` |
| `veo-3.0-fast-generate-001` | `veo-3.1-fast-generate-preview` | `veo-3.1-fast-generate-00` |
| `veo-2.0-generate-001` | `veo-3.1-generate-preview` | `veo-3.1-generate-00` |

This server uses Google AI Studio, so the **AI Studio** column is the one to use unless you have a fork pointed at Vertex.

## How to override today

You have three ways to switch to Veo 3.1 without waiting for the server default to move.

**Per-call argument** (highest priority, wins over everything):

```
Tool: gemini_start_video
Args: {
  "prompt": "A drone shot over a mountain valley at sunrise",
  "model": "veo-3.1-generate-preview"
}
```

**Process environment variable** (applies to every call that does not pass `model`):

```bash
export GEMINI_DEFAULT_MODEL=veo-3.1-generate-preview
```

**MCP client config** (Claude Code example, sets the env var when the server starts):

```bash
claude mcp remove gemini -s user
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -e GEMINI_DEFAULT_MODEL=veo-3.1-generate-preview \
  -- uvx --from git+https://github.com/azmym/gemini-mcp gemini-mcp
```

Resolution order is: explicit `model=` argument, then `GEMINI_DEFAULT_MODEL`, then the tool's built-in default. See [docs/configuration.md](configuration.md) for the full priority chain.

## Server default timeline

The built-in default for `gemini_start_video` stays `veo-3.0-generate-001` until **`veo-3.1-generate-preview` reaches GA on AI Studio, or 2026-06-01 at the latest, whichever is earlier**. At that point a versioned release will flip the default in `server.py`, update the tests, and refresh the example responses in `docs/tools.md`.

If you want to be on 3.1 before that release, use one of the override mechanisms above.

## Vertex users

The `-00` IDs (`veo-3.1-generate-00`, `veo-3.1-fast-generate-00`) are the Vertex GA model IDs. This server targets the Google AI Studio API, not Vertex, so those IDs will not work against the default client. If you maintain a fork that swaps the client for `genai.Client(vertexai=True, project=..., location=...)`, pass the `-00` IDs via `model=` or `GEMINI_DEFAULT_MODEL`.

## References

- Google AI Studio model documentation: https://ai.google.dev/gemini-api/docs/models
- Models guide: [docs/models.md](models.md)
- Tools reference: [docs/tools.md](tools.md)
