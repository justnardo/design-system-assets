# Contributing to design-system-assets

Thanks for considering a contribution. This is a pragmatic project — the goal is for AI-built sites to stop looking AI-built. PRs that move the needle on that are welcome.

## Quick orientation

The skill is structured around five steps: parse the design system, route the asset request, generate, review, place. Each script in `scripts/` corresponds to one of those steps, and the reference docs in `references/` explain the reasoning. Read `SKILL.md` first — it's the workflow Claude itself follows when using the skill, and it's the best map of how the pieces fit together.

## Setup for development

```bash
git clone https://github.com/justnardo/design-system-assets.git
cd design-system-assets

# All scripts are pure-stdlib Python 3.10+, no pip install needed
python3 --version    # should be 3.10 or higher

# Set keys (see .env.example)
cp .env.example .env
# fill in your keys, then:
source .env
```

## Before submitting a PR

**1. Run the router tests.** If you touched `scripts/route_asset.py`, the 23 cases in `TESTS.md` must still pass:

```bash
# Quick way — extract and run the test script from TESTS.md
# Or run a one-off check on a few cases manually:
python scripts/route_asset.py --request "Open Graph share card"
python scripts/route_asset.py --request "hero photo for home page"
python scripts/route_asset.py --request "menu icon"
```

**2. If you added a new asset type or refuse rule:** add at least 2 cases to `TESTS.md`:
- A canonical positive example
- A near-miss that should NOT match

The near-miss cases are the ones that catch real bugs. The "Open Graph"-vs-chart bug was found because we tested a near-miss.

**3. If you added a new script:** update `README.md`'s "What's in the box" section AND `SKILL.md`'s reference list. The package counts in both files should stay accurate.

**4. If you changed default behavior:** update `CHANGELOG.md` with what changed and why.

## Things that need contributors

Open lanes where help would meaningfully move v2:

### Higher priority
- **Pillow-based responsive resize pipeline.** One high-resolution generation + automatic mobile/tablet/desktop variants. The right approach is to generate once at the largest needed size, then resize down — never three independent generations (style drift). Adding Pillow as a dependency is fine if it stays optional.
- **Heroicons / Tabler fallback** in `fetch_icon.py` for icons Lucide doesn't have.
- **WebP/AVIF conversion** as an output option after generation.
- **Manifest writer.** `references/manifest_schema.md` defines the format but no script writes it yet. A small `manifest.py` that generators and reviewers can call would close the loop.

### Lower priority
- **Flux / Replicate provider** added to `generate_asset.py`.
- **Ideogram provider** for OG cards with crisp text.
- **Multi-reference compositing** for character/product consistency across a series.
- **Better synonym coverage in `fetch_icon.py`** — pulling Lucide's full icon list and building a smarter resolver.

### Documentation
- Real before/after screenshots from a shipped project for the README. If you ship something with this skill, please contribute a side-by-side.
- Worked examples for non-Viceroy industries (restaurants, SaaS, financial services) showing how their DESIGN.md should look.

## What WON'T get merged

- Anything that adds a hosted-service component. This is BYOK by design — adding a middleman defeats the open-source positioning.
- Generators for asset categories we explicitly refuse (real people, real products, charts). These are refused for ethical and quality reasons, not technical ones.
- Skills that bypass the design-system parsing step. The whole point is to read the brand first; an "ignore brand and just generate" mode would undermine the project.

## Code style

- Pure stdlib Python preferred. Adding a dep needs a real justification in the PR description (Pillow for resizing is justified; a HTTP client wrapper isn't).
- Type hints encouraged but not required.
- Comments should explain *why*, not *what*. The code already shows what.
- One thing per PR. "Add Heroicons fallback" is one PR; "Add Heroicons + refactor router + update docs" is three.

## License

By contributing, you agree your contributions are licensed under the same MIT license as the rest of the project.

## Questions?

Open an issue or a discussion. Tag with `question` if it's a clarification rather than a feature request or bug.
