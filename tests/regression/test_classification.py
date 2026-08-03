"""Data-state classification over the corpus (issue #5).

Three of the four categories the issue asks for — well-specified, thin, and
empty/task-less — are decided by `artifacts.py` before the judge is ever called.
That makes them fully deterministic and the part of the regression suite that can
honestly run in CI.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from specjudge.artifacts import read_project
from specjudge.cli import app
from specjudge.rating import load_rules

from .corpus import load_corpus

CASES = load_corpus()
runner = CliRunner()


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_data_state_matches_the_expected_label(case):
    analysis = read_project(case.path, load_rules())
    assert analysis.data_state.value == case.data_state, case.rationale


@pytest.mark.parametrize("case", [c for c in CASES if c.category == "thin"], ids=lambda c: c.name)
def test_thin_projects_carry_a_warning(case):
    """`scarce` without a warning would be a silent degradation (Principle IV)."""
    analysis = read_project(case.path, load_rules())
    assert analysis.warnings, f"{case.name} classified scarce but warned about nothing"


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.category == "well_specified"], ids=lambda c: c.name
)
def test_well_specified_projects_warn_about_nothing(case):
    analysis = read_project(case.path, load_rules())
    assert analysis.warnings == []


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.data_state == "insufficient"], ids=lambda c: c.name
)
def test_task_less_projects_refuse_before_reaching_the_judge(case, mock_ollama):
    """Exit 2 and no comparison — refusing, not guessing from an empty plan."""
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(app, [str(case.path), "--judge", "llama3.1:8b", "--json"])
    assert result.exit_code == 2, result.output
    assert "recommendation" in result.output.lower()


@pytest.mark.parametrize("case", [c for c in CASES if c.judged], ids=lambda c: c.name)
def test_judged_projects_produce_a_recommendation(case, mock_ollama, test_catalog):
    """With a judge that answers well, every non-refused case reaches a podium.

    This pins the plumbing, not the judgement: the mock cites what the prompt
    offered it. Whether a real judge rates these correctly is what the live tier
    measures, and it cannot run here.
    """
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [str(case.path), "--judge", "llama3.1:8b", "--json", "--catalog", str(test_catalog)],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["best_choice"], f"{case.name} produced no recommendation"
    assert data["demand"]["dimensions"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_every_judged_project_offers_something_to_cite(case):
    """A project the judge will rate must give it fragments to ground the rating in.

    If a case reached the judge with nothing citable, every dimension would come
    back `unsupported` and the run would refuse — a corpus case that can never
    pass tells us nothing.
    """
    if not case.judged:
        return
    from specjudge.judge.evaluator import artifact_limit
    from specjudge.judge.fragments import extract_fragments

    rules = load_rules()
    analysis = read_project(case.path, rules)
    fragments = extract_fragments(analysis, artifact_limit(rules, compact=True))
    assert fragments, f"{case.name} offers no citable fragment"
