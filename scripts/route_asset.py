#!/usr/bin/env python3
"""
route_asset.py — Classify an asset request and route it to the right tool.

Deterministic classifier so that external orchestrators (and Claude itself)
can route asset requests without a per-request LLM call. The decision logic
mirrors the table in references/asset_routing.md.

Usage:
    python route_asset.py --request "hero image for about page"
    python route_asset.py --request "menu icon"
    python route_asset.py --request "Open Graph share card"

Output (JSON):
    {
      "request": "hero image for about page",
      "asset_type": "photo",
      "route": "generate_asset.py",
      "needs_api": true,
      "reason": "Hero image requires raster photography generation."
    }

Exit codes:
    0  - successfully routed
    1  - request was empty or unintelligible
    2  - request matched a "do not generate" category (real people, real
         products, charts) — caller should escalate to human

The classifier is intentionally rule-based, not ML. Rules are easier to
audit, easier to extend, and free to run.
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict


HARD_REFUSE_ROUTES = frozenset({"DO_NOT_GENERATE", "USE_CHARTING_LIBRARY"})


def is_hard_refuse(asset_type: str, route: str) -> bool:
    """A request is a hard refuse if its type is a refuse_* category or its
    route points to a non-generation outcome (charts, do-not-generate)."""
    return asset_type.startswith("refuse_") or route in HARD_REFUSE_ROUTES


@dataclass
class Route:
    request: str
    asset_type: str
    route: str
    needs_api: bool
    reason: str
    aspect_hint: str | None = None
    refuse: bool = False


# Keyword groups, ordered by specificity. First match wins, so put more
# specific patterns first.
RULES: list[tuple[str, list[str], str, str, bool, str | None]] = [
    # (asset_type, keywords, route_script, reason, needs_api, aspect_hint)

    # REFUSE categories — these should never go through any generator.
    (
        "refuse_real_person",
        [r"\b(specific|real|named) (person|people|individual)\b",
         r"\b(ceo|founder|employee) photo\b",
         r"photo of (mr|mrs|ms|dr)\.?\s+\w+"],
        "DO_NOT_GENERATE",
        "Request appears to be for a real, identifiable person — never AI-generate likenesses.",
        False,
        None,
    ),
    (
        "refuse_real_product",
        [r"\b(actual|real) product (photo|shot|image)\b",
         r"\bproduct.*sells?\b.*\b(photo|image|picture)\b"],
        "DO_NOT_GENERATE",
        "Request is for a real product photo — get actual photography from the client.",
        False,
        None,
    ),

    # OG / social cards — must come before 'chart' because "Open Graph"
    # contains the word 'graph' which the chart rule would otherwise match.
    (
        "og",
        [r"\b(og|open graph)\b", r"\bshare (card|image)\b",
         r"\b(twitter|facebook|linkedin) (card|image|preview)\b",
         r"\bsocial (card|image|preview|graphic)\b",
         r"\bmeta (image|preview)\b"],
        "generate_asset.py",
        "Social/OG card requires raster generation with text-rendering provider.",
        True,
        "16:9",
    ),

    (
        "chart",
        [r"\b(chart|plot|visualization|metric)\b",
         r"\bdashboard (chart|metric|visualization|graph|data)\b",
         r"\b(data|metrics?) dashboard\b",
         r"\bdata viz\b", r"\bbar (chart|graph)\b", r"\bline (chart|graph)\b",
         r"\bpie chart\b", r"\bgraph of\b"],
        "USE_CHARTING_LIBRARY",
        "Charts must be code-generated from data, not AI-imagined.",
        False,
        None,
    ),

    # Logos
    (
        "logo_concept",
        [r"\blogo\b", r"\bwordmark\b", r"\bbrand mark\b", r"\bfavicon\b"],
        "generate_asset.py",
        "Logo concept; treat as one-off generation. For final logo, plan dedicated iteration session.",
        True,
        "1:1",
    ),

    # Patterns / textures / backgrounds
    (
        "pattern",
        [r"\b(pattern|texture|background)\b", r"\b(repeating|seamless) (fill|background)\b",
         r"\bdecorative (fill|background)\b"],
        "generate_asset.py",
        "Pattern/texture is raster-suitable.",
        True,
        "1:1",
    ),

    # Icons — broad pattern. Critical that this comes before "illustration"
    # because the word 'icon' often appears in illustration descriptions too.
    # Pattern requires explicit "icon" keyword OR a known icon-name standalone
    # request (e.g. just "menu" or "hamburger") — to avoid matching "home page"
    # or "user research" where the keyword appears in non-icon context.
    (
        "icon",
        [
            # Explicit icon keyword
            r"\bicon\b",
            r"\bglyph\b",
            r"\bsymbol\b",
            # Standalone icon-name requests (full request is just one keyword)
            r"^(menu|search|close|cart|user|profile|heart|star|home|"
            r"settings|hamburger|burger|dismiss|delete|edit|save|find|"
            r"account|basket|bag|preferences|config|back|next|expand|"
            r"collapse|calendar|schedule|date|phone|call|email|message|"
            r"chat|notification|alert|warning|error|info|help|question|"
            r"favorite|like|rating|share|download|upload|more|kebab)$",
        ],
        "fetch_icon.py",
        "Icons should be SVG, themed via CSS. Never bitmap.",
        False,
        None,
    ),

    # Decorative SVG
    (
        "decorative_svg",
        [r"\b(divider|separator|wave|squiggle)\b",
         r"\bbadge\b", r"\bsimple shape\b"],
        "HAND_WRITE_SVG",
        "Decorative SVG — write inline, no API call.",
        False,
        None,
    ),

    # Hero photos / lifestyle / specific photographic descriptors
    (
        "photo",
        [r"\bhero (image|photo|shot)\b",
         r"\b(hero|cover|banner|landing) (image|graphic|visual)\b",
         r"\b(photograph|photographic|photo of)\b",
         r"\b(headshot|portrait|lifestyle shot)\b",
         r"\bteam photo\b"],
        "generate_asset.py",
        "Photographic hero/lifestyle imagery.",
        True,
        "16:9",
    ),

    # Illustrations / spot art
    (
        "illustration",
        [r"\billustration\b", r"\b(spot|hero) art\b",
         r"\bempty state\b", r"\bcharacter (art|illustration)\b",
         r"\bgraphic\b"],
        "generate_asset.py",
        "Illustration — raster generation with strong style direction.",
        True,
        "1:1",
    ),

    # Generic "image" — last resort, defaults to photo
    (
        "photo",
        [r"\b(image|picture|visual)\b"],
        "generate_asset.py",
        "Generic image request; defaulting to photographic register.",
        True,
        "16:9",
    ),
]


def classify(request: str) -> Route:
    """Run the request through the rule list and return the first match."""
    text = request.strip().lower()
    if not text:
        return Route(
            request=request,
            asset_type="unknown",
            route="UNKNOWN",
            needs_api=False,
            reason="Empty request — provide a description of the asset needed.",
            refuse=True,
        )

    for asset_type, patterns, route, reason, needs_api, aspect in RULES:
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                return Route(
                    request=request,
                    asset_type=asset_type,
                    route=route,
                    needs_api=needs_api,
                    reason=reason,
                    aspect_hint=aspect,
                    refuse=is_hard_refuse(asset_type, route),
                )

    return Route(
        request=request,
        asset_type="unknown",
        route="ESCALATE",
        needs_api=False,
        reason=(
            "Could not classify request. Add more specific keywords "
            "(e.g. 'hero image', 'menu icon', 'OG card') or escalate to a human."
        ),
        refuse=True,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify an asset request and route it.")
    parser.add_argument("--request", required=True,
                        help="Natural-language description of the asset needed")
    parser.add_argument("--quiet", action="store_true",
                        help="Output only the JSON, no human-readable summary")
    args = parser.parse_args()

    route = classify(args.request)
    output = asdict(route)

    print(json.dumps(output, indent=2))

    if route.refuse:
        # 2 = hard refuse (real person, real product, chart). 1 = unintelligible.
        return 2 if is_hard_refuse(route.asset_type, route.route) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
