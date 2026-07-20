"""CLI interface contract tests (contracts/cli.md)."""

from __future__ import annotations

from typer.testing import CliRunner

from specjudge import __version__
from specjudge.cli import app

runner = CliRunner()


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_help_lists_flags():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for flag in ["--open", "--judge", "--set-judge", "--catalog", "--json", "--no-color"]:
        assert flag in result.output


def test_exit_code_insufficient_is_2(project_insufficient, mock_ollama):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(app, [str(project_insufficient), "--judge", "llama3.1:8b"])
    assert result.exit_code == 2
