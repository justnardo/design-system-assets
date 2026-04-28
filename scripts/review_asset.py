#!/usr/bin/env python3
"""
review_asset.py — Score a generated asset against the project's design system.

Uses Claude's vision capability (via the Anthropic API) to evaluate a generated
image on five dimensions, then returns a pass/regenerate/escalate verdict.

This is the "look at it like a designer would" step. Without it, you ship
generic-looking assets through to the project even when they fail the brand.

Five scoring dimensions (0-10 scale):
  1. color_match       - Do the dominant colors match the brand palette?
  2. style_consistency - Does it match the project's visual register
                          (editorial vs minimal vs playful, etc.)?
  3. subject_correctness - Does the image actually depict what was requested?
  4. technical_quality - Is it free of obvious AI artifacts (extra fingers,
                          warped text, blurred subjects, weird anatomy)?
  5. brand_fit         - Would a designer for this brand approve it?

Verdict logic:
  - All scores >= 7 AND average >= 8        -> approved
  - Any score < 5 OR average < 6.5          -> regenerate (with feedback)
  - Hard fails (e.g. wrong subject)         -> escalate_to_human

Usage:
    python review_asset.py \\
        --asset assets/about-hero.png \\
        --tokens design_tokens.json \\
        --intent "warm editorial hero showing elderly resident gardening"

    # Output JSON only (for chaining in scripts)
    python review_asset.py --asset ... --tokens ... --intent ... --json
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path
from typing import Any

from _common import load_json_file, post_json


CLAUDE_API_URL = "https://api.anthropic.com/v1/messages"
# Default to Sonnet 4.6 — vision-capable, 5x cheaper than Opus, plenty for
# image review. Override with ANTHROPIC_MODEL for Opus 4.7 (most rigorous)
# or Haiku 4.5 (cheapest, lower quality). See provider_capabilities.md.
DEFAULT_REVIEW_MODEL = "claude-sonnet-4-6"
ANTHROPIC_VERSION = "2023-06-01"

SCORE_KEYS = (
    "color_match",
    "style_consistency",
    "subject_correctness",
    "technical_quality",
    "brand_fit",
)


# Approval mode thresholds. Each mode defines (min_per_dim, min_avg) for
# the "approved" verdict. Below those numbers, the asset is regenerated
# (or escalated for hard fails / very low scores).
APPROVAL_MODES = {
    "strict":   {"min_per_dim": 7, "min_avg": 8.0,
                 "regen_floor": 5, "escalate_avg": 6.5},
    "balanced": {"min_per_dim": 6, "min_avg": 7.0,
                 "regen_floor": 4, "escalate_avg": 5.5},
    "fast":     {"min_per_dim": 4, "min_avg": 6.0,
                 "regen_floor": 3, "escalate_avg": 4.5},
}


REVIEW_SYSTEM_PROMPT = """\
You are a senior brand designer reviewing AI-generated visual assets for a real
client project. Your job is to catch generic, off-brand, or technically broken
assets BEFORE they ship to a client site.

Be honest and rigorous. The whole point of this review is to prevent low-quality
output from going live. If something feels generic or "AI-y," call it out and
score it accordingly. If colors don't match the brand palette, the score must
reflect that.

You will respond with a JSON object — and ONLY a JSON object — with this shape:

{
  "scores": {
    "color_match": <0-10>,
    "style_consistency": <0-10>,
    "subject_correctness": <0-10>,
    "technical_quality": <0-10>,
    "brand_fit": <0-10>
  },
  "observations": "<2-4 sentences of concrete observations>",
  "regenerate_advice": "<if regeneration is needed, specific prompt-tweak advice. Otherwise empty string>",
  "hard_fail_reason": "<if there is a hard fail (wrong subject, broken image, offensive content), describe it. Otherwise empty string>"
}

Scoring guidance:
- 9-10: Excellent. Indistinguishable from professional brand work.
- 7-8: Good. Minor refinements possible but acceptable to ship.
- 5-6: Borderline. Has issues but might work in some contexts.
- 3-4: Poor. Should be regenerated with specific feedback.
- 0-2: Hard fail. Wrong subject, broken render, or off-brand to the point
       of being unusable.

