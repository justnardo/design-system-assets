"""
Unit tests for route_asset.classify(). Mirrors the cases in test_router.sh
so that a bad routing change fails CI before anyone notices in production.
"""

import pytest

from route_asset import classify, is_hard_refuse


# (request, expected_asset_type, expected_route)
ROUTING_CASES = [
    # Photos / hero
    ("hero photo for about page", "photo", "generate_asset.py"),
    ("hero photo for home page", "photo", "generate_asset.py"),

    # OG / social cards
    ("Open Graph share card for pricing", "og", "generate_asset.py"),
    ("Twitter card for feature launch", "og", "generate_asset.py"),

    # Illustrations / patterns / decorative
    ("spot illustration for empty state", "illustration", "generate_asset.py"),
    ("decorative wave divider", "decorative_svg", "HAND_WRITE_SVG"),
    ("seamless texture pattern", "pattern", "generate_asset.py"),

    # Logos
    ("brand logo concept", "logo_concept", "generate_asset.py"),
    ("favicon", "logo_concept", "generate_asset.py"),

    # Icons (explicit + standalone keywords)
    ("menu icon", "icon", "fetch_icon.py"),
    ("menu", "icon", "fetch_icon.py"),
    ("hamburger", "icon", "fetch_icon.py"),
    ("user profile icon", "icon", "fetch_icon.py"),
    ("heart icon", "icon", "fetch_icon.py"),
    ("calendar", "icon", "fetch_icon.py"),

    # Charts (must come BEFORE 'photo' if they ever conflict)
    ("bar chart of monthly revenue", "chart", "USE_CHARTING_LIBRARY"),
    ("pie chart of user engagement", "chart", "USE_CHARTING_LIBRARY"),
    ("data viz for the dashboard", "chart", "USE_CHARTING_LIBRARY"),

    # Refuse categories
    ("photo of Mr. Johnson, our CEO", "refuse_real_person", "DO_NOT_GENERATE"),
    ("real product photo for our sauce bottle", "refuse_real_product", "DO_NOT_GENERATE"),

    # Unclassifiable
    ("something for the page", "unknown", "ESCALATE"),
]


@pytest.mark.parametrize("request_text,expected_type,expected_route", ROUTING_CASES)
def test_classify(request_text, expected_type, expected_route):
    route = classify(request_text)
    assert route.asset_type == expected_type, (
        f"asset_type mismatch for {request_text!r}: "
        f"got {route.asset_type}, expected {expected_type}"
    )
    assert route.route == expected_route, (
        f"route mismatch for {request_text!r}: "
        f"got {route.route}, expected {expected_route}"
    )


def test_classify_empty_request():
    """Empty input must refuse, not match a stray rule."""
    route = classify("")
    assert route.asset_type == "unknown"
    assert route.refuse is True


def test_classify_whitespace_only():
    route = classify("   \n  ")
    assert route.asset_type == "unknown"
    assert route.refuse is True


def test_og_beats_chart_keyword():
    """'Open Graph' contains 'graph' but must route to og, not chart."""
    route = classify("Open Graph image for blog post")
    assert route.asset_type == "og"


def test_is_hard_refuse():
    assert is_hard_refuse("refuse_real_person", "DO_NOT_GENERATE") is True
    assert is_hard_refuse("chart", "USE_CHARTING_LIBRARY") is True
    assert is_hard_refuse("photo", "generate_asset.py") is False
    # Unknown route is not a hard refuse — it's an escalate (rc=1).
    assert is_hard_refuse("unknown", "ESCALATE") is False


def test_refuse_flag_consistent_with_helper():
    """The dataclass refuse flag must match is_hard_refuse for hard cases."""
    for request_text, _, _ in ROUTING_CASES:
        route = classify(request_text)
        if is_hard_refuse(route.asset_type, route.route):
            assert route.refuse is True
