"""Unit tests for the rating engine (demand x capability)."""

from __future__ import annotations

from specjudge.domain import CatalogModel, DemandProfile, Price, Rating, RatingRules


def _rules() -> RatingRules:
    return RatingRules(
        version=1,
        dimensions=["reasoning", "size", "domain_specialization"],
        scarce_thresholds={"min_detailed_tasks": 3},
        per_dimension={
            "below_by_2_or_more": "poor",
            "below_by_1": "fair",
            "exact": "good",
            "above_by_1_or_more": "overkill",
        },
        aggregation="worst_dimension",
        levels=["low", "medium", "high", "top"],
    )


def _model(caps: dict[str, str]) -> CatalogModel:
    return CatalogModel(id="m", name="M", capabilities=caps, price=Price(1, 1, "USD", "2026-07-01"))


def _demand(dims: dict[str, str]) -> DemandProfile:
    return DemandProfile(dimensions=dims, justification="x", judge_model="j")


def test_exact_match_is_good():
    from specjudge.rating import evaluate_model

    rules = _rules()
    demand = _demand({"reasoning": "medium", "size": "medium", "domain_specialization": "medium"})
    model = _model({"reasoning": "medium", "size": "medium", "domain_specialization": "medium"})
    assert evaluate_model(model, demand, rules).rating == Rating.GOOD


def test_worst_dimension_dominates():
    from specjudge.rating import evaluate_model

    rules = _rules()
    demand = _demand({"reasoning": "high", "size": "high", "domain_specialization": "high"})
    # Strong in two dimensions, very weak in one -> the worst wins (poor).
    model = _model({"reasoning": "top", "size": "top", "domain_specialization": "low"})
    assert evaluate_model(model, demand, rules).rating == Rating.POOR


def test_overcapacity_is_overkill():
    from specjudge.rating import evaluate_model

    rules = _rules()
    demand = _demand({"reasoning": "low", "size": "low", "domain_specialization": "low"})
    model = _model({"reasoning": "high", "size": "high", "domain_specialization": "high"})
    assert evaluate_model(model, demand, rules).rating == Rating.OVERKILL


def test_justification_is_non_empty():
    """SC-006: every rating carries a human-readable justification."""
    from specjudge.rating import evaluate_model

    rules = _rules()
    demand = _demand({"reasoning": "medium", "size": "medium", "domain_specialization": "medium"})
    model = _model({"reasoning": "medium", "size": "medium", "domain_specialization": "medium"})
    assert evaluate_model(model, demand, rules).justification.strip()
