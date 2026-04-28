# Router Test Cases

Deterministic test cases for `scripts/route_asset.py`. These document the routing logic and protect against regressions when adding new rules.

To run all tests at once, see the test script at the bottom of this file.

## Expected behavior

| Request | Expected `asset_type` | Expected `route` | Expected `refuse` | Notes |
|---------|----------------------|------------------|-------------------|-------|
| `hero photo for about page` | `photo` | `generate_asset.py` | `false` | Standard photographic hero |
| `hero photo for home page` | `photo` | `generate_asset.py` | `false` | The word "home" must NOT trigger icon classification |
| `hero image for landing page` | `photo` | `generate_asset.py` | `false` | "Hero" + "image" both photo-routing keywords |
| `Open Graph share card for pricing` | `og` | `generate_asset.py` | `false` | "Open Graph" must NOT trigger chart classification (the word "graph") |
| `Twitter card for new feature launch` | `og` | `generate_asset.py` | `false` | Social card variant |
| `meta image for blog post` | `og` | `generate_asset.py` | `false` | "Meta image" is a synonym for OG card |
| `spot illustration for empty state` | `illustration` | `generate_asset.py` | `false` | Standard illustration request |
| `decorative wave divider` | `decorative_svg` | `HAND_WRITE_SVG` | `false` | Routes to inline SVG, no API call |
| `seamless texture pattern` | `pattern` | `generate_asset.py` | `false` | Texture/pattern goes to image gen |
| `brand logo concept` | `logo_concept` | `generate_asset.py` | `false` | Logo request |
| `favicon` | `logo_concept` | `generate_asset.py` | `false` | Favicon counted as logo |
| `menu icon` | `icon` | `fetch_icon.py` | `false` | Explicit icon keyword |
| `menu` | `icon` | `fetch_icon.py` | `false` | Standalone icon name |
| `hamburger` | `icon` | `fetch_icon.py` | `false` | Standalone synonym |
| `user profile icon` | `icon` | `fetch_icon.py` | `false` | "icon" keyword wins over "user" being a single word |
| `heart icon` | `icon` | `fetch_icon.py` | `false` | |
| `calendar` | `icon` | `fetch_icon.py` | `false` | Standalone single-word request |
| `bar chart of monthly revenue` | `chart` | `USE_CHARTING_LIBRARY` | `true` | Refuse — charts must be code-rendered |
| `pie chart of user engagement` | `chart` | `USE_CHARTING_LIBRARY` | `true` | Refuse |
| `data viz for the dashboard` | `chart` | `USE_CHARTING_LIBRARY` | `true` | "Data viz" is a chart synonym |
| `photo of Mr. Johnson, our CEO` | `refuse_real_person` | `DO_NOT_GENERATE` | `true` | Refuse — never generate likenesses of real people |
| `real product photo for our sauce bottle` | `refuse_real_product` | `DO_NOT_GENERATE` | `true` | Refuse — get actual product photography |
| `something for the page` | `unknown` | `ESCALATE` | `true` | Too vague to classify, ask for clarification |
| `` (empty) | `unknown` | `UNKNOWN` | `true` | Empty request is invalid |

## Run all tests

Run the test script from the skill root:

```bash
bash tests/test_router.sh
```

## When tests fail

If a test fails after you change `route_asset.py`, you have two options:

1. **The test reflects the old behavior and the new behavior is correct.** Update the expected value in this file and explain why in your commit message.
2. **The change broke something.** Fix the routing logic so the test passes again.

Don't delete failing tests without one of those two outcomes. The point of these tests is to make routing changes deliberate — the regex patterns interact in subtle ways (e.g. "home" was matching "home" page until the icon pattern got tightened in v1.1).

## Adding new tests

When you add a new asset type or refuse rule, add at least 2 test cases:
1. A canonical positive example
2. A near-miss that should NOT match (e.g. "graph of user growth" matches chart, but "Open Graph" must not)

The near-miss tests are the ones that catch real bugs.
