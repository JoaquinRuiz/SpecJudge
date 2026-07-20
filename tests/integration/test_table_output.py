"""Integration US2: default terminal output (table)."""

from __future__ import annotations

from typer.testing import CliRunner

from specjudge.cli import app

runner = CliRunner()


def test_default_output_is_table(project_sufficient, mock_ollama, test_catalog):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--no-color",
                "--catalog",
                str(test_catalog),
            ],
        )
    assert result.exit_code == 0, result.output
    out = result.output
    assert "Model comparison" in out
    assert "🥇 Gold:" in out
    assert "🥈 Silver:" in out
    assert "🥉 Bronze:" in out
    # Default catalog model names are present.
    assert "Balanced Mid" in out
