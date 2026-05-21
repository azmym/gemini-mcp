# Migrating to gemini-mcp v0.2.0

v0.2.0 ships with new built-in defaults across every existing tool, plus three new tools (Lyria 3 music, Gemini 3.1 TTS, Deep Research). The override priority chain is unchanged: per-call `model=` argument > `GEMINI_DEFAULT_MODEL` env var > built-in default.

## Why this matters

Existing callers that did not pass an explicit `model=` will hit a different model after upgrading. Behavior, latency, and cost characteristics may shift. This guide lists every flip and shows how to pin the previous default if you are not ready to move.

## Default flips

| Tool | v0.1.x default | v0.2.0 default |
|---|---|---|
| `gemini_generate` | `gemini-2.5-pro` | `gemini-3.1-pro-preview` |
| `gemini_generate_image` | `gemini-2.5-flash-image` | `gemini-3.1-flash-image-preview` |
| `gemini_generate_image_imagen` | `imagen-4.0-generate-001` | `imagen-4.0-ultra-generate-001` |
| `gemini_code_execute` | `gemini-2.5-pro` | `gemini-3.1-pro-preview-customtools` |
| `gemini_search_grounded` | `gemini-2.5-flash` | `gemini-3.5-flash` |
| `gemini_analyze_file` | `gemini-2.5-pro` | `gemini-3.1-pro-preview` |
| `gemini_chat` | `gemini-2.5-flash` | `gemini-3.5-flash` |
| `gemini_start_video` | `veo-3.0-generate-001` | `veo-3.1-generate-preview` |

The Veo flip ships in v0.2.0 because Veo 3.0 model IDs sunset on **2026-06-30**. After that date, requests to `veo-3.0-*` and `veo-2.0-*` return `404 Not Found`. v0.2.0 is the safe-to-upgrade release.

## Pinning the v0.1.x default

If you want one tool's default unchanged after upgrading, pass `model=` on every call:

```text
Tool: gemini_generate
  prompt: "..."
  model: "gemini-2.5-pro"
```

For a process-wide pin, set `GEMINI_DEFAULT_MODEL` on the MCP server entry. Note that this pins **every** tool to the same model, so it only makes sense if you want that one model everywhere.

```bash
claude mcp remove gemini -s user
claude mcp add gemini -s user \
  -e GEMINI_API_KEY=<your-key> \
  -e GEMINI_DEFAULT_MODEL=gemini-2.5-pro \
  -- uvx --from git+https://github.com/azmym/gemini-mcp gemini-mcp
```

For per-tool pins across a whole client, the only mechanism today is to pass `model=` on every call. There is no per-tool env var.

## New tools

v0.2.0 adds three tools that were not present in v0.1.x. They have no compatibility implication for existing code, but you may want to know they exist:

- `gemini_generate_music`: text-to-music with Lyria 3. Default model `lyria-3-pro-preview`. Writes WAV to `/tmp/gemini-music`.
- `gemini_tts`: text-to-speech with Gemini 3.1 TTS. Default model `gemini-3.1-flash-tts-preview`. Single-voice and multi-speaker modes. Writes WAV to `/tmp/gemini-tts`.
- `gemini_start_research` plus `gemini_get_research_report`: Deep Research polling pair, same shape as `gemini_start_video` plus `gemini_get_video`. Default model `deep-research-max-preview-04-2026`. Writes a markdown report to `/tmp/gemini-research`.

See [Tools reference](tools.md) for full signatures and example responses.

## Preview model warning

Most of the new defaults are preview models. Preview models can change behavior, pricing, or availability without notice. If you need a stable contract, pin to a stable model ID via the override mechanisms above. The v0.2.0 policy is "newest available", which biases toward preview where the stable tier has not caught up yet.

## References

- [Tools reference](tools.md)
- [Models](models.md)
- [Configuration](configuration.md)
- Google AI Studio model documentation: https://ai.google.dev/gemini-api/docs/models