If subject_correctness is 0-2, set hard_fail_reason — that's an escalate.
"""


def encode_image_to_base64(path: Path) -> tuple[str, str]:
    """Return (base64_data, media_type) for the image."""
    suffix = path.suffix.lower()
    media_type = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
        ".gif": "image/gif",
    }.get(suffix)
    if not media_type:
        raise ValueError(
            f"Unsupported image type: {suffix}. "
            f"Convert to PNG/JPG/WebP first."
        )
    data = base64.standard_b64encode(path.read_bytes()).decode("ascii")
    return data, media_type


def build_user_prompt(tokens: dict[str, Any], intent: str) -> str:
    """Build the per-asset review prompt based on tokens + caller intent."""
    lines = ["Review the attached image against this brand and intent:"]
    lines.append("")
    lines.append("BRAND")
    if tokens.get("industry"):
        lines.append(f"  Industry: {tokens['industry']}")
    if tokens.get("tone"):
        lines.append(f"  Tone: {tokens['tone']}")

    colors = tokens.get("colors", {})
    color_lines = []
    for label in ("primary", "secondary", "accent", "background", "text"):
        if label in colors and colors[label]:
            color_lines.append(f"{label} {colors[label]}")
    if color_lines:
        lines.append(f"  Palette: {', '.join(color_lines)}")
    elif "accent_palette" in colors:
        lines.append(f"  Palette: {', '.join(colors['accent_palette'])}")

    typography = tokens.get("typography", {})
    if typography:
        font_lines = [f"{k}={v}" for k, v in typography.items()]
        lines.append(f"  Typography: {', '.join(font_lines)}")

    include = tokens.get("style_directives", {}).get("include", [])
    exclude = tokens.get("style_directives", {}).get("exclude", [])
    if include:
        lines.append(f"  DO use: {', '.join(include)}")
    if exclude:
        lines.append(f"  AVOID: {'; '.join(exclude)}")

    lines.append("")
    lines.append(f"INTENT (what this asset should depict and accomplish)")
    lines.append(f"  {intent}")
    lines.append("")
    lines.append("Now produce the JSON review.")

    return "\n".join(lines)


def call_claude_vision(
    image_b64: str,
    media_type: str,
    user_prompt: str,
    api_key: str,
    model: str | None = None,
) -> str:
    """Call Claude with the image attached. Returns the model's text response."""
    chosen_model = model or os.environ.get("ANTHROPIC_MODEL", DEFAULT_REVIEW_MODEL)
    payload = post_json(
        CLAUDE_API_URL,
        body={
            "model": chosen_model,
            "max_tokens": 1024,
            "system": REVIEW_SYSTEM_PROMPT,
            "messages": [{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": user_prompt},
                ],
            }],
        },
        headers={
            "x-api-key": api_key,
            "anthropic-version": ANTHROPIC_VERSION,
        },
        timeout=120,
        provider_name="Anthropic",
    )

    content = payload.get("content", [])
    for block in content:
        if block.get("type") == "text":
            return block.get("text", "")
    raise RuntimeError(f"No text response from Claude: {payload}")


def parse_review_response(text: str) -> dict[str, Any]:
    """Extract the JSON review object from Claude's response."""
    # Strip code fences if present
    cleaned = text.strip()
    if cleaned.startswith("```"):
        # Drop opening fence and any language tag
        cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()
    if cleaned.startswith("json"):
        cleaned = cleaned[4:].strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        # Try to find a JSON object in the response
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            try:
                return json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                pass
        raise RuntimeError(
            f"Could not parse review JSON. Response was:\n{text[:500]}"
        ) from e


def extract_scores(scores: dict[str, Any]) -> list[float] | None:
    """
    Return the 5 score values in canonical order, or None if any required
    dimension is missing or non-numeric. A None return means the model
    response was malformed; callers should escalate rather than guess at
    a verdict from a partial score set.
    """
    values: list[float] = []
    for k in SCORE_KEYS:
        v = scores.get(k)
        if not isinstance(v, (int, float)) or isinstance(v, bool):
            return None
        values.append(float(v))
    return values


