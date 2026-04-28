# Provider Capabilities

Which image API to use for which job. This document is a snapshot — pricing and capabilities change. Verify current rates with each provider before quoting clients on cost.

## OpenAI gpt-image-1 (default)

**Strengths:**
- Strong photographic realism
- Good at text rendering (logos, OG cards with copy)
- Reliable instruction-following on color directives
- Multiple sizes including portrait and landscape
- Returns base64 directly (no separate URL fetch)

**Weaknesses:**
- More expensive per image than alternatives
- Slower than Gemini for batch use
- Stricter content filters

**Best for:** photography, OG images with text, illustrations where instruction-following matters more than aesthetic novelty

**API endpoint:** `https://api.openai.com/v1/images/generations`
**Env var:** `OPENAI_API_KEY`
**Sizes:** 1024×1024, 1024×1536 (portrait), 1536×1024 (landscape)

## Google Gemini image (alternative)

**Strengths:**
- Faster generation
- Cheaper per image
- Strong at illustrative and editorial styles
- Good at consistency across a series when given a reference image

**Weaknesses:**
- Less reliable text rendering (avoid for OG cards with copy)
- Output dimensions are less explicitly controlled
- Newer endpoint, more API churn

**Best for:** illustrations, large batches, projects where unit economics matter

**API endpoint:** `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent`
**Env var:** `GEMINI_API_KEY`

## Routing logic the skill uses by default

```python
DEFAULT_PROVIDER_FOR_TYPE = {
    "photo":         "openai",   # photographic realism is the priority
    "illustration":  "openai",   # could swap to gemini for cost; openai default for consistency
    "pattern":       "openai",
    "og":            "openai",   # text rendering matters
    "logo_concept":  "openai",
}
```

You can override per call: `--provider gemini` or `--provider openai`.

## Cost planning for client projects

For a typical 5-page brand site, expect roughly:
- 1 hero photo per page = 5 raster assets
- 1 OG / share image = 1 raster
- 5–8 spot illustrations or supporting photos = 6 raster
- 15–25 functional icons = 0 raster (Lucide is free)
- Decorative SVGs = 0 raster (hand-coded)

**Total raster generation: ~12 assets.** At gpt-image-1 list price, this is in the $0.50–$2.00 range depending on sizes. With regenerations during review (budget for ~30% regen rate), call it $1–$3 in API spend per site.

For agency work, this is well within the noise of a client project's labor cost. For DIY personal projects, the cache (`--cache-dir .asset-cache`) is what keeps repeat builds free.

## Models worth watching (not yet integrated)

- **Future OpenAI image models** as they reach GA — text rendering, batch generation, multi-reference compositing keep improving each generation. When a successor to gpt-image-1 is stable, swap the default.
- **Flux 1.1 Pro / Flux Dev** via Replicate or Fal: strong photorealism, often cheaper than OpenAI per image. Adds a third API to manage.
- **Ideogram**: best-in-class text rendering. Useful for OG cards and signage if you can swap a third provider in.

When adding new providers, keep them behind the same `--provider` flag and add a routing entry to `DEFAULT_PROVIDER_FOR_TYPE` if there's a clear best-fit asset type.

## Claude (review step)

The review step uses an Anthropic Claude vision model. Current options as of skill creation:

| Model | Pricing (input/output per M tokens) | When to use |
|-------|-------------------------------------|-------------|
| `claude-sonnet-4-6` | $3 / $15 | **Default.** Vision-capable, strong instruction-following, much cheaper than Opus. Plenty for review work. |
| `claude-opus-4-7` | $5 / $25 | Most rigorous review. Worth it for high-stakes client deliverables where you want the most discriminating reviewer. |
| `claude-haiku-4-5` | $1 / $5 | Cheapest option. Vision-capable but less reliable judgment — best for prototyping. |

Override via `ANTHROPIC_MODEL` env var or `--model` flag. A typical review uses ~1K input tokens (system prompt + image) and ~500 output tokens, which on Sonnet 4.6 is roughly $0.01 per asset.

## When to skip image AI entirely

- The user has a strict $0 budget — fall back to Unsplash / Pexels stock with proper attribution, or hand-coded SVG illustrations
- The asset is a real product the client sells — get real photos
- The asset depicts a real person — get real photos or use editorial stock
- The asset is a chart or data viz — render with a charting library, not image AI
