# Scope Questions

The skill always asks about scope before running on a new project. For simple projects (single page, clear brand) the basic two questions in SKILL.md are enough. For complex projects, work through these.

## When to use the extended set

- Multi-page or multi-section site
- Multiple sub-brands or product lines
- Mixed asset needs (some real photos, some AI, some stock)
- Tight client budget where every API call matters
- Brand is still being established (no DESIGN.md yet)

## The extended question set

### Scope clarification

1. **Which pages/sections need assets?** Get a list. "All of them" is not a list — push for specifics so we can estimate cost.

2. **For each section, what asset types?** Photo, illustration, icon, decorative SVG, OG image. The router decides per-asset, but the user's intent matters.

3. **Is anyone supplying real photos?** If the client has product photos, team photos, or campaign shots already, we use those — no AI for those slots. Only AI-generate where there's a real gap.

4. **Are there any "must NOT use AI" categories?** Some clients (medical, legal, journalism) have rules against AI imagery for editorial use. Confirm before generating.

### Brand clarification (if no DESIGN.md exists)

5. **What three adjectives describe the brand visually?** Specifically visually — not "trustworthy and innovative" but "warm, hand-made, light-filled."

6. **Show me one image that captures the brand mood.** A reference image, even from a competitor or unrelated source, gets us further than 1000 words of description.

7. **What styles is the brand explicitly NOT?** "We don't want to look like Apple / Salesforce / a tech startup / a corporate stock photo / etc." Negative space matters.

### Cost & cadence

8. **Budget tolerance for API spend?** Hard ceiling: $X. Or "no ceiling, optimize for quality."

9. **One pass or iterative?** "Generate everything once" is faster but lower quality. "Generate, review, refine" produces better assets but costs more in API and human review time.

10. **Should we cache aggressively?** If the project is going to rebuild repeatedly during development, aggressive caching saves money. If the design system is still moving, frequent cache invalidation is healthier.

### Technical placement

11. **Where do approved assets go?** `/public/images/`, `/src/assets/`, or another path. Match the project's existing convention.

12. **Are there responsive size requirements?** Some sites need 3 sizes per hero image (mobile, tablet, desktop). Plan for that — `generate_asset.py` doesn't auto-resize; you'd run the cached image through a resize pipeline.

13. **Does the project need WebP/AVIF conversion?** Image AI returns PNG/JPEG; web optimization happens downstream.

## Quick estimation script

For sizing the project before starting, ask the user to roughly estimate counts and use this formula:

```
total_raster = hero_count + og_count + spot_illustration_count
total_icons  = icon_count   # free, no API spend
total_decorative = decorative_count  # free, hand-coded SVG

estimated_api_cost_usd = total_raster * 0.10  # OpenAI gpt-image-1 standard size
                       * 1.3                  # add 30% for regeneration loops
                       * 1.0                  # multiplier for review (Claude vision is much cheaper)
```

A typical 5-page brand site lands at ~$1.50 in API spend. A 10-section landing page with hero illustrations on each section might be $3–$5. If your estimate exceeds $20, scope is likely too aggressive — break the project into phases.

## Trigger for falling back to alternatives

If the user's answers indicate ANY of the following, recommend skipping AI generation for those slots:

- "Strict $0 budget" → Unsplash/Pexels stock with attribution, or hand-coded SVG illustrations
- "All assets must be of real people we can identify" → No AI; client-supplied photos only
- "We're a regulated industry that prohibits AI imagery" → No AI; respect the rules
- "We already have a stock photo subscription" → Use what they have
