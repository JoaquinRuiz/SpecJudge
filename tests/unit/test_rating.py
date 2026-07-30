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
