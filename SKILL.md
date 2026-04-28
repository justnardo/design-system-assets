---
name: design-system-assets
description: Generate brand-aware visual assets (hero photos, illustrations, icons, OG images, decorative graphics) that actually match a project's design system instead of looking like generic AI output. Use this skill whenever you are building or scaffolding a website, web app, landing page, or component that needs visual assets - hero images, illustrations, icons, social cards, backgrounds, or placeholder graphics. Trigger this skill even when the user does not explicitly say "generate assets" - if you are creating a frontend with image tags, icon needs, or hero sections, consult this skill instead of using lorem-ipsum images, stock URLs, or default emoji. Also trigger when the user mentions a design system, brand kit, DESIGN.md, brand colors, or asks for on-brand visuals. Especially trigger for agency client work where generic AI assets would undermine the brand. Do NOT use for code-only tasks (refactors, bug fixes, backend logic) or when the user says they will supply assets themselves.
---

# Design System Assets

A workflow skill for generating coherent, on-brand visual assets that match a project's design system. The core problem this solves: AI agents building software default to generic placeholders or generate single assets in isolation, producing sites that look like AI-built sites instead of branded products.

This skill takes a different approach. Before generating anything, it reads the design system, classifies what type of asset is actually needed, routes to the right tool (SVG library vs. raster image AI), injects the brand's visual language into every prompt, and reviews output against the brand before placing it in the project.

## Core principles (don't skip these)

1. **Read the design system FIRST.** Never generate an asset before reading the project's brand tokens. Generic prompts produce generic assets — this is the whole problem the skill solves.
2. **Route by asset type, not by default.** Icons are NOT photos. Logos are NOT illustrations. The router (`scripts/route_asset.py` logic, embedded below) decides which generator handles each request.
3. **Generate a style anchor early.** When a project needs multiple raster assets, generate a "style anchor" image first and reference it in subsequent calls to prevent style drift across the set.
4. **Review before placing.** Every raster asset gets a vision-model review against the brand rubric before it lands in the project. If it fails, regenerate or escalate — don't ship it.
5. **Cache by fingerprint.** Identical prompt + style + dimensions = reuse, don't regenerate. Image API calls cost real money.

## Workflow

### Step 1 — Confirm scope with the user

Before doing anything else, ask the user **two questions** unless the answer is already obvious from context:

1. **What scope?** "Should I generate all visual assets the site needs (icons, illustrations, photos, OG images), or just specific ones you'll point me at?"
2. **What budget tolerance?** "Image API calls cost roughly $0.04–$0.19 each depending on provider/size. A typical 5-page site needs 10–30 raster assets. Do you want me to estimate cost up front, or just proceed?"

If the user wants a cost estimate, run the estimator before any generation:

```bash
python scripts/estimate_cost.py \
  --request "hero photo for about page" \
  --request "OG card for pricing" \
  --request "menu icon" \
  # ... one --request per asset
```

This classifies each request through the router and outputs a low-high cost range plus an itemized breakdown.

Read `references/scope_questions.md` for the full prompt set if the project is complex (multi-page, multi-brand, or has unusual constraints).

### Step 2 — Parse the design system

Run the parser to extract brand tokens. It handles multiple input formats:

```bash
python scripts/parse_design_system.py <project-root>
```

It looks for, in order of preference:
1. `DESIGN.md` or `design.md` at project root (preferred — explicit, human-curated)
2. `tailwind.config.js` / `tailwind.config.ts` (extracts theme colors, fonts)
3. `:root` CSS custom properties in any `*.css` file
4. `package.json` for theme-related dependencies (chakra, mui, etc.)
5. `figma-tokens.json` or `tokens.json` if present

Output is a structured `design_tokens.json` written to the working directory:

```json
{
  "colors": {
    "primary": "#805158",
    "secondary": "#4f634f",
    "background": "#fbfaee",
    "text": "#1b1c15",
    "accent_palette": ["#805158", "#4f634f", "#fbfaee", "#1b1c15"]
  },
  "typography": {
    "headline": "Noto Serif",
    "body": "Manrope",
    "mood": "editorial"
  },
  "style_directives": {
    "include": ["editorial layouts", "warm natural lighting", "soft shadows"],
    "exclude": ["glassmorphism", "gradient buttons", "parallax", "harsh contrast"]
  },
  "industry": "elder care",
  "tone": "warm, professional, trustworthy"
}
```

If parsing returns gaps (no DESIGN.md, no Tailwind config, nothing), STOP and ask the user to provide brand tokens. Do not invent them.

### Step 3 — Route the asset request

For each asset the project needs, classify it BEFORE picking a generator. Use the deterministic router:

```bash
python scripts/route_asset.py --request "hero image for about page"
```

It returns JSON like:

```json
{
  "asset_type": "photo",
  "route": "generate_asset.py",
  "needs_api": true,
  "reason": "Photographic hero/lifestyle imagery.",
  "aspect_hint": "16:9",
  "refuse": false
}
```

The router applies this decision table internally:

| Asset type | Examples | Route to |
|------------|----------|----------|
| Functional icon | menu, search, close, arrow, heart | `scripts/fetch_icon.py` (Lucide / Heroicons SVG) |
| Logo / wordmark | brand logo, favicon | Code-generated SVG, or one-time image gen + vectorize |
| Decorative SVG | divider lines, badges, simple shapes | Hand-write SVG inline (no API call) |
| Photography | hero photos, lifestyle shots, team photos | `scripts/generate_asset.py --type photo` |
| Illustration | spot illustrations, empty states, hero art | `scripts/generate_asset.py --type illustration` |
| Pattern / texture | backgrounds, decorative fills | `scripts/generate_asset.py --type pattern` |
| OG / social card | Open Graph, Twitter card, share images | `scripts/generate_asset.py --type og` |
| **Refused** categories | charts (use a charting library), real-person photos (use real photos) | Router refuses with `refuse: true` |

