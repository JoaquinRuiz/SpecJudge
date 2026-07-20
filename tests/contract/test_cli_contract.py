"""CLI interface contract tests (contracts/cli.md)."""

from __future__ import annotations

import re

from typer.main import get_command
from typer.testing import CliRunner

from specjudge import __version__
from specjudge.cli import app

runner = CliRunner()

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _plain(text: str) -> str:
    """Strip ANSI styling so assertions don't depend on how Rich renders."""
    return _ANSI.sub("", text)


def test_version_flag():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in _plain(result.output)


def test_cli_declares_the_documented_options():
    """The documented flags must exist on the command.

    Asserted against the command's declared parameters rather than the rendered
    `--help` text: Rich wraps and styles that output differently depending on
    terminal width and colour support, so parsing it tests the renderer, not the
    contract.
    """
    declared = {opt for param in get_command(app).params for opt in param.opts}
    for flag in ["--open", "--judge", "--set-judge", "--catalog", "--json", "--no-color"]:
        assert flag in declared, f"{flag} is documented in contracts/cli.md but not declared"


def test_help_runs():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert result.output.strip()


def test_exit_code_insufficient_is_2(project_insufficient, mock_ollama):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(app, [str(project_insufficient), "--judge", "llama3.1:8b"])
    assert result.exit_code == 2
