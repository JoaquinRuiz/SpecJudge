"""Unit tests for the table renderer (ordering/highlighting) - T027."""

from __future__ import annotations

from specjudge.domain import (
    Comparison,
    Constraint,
    DataState,
    Envelope,
    Evaluation,
    ExecutionModel,
    Price,
    Rating,
)
from specjudge.render.table import render_comparison


def _comp() -> Comparison:
    evals = [
        Evaluation("best", "Best", Rating.GOOD, "good fit", Price(0.5, 1.5, "USD", "2026-07-01")),
        Evaluation("over", "Over", Rating.OVERKILL, "overkill", Price(10, 40, "USD", "2026-07-01")),
    ]
    return Comparison(evals, DataState.SUFFICIENT, "llama3.1:8b", "best", podium=["best", "over"])


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
        Evaluation(
            "local", "Local Model", Rating.GOOD, "fits", Price(0.0, 0.0, "USD", "2026-07-20")
        ),
    ]
    comp = Comparison(evals, DataState.SUFFICIENT, "llama3.1:8b", "local")
    render_comparison(comp, no_color=True)
    out = capsys.readouterr().out
    assert "open-source/free" in out
    assert "0.00" not in out


def test_the_sources_read_are_named(capsys):
    """Several kinds of file can feed the judge now, so "from what?" needs answering."""
    comp = _comp()
    comp.source_kinds = ["constitution", "spec", "tasks", "agents"]
    render_comparison(comp, no_color=True)
    out = capsys.readouterr().out
    assert "Read: constitution, spec, tasks, AGENTS.md" in out


def test_repeated_sources_are_counted(capsys):
    """ "AGENTS.md" when four were read is a smaller claim than the truth."""
    comp = _comp()
    comp.source_kinds = ["agents", "agents", "agents", "adr"]
    render_comparison(comp, no_color=True)
    assert "Read: 3× AGENTS.md, ADR" in capsys.readouterr().out


def test_nothing_is_claimed_when_no_source_was_recorded(capsys):
    render_comparison(_comp(), no_color=True)
    assert "Read:" not in capsys.readouterr().out


# ------------------------------------------------- budget envelope (issue #3)


def _envelope(model: ExecutionModel, **kwargs) -> Envelope:
    hard = Constraint("reasoning", "top", "S:FR-001", "**FR-001**: it MUST hold", True)
    soft = Constraint("size", "low", "T:T002", "T002 Rename a label", False)
    return Envelope(
        execution_model=model,
        default_demand=kwargs.get("default", {"reasoning": "top", "size": "low"}),
        peak_demand={"reasoning": "top", "size": "low"},
        constraints=[hard, soft],
        escalations=kwargs.get("escalations", []),
    )


def test_the_envelope_names_the_fragment_behind_each_level(capsys):
    """The reader can go and look at the thing that is costing them money."""
    comp = _comp()
    comp.envelope = _envelope(ExecutionModel.SINGLE)
    render_comparison(comp, no_color=True)
    out = capsys.readouterr().out
    assert "Budget envelope" in out
    assert "reasoning: top — S:FR-001 (requirement)" in out
    assert "size: low — T:T002 (customary)" in out


def test_an_escalating_run_says_the_ranking_is_on_the_bulk(capsys):
    comp = _comp()
    comp.envelope = _envelope(
        ExecutionModel.ESCALATING,
        default={"reasoning": "medium", "size": "low"},
        escalations=[Constraint("reasoning", "top", "S:FR-001", "MUST hold", True)],
    )
    render_comparison(comp, no_color=True)
    out = capsys.readouterr().out
    assert "ranked on the bulk of the work" in out
    assert "escalate for:" in out
    assert "S:FR-001" in out


def test_uniform_work_shows_no_escalation_block(capsys):
    comp = _comp()
    comp.envelope = _envelope(ExecutionModel.ESCALATING)
    render_comparison(comp, no_color=True)
    assert "escalate for:" not in capsys.readouterr().out


def test_a_comparison_without_an_envelope_prints_none(capsys):
    render_comparison(_comp(), no_color=True)
    assert "Budget envelope" not in capsys.readouterr().out
