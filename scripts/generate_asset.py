#!/usr/bin/env python3
"""
generate_asset.py — Generate raster brand assets using BYOK image APIs.

Translates design tokens into a "style prefix" that gets prepended to every
prompt, so the output matches the project's brand instead of looking generic.

Supports:
  - OpenAI image API (gpt-image-1, gpt-image-1-mini)
  - Google Gemini image generation (via google-genai)

Bring your own keys via environment:
  OPENAI_API_KEY
  GEMINI_API_KEY

Usage:
    # Generate a hero photo
    python generate_asset.py \\
        --type photo \\
        --tokens design_tokens.json \\
        --prompt "elderly woman gardening in soft afternoon light" \\
        --output assets/about-hero.png \\
        --aspect 16:9

    # Generate a style anchor (do this first for multi-asset projects)
    python generate_asset.py --anchor \\
        --tokens design_tokens.json \\
        --prompt "establishing brand mood reference" \\
        --output .asset-cache/style_anchor.png

    # Force a specific provider
    python generate_asset.py --type illustration --provider gemini ...
"""

import argparse
import base64
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ASSET_TYPES = {"photo", "illustration", "pattern", "og", "logo_concept"}
DEFAULT_PROVIDER_FOR_TYPE = {
    "photo": "openai",
    "illustration": "openai",
    "pattern": "openai",
    "og": "openai",
    "logo_concept": "openai",
}

ASPECT_TO_OPENAI_SIZE = {
    "1:1": "1024x1024",
    "16:9": "1536x1024",
    "9:16": "1024x1536",
    "4:3": "1536x1024",   # closest available
    "3:4": "1024x1536",
}


def build_style_prefix(tokens: dict[str, Any], asset_type: str) -> str:
    """
    Convert structured design tokens into a directive prompt prefix that
    image models will actually respect. This is the core value of the skill.
    """
    parts: list[str] = []

    # Lead with the visual register the model should target.
    register = {
        "photo": "Photographic image",
        "illustration": "Editorial illustration",
        "pattern": "Seamless decorative pattern",
        "og": "Social media share card composition",
        "logo_concept": "Logo concept exploration",
    }.get(asset_type, "Image")
    parts.append(register + ".")

    # Tone & industry context — these set the emotional register.
    if "tone" in tokens:
        parts.append(f"Tone: {tokens['tone']}.")
    if "industry" in tokens:
        parts.append(f"Context: {tokens['industry']}.")

    # Color directive. Name the colors with hex codes so the model can hit them.
    colors = tokens.get("colors", {})
    color_phrases = []
    for label in ("primary", "secondary", "accent", "background"):
        if label in colors and colors[label]:
            color_phrases.append(f"{label} {colors[label]}")
    if color_phrases:
        parts.append(
            "Color palette must include: " + ", ".join(color_phrases) + "."
        )
    elif "accent_palette" in colors and colors["accent_palette"]:
        parts.append(
            "Color palette: " + ", ".join(colors["accent_palette"]) + "."
        )

    # Typography hint — only useful when text appears in the asset (OG cards etc.)
    typography = tokens.get("typography", {})
    if asset_type in ("og", "logo_concept") and typography:
        if "headline" in typography:
            parts.append(f"If text appears, use a {typography['headline']}-style serif/display.")

    # Include directives — what the brand DOES use.
    include = tokens.get("style_directives", {}).get("include", [])
    if include:
        # Filter to descriptive phrases only
        meaningful = [d for d in include if len(d) > 3]
        if meaningful:
            parts.append("Visual qualities: " + ", ".join(meaningful) + ".")

    # Exclude directives — what the brand NEVER uses. Critical for avoiding
    # the generic AI look.
    exclude = tokens.get("style_directives", {}).get("exclude", [])
    if exclude:
        parts.append("AVOID: " + "; ".join(exclude) + ".")

    return " ".join(parts)


def build_full_prompt(
    user_prompt: str,
    tokens: dict[str, Any],
    asset_type: str,
    is_anchor: bool = False,
) -> str:
    """Combine the style prefix with the user's specific prompt."""
    prefix = build_style_prefix(tokens, asset_type)

    if is_anchor:
        # Anchor prompts establish the visual world, not a specific scene.
        return (
            f"{prefix} "
            f"This is a brand mood reference image establishing the visual world. "
            f"Subject: {user_prompt}. "
            f"The composition should feel like a key visual — atmospheric, "
            f"on-brand, suitable for use as a style reference for related images."
        )

    return f"{prefix} Subject: {user_prompt}."


def fingerprint(prompt: str, provider: str, size: str) -> str:
    """Deterministic hash for caching identical requests."""
    h = hashlib.sha256()
    h.update(prompt.encode("utf-8"))
    h.update(provider.encode("utf-8"))
    h.update(size.encode("utf-8"))
    return h.hexdigest()[:16]


def call_openai_image(
    prompt: str,
    size: str,
    api_key: str,
    model: str = "gpt-image-1",
) -> bytes:
    """
    Call OpenAI's image generation endpoint. Returns raw PNG bytes.

    Uses the /v1/images/generations endpoint. We hit it with stdlib
    urllib so the skill has zero install footprint beyond Python.
    """
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": 1,
    }).encode("utf-8")

    req = Request(
        "https://api.openai.com/v1/images/generations",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"OpenAI API returned {e.code}: {err_body[:500]}"
        ) from e
    except URLError as e:
        raise RuntimeError(f"Network error calling OpenAI: {e}") from e

    data = payload.get("data", [])
    if not data:
        raise RuntimeError(f"OpenAI response had no data: {payload}")

    item = data[0]
    if "b64_json" in item:
        return base64.b64decode(item["b64_json"])

    # Some models return a URL instead. Fetch it.
    if "url" in item:
        with urlopen(item["url"], timeout=60) as r:
            return r.read()

    raise RuntimeError(f"OpenAI response missing image data: {item}")


