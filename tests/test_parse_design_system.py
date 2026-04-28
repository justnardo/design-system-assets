"""
Unit tests for parse_design_system parsing helpers.

These cover the regex-based extractors that have historically been the most
fragile part of the pipeline (Tailwind config and CSS variables).
"""

from textwrap import dedent

from parse_design_system import (
    has_usable_tokens,
    merge_tokens,
    parse_css_variables,
    parse_tailwind_config,
)


def write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(dedent(content), encoding="utf-8")
    return p


class TestParseTailwindConfig:
    def test_extracts_named_colors(self, tmp_path):
        path = write(tmp_path, "tailwind.config.js", """
            module.exports = {
              theme: {
                extend: {
                  colors: {
                    primary: '#805158',
                    secondary: '#1A1A1A',
                    accent: "#F4E1D2"
                  },
                },
              },
            }
        """)
        tokens = parse_tailwind_config(path)
        assert tokens["colors"]["primary"] == "#805158"
        assert tokens["colors"]["secondary"] == "#1a1a1a"
        assert tokens["colors"]["accent"] == "#f4e1d2"
        assert "accent_palette" in tokens["colors"]

    def test_extracts_font_families(self, tmp_path):
        path = write(tmp_path, "tailwind.config.js", """
            module.exports = {
              theme: {
                fontFamily: {
                  sans: ['Manrope', 'system-ui'],
                  serif: ['Noto Serif', 'serif'],
                  mono: ['JetBrains Mono', 'monospace'],
                },
              },
            }
        """)
        tokens = parse_tailwind_config(path)
        assert tokens["typography"]["body"] == "Manrope"
        assert tokens["typography"]["headline"] == "Noto Serif"
        assert tokens["typography"]["mono"] == "JetBrains Mono"

    def test_handles_empty_config(self, tmp_path):
        path = write(tmp_path, "tailwind.config.js", "module.exports = {};")
        tokens = parse_tailwind_config(path)
        assert tokens["colors"] == {}
        assert tokens["typography"] == {}


class TestParseCssVariables:
    def test_extracts_labeled_colors(self, tmp_path):
        path = write(tmp_path, "theme.css", """
            :root {
              --color-primary: #805158;
              --color-secondary: #1a1a1a;
              --color-background: #fafafa;
              --color-text: #222222;
            }
        """)
        tokens = parse_css_variables([path])
        assert tokens["colors"]["primary"] == "#805158"
        assert tokens["colors"]["background"] == "#fafafa"
        assert tokens["colors"]["text"] == "#222222"

    def test_builds_palette_from_all_hex(self, tmp_path):
        path = write(tmp_path, "vars.css", """
            :root {
              --primary: #805158;
              --extra: #abcdef;
            }
        """)
        tokens = parse_css_variables([path])
        palette = tokens["colors"]["accent_palette"]
        assert "#805158" in palette
        assert "#abcdef" in palette

    def test_extracts_font_family_variable(self, tmp_path):
        path = write(tmp_path, "fonts.css", """
            :root {
              --font-headline: "Noto Serif", serif;
              --font-body: "Manrope", sans-serif;
            }
        """)
        tokens = parse_css_variables([path])
        assert tokens["typography"].get("headline") == "Noto Serif"
        assert tokens["typography"].get("body") == "Manrope"

    def test_skips_unreadable_files(self, tmp_path):
        good = write(tmp_path, "good.css", ":root { --primary: #aabbcc; }")
        # Pass a non-existent path alongside; should not crash.
        bogus = tmp_path / "missing.css"
        tokens = parse_css_variables([bogus, good])
        assert tokens["colors"].get("primary") == "#aabbcc"


class TestMergeAndUsable:
    def test_merge_first_source_wins_per_key(self):
        a = {"colors": {"primary": "#111111"}, "typography": {}, "style_directives": {"include": [], "exclude": []}}
        b = {"colors": {"primary": "#222222", "accent": "#333333"}, "typography": {}, "style_directives": {"include": [], "exclude": []}}
        merged = merge_tokens(a, b)
        assert merged["colors"]["primary"] == "#111111"  # a wins
        assert merged["colors"]["accent"] == "#333333"   # filled from b

    def test_merge_dedupes_directives(self):
        a = {"colors": {}, "typography": {}, "style_directives": {"include": ["editorial"], "exclude": []}}
        b = {"colors": {}, "typography": {}, "style_directives": {"include": ["editorial", "minimal"], "exclude": []}}
        merged = merge_tokens(a, b)
        assert merged["style_directives"]["include"] == ["editorial", "minimal"]

    def test_usable_requires_two_colors_or_color_plus_font(self):
        assert has_usable_tokens({"colors": {"primary": "#000", "accent": "#fff"}, "typography": {}}) is True
        assert has_usable_tokens({"colors": {"primary": "#000"}, "typography": {"body": "Manrope"}}) is True
        assert has_usable_tokens({"colors": {"primary": "#000"}, "typography": {}}) is False

    def test_usable_accepts_palette_with_three_colors(self):
        tokens = {
            "colors": {"accent_palette": ["#111", "#222", "#333"]},
            "typography": {},
        }
        assert has_usable_tokens(tokens) is True
