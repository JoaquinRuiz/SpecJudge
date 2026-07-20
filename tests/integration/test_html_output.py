"""Integration US3: self-contained HTML matrix via --open (headless-safe)."""

from __future__ import annotations

import re

from typer.testing import CliRunner

from specjudge.cli import app

runner = CliRunner()


def test_open_generates_self_contained_html(
    project_sufficient, mock_ollama, tmp_path, monkeypatch, test_catalog
):
    written = {}

    # Do not open a real browser during the test (headless-safe).
    monkeypatch.setattr(
        "specjudge.render.html.webbrowser.open", lambda uri: written.setdefault("uri", uri)
    )

    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--no-color",
                "--open",
                "--catalog",
                str(test_catalog),
            ],
        )
    assert result.exit_code == 0, result.output
    assert "HTML matrix" in result.output

    # Extract the HTML path from the output and check self-containment.
    m = re.search(r"HTML matrix: (.+\.html)", result.output)
    assert m, result.output
    html = open(m.group(1).strip(), encoding="utf-8").read()
    # Self-contained = loads nothing from the network. Navigation links are fine
    # (nothing is fetched until clicked); see tests/unit/test_html.py.
    assert not re.search(r'\bsrc\s*=\s*["\']https?://', html, re.I)
    assert not re.search(r'<link\b[^>]*\bhref\s*=\s*["\']https?://', html, re.I)
    assert "@import" not in html
    assert "Balanced Mid" in html


def test_open_headless_does_not_crash(project_sufficient, mock_ollama, monkeypatch):
    # Simulate a browser-less environment: webbrowser.open raises.
    def _raise(uri):
        raise RuntimeError("no browser")

    monkeypatch.setattr("specjudge.render.html.webbrowser.open", _raise)
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app, [str(project_sufficient), "--judge", "llama3.1:8b", "--open", "--no-color"]
        )
    assert result.exit_code == 0, result.output