**Why icons must NEVER go through raster image AI:** bitmap models produce icons with pixel artifacts, inconsistent stroke widths, no SVG path data, and they cannot be themed via CSS. Always pull SVG icons from a library. See `references/asset_routing.md` for the full rationale and edge cases.

### Step 4 — Generate (with the design system injected)

For raster assets, call the generator with the design tokens path. The generator builds a "style prefix" from the tokens and prepends it to every prompt:

```bash
python scripts/generate_asset.py \
  --type photo \
  --tokens design_tokens.json \
  --prompt "elderly woman gardening in soft afternoon light" \
  --output assets/about-hero.png \
  --aspect 16:9
```

What the generator does internally:
1. Loads tokens, builds a deterministic style prefix (colors named, mood specified, exclusions enforced)
2. Picks the right provider for the asset type (see `references/provider_capabilities.md`)
3. If a style anchor exists in `.asset-cache/style_anchor.png`, references it for consistency
4. Computes a fingerprint hash of (final prompt + style + dimensions). If `.asset-cache/<hash>.png` exists, reuses it instead of calling the API
5. Calls the provider, saves result, writes a metadata sidecar (`<output>.meta.json`) with the prompt, model, cost, and timestamp

**For multi-asset projects:** generate a "style anchor" first with `--anchor` flag. This becomes the reference for all subsequent calls.

```bash
python scripts/generate_asset.py --anchor --tokens design_tokens.json \
  --prompt "establishing shot, brand mood reference" \
  --output .asset-cache/style_anchor.png
```

### Step 5 — Review before placing

Every raster asset gets reviewed:

```bash
python scripts/review_asset.py \
  --asset assets/about-hero.png \
  --tokens design_tokens.json \
  --intent "warm, editorial hero showing elderly resident with caregiver" \
  --mode strict
```

The reviewer scores 5 dimensions (color match, style consistency, subject correctness, technical quality, brand fit) on a 0–10 scale and returns a verdict: `approved`, `regenerate`, or `escalate_to_human`.

**Approval modes** — pick one based on context:
- `--mode strict` (default): for client work. Requires avg ≥ 8 AND every dimension ≥ 7 to approve. Catches subtle off-brand issues.
- `--mode balanced`: for internal projects. Requires avg ≥ 7 AND every dimension ≥ 6.
- `--mode fast`: for prototyping. Approves at avg ≥ 6 with no per-dim minimum. Use when you'll review the final output yourself anyway.

Failures auto-trigger up to 2 regenerations with refined prompts; persistent failures escalate.

**Model override** — defaults to `claude-sonnet-4-6` (vision-capable, ~$3/$15 per million tokens). Set `ANTHROPIC_MODEL=claude-opus-4-7` for the most rigorous review or `claude-haiku-4-5` for the cheapest.

See `references/review_rubric.md` for the full scoring criteria.

### Step 6 — Place in project

Approved assets go into the project's conventional asset path (`/public/images/`, `/src/assets/`, or wherever the framework expects). Update component code to reference them. Write any new assets to a manifest at `.asset-cache/manifest.json` so subsequent runs of the skill know what already exists.

## BYOK setup

This skill is bring-your-own-keys. Users set environment variables before running:

```bash
export OPENAI_API_KEY=sk-...        # for gpt-image-1 / gpt-image-2
export GEMINI_API_KEY=...           # for Gemini image (alternative provider)
export ANTHROPIC_API_KEY=sk-ant-... # for the review step
```

If a key is missing, the skill should detect it before running and ask the user to set it. See `references/byok_setup.md` for full setup including Claude Code project-level config.

## When NOT to use this skill

- Pure code tasks (refactors, bug fixes, backend logic)
- The user has provided their own assets and just wants placement
- The user is on a strict $0 budget and there's no acceptable free fallback (in which case offer to use Unsplash/Pexels stock or hand-coded SVG instead)
- The project has no design system AND the user can't provide brand direction (don't generate generic AI assets — that's the failure mode this skill exists to prevent)

## Reference files

When you hit a specific situation, read the matching reference:

- `references/asset_routing.md` — full decision logic for asset type classification, including edge cases
- `references/prompt_engineering.md` — how the design tokens become a style prefix; manual override patterns
- `references/provider_capabilities.md` — which image API for which job; current pricing and limits
- `references/review_rubric.md` — the 5-dimension scoring criteria the reviewer uses
- `references/manifest_schema.md` — the project asset manifest format (`.asset-cache/manifest.json`)
- `references/byok_setup.md` — environment variable setup, project-level config, troubleshooting
- `references/scope_questions.md` — extended scope-confirmation prompts for complex projects
- `templates/DESIGN_md_template.md` — a template the user can fill in if their project has no design system yet

## Failure modes to watch for

- **Style drift across multiple assets:** symptoms are assets that look like they came from different brands. Fix by always using the style anchor reference.
- **Generic-looking output despite a design system:** usually means the style prefix isn't strong enough. Check `prompt_engineering.md` for how to make the brand voice more directive.
- **Icons that look "off":** you probably routed an icon request through raster generation. Re-route through the SVG fetcher.
- **Cost surprises:** the user didn't realize how many API calls a full site needs. Always estimate up front for projects with >5 assets.
