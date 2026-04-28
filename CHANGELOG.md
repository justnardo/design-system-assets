# CHANGELOG

## v1.2 — Documentation polish + contributor onboarding

Small but real fixes from the second review pass. No code changes to the runtime; this version makes the package consistent with itself and easier for contributors to pick up.

### Fixed

- **Wrong script count in v1.1 changelog and quickstart.** v1.1 added TWO scripts (`route_asset.py` AND `estimate_cost.py`) but my own changelog said "5 scripts (was 4)" — the actual count was 6. The quickstart still said "4 Python scripts" because it was the v1.0 version and never got updated. Both now correctly say 6 scripts.
- **Stale `GPT-Image-2` reference in QUICKSTART.md.** I updated the README and provider docs in v1.1 but missed the quickstart. Now uses model-agnostic forward-looking language consistent with the rest of the docs.

### Added

- **`TESTS.md`** at the skill root — 23 documented router test cases covering all the regex edge cases I fought during v1.1 (the "Open Graph"-vs-chart bug, the "home page"-vs-icon bug, refuse rules for real people and real products, etc.). Includes a runnable shell script for contributors to verify the router after they make changes. All 23 cases verified passing before commit.
- **`templates/asset_plan.example.json`** — sample asset plan showing the cost estimator's input format. Run with `python scripts/estimate_cost.py --plan templates/asset_plan.example.json` for a concrete walkthrough.
- **Before/After section in README** — placeholder structure for visual proof. Will fill in after the first real Viceroy run produces real screenshots.

### Skill manifest stats (corrected)

- 6 scripts (parse, route, generate, fetch_icon, review, estimate_cost)
- 7 reference docs (asset_routing, prompt_engineering, provider_capabilities, review_rubric, manifest_schema, byok_setup, scope_questions)
- 2 template files (DESIGN_md_template.md, asset_plan.example.json)
- 1 test doc (TESTS.md)
- 19 files total in the package

---

## v1.1 — Review feedback round

This version addresses external review feedback on v1.0. Most changes were genuine improvements; one suggestion was deferred to a future version with explicit reasoning.

### Added

- **`scripts/route_asset.py`** — deterministic CLI classifier. Replaces the implicit-only routing logic in v1.0. External tools and orchestrators can now classify asset requests without an LLM call. Returns JSON with `asset_type`, `route`, `needs_api`, `aspect_hint`, and `refuse` fields. Refuses real-person requests, real-product photo requests, and chart/data-viz requests.
- **`scripts/estimate_cost.py`** — pre-flight cost estimator. Takes a list of asset requests, classifies each, and returns a low/high cost estimate with itemized breakdown. Critical for client work — let agency owners quote with real numbers.
- **`references/manifest_schema.md`** — formal schema for `.asset-cache/manifest.json`. Defines the asset audit trail format so the skill is reusable across runs and other tools can read what's been generated.
- **Approval modes** in `review_asset.py` (`--mode strict|balanced|fast`). Strict (default) for client work; balanced for internal projects; fast for prototyping. Different score thresholds for each.
- **Configurable Claude model** for review via `ANTHROPIC_MODEL` env var or `--model` flag. Default changed to `claude-sonnet-4-6` (vision-capable, ~5x cheaper than Opus, plenty for review work).

### Fixed

- **Wrong default Claude model.** v1.0 hardcoded `claude-opus-4-5` (which doesn't exist as a current model). v1.1 defaults to `claude-sonnet-4-6` and is configurable.
- **Misleading reference to `route_asset.py` in SKILL.md** when no such file existed. The script now exists.
- **Router classifying "Open Graph share card" as a chart** — the `\bgraph\b` pattern was matching "Graph" in "Open Graph". OG/social rules now run before chart rules, and the chart rule no longer matches the bare word `graph`.
- **Router classifying "hero photo for home page" as an icon** — the icon pattern was matching the word "home". Icon classification now requires either an explicit "icon"/"glyph"/"symbol" keyword OR a standalone single-word request.
- **Stale GPT-Image-2 references** in README and provider docs. Replaced with model-agnostic forward-looking language so the repo doesn't go out of date as model names change.

### Considered and deferred

- **Responsive output naming convention.** Suggestion was to define `about-hero.desktop.png` / `.tablet.png` / `.mobile.png` now even without resize implementation. Pushed back: the right responsive approach is one high-resolution generation + Pillow/sharp resize, not three separate generations (which would have style drift — the exact problem this skill exists to solve). Adding Pillow as a dep breaks the pure-stdlib simplicity. Marked as v2 with explicit reasoning.
- **Example project with before/after screenshots.** Can't be built from a sandboxed environment — needs real API access. To be done after first real client run (Viceroy).

---

## v1.0 — Initial release

Initial skill with parser, generator, icon fetcher, reviewer.
