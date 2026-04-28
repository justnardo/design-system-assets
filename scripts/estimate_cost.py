#!/usr/bin/env python3
"""
estimate_cost.py — Estimate API spend before running a project.

Takes either:
  - A list of asset requests via --request flags (one per asset)
  - An asset_plan.json file with structured requests

Routes each request through the same classifier as route_asset.py, then
adds up estimated costs based on current provider list prices.

Usage:
    # Quick estimate from CLI
    python estimate_cost.py \\
        --request "hero photo for about page" \\
        --request "OG share card for pricing" \\
        --request "menu icon" \\
        --request "user profile icon"

    # From a plan file
    python estimate_cost.py --plan asset_plan.json

asset_plan.json shape:
    {
        "project": "Viceroy",
        "requests": [
            "hero photo for about page",
            "spot illustration for our values",
            "menu icon",
            ...
        ],
        "regen_assumption": 1.3,   // budget for 30% regeneration loops
        "review_per_asset": true   // include review cost?
    }

Pricing assumptions (April 2026, verify before quoting clients):
  - OpenAI gpt-image-1 standard size (1024x1024): ~$0.04
  - OpenAI gpt-image-1 large (1536x1024 or 1024x1536): ~$0.08
  - Gemini image: ~$0.03
  - Claude Sonnet 4.6 (review, ~1k input + 500 output): ~$0.01

These are best-guess midpoints — real rates change. Override with --price
flags if you want to recompute with different numbers.
"""

import argparse
import json
import sys
from pathlib import Path

# Import sibling scripts. They share a directory; making it importable lets
# us reuse the classifier without subprocess overhead.
sys.path.insert(0, str(Path(__file__).parent))
from _common import load_json_file  # noqa: E402
from route_asset import classify  # noqa: E402


# Default per-asset price midpoints (USD). These should be reviewed against
# current provider pricing pages — see references/provider_capabilities.md.
DEFAULT_PRICES = {
    "openai_standard":  0.04,
    "openai_large":     0.08,
    "gemini":           0.03,
    "claude_review":    0.01,
    "icon":             0.00,
    "decorative_svg":   0.00,
    "chart":            0.00,
    "refused":          0.00,
}


def estimate_for_request(request: str, prices: dict[str, float]) -> dict:
    """Classify a request and attach an estimated cost."""
    route = classify(request)
    asset_type = route.asset_type

    if route.refuse and asset_type.startswith("refuse_"):
        return {
            "request": request,
            "asset_type": asset_type,
            "cost_low": 0.0,
            "cost_high": 0.0,
            "note": "REFUSED — " + route.reason,
            "skip_review": True,
        }

    if asset_type == "icon":
        return {
            "request": request,
            "asset_type": "icon",
            "cost_low": prices["icon"],
            "cost_high": prices["icon"],
            "note": "Lucide SVG, no API cost",
            "skip_review": True,
        }

    if asset_type == "decorative_svg":
        return {
            "request": request,
            "asset_type": "decorative_svg",
            "cost_low": prices["decorative_svg"],
            "cost_high": prices["decorative_svg"],
            "note": "Hand-coded SVG",
            "skip_review": True,
        }

    if asset_type == "chart":
        return {
            "request": request,
            "asset_type": "chart",
            "cost_low": prices["chart"],
            "cost_high": prices["chart"],
            "note": "Charting library, not AI",
            "skip_review": True,
        }

    # Raster generation — estimate based on aspect hint
    aspect = route.aspect_hint or "1:1"
    is_large = aspect in ("16:9", "9:16", "4:3", "3:4")
    base_low = prices["openai_large"] if is_large else prices["openai_standard"]
    base_high = base_low

    return {
        "request": request,
        "asset_type": asset_type,
        "cost_low": base_low,
        "cost_high": base_high,
        "note": f"Raster image ({aspect})",
        "skip_review": False,
    }


