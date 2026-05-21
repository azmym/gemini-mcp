# Models

The server accepts any model string valid for the Google AI Studio API. You are not limited to the defaults; pass `model` on any tool call to pick a different one.

## Listing available models

Call `gemini_list_models` from your MCP client:

```
Tool: gemini_list_models
```

The response lists every model your API key can access, along with supported actions and input/output token limits. See `docs/tools.md` for the exact response shape.

## Common choices

| Goal | Model |
|---|---|
| Fast, cheap chat or short answers | `gemini-3.5-flash` |
| Strongest reasoning, code, analysis | `gemini-3.1-pro-preview` |
| Stable reasoning (no preview) | `gemini-2.5-pro` |
| Stable native image generation | `gemini-2.5-flash-image` |
| Latest native image generation | `gemini-3.1-flash-image-preview` (default) or `gemini-3-pro-image-preview` |
| High-quality Imagen image generation | `imagen-4.0-ultra-generate-001` (default), `imagen-4.0-generate-001` (standard), `imagen-4.0-fast-generate-001` (quickest) |
| Video generation (Veo) | `veo-3.1-generate-preview` (default), `veo-3.1-fast-generate-preview`, `veo-3.1-lite-generate-preview` |
| Music generation (Lyria) | `lyria-3-pro-preview` (default) or `lyria-3-clip-preview` |
| Text-to-speech | `gemini-3.1-flash-tts-preview` (default) |
| Deep Research | `deep-research-max-preview-04-2026` (default) or `deep-research-pro-preview-12-2025` |
| Grounded answers with citations | `gemini-3.5-flash` |

## Nano Banana

"Nano Banana" is Google's codename for Gemini's native image generation models. `gemini_generate_image` calls these models, so you already have access:

| Model ID | Alias | Status |
|---|---|---|
| `gemini-2.5-flash-image` | Nano Banana | Stable (default) |
| `gemini-3.1-flash-image-preview` | Nano Banana 2 | Preview |
| `gemini-3-pro-image-preview` | Nano Banana Pro | Preview |

All three are text-to-image. Nano Banana also supports reference-image editing (up to 14 input images per prompt) but this server does not expose that surface today; `gemini_generate_image` is text-only.

## Stable vs preview

- **Stable** models (no `-preview` in the name) have fixed behavior and long-term availability guarantees.
- **Preview** models (anything with `-preview` in the name) can change behavior, pricing, or availability without notice.

v0.2.0 defaults bias toward "newest available", which means several tools default to preview models (`gemini_generate`, `gemini_generate_image`, `gemini_code_execute`, `gemini_analyze_file`, `gemini_start_video`, `gemini_generate_music`, `gemini_tts`, `gemini_start_research`). If you need a stable contract, pin via `GEMINI_DEFAULT_MODEL` or pass `model=` on every call. See [Migrating to v0.2.0](migration-v0.2.md) for the full list and pin recipes.

Stick to stable models for workflows you rely on. Use previews for experimentation.

## Tool defaults

Each tool has a built-in default model. Overriding per call or via `GEMINI_DEFAULT_MODEL` takes precedence. See the table in `docs/tools.md` for each tool's default.

## References

- Google AI Studio model documentation: https://ai.google.dev/gemini-api/docs/models
- Release notes: https://ai.google.dev/gemini-api/docs/changelog
- API key management: https://aistudio.google.com/app/apikey
