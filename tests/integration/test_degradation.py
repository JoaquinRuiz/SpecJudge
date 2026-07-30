"""Integration US4: explicit degradation by data state (FR-009/010, SC-002/003)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from specjudge.cli import app

runner = CliRunner()


def test_insufficient_exits_2_no_comparison(project_insufficient, mock_ollama):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(app, [str(project_insufficient), "--judge", "llama3.1:8b", "--json"])
    assert result.exit_code == 2
    assert "not enough" in result.output.lower()
    # Must not emit a JSON comparison.
    assert '"evaluations"' not in result.output


def test_scarce_exits_0_with_warning(project_scarce, mock_ollama):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(app, [str(project_scarce), "--judge", "llama3.1:8b", "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["data_state"] == "scarce"
    assert data["warnings"], "scarce must carry a warning"


def test_insufficient_and_scarce_are_distinct(project_insufficient, project_scarce, mock_ollama):
    with mock_ollama(models=["llama3.1:8b"]):
        r_insuf = runner.invoke(
            app, [str(project_insufficient), "--judge", "llama3.1:8b", "--json"]
        )
        r_scarce = runner.invoke(app, [str(project_scarce), "--judge", "llama3.1:8b", "--json"])
    assert r_insuf.exit_code == 2
    assert r_scarce.exit_code == 0


def test_empty_catalog_exits_4(project_sufficient, mock_ollama, tmp_path):
    empty = tmp_path / "empty.yaml"
    empty.write_text("version: 1\ndimensions: [reasoning]\nmodels: []\n", encoding="utf-8")
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [str(project_sufficient), "--judge", "llama3.1:8b", "--catalog", str(empty)],
        )
    assert result.exit_code == 4
    assert "catalog" in result.output.lower()


def test_stale_pricing_warns_without_changing_the_exit_code(
    project_sufficient, mock_ollama, tmp_path
):
    """FR-019: staleness qualifies the recommendation, it does not fail the run."""
    catalog = tmp_path / "stale-catalog.yaml"
    catalog.write_text(
        "version: 1\n"
        "dimensions: [reasoning, size, domain_specialization]\n"
        "models:\n"
        "  - id: ancient\n"
        "    name: Ancient Model\n"
        "    capabilities: {reasoning: medium, size: medium, domain_specialization: medium}\n"
        "    price:\n"
        "      input_per_million: 1\n"
        "      output_per_million: 2\n"
        "      currency: USD\n"
        "      pricing_date: 2020-01-01\n",
        encoding="utf-8",
    )
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--json",
                "--catalog",
                str(catalog),
            ],
        )
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert any("older than" in w for w in data["warnings"])
    # A dated-but-old price is still verifiable: price_stale keeps its meaning.
    assert data["evaluations"][0]["price_stale"] is False
    assert data["best_choice"], "a stale catalog must still yield a recommendation"
