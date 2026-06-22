# Migrating to gemini-mcp v0.2.1

v0.2.1 deprecates the `gemini_generate_image_imagen` tool ahead of Google discontinuing the Imagen 4 endpoints.

## Why this matters

Google discontinues all Imagen 4 model IDs on **2026-08-17**:

- `imagen-4.0-generate-001`
- `imagen-4.0-ultra-generate-001`
- `imagen-4.0-fast-generate-001`

After that date, calls to these IDs return `404 Not Found`. There is no surviving Imagen model to repoint to. Google's recommended replacement is the Gemini flash-image path, which this server already ships as `gemini_generate_image`.

## What changed in v0.2.1

`gemini_generate_image_imagen` no longer calls Imagen. It now redirects to `gemini-3.1-flash-image-preview` (the `generateContent` image path):

- A call with no `model=` (or with any `imagen-4.0-*` ID) is served by `gemini-3.1-flash-image-preview`.
- An explicit non-Imagen model ID is still honored, and `GEMINI_DEFAULT_MODEL` still applies.
- `aspect_ratio` is translated into a prompt instruction (the flash-image path has no aspect-ratio config field), so it is prompt-steered rather than a hard crop.
- `count` maps to `candidate_count`.
- Every response carries `"deprecated": true` plus a `"deprecation"` message, and `"model"` reports the actual model used.

No call to this tool returns a 404 from the sunset, because Imagen is never called.

## What you should do

Move to `gemini_generate_image` for native image generation. It is the same flash-image path without the deprecated wrapper. The `gemini_generate_image_imagen` tool will be removed entirely in a later release, just before 2026-08-17.

## References

- [Tools reference](tools.md)
- [Models](models.md)
- [v0.2.0 migration](migration-v0.2.md)
- Google AI Studio model documentation: https://ai.google.dev/gemini-api/docs/models
