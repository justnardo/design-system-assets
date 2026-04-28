#!/usr/bin/env python3
"""
fetch_icon.py — Pull SVG icons from Lucide and theme them to the project.

Why this exists: bitmap image AI is genuinely bad at icons. Pixel artifacts,
inconsistent stroke widths, no SVG path data, can't be themed via CSS. So
icon requests should NEVER go through the image generator — they go here.

Lucide is the default source because it's CDN-served, MIT licensed, and the
most-used icon library on the web. We could add Heroicons or Tabler later as
fallbacks, but Lucide covers ~1,500 icons which handles the vast majority of
real product needs.

Usage:
    # Fetch and save with default styling (currentColor)
    python fetch_icon.py menu --output public/icons/menu.svg

    # Theme to a specific brand color
    python fetch_icon.py heart \\
        --tokens design_tokens.json \\
        --color primary \\
        --output public/icons/heart.svg

    # Search for icons matching a need (helpful when you don't know the name)
    python fetch_icon.py --search "user profile"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen, Request


LUCIDE_SOURCES = [
    "https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/{name}.svg",
    "https://unpkg.com/lucide-static@latest/icons/{name}.svg",
]
# Curated synonyms for common product needs that don't map 1:1 to icon names.
# Helps when callers say "menu" but the icon is actually called "menu" or
# "hamburger" or whatever — keeps lookup forgiving.
ICON_SYNONYMS = {
    "hamburger": "menu",
    "burger": "menu",
    "close": "x",
    "dismiss": "x",
    "delete": "trash-2",
    "remove": "x",
    "edit": "pencil",
    "save": "save",
    "search": "search",
    "find": "search",
    "user": "user",
    "profile": "user",
    "account": "user-circle-2",
    "cart": "shopping-cart",
    "basket": "shopping-cart",
    "bag": "shopping-bag",
    "settings": "settings",
    "preferences": "settings",
    "config": "settings-2",
    "back": "arrow-left",
    "next": "arrow-right",
    "expand": "chevron-down",
    "collapse": "chevron-up",
    "calendar": "calendar",
    "schedule": "calendar",
    "date": "calendar",
    "phone": "phone",
    "call": "phone",
    "email": "mail",
    "message": "message-square",
    "chat": "message-circle",
    "notification": "bell",
    "alert": "bell",
    "warning": "alert-triangle",
    "error": "alert-circle",
    "info": "info",
    "help": "circle-help",
    "question": "circle-help",
    "favorite": "heart",
    "like": "heart",
    "star": "star",
    "rating": "star",
    "share": "share-2",
    "download": "download",
    "upload": "upload",
    "home": "house",
    "house": "house",
    "menu": "menu",
    "more": "more-horizontal",
    "kebab": "more-vertical",
}


def resolve_icon_name(query: str) -> str:
    """Resolve a query to a likely Lucide icon name."""
    q = query.strip().lower().replace("_", "-").replace(" ", "-")
    # Direct synonym hit
    if q in ICON_SYNONYMS:
        return ICON_SYNONYMS[q]
    return q


def fetch_lucide(name: str) -> str:
    """Fetch the raw SVG for a Lucide icon name. Tries GitHub raw first
    (most reliable), falls back to unpkg CDN."""
    last_error: Exception | None = None
    for url_template in LUCIDE_SOURCES:
        url = url_template.format(name=name)
        try:
            with urlopen(url, timeout=15) as resp:
                return resp.read().decode("utf-8")
        except HTTPError as e:
            if e.code == 404:
                # Genuine "icon doesn't exist" — don't try other sources.
                raise ValueError(
                    f"Lucide has no icon called '{name}'. "
                    f"Try `--search '<keyword>'` to find similar icons."
                ) from e
            last_error = e
            continue
        except URLError as e:
            last_error = e
            continue
    raise RuntimeError(
        f"Could not fetch Lucide icon '{name}' from any source. "
        f"Last error: {last_error}"
    )


def theme_svg(
    svg: str,
    color: str | None,
    stroke_width: float | None,
) -> str:
    """
    Apply theme overrides to a Lucide SVG. Lucide SVGs use stroke="currentColor"
    by default, which is the right thing for most uses (color inherits from CSS).
    Only override if the caller asked for a specific color.
    """
    out = svg

    if color and color != "currentColor":
        out = re.sub(
            r'stroke="[^"]*"',
            f'stroke="{color}"',
            out,
            count=1,  # only the outer attribute
        )
        # Also update fill if it's currentColor (rare in Lucide but possible)
        out = re.sub(
            r'fill="currentColor"',
            f'fill="{color}"',
            out,
        )

    if stroke_width is not None:
        out = re.sub(
            r'stroke-width="[^"]*"',
            f'stroke-width="{stroke_width}"',
            out,
            count=1,
        )

    return out


def resolve_color_from_tokens(
    tokens: dict, label: str
) -> str | None:
    """Look up a color token by label (e.g., 'primary' -> '#805158')."""
    colors = tokens.get("colors", {})
    if label in colors and isinstance(colors[label], str) and colors[label].startswith("#"):
        return colors[label]
    return None


def search_icons(query: str) -> list[str]:
    """
    Naive search using the synonym map. For exhaustive search you'd hit
    Lucide's search endpoint, but the synonym map covers the common cases
    without an extra network call.
    """
    q = query.lower()
    matches = []
    for synonym, icon in ICON_SYNONYMS.items():
        if q in synonym or synonym in q or q in icon:
            if icon not in matches:
                matches.append(icon)
    return matches


def llm_assisted_icon_search(query: str, api_key: str) -> str | None:
    """Use Claude to map an ambiguous query to a standard Lucide icon name."""
    system_prompt = (
        "You are an expert at mapping user requests to Lucide icon names. "
        "Lucide icons use lowercase, kebab-case names like 'shopping-cart', 'arrow-right', 'user'. "
        "Return ONLY the exact icon name, nothing else. No quotes, no markdown, no explanation. "
        "If you cannot determine a good match, return 'none'."
    )
    user_prompt = f"What is the best Lucide icon name for this request: '{query}'?"
    
    model = os.environ.get("ANTHROPIC_MODEL", "claude-3-5-haiku-latest")
    body = json.dumps({
        "model": model,
        "max_tokens": 50,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}],
    }).encode("utf-8")

    req = Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except Exception:
        return None  # Fail gracefully if API is down or key is bad

    content = payload.get("content", [])
    for block in content:
        if block.get("type") == "text":
            name = block.get("text", "").strip().lower()
            if name and name != "none":
                return name
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch a themed SVG icon from Lucide.")
    parser.add_argument("name", nargs="?", help="Icon name or keyword (e.g., 'menu', 'cart')")
    parser.add_argument("--output", help="Output path for the SVG file")
    parser.add_argument("--tokens", help="Path to design_tokens.json (for --color resolution)")
    parser.add_argument(
        "--color",
        help="Color override. Either a hex value (#805158), a token label "
             "(primary, secondary, accent, text), or 'currentColor' (default).",
    )
    parser.add_argument(
        "--stroke-width", type=float,
        help="Override stroke width (default Lucide is 2)",
    )
    parser.add_argument(
        "--search", help="Search for icons matching a keyword instead of fetching",
    )
    parser.add_argument(
        "--inline", action="store_true",
        help="Print SVG to stdout instead of writing a file",
    )
    args = parser.parse_args()

    if args.search:
        results = search_icons(args.search)
        if results:
            print("Likely matches:")
            for r in results:
                print(f"  {r}")
        else:
            print(f"No synonym matches for '{args.search}'.")
            print("Try browsing https://lucide.dev/icons for the full set.")
        return 0

    if not args.name:
        print("ERROR: icon name required (or use --search)", file=sys.stderr)
        return 1

    icon_name = resolve_icon_name(args.name)

    try:
        svg = fetch_lucide(icon_name)
    except ValueError as e:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            print(f"Icon '{icon_name}' not found. Asking Claude for a suggestion...", file=sys.stderr)
            suggested = llm_assisted_icon_search(args.name, api_key)
            if suggested and suggested != icon_name:
                print(f"Claude suggested: '{suggested}'. Trying that...", file=sys.stderr)
                try:
                    svg = fetch_lucide(suggested)
                    icon_name = suggested
                except ValueError:
                    print(f"ERROR: Suggestion '{suggested}' also not found.", file=sys.stderr)
                    suggestions = search_icons(args.name)
                    if suggestions:
                        print(f"Did you mean: {', '.join(suggestions[:5])}?", file=sys.stderr)
                    return 1
            else:
                print(f"ERROR: {e}", file=sys.stderr)
                suggestions = search_icons(args.name)
                if suggestions:
                    print(f"Did you mean: {', '.join(suggestions[:5])}?", file=sys.stderr)
                return 1
        else:
            print(f"ERROR: {e}", file=sys.stderr)
            suggestions = search_icons(args.name)
            if suggestions:
                print(f"Did you mean: {', '.join(suggestions[:5])}?", file=sys.stderr)
            return 1

    # Resolve color
    color: str | None = None
    if args.color:
        if args.color.startswith("#"):
            color = args.color
        elif args.color == "currentColor":
            color = None
        elif args.tokens:
            tokens = json.loads(Path(args.tokens).read_text())
            resolved = resolve_color_from_tokens(tokens, args.color)
            if resolved:
                color = resolved
            else:
                print(
                    f"WARNING: token '{args.color}' not found, using currentColor",
                    file=sys.stderr,
                )
        else:
            print(
                f"WARNING: '{args.color}' is not a hex color and no --tokens "
                f"provided, using currentColor",
                file=sys.stderr,
            )

    themed = theme_svg(svg, color, args.stroke_width)

    if args.inline:
        print(themed)
    elif args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(themed)
        print(f"Wrote {out} (icon: {icon_name})")
    else:
        print("ERROR: pass --output <path> or --inline", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
