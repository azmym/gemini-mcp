# Configuration

The server is configured entirely through environment variables. No config files.

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | Yes | Google AI Studio API key. Create one at https://aistudio.google.com/app/apikey. Must be a Google AI Studio key; Vertex AI keys are not supported. AI Studio now issues Authorization keys starting with `AQ.` — both the new `AQ.` format and legacy `AIza` keys are accepted. |
| `GEMINI_DEFAULT_MODEL` | No | Overrides the default model for every tool globally. Any model string accepted by the Google AI Studio API. |

Both variables are read at server startup. Changing them requires restarting the MCP server (e.g., re-registering with `claude mcp add`, or restarting Claude Code if Option B is used).

## Model resolution priority

When a tool runs, it picks the model using this order (highest priority wins):

1. The `model` argument on the individual tool call.
2. The `GEMINI_DEFAULT_MODEL` environment variable, if set.
3. The tool's built-in default (see `docs/tools.md`).

### Worked examples

**Example 1: No env var, no per-call model**

```
GEMINI_DEFAULT_MODEL unset
Tool: gemini_generate
  prompt: "Hello"
```

Resolves to `gemini-2.5-pro` (the built-in default for `gemini_generate`).

**Example 2: Env var set, no per-call model**

```
GEMINI_DEFAULT_MODEL=gemini-3-flash-preview
Tool: gemini_generate
  prompt: "Hello"
```

Resolves to `gemini-3-flash-preview` (env var overrides the built-in).

**Example 3: Env var set, per-call model also set**

```
GEMINI_DEFAULT_MODEL=gemini-3-flash-preview
Tool: gemini_generate
  prompt: "Hello"
  model: "gemini-2.5-pro"
```

Resolves to `gemini-2.5-pro` (per-call wins over the env var).

## Changing the global default

Re-register the server with the extra env flag:

```bash
claude mcp remove gemini -s user
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -e GEMINI_DEFAULT_MODEL=gemini-3-flash-preview \
  -- uvx --from git+https://github.com/azmym/gemini-mcp gemini-mcp
```

Any explicit `model` argument on a tool call still wins.

## Inspecting the current configuration

```bash
claude mcp get gemini
```

Shows the registered command, scope, and environment variables. Note: this prints `GEMINI_API_KEY` in plaintext; treat the output as sensitive.
