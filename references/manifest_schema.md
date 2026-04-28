# Asset Manifest Schema

The skill writes a project-level manifest at `.asset-cache/manifest.json` so subsequent runs (and external tools) know what's already been generated, approved, and placed.

## Why this exists

Without a manifest, every run of the skill starts from zero. With one:
- Repeat builds skip regeneration of already-approved assets (saves API spend)
- Other agents in a pipeline can read what assets exist and route around them
- You get an audit trail: which prompt produced which file, which review approved it
- A client handoff includes a single file listing every AI-generated asset with provenance

## Implementation status

As of v1.2, **no script in this repo writes the manifest**. The schema below
defines the format the writer should produce; the writer itself is tracked as
an open task in CONTRIBUTING.md. Today, `generate_asset.py` writes a per-file
`<asset>.meta.json` sidecar instead, and `fetch_icon.py` writes nothing
beyond the SVG itself. Any tool that needs an audit trail today must roll
its own.

## Schema (v1)

```json
{
  "$schema": "https://design-system-assets.dev/schemas/manifest-v1.json",
  "version": "1.0",
  "project": "Viceroy Elderly Care Services",
  "generated_at": "2026-04-27T20:30:00-04:00",
  "design_system_source": "DESIGN.md",
  "design_tokens_hash": "sha256:abc123...",
  "assets": [
    {
      "id": "about-hero",
      "type": "photo",
      "path": "public/images/about-hero.png",
      "alt": "Elderly woman tending herbs in a sunlit kitchen window",
      "intent": "warm editorial hero showing elderly resident gardening",
      "provider": "openai",
      "model": "gpt-image-1",
      "prompt": "Photographic image. Tone: Warm, professional...",
      "prompt_hash": "sha256:def456...",
      "size": "1536x1024",
      "review": {
        "model": "claude-sonnet-4-6",
        "mode": "strict",
        "verdict": "approved",
        "scores": {
          "color_match": 9,
          "style_consistency": 9,
          "subject_correctness": 9,
          "technical_quality": 8,
          "brand_fit": 9
        }
      },
      "generated_at": "2026-04-27T20:31:14-04:00",
      "regenerations": 0,
      "cost_usd_estimate": 0.08
    },
    {
      "id": "menu",
      "type": "icon",
      "path": "public/icons/menu.svg",
      "source": "lucide",
      "lucide_name": "menu",
      "themed_color": "#805158",
      "stroke_width": 2,
      "generated_at": "2026-04-27T20:31:01-04:00",
      "cost_usd_estimate": 0.00
    }
  ],
  "totals": {
    "asset_count": 2,
    "raster_count": 1,
    "icon_count": 1,
    "approved_count": 1,
    "regenerated_count": 0,
    "escalated_count": 0,
    "total_cost_usd": 0.08
  }
}
```

## Field guide

| Field | Required? | Notes |
|-------|-----------|-------|
| `version` | Yes | Schema version. Currently always "1.0". |
| `project` | Yes | Human-readable project name. |
| `generated_at` | Yes | ISO 8601 timestamp of last manifest write. |
| `design_system_source` | Yes | Where tokens came from: `"DESIGN.md"`, `"tailwind.config"`, `"css_variables"`, etc. |
| `design_tokens_hash` | Yes | SHA-256 of the design_tokens.json contents. If this changes, re-evaluate all cached assets. |
| `assets[]` | Yes | List of every asset in the project's tree, including non-AI ones if they came through this skill. |
| `assets[].id` | Yes | Stable identifier. Use kebab-case. Should match a logical slot name (`hero-about`, `og-pricing`, `icon-menu`). |
| `assets[].type` | Yes | One of: `photo`, `illustration`, `pattern`, `og`, `logo_concept`, `icon`, `decorative_svg`. |
| `assets[].path` | Yes | Relative path from project root to the asset file. |
| `assets[].alt` | Recommended | Alt text. Required for accessibility. |
| `assets[].intent` | Yes for raster | What the asset was supposed to depict. Used for review and regeneration. |
| `assets[].provider` | Raster only | `openai`, `gemini`. Not set for icons / decorative SVG. |
| `assets[].model` | Raster only | Specific model used. |
| `assets[].prompt` | Raster only | Final prompt sent to provider (with style prefix). |
| `assets[].prompt_hash` | Raster only | SHA-256 of the prompt for cache lookup. |
| `assets[].size` | Raster only | Pixel dimensions, e.g. `"1536x1024"`. |
| `assets[].review` | Raster only | Last review record. Includes mode, model, verdict, scores. |
| `assets[].source` | Icon only | `"lucide"`, `"heroicons"`, `"hand-coded"`. |
| `assets[].lucide_name` | Icon only | Canonical Lucide name used (after synonym resolution). |
| `assets[].generated_at` | Yes | ISO 8601 timestamp this specific asset was created. |
| `assets[].regenerations` | Raster only | Count of regenerations to reach the current version. |
| `assets[].cost_usd_estimate` | Yes | Best-guess cost for this asset's generation + review. |
| `totals` | Yes | Aggregate counts and cost. Recompute on every manifest write. |

## When the manifest is updated

- After `parse_design_system.py` runs successfully → updates `design_tokens_hash`
- After `generate_asset.py` produces a new approved asset → adds an entry to `assets[]`
- After `fetch_icon.py` saves an icon → adds an entry to `assets[]`
- After a regeneration loop → updates the relevant asset's `regenerations` count and review record
- Manual edits to `assets[].alt` are preserved across runs

## When to discard the cache

If `design_tokens_hash` changes (i.e. brand tokens were edited), the calling skill should:
1. Warn the user that the design system has changed
2. Mark all existing assets as "needs re-review" (don't auto-delete — that's destructive)
3. Offer to regenerate any assets that fail re-review under the new tokens

## Reading the manifest from another tool

```python
import json, pathlib

manifest_path = pathlib.Path(".asset-cache/manifest.json")
if manifest_path.exists():
    manifest = json.loads(manifest_path.read_text())
    existing_ids = {a["id"] for a in manifest["assets"]}
    # Skip generation for already-approved assets:
    for request_id in planned_assets:
        if request_id in existing_ids:
            continue
        # ... generate ...
```

## What's NOT in the manifest

- API keys (never)
- Cached image bytes (those live in `.asset-cache/<hash>.png`)
- Per-asset metadata sidecars (`<asset>.meta.json` — those are per-file companions)
- Token costs for review (rolled into `cost_usd_estimate` only)

The manifest is meant to be checked in to source control alongside the project, while `.asset-cache/` (the binary cache) is gitignored.
