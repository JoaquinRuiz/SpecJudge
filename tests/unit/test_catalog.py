"""Catalog freshness checks - T061 (FR-019).

`today` is injected everywhere so these tests do not rot as the clock moves.
"""

from __future__ import annotations

from datetime import date

from specjudge.catalog import check_freshness
from specjudge.domain import DEFAULT_MAX_PRICING_AGE_DAYS, CatalogModel, Price

TODAY = date(2026, 7, 28)


def _model(model_id: str, pricing_date: str | None) -> CatalogModel:
    return CatalogModel(
        id=model_id,
        name=model_id.replace("-", " ").title(),
        capabilities={"reasoning": "medium", "size": "medium", "domain_specialization": "medium"},
        price=Price(
            input_per_million=1.0,
            output_per_million=2.0,
            currency="USD",
            pricing_date=pricing_date,
        ),
    )


# --------------------------------------------------------------- Price.age_days


def test_age_days_counts_elapsed_days():
    assert _model("m", "2026-07-01").price.age_days(TODAY) == 27


def test_age_days_is_zero_on_the_pricing_date():
    assert _model("m", "2026-07-28").price.age_days(TODAY) == 0


def test_age_days_is_none_without_a_date():
    """No date is 'unverifiable', which is not the same as 'old'."""
    assert _model("m", None).price.age_days(TODAY) is None


def test_age_days_is_none_for_an_unparseable_date():
    """A junk date must degrade, never crash and never read as age zero."""
    assert _model("m", "julio 2026").price.age_days(TODAY) is None


def test_age_days_clamps_a_future_date_to_zero():
    assert _model("m", "2027-01-01").price.age_days(TODAY) == 0


# ------------------------------------------------------------- check_freshness


def test_no_warning_below_the_threshold():
    models = [_model("fresh", "2026-07-01")]
    assert check_freshness(models, 90, today=TODAY) == []


def test_no_warning_exactly_at_the_threshold():
    """The threshold is the last acceptable age, not the first rejected one."""
    models = [_model("edge", "2026-04-29")]  # exactly 90 days
    assert models[0].price.age_days(TODAY) == 90
    assert check_freshness(models, 90, today=TODAY) == []


def test_warns_one_day_past_the_threshold():
    models = [_model("edge", "2026-04-28")]  # 91 days
    assert check_freshness(models, 90, today=TODAY)


def test_warning_names_the_age_not_just_staleness():
    """Done-when criterion: the warning must state how old, not merely that it is old."""
    models = [_model("ancient", "2025-01-01")]
    (warning,) = check_freshness(models, 90, today=TODAY)
    assert "573 days" in warning
    assert "Ancient" in warning


def test_warning_counts_stale_entries_against_the_catalog_size():
    models = [
        _model("old-one", "2025-01-01"),
        _model("old-two", "2025-06-01"),
        _model("fresh", "2026-07-01"),
    ]
    (warning,) = check_freshness(models, 90, today=TODAY)
    assert "2 of 3" in warning
    # The oldest entry is the one named.
    assert "Old One" in warning


def test_warning_is_singular_for_a_single_stale_entry():
    models = [_model("old-one", "2025-01-01"), _model("fresh", "2026-07-01")]
    (warning,) = check_freshness(models, 90, today=TODAY)
    assert "1 of 2 catalog prices is older" in warning


def test_undated_models_are_not_counted_as_stale():
    """A missing date is already reported by the loader; don't double-report it."""
    models = [_model("no-date", None), _model("fresh", "2026-07-01")]
    assert check_freshness(models, 90, today=TODAY) == []


def test_empty_catalog_produces_no_warning():
    assert check_freshness([], 90, today=TODAY) == []


def test_threshold_is_honoured():
    """A stricter threshold flags what a laxer one lets through."""
    models = [_model("m", "2026-06-01")]  # 57 days
    assert check_freshness(models, 90, today=TODAY) == []
    assert check_freshness(models, 30, today=TODAY)


def test_default_threshold_is_a_quarter():
    assert DEFAULT_MAX_PRICING_AGE_DAYS == 90