def estimate_total(
    requests: list[str],
    prices: dict[str, float],
    regen_assumption: float = 1.3,
    include_review: bool = True,
) -> dict:
    """Estimate total cost for a project's worth of asset requests."""
    items = [estimate_for_request(r, prices) for r in requests]

    raster_count = sum(
        1 for i in items if not i["skip_review"]
    )
    refused_count = sum(
        1 for i in items if i["asset_type"].startswith("refuse_")
    )
    chart_count = sum(1 for i in items if i["asset_type"] == "chart")
    icon_count = sum(1 for i in items if i["asset_type"] == "icon")
    svg_count = sum(1 for i in items if i["asset_type"] == "decorative_svg")

    base_generation = sum(i["cost_low"] for i in items)
    with_regen = base_generation * regen_assumption

    review_cost = 0.0
    if include_review:
        # Each raster gets reviewed; assume regen also gets reviewed
        review_cost = raster_count * regen_assumption * prices["claude_review"]

    total_low = base_generation + (review_cost if include_review else 0)
    total_high = with_regen + (review_cost if include_review else 0)

    # Apply a +25% ceiling to the high estimate to account for variance
    total_high *= 1.25

    return {
        "items": items,
        "summary": {
            "total_assets": len(items),
            "raster_assets": raster_count,
            "icons": icon_count,
            "decorative_svg": svg_count,
            "charts": chart_count,
            "refused": refused_count,
            "regen_assumption": regen_assumption,
            "review_included": include_review,
        },
        "cost_estimate_usd": {
            "low": round(total_low, 2),
            "high": round(total_high, 2),
            "base_generation": round(base_generation, 2),
            "regen_buffer": round(with_regen - base_generation, 2),
            "review": round(review_cost, 2),
        },
    }


def print_human_summary(estimate: dict) -> None:
    s = estimate["summary"]
    c = estimate["cost_estimate_usd"]

    print("Asset breakdown:")
    print(f"  Raster images:  {s['raster_assets']:3d}  (paid generation)")
    print(f"  Icons:          {s['icons']:3d}  (free, Lucide SVG)")
    print(f"  Decorative SVG: {s['decorative_svg']:3d}  (free, hand-coded)")
    print(f"  Charts:         {s['charts']:3d}  (free, charting library)")
    if s["refused"]:
        print(f"  Refused:        {s['refused']:3d}  (need real photos / different approach)")
    print()
    print("Cost estimate:")
    print(f"  Base generation:   ${c['base_generation']:.2f}")
    print(f"  Regen buffer ({int(s['regen_assumption']*100)}%): +${c['regen_buffer']:.2f}")
    if s["review_included"]:
        print(f"  Review (Claude):   +${c['review']:.2f}")
    print(f"  ----")
    print(f"  Estimated total:   ${c['low']:.2f} – ${c['high']:.2f}")
    print()
    if any(i["asset_type"].startswith("refuse_") for i in estimate["items"]):
        print("⚠️  Some requests were refused — see itemized list below.")
    if any(i["asset_type"] == "unknown" for i in estimate["items"]):
        print("⚠️  Some requests couldn't be classified — be more specific.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Estimate API cost for a project's asset needs.")
    parser.add_argument(
        "--request", action="append", default=[],
        help="Add an asset request (repeatable). E.g. --request 'hero photo' --request 'menu icon'",
    )
    parser.add_argument("--plan", help="Path to asset_plan.json")
    parser.add_argument("--regen", type=float, default=1.3,
                        help="Regeneration multiplier (default 1.3 = budget for 30%% regens)")
    parser.add_argument("--no-review", action="store_true",
                        help="Don't include review costs in estimate")
    parser.add_argument("--json", action="store_true",
                        help="Output JSON instead of human summary")
    args = parser.parse_args()

    requests: list[str] = list(args.request)
    include_review = not args.no_review
    regen = args.regen

    if args.plan:
        plan = load_json_file(args.plan, label="plan file")
        requests.extend(plan.get("requests", []))
        if "regen_assumption" in plan:
            regen = plan["regen_assumption"]
        if "review_per_asset" in plan:
            include_review = plan["review_per_asset"]

    if not requests:
        print("ERROR: provide at least one --request or a --plan file", file=sys.stderr)
        return 1

    estimate = estimate_total(
        requests, DEFAULT_PRICES,
        regen_assumption=regen,
        include_review=include_review,
    )

    if args.json:
        print(json.dumps(estimate, indent=2))
    else:
        print_human_summary(estimate)
        print()
        print("Itemized:")
        for item in estimate["items"]:
            req = item["request"][:50] + ("..." if len(item["request"]) > 50 else "")
            print(f"  ${item['cost_low']:.2f}  [{item['asset_type']:20s}]  {req}")
            if item.get("note") and item["asset_type"].startswith("refuse_"):
                print(f"         ↳ {item['note']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
