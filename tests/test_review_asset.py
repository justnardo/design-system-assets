"""
Unit tests for review_asset.compute_verdict() and extract_scores().

These cover the verdict thresholds (strict/balanced/fast), the regen-floor
fast-path, and the truncated-response defense added to extract_scores().
"""

import pytest

from review_asset import (
    APPROVAL_MODES,
    SCORE_KEYS,
    compute_verdict,
    extract_scores,
)


def make_scores(value):
    """All five dimensions equal to `value`."""
    return {k: value for k in SCORE_KEYS}


def review_with(scores=None, hard_fail=""):
    return {
        "scores": scores if scores is not None else {},
        "hard_fail_reason": hard_fail,
        "observations": "",
    }


class TestExtractScores:
    def test_full_set_returns_floats_in_order(self):
        scores = make_scores(7)
        values = extract_scores(scores)
        assert values == [7.0, 7.0, 7.0, 7.0, 7.0]

    def test_missing_dimension_returns_none(self):
        scores = make_scores(8)
        del scores["brand_fit"]
        assert extract_scores(scores) is None

    def test_non_numeric_returns_none(self):
        scores = make_scores(8)
        scores["color_match"] = "high"
        assert extract_scores(scores) is None

    def test_bool_rejected_even_though_isinstance_int(self):
        # True is technically isinstance(int) — explicitly reject.
        scores = make_scores(8)
        scores["color_match"] = True
        assert extract_scores(scores) is None

    def test_empty_dict_returns_none(self):
        assert extract_scores({}) is None


class TestComputeVerdict:
    def test_strict_all_nines_approved(self):
        assert compute_verdict(review_with(make_scores(9))) == "approved"

    def test_strict_all_eights_approved(self):
        # 8 >= min_per_dim (7) and avg 8.0 >= min_avg (8.0)
        assert compute_verdict(review_with(make_scores(8))) == "approved"

    def test_strict_all_sevens_below_avg(self):
        # 7 >= min_per_dim but avg 7.0 < min_avg 8.0 → regenerate
        assert compute_verdict(review_with(make_scores(7))) == "regenerate"

    def test_strict_one_dim_below_floor_regenerates(self):
        scores = make_scores(9)
        scores["color_match"] = 4  # below regen_floor (5)
        assert compute_verdict(review_with(scores)) == "regenerate"

    def test_strict_low_avg_escalates(self):
        # All values 5 → above regen floor, but avg 5.0 < escalate_avg 6.5
        assert compute_verdict(review_with(make_scores(5))) == "escalate_to_human"

    def test_balanced_threshold(self):
        # 7s in balanced mode: min_per_dim=6, min_avg=7.0 → approved
        assert compute_verdict(review_with(make_scores(7)), mode="balanced") == "approved"

    def test_fast_threshold(self):
        # 6s in fast mode: min_per_dim=4, min_avg=6.0 → approved
        assert compute_verdict(review_with(make_scores(6)), mode="fast") == "approved"

    def test_hard_fail_always_escalates(self):
        review = review_with(make_scores(10), hard_fail="Subject is wrong person")
        assert compute_verdict(review) == "escalate_to_human"

    def test_missing_scores_escalate_not_approve(self):
        """Truncated model response must NOT be silently averaged to approval."""
        scores = make_scores(10)
        del scores["technical_quality"]
        del scores["brand_fit"]
        # Old behavior would average the 3 remaining 10s to 10.0 and approve.
        # New behavior: extract_scores returns None → escalate.
        assert compute_verdict(review_with(scores)) == "escalate_to_human"

    def test_unknown_mode_falls_back_to_strict(self):
        # 7s with bogus mode should behave like strict (regenerate, not approve).
        assert compute_verdict(review_with(make_scores(7)), mode="bogus") == "regenerate"


def test_approval_modes_thresholds_consistent():
    """Each mode's regen_floor must be < min_per_dim < min_avg."""
    for mode_name, thresholds in APPROVAL_MODES.items():
        assert thresholds["regen_floor"] < thresholds["min_per_dim"], (
            f"{mode_name}: regen_floor must be below min_per_dim"
        )
        assert thresholds["escalate_avg"] < thresholds["min_avg"], (
            f"{mode_name}: escalate_avg must be below min_avg"
        )
