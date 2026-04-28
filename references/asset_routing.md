# Asset Routing

Decision logic for choosing the right generator for each asset request. Reading this matters because the most common failure mode of AI-generated frontends is sending the wrong asset type through the wrong generator — usually icons through raster image AI.

## The decision table

| Asset type | Canonical examples | Route to | Why |
|------------|-------------------|----------|-----|
| Functional icon | menu, search, close, arrow, heart, cart | `fetch_icon.py` (Lucide SVG) | Icons need to be SVG. Raster AI produces pixel artifacts, inconsistent strokes, and the result can't be themed via CSS. Lucide covers ~1,500 commonly-needed icons. |
| Logo / wordmark | brand mark, favicon | Code-generated SVG, OR one-time image gen + manual vectorize | Logos must be vector for scalability. Generate once, save as SVG, never regenerate per request. |
| Decorative SVG | dividers, badges, simple shapes, stars | Hand-write SVG inline | Trivial to write directly, no API call needed, themes via `currentColor`. |
| Photography | hero photos, lifestyle shots, team-style placeholders | `generate_asset.py --type photo` | Image AI is genuinely good at photography. This is its core strength. |
| Illustration | spot illustrations, empty states, hero art, character art | `generate_asset.py --type illustration` | Image AI handles illustrations well, especially with strong style direction. |
| Pattern / texture | repeating backgrounds, decorative fills | `generate_asset.py --type pattern` | Image AI can do this; just keep aspect ratio in mind. |
| OG / social card | Open Graph images, Twitter cards | `generate_asset.py --type og` | These are 1200×630 raster compositions with text overlay; image AI handles them, but consider compositing text in code post-generation for crisp typography. |
| Chart / graph | data visualizations | Use a charting library (Recharts, Chart.js, D3) — NOT image AI | Charts must be data-bound. Image AI can fake them but they're not real. Code generates them from data. |
| Product photo (real product) | actual SKUs the client sells | Client supplies, OR explicit AI mockup with disclosure | Don't fake products. If the client sells an actual physical good, ask them for photos. AI mockups are OK only with explicit user awareness. |
| People (real, identified) | a specific person | Don't generate | Never AI-generate a likeness of a real, identifiable person without their consent. Use stock or get a real photo. |

## Edge cases

**"I need an icon for X but Lucide doesn't have it."** First try `--search` to see if there's a synonym match. If no, the second-best options in order are:
1. Hand-write a simple SVG (most icons are simple paths)
2. Use Heroicons or Tabler as a fallback library
3. Generate as an illustration with explicit "flat icon style, single color, transparent background" directives — accept that quality will be lower than a library icon

**"I need a brand logo and the client doesn't have one."** Don't auto-generate logos as part of a normal asset pass. Logos deserve a dedicated session with multiple iterations and human review. Tell the user: "I'd treat logo design as a separate task — it benefits from focused iteration rather than batch generation."

**"I need a hero image but the client's industry has visual conventions (e.g. dental office, law firm, restaurant)."** Industry conventions go in the design tokens (`industry` field) and in the per-asset prompt. Image AI knows what dental offices look like; the directive is just to make the look match THIS client's brand within those conventions.

**"I need an OG image with the client's logo + tagline."** Generate the background art with `--type og`, then composite the logo and text in code (e.g., `sharp` in Node, PIL in Python, or HTML-to-image with Satori). Image AI handles text rendering inconsistently; in-code compositing is reliable.

**"The client uses Material/Chakra/Mantine icons, not Lucide."** Pull from those libraries directly via npm rather than fetching from Lucide. Update the icon source if you're working in a project that has an icon system already in place — don't introduce a second one.

## Why icons are non-negotiable as SVG

A bitmap icon at 24×24 has 576 pixels to work with. Image AI doesn't produce clean lines at that resolution; you get fuzzy edges, inconsistent stroke widths between icons in the same set, and artifacts that look like compression damage. SVG icons are vector — sharp at any size — and use `stroke="currentColor"` so they pick up CSS color, which means the SAME icon file works in light mode and dark mode and across different sections of the site without regeneration.

If you ever find yourself routing an icon request through the image generator, stop and re-route through `fetch_icon.py`.
