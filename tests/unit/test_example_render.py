"""Unit tests for the README example generator (issue #7).

Synthetic comparisons, so the selection and arithmetic are pinned independently of
whatever the real catalog happens to contain today.
"""

from __future__ import annotations

import render_example

from specjudge.domain import Comparison, DataState, Evaluation, Price, Rating


def _evaluation(
    model_id: str,
    rating: Rating,
    output: float,
    *,
    input_price: float = 1.0,
    deficit: int = 0,
    excess: int = 0,
) -> Evaluation:
    return Evaluation(
        model_id=model_id,
        model_name=model_id.replace("-", " ").title(),
        rating=rating,
        justification="because",
        price=Price(
            input_per_million=input_price,
            output_per_million=output,
            currency="USD",
            pricing_date="2026-07-28",
        ),
        deficit=deficit,
        excess=excess,
    )


def _comparison(evaluations: list[Evaluation], podium: list[str]) -> Comparison:
    return Comparison(
        evaluations=evaluations,
        data_state=DataState.SUFFICIENT,
        judge_model="judge",
        best_choice=podium[0] if podium else None,
        podium=podium,
    )


# --------------------------------------------------------- reference_overkill


def test_reference_overkill_picks_the_priciest_overkill():
    comparison = _comparison(
        [
            _evaluation("fit", Rating.GOOD, 1.0),
            _evaluation("mid-overkill", Rating.OVERKILL, 20.0, excess=1),
            _evaluation("top-overkill", Rating.OVERKILL, 50.0, excess=2),
        ],
        ["fit"],
    )
    assert render_example.reference_overkill(comparison).model_id == "top-overkill"


def test_reference_overkill_ignores_non_overkill_rows():
    """A merely expensive 'good' model is not what the example argues against."""
    comparison = _comparison(
        [
            _evaluation("pricey-fit", Rating.GOOD, 99.0),
            _evaluation("overkill", Rating.OVERKILL, 20.0, excess=1),
        ],
        ["pricey-fit"],
    )
    assert render_example.reference_overkill(comparison).model_id == "overkill"


def test_reference_overkill_is_none_without_any():
    comparison = _comparison([_evaluation("fit", Rating.GOOD, 1.0)], ["fit"])
    assert render_example.reference_overkill(comparison) is None


# --------------------------------------------------------- cheapest_paid_fit


def test_cheapest_paid_fit_skips_free_models():
    comparison = _comparison(
        [
            _evaluation("local", Rating.GOOD, 0.0, input_price=0.0),
            _evaluation("cheap-hosted", Rating.GOOD, 0.28),
            _evaluation("dear-hosted", Rating.GOOD, 5.0),
        ],
        ["local"],
    )
    assert render_example.cheapest_paid_fit(comparison).model_id == "cheap-hosted"


def test_cheapest_paid_fit_skips_models_that_do_not_fit():
    comparison = _comparison(
        [
            _evaluation("too-weak", Rating.POOR, 0.01, deficit=2),
            _evaluation("fits", Rating.GOOD, 3.0),
        ],
        ["fits"],
    )
    assert render_example.cheapest_paid_fit(comparison).model_id == "fits"


def test_cheapest_paid_fit_is_none_when_everything_is_free():
    comparison = _comparison([_evaluation("local", Rating.GOOD, 0.0, input_price=0.0)], ["local"])
    assert render_example.cheapest_paid_fit(comparison) is None


# ------------------------------------------------------------------- abridge


def test_abridge_keeps_the_podium_and_the_reference():
    rows = [
        _evaluation("gold", Rating.GOOD, 0.0, input_price=0.0),
        _evaluation("silver", Rating.GOOD, 1.0),
        _evaluation("bronze", Rating.GOOD, 2.0),
        _evaluation("ignored", Rating.GOOD, 3.0),
        _evaluation("reference", Rating.OVERKILL, 50.0, excess=2),
    ]
    comparison = _comparison(rows, ["gold", "silver", "bronze"])
    reference = render_example.reference_overkill(comparison)

    kept = [e.model_id for e in render_example.abridge(comparison, reference).evaluations]
    assert kept == ["gold", "silver", "bronze", "reference"]


def test_abridge_preserves_medals():
    """Filtering rows must not cost the podium its 🥇🥈🥉 markers."""
    rows = [
        _evaluation("gold", Rating.GOOD, 0.0, input_price=0.0),
        _evaluation("reference", Rating.OVERKILL, 50.0, excess=2),
    ]
    comparison = _comparison(rows, ["gold"])
    abridged = render_example.abridge(comparison, render_example.reference_overkill(comparison))
    assert abridged.medal("gold") == "gold"
    assert abridged.medal("reference") is None


# -------------------------------------------------------------- cost_summary


def test_cost_summary_states_the_gap_when_the_winner_is_free():
    """A multiple against zero is undefined, so the free case is phrased, not divided."""
    rows = [
        _evaluation("local", Rating.GOOD, 0.0, input_price=0.0),
        _evaluation("hosted", Rating.GOOD, 0.50),
        _evaluation("frontier", Rating.OVERKILL, 50.0, excess=2),
    ]
    comparison = _comparison(rows, ["local"])
    summary = render_example.cost_summary(comparison, render_example.reference_overkill(comparison))

    assert "costs nothing per token" in summary
    assert "100× cheaper on output" in summary  # 50.00 / 0.50, via the hosted fallback


def test_cost_summary_uses_a_multiple_when_the_winner_is_paid():
    rows = [
        _evaluation("hosted", Rating.GOOD, 2.0),
        _evaluation("frontier", Rating.OVERKILL, 50.0, excess=2),
    ]
    comparison = _comparison(rows, ["hosted"])
    summary = render_example.cost_summary(comparison, render_example.reference_overkill(comparison))

    assert "25× more on output" in summary
    assert "costs nothing per token" not in summary


def test_cost_summary_is_empty_without_a_reference():
    comparison = _comparison([_evaluation("only", Rating.GOOD, 1.0)], ["only"])
    assert render_example.cost_summary(comparison, None) == ""
