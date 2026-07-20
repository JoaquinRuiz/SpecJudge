"""Unit tests for the table renderer (ordering/highlighting) - T027."""

from __future__ import annotations

from specjudge.domain import Comparison, DataState, Evaluation, Price, Rating
from specjudge.render.table import render_comparison


def _comp() -> Comparison:
    evals = [
        Evaluation("best", "Best", Rating.GOOD, "good fit", Price(0.5, 1.5, "USD", "2026-07-01")),
        Evaluation("over", "Over", Rating.OVERKILL, "overkill", Price(10, 40, "USD", "2026-07-01")),
    ]
    return Comparison(evals, DataState.SUFFICIENT, "llama3.1:8b", "best",
                      podium=["best", "over"])


def test_table_renders_best_and_models(capsys):
    render_comparison(_comp(), no_color=True)
    out = capsys.readouterr().out
    assert "Best" in out
    assert "Over" in out
    assert "🥇 Gold: Best" in out
    assert "🥈 Silver: Over" in out


def test_scarce_shows_warning(capsys):
    comp = _comp()
    comp.data_state = DataState.SCARCE
    comp.warnings = ["Missing artifacts"]
    render_comparison(comp, no_color=True)
    out = capsys.readouterr().out
    assert "Missing artifacts" in out


def test_free_price_renders_as_open_source(capsys):
    """A 0/0 price is shown as 'open-source/free', not '0.00 out / 0.00 in'."""
    evals = [
        Evaluation("local", "Local Model", Rating.GOOD, "fits", Price(0.0, 0.0, "USD", "2026-07-20")),
    ]
    comp = Comparison(evals, DataState.SUFFICIENT, "llama3.1:8b", "local")
    render_comparison(comp, no_color=True)
    out = capsys.readouterr().out
    assert "open-source/free" in out
    assert "0.00" not in out
