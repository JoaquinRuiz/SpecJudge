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
            [str(project_sufficient), "--judge", "llama3.1:8b", "--json",
             "--catalog", str(test_catalog)],
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
            app, [str(project_sufficient), "--judge", "llama3.1:8b", "--json",
                  "--catalog", str(test_catalog)]
        )
    data = json.loads(result.output)
    assert data["best_choice"] == "balanced-mid"


def test_json_exposes_the_podium(project_sufficient, mock_ollama, test_catalog):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app, [str(project_sufficient), "--judge", "llama3.1:8b", "--json",
                  "--catalog", str(test_catalog)]
        )
    data = json.loads(result.output)
    assert data["podium"][0] == data["best_choice"]
    assert 1 <= len(data["podium"]) <= 3
