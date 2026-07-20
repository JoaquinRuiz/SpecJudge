"""Integration US5: actionable guidance when the judge dependency is missing (FR-011, SC-004)."""

from __future__ import annotations

from typer.testing import CliRunner

from specjudge.cli import app

runner = CliRunner()


def test_ollama_down_exits_3_actionable(project_sufficient, mock_ollama):
    with mock_ollama(down=True):
        result = runner.invoke(app, [str(project_sufficient), "--judge", "llama3.1:8b"])
    assert result.exit_code == 3
    out = result.output.lower()
    assert "ollama" in out
    assert "traceback" not in out  # no technical dump


def test_ollama_no_models_exits_3_suggests_pull(project_sufficient, mock_ollama):
    with mock_ollama(models=[]):
        result = runner.invoke(app, [str(project_sufficient), "--judge", "llama3.1:8b"])
    assert result.exit_code == 3
    assert "pull" in result.output.lower()
