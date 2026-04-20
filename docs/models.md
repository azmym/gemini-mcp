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
| Fast, cheap chat or short answers | `gemini-2.5-flash` |
| Strongest stable reasoning, code, analysis | `gemini-2.5-pro` |
| Latest preview, advanced reasoning | `gemini-3.1-pro-preview` |
| Fast preview variant | `gemini-3-flash-preview` |
| Stable native image generation | `gemini-2.5-flash-image` |
| Preview native image generation | `gemini-3-pro-image-preview` or `gemini-3.1-flash-image-preview` |
| High-quality Imagen image generation | `imagen-4.0-generate-001` (standard), `imagen-4.0-ultra-generate-001` (highest fidelity), `imagen-4.0-fast-generate-001` (quickest) |
| Video generation (Veo 3) | `veo-3.0-generate-001` (stable), `veo-3.0-fast-generate-001` (faster), `veo-3.1-generate-preview` (latest) |
| Grounded answers with citations | `gemini-2.5-flash` (fast) or `gemini-2.5-pro` (thorough) |

## Nano Banana

"Nano Banana" is Google's codename for Gemini's native image generation models. `gemini_generate_image` calls these models, so you already have access:

| Model ID | Alias | Status |
|---|---|---|
| `gemini-2.5-flash-image` | Nano Banana | Stable (default) |
| `gemini-3.1-flash-image-preview` | Nano Banana 2 | Preview |
| `gemini-3-pro-image-preview` | Nano Banana Pro | Preview |

All three are text-to-image. Nano Banana also supports reference-image editing (up to 14 input images per prompt) but this server does not expose that surface today; `gemini_generate_image` is text-only.

## Stable vs preview

- **Stable** models (`gemini-2.5-*`, `imagen-4.0-generate-001`, `veo-3.0-generate-001`) have fixed behavior and long-term availability guarantees.
- **Preview** models (anything with `-preview` in the name) can change behavior, pricing, or availability without notice.

Stick to stable models for workflows you rely on. Use previews for experimentation.

## Tool defaults

Each tool has a built-in default model. Overriding per call or via `GEMINI_DEFAULT_MODEL` takes precedence. See the table in `docs/tools.md` for each tool's default.

## References

- Google AI Studio model documentation: https://ai.google.dev/gemini-api/docs/models
- Release notes: https://ai.google.dev/gemini-api/docs/changelog
- API key management: https://aistudio.google.com/app/apikey