def call_gemini_image(
    prompt: str,
    api_key: str,
    model: str = "gemini-2.5-flash-image",
) -> bytes:
    """
    Call Gemini's image generation. Returns raw PNG bytes.

    Uses the REST API directly with stdlib so we don't require the
    google-genai package.
    """
    body = json.dumps({
        "contents": [{
            "parts": [{"text": prompt}],
        }],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
        },
    }).encode("utf-8")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={api_key}"
    )
    req = Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(req, timeout=180) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(
            f"Gemini API returned {e.code}: {err_body[:500]}"
        ) from e
    except URLError as e:
        raise RuntimeError(f"Network error calling Gemini: {e}") from e

    candidates = payload.get("candidates", [])
    for cand in candidates:
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and "data" in inline:
                return base64.b64decode(inline["data"])

    raise RuntimeError(f"Gemini response had no image data: {payload}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a brand-aware asset.")
    parser.add_argument("--type", choices=sorted(ASSET_TYPES), required=False,
                        help="Asset type. Required unless --anchor is set.")
    parser.add_argument("--tokens", required=True,
                        help="Path to design_tokens.json (from parse_design_system.py)")
    parser.add_argument("--prompt", required=True,
                        help="What to depict (subject of the image)")
    parser.add_argument("--output", required=True,
                        help="Output PNG path")
    parser.add_argument("--aspect", default="1:1",
                        choices=list(ASPECT_TO_OPENAI_SIZE.keys()),
                        help="Aspect ratio (default 1:1)")
    parser.add_argument("--provider", choices=("openai", "gemini", "auto"),
                        default="auto",
                        help="Which provider to use (default: auto, picks per asset type)")
    parser.add_argument("--anchor", action="store_true",
                        help="Generate as a style anchor (different prompt framing, no asset type required)")
    parser.add_argument("--no-cache", action="store_true",
                        help="Skip the fingerprint cache and force regeneration")
    parser.add_argument("--cache-dir", default=".asset-cache",
                        help="Where to keep the fingerprint cache (default: .asset-cache)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the final prompt and exit; don't call any API")
    args = parser.parse_args()

    if not args.anchor and not args.type:
        print("ERROR: --type is required unless --anchor is set", file=sys.stderr)
        return 1

    asset_type = args.type or "photo"  # anchor defaults to photo register

    tokens_path = Path(args.tokens)
    if not tokens_path.exists():
        print(f"ERROR: tokens file not found: {tokens_path}", file=sys.stderr)
        return 1

    tokens = json.loads(tokens_path.read_text())
    full_prompt = build_full_prompt(args.prompt, tokens, asset_type, is_anchor=args.anchor)

    # Pick provider
    provider = args.provider
    if provider == "auto":
        provider = DEFAULT_PROVIDER_FOR_TYPE.get(asset_type, "openai")

    size = ASPECT_TO_OPENAI_SIZE.get(args.aspect, "1024x1024")

    if args.dry_run:
        print(f"Provider: {provider}")
        print(f"Size: {size}")
        print(f"Final prompt:\n{full_prompt}")
        return 0

    # Fingerprint cache check
    fp = fingerprint(full_prompt, provider, size)
    cache_dir = Path(args.cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    cached = cache_dir / f"{fp}.png"

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if not args.no_cache and cached.exists():
        output_path.write_bytes(cached.read_bytes())
        sidecar = output_path.with_suffix(output_path.suffix + ".meta.json")
        sidecar.write_text(json.dumps({
            "provider": provider,
            "size": size,
            "prompt": full_prompt,
            "fingerprint": fp,
            "cached": True,
            "generated_at": int(time.time()),
        }, indent=2))
        print(f"[cache hit] {output_path} (fingerprint {fp})")
        return 0

    # Provider call
    if provider == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print(
                "ERROR: OPENAI_API_KEY not set.\n"
                "Run: export OPENAI_API_KEY=sk-...\n"
                "Or use --provider gemini if you have a Gemini key.",
                file=sys.stderr,
            )
            return 3
        print(f"Calling OpenAI ({size})...")
        image_bytes = call_openai_image(full_prompt, size, api_key)

    elif provider == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print(
                "ERROR: GEMINI_API_KEY not set.\n"
                "Run: export GEMINI_API_KEY=...",
                file=sys.stderr,
            )
            return 3
        print(f"Calling Gemini...")
        image_bytes = call_gemini_image(full_prompt, api_key)

    else:
        print(f"ERROR: unknown provider {provider}", file=sys.stderr)
        return 1

    # Save image + cache + sidecar
    output_path.write_bytes(image_bytes)
    cached.write_bytes(image_bytes)

    sidecar = output_path.with_suffix(output_path.suffix + ".meta.json")
    sidecar.write_text(json.dumps({
        "provider": provider,
        "size": size,
        "prompt": full_prompt,
        "fingerprint": fp,
        "cached": False,
        "generated_at": int(time.time()),
        "asset_type": "anchor" if args.anchor else asset_type,
    }, indent=2))

    print(f"Wrote {output_path} ({len(image_bytes)} bytes, fingerprint {fp})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
