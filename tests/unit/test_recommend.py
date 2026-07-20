"""Unit tests for the best-fit rule (FR-008): fit to complexity, price ignored."""

from __future__ import annotations

from specjudge.domain import DataState, Evaluation, Price, Rating
from specjudge.recommend import build_comparison, choose_best, choose_podium


def _ev(
    model_id: str,
    rating: Rating,
    out_price: float,
    *,
    deficit: int = 0,
    excess: int = 0,
) -> Evaluation:
    return Evaluation(
        model_id=model_id,
        model_name=model_id,
        rating=rating,
        justification="x",
        price=Price(1.0, out_price, "USD", "2026-07-01"),
        deficit=deficit,
        excess=excess,
    )


def test_prefers_exact_fit_over_overpowered():
    evals = [
        _ev("overpowered", Rating.OVERKILL, 0.1, excess=4),  # cheapest, but too capable
        _ev("right-sized", Rating.GOOD, 50.0, excess=0),
    ]
    assert choose_best(evals) == "right-sized"


def test_price_never_overrides_fit():
    """A far cheaper but worse-fitting model must not win."""
    evals = [
        _ev("cheap-overpowered", Rating.OVERKILL, 0.01, excess=3),
        _ev("expensive-exact", Rating.GOOD, 999.0, excess=0),
    ]
    assert choose_best(evals) == "expensive-exact"


def test_least_excess_wins_among_capable():
    evals = [
        _ev("excess-3", Rating.OVERKILL, 1.0, excess=3),
        _ev("excess-1", Rating.GOOD, 1.0, excess=1),
        _ev("excess-2", Rating.OVERKILL, 1.0, excess=2),
    ]
    assert choose_best(evals) == "excess-1"


def test_under_capable_models_are_never_chosen():
    evals = [
        _ev("too-weak", Rating.FAIR, 0.0, deficit=1),
        _ev("way-too-weak", Rating.POOR, 0.0, deficit=3),
        _ev("capable", Rating.OVERKILL, 100.0, excess=2),
    ]
    assert choose_best(evals) == "capable"


def test_no_best_when_every_model_is_under_capable():
    evals = [
        _ev("a", Rating.FAIR, 1.0, deficit=1),
        _ev("b", Rating.POOR, 0.5, deficit=2),
    ]
    assert choose_best(evals) is None


def test_comparison_warns_when_no_capable_model():
    evals = [_ev("a", Rating.FAIR, 1.0, deficit=1)]
    comp = build_comparison(evals, DataState.SUFFICIENT, "judge")
    assert comp.best_choice is None
    assert any("No model" in w for w in comp.warnings)


def test_results_ordered_most_to_least_optimal():
    """Exact fit first, then increasing excess, then under-capable by deficit."""
    evals = [
        _ev("short-by-2", Rating.POOR, 0.1, deficit=2),
        _ev("excess-2", Rating.OVERKILL, 0.1, excess=2),
        _ev("short-by-1", Rating.FAIR, 0.1, deficit=1),
        _ev("exact", Rating.GOOD, 0.1, excess=0),
    ]
    comp = build_comparison(evals, DataState.SUFFICIENT, "judge")
    assert [e.model_id for e in comp.evaluations] == [
        "exact",
        "excess-2",
        "short-by-1",
        "short-by-2",
    ]


def test_price_breaks_ties_only_between_identical_fits():
    evals = [
        _ev("same-fit-expensive", Rating.GOOD, 10.0, excess=0),
        _ev("same-fit-free", Rating.GOOD, 0.0, excess=0),
    ]
    comp = build_comparison(evals, DataState.SUFFICIENT, "judge")
    assert comp.best_choice == "same-fit-free"
    assert comp.evaluations[0].model_id == "same-fit-free"


def test_ties_broken_deterministically_by_model_id():
    """Identical fit and identical price must not depend on catalog file order."""
    evals = [
        _ev("zeta", Rating.GOOD, 0.0, excess=0),
        _ev("alpha", Rating.GOOD, 0.0, excess=0),
        _ev("mid", Rating.GOOD, 0.0, excess=0),
    ]
    comp = build_comparison(evals, DataState.SUFFICIENT, "judge")
    assert [e.model_id for e in comp.evaluations] == ["alpha", "mid", "zeta"]
    assert comp.best_choice == "alpha"


def test_podium_is_top_three_by_fit():
    evals = [
        _ev("fourth", Rating.OVERKILL, 1.0, excess=4),
        _ev("gold", Rating.GOOD, 1.0, excess=0),
        _ev("bronze", Rating.OVERKILL, 1.0, excess=2),
        _ev("silver", Rating.GOOD, 1.0, excess=1),
    ]
    comp = build_comparison(evals, DataState.SUFFICIENT, "judge")
    assert comp.podium == ["gold", "silver", "bronze"]
    assert comp.best_choice == "gold"
    assert comp.medal("gold") == "gold"
    assert comp.medal("silver") == "silver"
    assert comp.medal("bronze") == "bronze"
    assert comp.medal("fourth") is None


def test_podium_excludes_under_capable_models():
    """A model that cannot do the job never gets a medal, even to fill the podium."""
    evals = [
        _ev("only-capable", Rating.GOOD, 1.0, excess=0),
        _ev("too-weak", Rating.FAIR, 0.0, deficit=1),
        _ev("way-too-weak", Rating.POOR, 0.0, deficit=3),
    ]
    comp = build_comparison(evals, DataState.SUFFICIENT, "judge")
    assert comp.podium == ["only-capable"]
    assert comp.medal("too-weak") is None


def test_podium_empty_when_nothing_is_capable():
    evals = [_ev("weak", Rating.FAIR, 1.0, deficit=1)]
    comp = build_comparison(evals, DataState.SUFFICIENT, "judge")
    assert comp.podium == []
    assert comp.best_choice is None


def test_choose_podium_respects_size():
    evals = [_ev(f"m{i}", Rating.GOOD, 1.0, excess=i) for i in range(5)]
    assert choose_podium(evals, size=2) == ["m0", "m1"]
