"""
Unit tests for estimate_cost: pricing math and per-type cost rules.
"""

import pytest

from estimate_cost import DEFAULT_PRICES, estimate_for_request, estimate_total


def test_icon_request_is_free():
    item = estimate_for_request("menu icon", DEFAULT_PRICES)
    assert item["asset_type"] == "icon"
    assert item["cost_low"] == 0.0
    assert item["cost_high"] == 0.0
    assert item["skip_review"] is True


def test_decorative_svg_is_free():
    item = estimate_for_request("decorative wave divider", DEFAULT_PRICES)
    assert item["asset_type"] == "decorative_svg"
    assert item["cost_low"] == 0.0


def test_chart_is_free():
    item = estimate_for_request("bar chart of revenue", DEFAULT_PRICES)
    assert item["asset_type"] == "chart"
    assert item["cost_low"] == 0.0


def test_refused_request_is_free_and_marked():
    item = estimate_for_request("photo of Mr. Johnson, our CEO", DEFAULT_PRICES)
    assert item["asset_type"].startswith("refuse_")
    assert item["cost_low"] == 0.0
    assert "REFUSED" in item["note"]


def test_hero_photo_uses_large_price():
    item = estimate_for_request("hero photo for about page", DEFAULT_PRICES)
    assert item["asset_type"] == "photo"
    # Hero defaults to 16:9 → openai_large
    assert item["cost_low"] == DEFAULT_PRICES["openai_large"]


def test_logo_uses_standard_price():
    item = estimate_for_request("brand logo concept", DEFAULT_PRICES)
    assert item["asset_type"] == "logo_concept"
    # Logo defaults to 1:1 → openai_standard
    assert item["cost_low"] == DEFAULT_PRICES["openai_standard"]


def test_total_includes_regen_buffer():
    requests = ["hero photo for about page"]  # 1 large raster → $0.08
    estimate = estimate_total(
        requests, DEFAULT_PRICES, regen_assumption=2.0, include_review=False,
    )
    # Base = 0.08, with 2x regen = 0.16. High also gets +25% variance ceiling.
    assert estimate["cost_estimate_usd"]["base_generation"] == 0.08
    assert estimate["cost_estimate_usd"]["regen_buffer"] == pytest.approx(0.08, abs=0.001)
    assert estimate["cost_estimate_usd"]["low"] == pytest.approx(0.08, abs=0.001)
    assert estimate["cost_estimate_usd"]["high"] == pytest.approx(0.16 * 1.25, abs=0.001)


def test_total_includes_review_when_requested():
    requests = ["hero photo for about page"]
    no_review = estimate_total(requests, DEFAULT_PRICES, include_review=False)
    with_review = estimate_total(requests, DEFAULT_PRICES, include_review=True)
    assert with_review["cost_estimate_usd"]["review"] > 0
    assert no_review["cost_estimate_usd"]["review"] == 0


def test_summary_counts_match_items():
    requests = [
        "hero photo for about page",      # raster
        "menu icon",                       # icon
        "decorative wave divider",         # svg
        "bar chart of monthly revenue",    # chart
        "photo of Mr. Johnson, our CEO",   # refused
    ]
    estimate = estimate_total(requests, DEFAULT_PRICES, include_review=False)
    s = estimate["summary"]
    assert s["total_assets"] == 5
    assert s["raster_assets"] == 1
    assert s["icons"] == 1
    assert s["decorative_svg"] == 1
    assert s["charts"] == 1
    assert s["refused"] == 1
