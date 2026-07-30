"""Integration US1: full pipeline -> comparison via --json (Ollama mocked)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from specjudge.cli import app

runner = CliRunner()


def test_sufficient_project_json(project_sufficient, mock_ollama, test_catalog):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--json",
                "--catalog",
                str(test_catalog),
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["data_state"] == "sufficient"
    assert data["judge_model"] == "llama3.1:8b"
    assert len(data["evaluations"]) == 4
    # Every evaluation carries a non-empty justification (SC-006).
    assert all(e["justification"].strip() for e in data["evaluations"])
    # best_choice present and consistent with the rule (cheapest good).
    assert data["best_choice"] is not None


def test_best_choice_is_cheapest_good(project_sufficient, mock_ollama, test_catalog):
    # Medium demand -> balanced-mid fits 'good'; capable/frontier are 'overkill'.
    demand = {"reasoning": "medium", "size": "medium", "domain_specialization": "medium"}
    with mock_ollama(models=["llama3.1:8b"], demand=demand):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--json",
                "--catalog",
                str(test_catalog),
            ],
        )
    data = json.loads(result.output)
    assert data["best_choice"] == "balanced-mid"


def test_json_exposes_the_podium(project_sufficient, mock_ollama, test_catalog):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--json",
                "--catalog",
                str(test_catalog),
            ],
        )
    data = json.loads(result.output)
    assert data["podium"][0] == data["best_choice"]
    assert 1 <= len(data["podium"]) <= 3


def test_example_project_classifies_as_sufficient():
    """The README example must stay a *worked* example (issue #7).

    If examples/task-manager ever degrades to `scarce`, the README would be
    demonstrating the degraded path while claiming to show the normal one.
    """
    from pathlib import Path

    from specjudge.artifacts import read_project
    from specjudge.domain import DataState
    from specjudge.rating import load_rules

    project = Path(__file__).resolve().parents[2] / "examples" / "task-manager"
    analysis = read_project(project, load_rules())
    assert analysis.data_state == DataState.SUFFICIENT
    assert not analysis.warnings


def test_json_exposes_the_evidence_behind_each_dimension(
    project_sufficient, mock_ollama, test_catalog
):
    """Criterion 4 of issue #1: coverage is in the output, not just used internally."""
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--json",
                "--catalog",
                str(test_catalog),
            ],
        )
    assert result.exit_code == 0, result.output
    demand = json.loads(result.output)["demand"]

    assert demand["dimensions"], "the judge's assessment must reach the output"
    assert "dimensions grounded" in demand["coverage"]
    for dim in demand["dimensions"]:
        entry = demand["evidence"][dim]
        assert entry["status"] == "grounded"
        assert entry["fragment_id"], "a grounded dimension must name its fragment"
