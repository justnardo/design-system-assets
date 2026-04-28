#!/usr/bin/env python3
"""
parse_design_system.py — Extract brand tokens from a project.

Reads (in order of preference):
  1. DESIGN.md / design.md at project root
  2. tailwind.config.{js,ts,cjs,mjs}
  3. CSS custom properties in *.css files (looking for :root, .theme, etc.)
  4. tokens.json / figma-tokens.json
  5. package.json (theme dependency hints)

Outputs design_tokens.json to the working directory, structured for
downstream consumption by generate_asset.py.

If parsing finds no usable design system, exits with code 2 and a clear
message — the calling skill should ask the user for tokens rather than
inventing them.

Usage:
    python parse_design_system.py <project_root>
    python parse_design_system.py <project_root> --output custom_path.json
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


HEX_PATTERN = re.compile(r"#(?:[0-9a-fA-F]{3}){1,2}\b")
TAILWIND_COLOR_BLOCK = re.compile(
    r"colors\s*:\s*\{(.*?)\n\s*\}", re.DOTALL
)
CSS_VAR_PATTERN = re.compile(r"--([a-zA-Z0-9-_]+)\s*:\s*([^;]+);")
FONT_FAMILY_PATTERN = re.compile(
    r"font-family\s*:\s*['\"]?([^,;'\"]+)", re.IGNORECASE
)


def find_design_md(root: Path) -> Path | None:
    for name in ("DESIGN.md", "design.md", "Design.md", "BRAND.md", "brand.md"):
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def find_tailwind_config(root: Path) -> Path | None:
    for ext in ("js", "ts", "cjs", "mjs"):
        candidate = root / f"tailwind.config.{ext}"
        if candidate.exists():
            return candidate
    return None


def find_tokens_json(root: Path) -> Path | None:
    for name in ("tokens.json", "figma-tokens.json", "design-tokens.json"):
        candidate = root / name
        if candidate.exists():
            return candidate
    return None


def find_css_files(root: Path, limit: int = 10) -> list[Path]:
    """Find CSS files most likely to contain theme variables."""
    candidates: list[Path] = []
    skip_dirs = {"node_modules", ".next", "dist", "build", ".git", "vendor"}

    for css in root.rglob("*.css"):
        if any(part in skip_dirs for part in css.parts):
            continue
        candidates.append(css)
        if len(candidates) >= limit:
            break

    # Prioritize files with theme-y names
    def priority(p: Path) -> int:
        name = p.name.lower()
        if any(kw in name for kw in ("theme", "tokens", "variables", "global", "root")):
            return 0
        return 1

    candidates.sort(key=priority)
    return candidates


def parse_design_md(path: Path) -> dict[str, Any]:
    """
    Parse a DESIGN.md file. Look for:
      - Hex colors (with surrounding context to label them)
      - Font names
      - Style directives (include / exclude / avoid / never)
      - Industry / tone hints from prose

    This is intentionally tolerant — DESIGN.md files vary widely.
    """
    text = path.read_text(encoding="utf-8")
    tokens: dict[str, Any] = {
        "source": "DESIGN.md",
        "colors": {},
        "typography": {},
        "style_directives": {"include": [], "exclude": []},
    }

    # Hex colors with context. Look for color name patterns near hex codes.
    color_lines = []
    for line in text.splitlines():
        if HEX_PATTERN.search(line):
            color_lines.append(line.strip())

    palette: list[str] = []
    for line in color_lines:
        for match in HEX_PATTERN.finditer(line):
            hex_code = match.group(0).lower()
            if hex_code not in palette:
                palette.append(hex_code)

            # Try to label the color from context
            context = line.lower()
            label = None
            for keyword in (
                "primary", "secondary", "accent", "background", "bg",
                "text", "foreground", "fg", "muted", "border", "surface",
                "neutral", "success", "danger", "warning",
            ):
                if keyword in context:
                    label = keyword if keyword not in ("bg", "fg") else (
                        "background" if keyword == "bg" else "text"
                    )
                    break
            if label and label not in tokens["colors"]:
                tokens["colors"][label] = hex_code

    if palette:
        tokens["colors"]["accent_palette"] = palette

    # Fonts. Look for "<label>: <font name>" patterns where label is one of
    # our known typography roles. Extract the value AFTER the colon, not the label.
    typography_label_map = {
        "headline": ["headline", "heading", "display", "h1", "title"],
        "body": ["body", "paragraph", "base", "text"],
        "mono": ["mono", "code"],
    }
    noise_words = {
        "typography", "fonts", "design", "system", "style", "brand",
        "headline", "heading", "display", "body", "paragraph", "base",
        "text", "mono", "code", "title",
    }

    for line in text.splitlines():
        # Match patterns like "- Headline: Noto Serif" or "Body: Manrope"
        m = re.match(
            r'^\s*[-*•]?\s*([A-Za-z][A-Za-z\s]+?)\s*[:\-]\s*(.+)$',
            line,
        )
        if not m:
            continue
        label_text = m.group(1).strip().lower()
        value_text = m.group(2).strip().strip('"\'').strip("`")
        # Strip parenthetical or trailing comments
        value_text = re.sub(r'\s*[\(\[].*?[\)\]]\s*', '', value_text).strip()
        # Strip trailing commas/semicolons
        value_text = value_text.rstrip(",;.")

        if not value_text or value_text.lower() in noise_words:
            continue

        for our_label, keywords in typography_label_map.items():
            if any(k == label_text or label_text.startswith(k + " ") or label_text.endswith(" " + k) for k in keywords):
                if our_label not in tokens["typography"]:
                    tokens["typography"][our_label] = value_text
                break

    # Style directives — look for explicit no/never/avoid/include sections
    text_lower = text.lower()
    for keyword in ("no glassmorphism", "no gradient", "no parallax",
                     "avoid glassmorphism", "never use", "do not use"):
        if keyword in text_lower:
            # Pull the line for context
            for line in text.splitlines():
                if keyword in line.lower():
                    cleaned = line.strip().lstrip("-*•# ").strip()
                    # Skip section headers (lines ending in colon, or generic phrases)
                    if cleaned.endswith(":"):
                        continue
                    if len(cleaned) < 5:
                        continue
                    if cleaned.lower() in ("what we never use", "never use", "do not use"):
                        continue
                    if cleaned and cleaned not in tokens["style_directives"]["exclude"]:
                        tokens["style_directives"]["exclude"].append(cleaned)

    for keyword in ("editorial", "minimal", "warm", "playful", "professional",
                     "clean grid", "soft shadow", "natural light"):
        if keyword in text_lower:
            if keyword not in tokens["style_directives"]["include"]:
                tokens["style_directives"]["include"].append(keyword)

    # Industry / tone — look for explicit "Industry:" or "Tone:" lines
    industry_match = re.search(r"industry\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if industry_match:
        tokens["industry"] = industry_match.group(1).strip().split("\n")[0]

    tone_match = re.search(r"tone\s*[:\-]\s*(.+)", text, re.IGNORECASE)
    if tone_match:
        tokens["tone"] = tone_match.group(1).strip().split("\n")[0]

    return tokens


def parse_tailwind_config(path: Path) -> dict[str, Any]:
    """
    Best-effort parse of tailwind.config.{js,ts}. We're not running JS — just
    regex-extracting the colors block and fontFamily block. Good enough for
    most project configs; complex setups should rely on DESIGN.md instead.
    """
    text = path.read_text(encoding="utf-8")
    tokens: dict[str, Any] = {
        "source": "tailwind.config",
        "colors": {},
        "typography": {},
        "style_directives": {"include": [], "exclude": []},
    }

    # Find the colors object
    colors_match = TAILWIND_COLOR_BLOCK.search(text)
    if colors_match:
        block = colors_match.group(1)
        # Extract key: '#hex' pairs
        for m in re.finditer(
            r'["\']?([a-zA-Z0-9-_]+)["\']?\s*:\s*["\']?(#[0-9a-fA-F]{3,8})["\']?',
            block,
        ):
            name, hex_code = m.group(1), m.group(2).lower()
            tokens["colors"][name] = hex_code

        if tokens["colors"]:
            tokens["colors"]["accent_palette"] = list(
                {v for v in tokens["colors"].values() if isinstance(v, str)}
            )

    # Font families
    for m in re.finditer(
        r'(sans|serif|mono|display|heading|body)\s*:\s*\[\s*["\']([^"\']+)["\']',
        text,
    ):
        family_type, family_name = m.group(1), m.group(2)
        label = {
            "serif": "headline",
            "display": "headline",
            "heading": "headline",
            "sans": "body",
            "body": "body",
            "mono": "mono",
        }.get(family_type, family_type)
        if label not in tokens["typography"]:
            tokens["typography"][label] = family_name

    return tokens


def parse_css_variables(paths: list[Path]) -> dict[str, Any]:
    """
    Extract CSS custom properties that look like brand tokens.
    """
    tokens: dict[str, Any] = {
        "source": "css_variables",
        "colors": {},
        "typography": {},
        "style_directives": {"include": [], "exclude": []},
    }
    palette: list[str] = []

    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for m in CSS_VAR_PATTERN.finditer(text):
            var_name, var_value = m.group(1), m.group(2).strip()
            lower_name = var_name.lower()

            # Color variables
            if HEX_PATTERN.search(var_value):
                hex_code = HEX_PATTERN.search(var_value).group(0).lower()
                if hex_code not in palette:
                    palette.append(hex_code)

                for label_key in ("primary", "secondary", "accent",
                                    "background", "text", "muted", "border"):
                    if label_key in lower_name:
                        if label_key not in tokens["colors"]:
                            tokens["colors"][label_key] = hex_code
                        break

            # Font variables
            if "font" in lower_name and ("family" in lower_name or "-" in var_name):
                font_match = re.search(r'["\']?([A-Z][\w\s]+)', var_value)
                if font_match:
                    family = font_match.group(1).split(",")[0].strip().strip('"\'')
                    if "head" in lower_name or "display" in lower_name:
                        tokens["typography"]["headline"] = family
                    elif "body" in lower_name or "base" in lower_name:
                        tokens["typography"]["body"] = family

    if palette:
        tokens["colors"]["accent_palette"] = palette

    return tokens


def merge_tokens(*token_sets: dict[str, Any]) -> dict[str, Any]:
    """Merge token sets; earlier sources take priority over later ones."""
    merged: dict[str, Any] = {
        "colors": {},
        "typography": {},
        "style_directives": {"include": [], "exclude": []},
        "sources": [],
    }

    for tokens in token_sets:
        if not tokens:
            continue
        if "source" in tokens:
            merged["sources"].append(tokens["source"])

        for k, v in tokens.get("colors", {}).items():
            if k not in merged["colors"]:
                merged["colors"][k] = v

        for k, v in tokens.get("typography", {}).items():
            if k not in merged["typography"]:
                merged["typography"][k] = v

        for item in tokens.get("style_directives", {}).get("include", []):
            if item not in merged["style_directives"]["include"]:
                merged["style_directives"]["include"].append(item)

        for item in tokens.get("style_directives", {}).get("exclude", []):
            if item not in merged["style_directives"]["exclude"]:
                merged["style_directives"]["exclude"].append(item)

        for key in ("industry", "tone"):
            if key in tokens and key not in merged:
                merged[key] = tokens[key]

    return merged


def has_usable_tokens(tokens: dict[str, Any]) -> bool:
    """A token set is usable if it has at least 2 colors OR 1 color + 1 font."""
    color_count = sum(
        1 for k in tokens.get("colors", {})
        if k != "accent_palette" and tokens["colors"][k]
    )
    font_count = len(tokens.get("typography", {}))

    if color_count >= 2:
        return True
    if color_count >= 1 and font_count >= 1:
        return True
    if "accent_palette" in tokens.get("colors", {}) and len(tokens["colors"]["accent_palette"]) >= 3:
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse a project's design system.")
    parser.add_argument("project_root", help="Path to the project root")
    parser.add_argument(
        "--output", default="design_tokens.json",
        help="Where to write the parsed tokens (default: design_tokens.json)",
    )
    parser.add_argument(
        "--quiet", action="store_true",
        help="Suppress progress output",
    )
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    if not root.exists():
        print(f"ERROR: project root does not exist: {root}", file=sys.stderr)
        return 1

    if not args.quiet:
        print(f"Scanning {root}...")

    sources: list[dict[str, Any]] = []

    design_md = find_design_md(root)
    if design_md:
        if not args.quiet:
            print(f"  Found {design_md.relative_to(root)}")
        sources.append(parse_design_md(design_md))

    tailwind = find_tailwind_config(root)
    if tailwind:
        if not args.quiet:
            print(f"  Found {tailwind.relative_to(root)}")
        sources.append(parse_tailwind_config(tailwind))

    css_files = find_css_files(root)
    if css_files:
        if not args.quiet:
            print(f"  Scanning {len(css_files)} CSS file(s) for variables")
        sources.append(parse_css_variables(css_files))

    tokens_file = find_tokens_json(root)
    if tokens_file:
        if not args.quiet:
            print(f"  Found {tokens_file.relative_to(root)}")
        try:
            raw = json.loads(tokens_file.read_text())
            sources.append({
                "source": tokens_file.name,
                "colors": raw.get("colors", {}),
                "typography": raw.get("typography", {}),
                "style_directives": raw.get("style_directives", {"include": [], "exclude": []}),
            })
        except (json.JSONDecodeError, OSError) as e:
            if not args.quiet:
                print(f"  Could not parse {tokens_file.name}: {e}")

    merged = merge_tokens(*sources)

    if not has_usable_tokens(merged):
        print(
            "ERROR: No usable design system found.\n"
            "Tried: DESIGN.md, tailwind.config, CSS variables, tokens.json.\n"
            "Add a DESIGN.md file (see templates/DESIGN_md_template.md) "
            "or provide brand tokens manually before generating assets.",
            file=sys.stderr,
        )
        return 2

    output_path = Path(args.output)
    output_path.write_text(json.dumps(merged, indent=2))

    if not args.quiet:
        print(f"\nWrote {output_path}")
        print(f"  Sources: {', '.join(merged['sources'])}")
        print(f"  Colors: {len([k for k in merged['colors'] if k != 'accent_palette'])} labeled, "
              f"{len(merged['colors'].get('accent_palette', []))} in palette")
        print(f"  Typography: {list(merged['typography'].keys())}")
        if merged["style_directives"]["exclude"]:
            print(f"  Exclude rules: {len(merged['style_directives']['exclude'])}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
