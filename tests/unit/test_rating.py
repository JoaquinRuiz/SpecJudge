"""Unit tests for the rating engine (demand x capability)."""

from __future__ import annotations

import pytest

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


# ------------------------------------- catalog_freshness threshold (T061/FR-019)

_MINIMAL_RULES = (
    "version: 1\n"
    "dimensions: [reasoning, size, domain_specialization]\n"
    "mapping:\n"
    "  levels: [low, medium, high, top]\n"
    "  per_dimension: {exact: good}\n"
)


def _write_rules(tmp_path, extra: str = ""):
    path = tmp_path / "rating-rules.yaml"
    path.write_text(_MINIMAL_RULES + extra, encoding="utf-8")
    return path


def test_freshness_threshold_is_read_from_the_rules(tmp_path):
    from specjudge.rating import load_rules

    path = _write_rules(tmp_path, "catalog_freshness:\n  max_age_days: 30\n")
    assert load_rules(path).max_pricing_age_days == 30


def test_freshness_threshold_defaults_when_absent(tmp_path):
    """Editing the knob is optional; omitting it must not break the load."""
    from specjudge.domain import DEFAULT_MAX_PRICING_AGE_DAYS
    from specjudge.rating import load_rules

    path = _write_rules(tmp_path)
    assert load_rules(path).max_pricing_age_days == DEFAULT_MAX_PRICING_AGE_DAYS


def test_shipped_rules_declare_the_freshness_threshold():
    from specjudge.rating import load_rules

    assert load_rules().max_pricing_age_days >= 1


def test_invalid_freshness_threshold_degrades_to_the_default(tmp_path):
    """A bad knob must not stop a recommendation (Principle IV)."""
    from specjudge.domain import DEFAULT_MAX_PRICING_AGE_DAYS
    from specjudge.rating import load_rules

    for bad in ("max_age_days: not-a-number", "max_age_days: 0", "max_age_days: -5"):
        path = _write_rules(tmp_path, f"catalog_freshness:\n  {bad}\n")
        assert load_rules(path).max_pricing_age_days == DEFAULT_MAX_PRICING_AGE_DAYS


# -------------------------------------- unsupported dimensions (issue #1 / FR-020)


def test_unsupported_dimension_is_excluded_from_the_fit_arithmetic():
    """It must not fall through to the weakest level and make projects look easy.

    Before this, an unknown level silently indexed to 0 (= low), so an ungrounded
    dimension made every model look capable there.
    """
    from specjudge.rating import evaluate_model

    rules = _rules()
    model = _model({"reasoning": "low", "size": "low", "domain_specialization": "low"})

    grounded = _demand({"reasoning": "top", "size": "low", "domain_specialization": "low"})
    ungrounded = _demand(
        {"reasoning": "unsupported", "size": "low", "domain_specialization": "low"}
    )

    # With the demanding dimension scored, the weak model is short by 3 steps.
    assert evaluate_model(model, grounded, rules).deficit == 3
    # Ungrounded, that dimension simply does not participate — it is not treated as
    # satisfied, it is absent, and the remaining dimensions still fit exactly.
    assert evaluate_model(model, ungrounded, rules).deficit == 0
    assert evaluate_model(model, ungrounded, rules).rating == Rating.GOOD


def test_rating_a_profile_with_no_supported_dimension_fails_loudly():
    """Callers refuse this earlier; reaching here must not crash on an empty min()."""
    from specjudge.errors import CatalogError
    from specjudge.rating import evaluate_model

    rules = _rules()
    model = _model({"reasoning": "high", "size": "high", "domain_specialization": "high"})
    demand = _demand(dict.fromkeys(rules.dimensions, "unsupported"))

    with pytest.raises(CatalogError, match="no supported dimension"):
        evaluate_model(model, demand, rules)


# ------------------------------------------- which demand the ranking uses (#3)


def test_the_ranking_uses_the_peak_by_default():
    """Unchanged behaviour: with no execution model given, one model does it all.

    This is the regression guard for every existing user. If it moves, someone's
    recommendation moved without them asking for it.
    """
    from specjudge.rating import evaluate_model

    demand = _demand({"reasoning": "top", "size": "low", "domain_specialization": "low"})
    model = _model({"reasoning": "medium", "size": "low", "domain_specialization": "low"})
    assert evaluate_model(model, demand, _rules()).rating is Rating.POOR


def test_the_ranking_can_be_built_on_the_bulk_instead():
    """The same project, judged on what most of the work needs."""
    from specjudge.rating import evaluate_model

    demand = _demand({"reasoning": "top", "size": "low", "domain_specialization": "low"})
    model = _model({"reasoning": "medium", "size": "low", "domain_specialization": "low"})
    bulk = {"reasoning": "medium", "size": "low", "domain_specialization": "low"}
    assert evaluate_model(model, demand, _rules(), bulk).rating is Rating.GOOD


def test_the_justification_quotes_the_demand_that_was_used():
    """Reporting the peak next to a bulk-based rating would be incoherent."""
    from specjudge.rating import evaluate_model

    demand = _demand({"reasoning": "top", "size": "low", "domain_specialization": "low"})
    model = _model({"reasoning": "medium", "size": "medium", "domain_specialization": "medium"})
    bulk = {"reasoning": "medium", "size": "low", "domain_specialization": "low"}
    justification = evaluate_model(model, demand, _rules(), bulk).justification
    assert "demand=medium" in justification
    assert "demand=top" not in justification
