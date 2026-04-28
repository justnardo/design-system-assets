# design-system-assets

A Claude Code skill that generates brand-aware visual assets — hero photos, illustrations, icons, OG cards — that actually match your project's design system instead of looking like generic AI output.

**The problem:** AI-built sites look like AI-built sites. Hero images don't match the brand. Icons get bitmap-rendered with artifacts. Multiple assets in the same project don't visually agree with each other. The asset layer is treated as an afterthought.

**The fix:** read the design system FIRST, route each asset to the right generator (icons → SVG library, photos → image AI), inject the brand directives into every prompt, and review output against the brand before placing it. Bring your own API keys.

## Before / After

Coming after the first real client project test. The intent is a side-by-side:

- **Before:** the same client site with default AI placeholder assets — generic stock-style photos, bitmap icons, a hero image that could be for any business in the same industry.
- **After:** the same site after the skill runs — assets that visibly carry the client's brand colors, typography, and visual register, with icons cleanly themed and assets visually agreeing across the page.

If you ship a project using this skill and want to contribute a before/after, open a PR with the screenshots in `examples/`.

## Installation

This is a Claude Code skill. You can install it automatically using the provided install script:

```bash
# Clone or download this repo, then run:
./install.sh

# Restart Claude Code to pick up the new skill.
```

Alternatively, you can install it manually by copying the directory:

```bash
cp -r design-system-assets ~/.claude/skills/
```

Or as a `.skill` file:

```bash
claude skills install design-system-assets.skill
```

## Quick start

1. **Add your keys** to a project `.env` (see `.env.example`):
   ```bash
   export OPENAI_API_KEY=sk-proj-...
   export ANTHROPIC_API_KEY=sk-ant-...
   ```

2. **Make sure the project has a design system.** Either a `DESIGN.md` (template provided), a `tailwind.config.js`, or CSS variables. Without these, the skill won't generate generic assets — it'll ask you to provide brand direction.

3. **Ask Claude in your project**:
   > "I'm building the about page hero. Use the design-system-assets skill to generate a hero image of an elderly woman gardening, and an icon for the contact section."

   Claude will read the design system, route the icon through Lucide (no API call), generate the hero photo through OpenAI with brand directives baked in, review the output against the brand, and place approved assets in your project.

## What's in the box

```
design-system-assets/
├── SKILL.md                          # Workflow & decision rules
├── README.md                         # This file
├── TESTS.md                          # Router test cases for contributors
├── .env.example                      # BYOK starter
├── scripts/
│   ├── parse_design_system.py        # Extracts brand tokens from DESIGN.md, Tailwind, CSS vars
│   ├── route_asset.py                # Deterministic classifier: which generator handles which request
│   ├── generate_asset.py             # Brand-aware image generation (OpenAI, Gemini)
│   ├── fetch_icon.py                 # Lucide SVG icons with brand-color theming
│   ├── review_asset.py               # Vision-model brand review with strict/balanced/fast modes
│   └── estimate_cost.py              # Pre-run cost estimate from a list of asset requests
├── references/
│   ├── asset_routing.md              # Which generator for which asset type
│   ├── prompt_engineering.md         # How design tokens become prompt prefix
│   ├── provider_capabilities.md      # API capabilities and cost planning
│   ├── review_rubric.md              # 5-dimension scoring criteria
│   ├── manifest_schema.md            # Project manifest format (.asset-cache/manifest.json)
│   ├── byok_setup.md                 # API key setup and troubleshooting
│   └── scope_questions.md            # Extended scope confirmation for complex projects
└── templates/
    ├── DESIGN_md_template.md         # Brand-system template with worked example
    └── asset_plan.example.json       # Sample plan for the cost estimator
```

## Why this skill exists (the design philosophy)

Most existing AI asset tools take a request and call an image API. This produces generic-looking output because the request is generic. A photo prompt without brand context becomes a stock photo. An icon request through bitmap AI becomes a fuzzy icon.

This skill is opinionated about a few things:

1. **Read the design system before generating anything.** No prompt should hit an image API without the project's brand voice baked in.
2. **Icons are NEVER bitmap.** They're SVG, themed via `currentColor` or explicit color tokens, pulled from a library (Lucide).
3. **Style anchor first for multi-asset projects.** Generate one reference, use it to constrain the rest.
4. **Review before placing.** Every raster asset gets scored against the brand; failures regenerate or escalate.
5. **Bring your own keys.** No hosted service, no middleman, no rate-limited free tier. You pay providers directly at list price.

## Roadmap

- [ ] Future OpenAI image model support as new production models become available
- [ ] Flux 1.1 Pro via Replicate as a third provider
- [ ] Ideogram for OG cards with text rendering
- [ ] Auto-resize pipeline for responsive image sets (mobile/tablet/desktop)
- [ ] WebP/AVIF conversion step
- [ ] Heroicons and Tabler icon fallbacks
- [ ] `--override-prefix` flag for advanced prompt control
- [ ] Multi-reference compositing for character/product consistency across a series

## Built by

[**Just_Nardo**](https://github.com/Just_Nardo) — built this because I needed it on real client projects. The existing AI tooling doesn't read your design system before generating, so the output never quite matches the brand. This skill closes that gap.

If you ship something useful with it, open an issue or a PR. Contributions welcome.

## License

MIT — use, fork, modify freely.