def compute_verdict(review: dict[str, Any], mode: str = "strict") -> str:
    """Apply the verdict rules using the chosen approval mode."""
    if review.get("hard_fail_reason", "").strip():
        return "escalate_to_human"

    values = extract_scores(review.get("scores", {}))
    if values is None:
        # Truncated / malformed score set — never approve on partial data.
        return "escalate_to_human"

    thresholds = APPROVAL_MODES.get(mode, APPROVAL_MODES["strict"])

    # Anything beneath the regen_floor is an immediate regenerate.
    if any(v < thresholds["regen_floor"] for v in values):
        return "regenerate"

    avg = sum(values) / len(values)

    # Approved: meets both per-dim minimum AND average threshold.
    if avg >= thresholds["min_avg"] and all(v >= thresholds["min_per_dim"] for v in values):
        return "approved"

    # Above the regen floor but below approval = regenerate with feedback.
    if avg >= thresholds["escalate_avg"]:
        return "regenerate"

    # Below the escalate average = escalate to human.
    return "escalate_to_human"


def main() -> int:
    parser = argparse.ArgumentParser(description="Review a generated asset against brand.")
    parser.add_argument("--asset", required=True, help="Path to image file")
    parser.add_argument("--tokens", required=True, help="Path to design_tokens.json")
    parser.add_argument("--intent", required=True, help="What the asset is supposed to depict/accomplish")
    parser.add_argument(
        "--mode", choices=("strict", "balanced", "fast"), default="strict",
        help="Approval threshold (strict=client work, balanced=internal, "
             "fast=prototyping). Default: strict.",
    )
    parser.add_argument(
        "--model",
        help="Override Claude model (default: claude-sonnet-4-6, or "
             "ANTHROPIC_MODEL env var)",
    )
    parser.add_argument("--json", action="store_true",
                        help="Output JSON only (for piping)")
    args = parser.parse_args()

    asset_path = Path(args.asset)
    if not asset_path.exists():
        print(f"ERROR: asset not found: {asset_path}", file=sys.stderr)
        return 1

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print(
            "ERROR: ANTHROPIC_API_KEY not set.\n"
            "Run: export ANTHROPIC_API_KEY=sk-ant-...",
            file=sys.stderr,
        )
        return 3

    tokens = load_json_file(args.tokens, label="tokens file")
    image_b64, media_type = encode_image_to_base64(asset_path)
    user_prompt = build_user_prompt(tokens, args.intent)

    response_text = call_claude_vision(
        image_b64, media_type, user_prompt, api_key, model=args.model,
    )
    review = parse_review_response(response_text)
    verdict = compute_verdict(review, mode=args.mode)

    result = {
        "asset": str(asset_path),
        "verdict": verdict,
        "mode": args.mode,
        "review": review,
    }

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        scores = review.get("scores", {})
        # Average only over the canonical 5 dimensions. If any are missing,
        # report N/A — never an inflated mean over a partial response.
        validated = extract_scores(scores)
        avg_str = f"{sum(validated) / len(validated):.1f}/10" if validated else "N/A (incomplete scores)"
        print(f"Asset: {asset_path}")
        print(f"Mode: {args.mode}")
        print(f"Verdict: {verdict.upper()}")
        print(f"Average score: {avg_str}")
        for k in SCORE_KEYS:
            print(f"  {k + ':':21s}{scores.get(k, 'N/A')}")
        print(f"\nObservations: {review.get('observations', '')}")
        if review.get("regenerate_advice"):
            print(f"\nRegenerate advice: {review['regenerate_advice']}")
        if review.get("hard_fail_reason"):
            print(f"\nHARD FAIL: {review['hard_fail_reason']}")

    # Exit code reflects the verdict so callers can branch on it.
    return {
        "approved": 0,
        "regenerate": 4,
        "escalate_to_human": 5,
    }.get(verdict, 1)


if __name__ == "__main__":
    sys.exit(main())
