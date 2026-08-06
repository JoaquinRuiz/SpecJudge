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


def _stale_catalog(tmp_path):
    """Catalog whose prices are old enough to be stale whenever the suite runs."""
    path = tmp_path / "stale-catalog.yaml"
    path.write_text(
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
    return path


def test_stale_catalog_warning_is_shown_on_a_sufficient_project(
    project_sufficient, mock_ollama, tmp_path
):
    """FR-019: the warning must reach the user on a healthy project too.

    Regression guard: warnings used to render only when data_state was 'scarce',
    which hid catalog warnings on exactly the runs where the price data is used.
    """
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--no-color",
                "--catalog",
                str(_stale_catalog(tmp_path)),
            ],
        )
    assert result.exit_code == 0, result.output
    assert "older than" in result.output
    assert "days" in result.output
    assert "Ancient Model" in result.output


def test_fresh_catalog_shows_no_staleness_warning(project_sufficient, mock_ollama, test_catalog):
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
    assert "older than" not in result.output


def test_table_shows_the_evidence_coverage(project_sufficient, mock_ollama, test_catalog):
    """The grounding must be visible without reaching for --json (issue #1)."""
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
    assert "Evidence:" in result.output
    assert "dimensions grounded" in result.output
    assert "cites" in result.output


def _thin_project(tmp_path):
    """A project with tasks but a one-line spec: the middle case issue #11 is about."""
    feature = tmp_path / "specs" / "001-f"
    feature.mkdir(parents=True)
    (feature / "spec.md").write_text("# Spec: Dashboard\n\n## Summary\nShow some charts.\n")
    (feature / "tasks.md").write_text(
        "# Tasks\n- [ ] T001 Build the chart component\n- [ ] T002 Wire the data source\n"
    )
    memory = tmp_path / ".specify" / "memory"
    memory.mkdir(parents=True)
    (memory / "constitution.md").write_text("# Constitution\n\n## I. Fast\nUnder a second.\n")
    return tmp_path


def test_a_thin_project_says_what_is_missing_after_the_table(tmp_path, mock_ollama, test_catalog):
    """FR-023: the caveat must land where reading ends, not above the podium.

    The whole point of the issue: one line above a ranked table loses to the table.
    """
    project = _thin_project(tmp_path)
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [str(project), "--judge", "llama3.1:8b", "--no-color", "--catalog", str(test_catalog)],
        )
    assert result.exit_code == 0, result.output
    out = result.output

    assert "This ranking rests on a thin definition" in out
    # Named concretely, and saying what it searched for.
    assert "FR-NNN" in out
    assert "SC-NNN" in out
    # And after the table, not before it.
    assert out.index("Model comparison") < out.index("This ranking rests on")
    assert out.index("🥇 Gold:") < out.index("This ranking rests on")


def test_every_gap_is_followed_by_what_to_write(tmp_path, mock_ollama, test_catalog):
    project = _thin_project(tmp_path)
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [str(project), "--judge", "llama3.1:8b", "--no-color", "--catalog", str(test_catalog)],
        )
    assert "→" in result.output, "a gap without a fix is just a complaint"


def test_a_well_defined_project_gets_no_gap_block(project_sufficient, mock_ollama, test_catalog):
    """Firing on a healthy project would train people to skip the block entirely."""
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
    assert "This ranking rests on" not in result.output
