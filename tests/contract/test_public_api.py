"""The public Python surface is a promise, so its shape is pinned (FR-022).

`__all__` is asserted against a literal list rather than derived from the module.
Deriving it would make the test agree with whatever the code happens to export,
which is precisely the mistake this guards against: a symbol added in passing is a
symbol we are now committed to.
"""

from __future__ import annotations

import json

import jsonschema
import pytest

from specjudge import api
from specjudge.serialize import schema_path

# Every name below is covered by semantic versioning. Adding one is a MINOR release
# and a documentation change; removing or renaming one is MAJOR.
PUBLIC_SURFACE = {
    "analyze",
    "SCHEMA_VERSION",
    "to_dict",
    "json_schema",
    "Comparison",
    "Constraint",
    "DataState",
    "DemandProfile",
    "Envelope",
    "ExecutionModel",
    "Evaluation",
    "Evidence",
    "EvidenceStatus",
    "Price",
    "Rating",
    "SpecJudgeError",
    "CatalogError",
    "InsufficientInfoError",
    "JudgeUnavailableError",
}


def test_public_surface_is_exactly_what_is_documented():
    assert set(api.__all__) == PUBLIC_SURFACE


def test_every_exported_name_actually_exists():
    for name in api.__all__:
        assert hasattr(api, name), f"{name} is exported but not defined"


def test_the_documented_surface_is_listed_in_the_docs():
    """A promise nobody wrote down is not a promise."""
    from pathlib import Path

    docs = (Path(__file__).resolve().parents[2] / "docs" / "api.md").read_text(encoding="utf-8")
    for name in PUBLIC_SURFACE:
        assert f"`{name}`" in docs, f"{name} is public but undocumented"


def test_errors_carry_the_exit_codes_the_cli_uses():
    """The point of exporting the error types: branch without parsing messages."""
    assert api.InsufficientInfoError("x").exit_code == 2
    assert api.JudgeUnavailableError("x").exit_code == 3
    assert api.CatalogError("x").exit_code == 4
    for error in (api.InsufficientInfoError, api.JudgeUnavailableError, api.CatalogError):
        assert issubclass(error, api.SpecJudgeError)


def test_json_schema_matches_the_packaged_document():
    assert api.json_schema() == json.loads(schema_path().read_text(encoding="utf-8"))


def test_analyze_returns_a_comparison_that_serialises(
    project_sufficient, test_catalog, mock_ollama
):
    """The whole point of the façade: one call in, a valid payload out."""
    with mock_ollama(models=["llama3.1:8b"]):
        comparison = api.analyze(
            project_sufficient, judge_model="llama3.1:8b", catalog_path=test_catalog
        )

    assert isinstance(comparison, api.Comparison)
    assert comparison.best_choice
    payload = api.to_dict(comparison)
    jsonschema.validate(payload, api.json_schema())


def test_analyze_refuses_a_project_without_tasks(project_insufficient, test_catalog, mock_ollama):
    with mock_ollama(models=["llama3.1:8b"]):
        with pytest.raises(api.InsufficientInfoError) as exc:
            api.analyze(project_insufficient, judge_model="llama3.1:8b", catalog_path=test_catalog)
    assert exc.value.exit_code == 2


def test_analyze_reports_an_unavailable_judge(project_sufficient, test_catalog, mock_ollama):
    with mock_ollama(down=True):
        with pytest.raises(api.JudgeUnavailableError) as exc:
            api.analyze(project_sufficient, judge_model="llama3.1:8b", catalog_path=test_catalog)
    assert exc.value.exit_code == 3


def test_analyze_matches_what_the_cli_would_print(project_sufficient, test_catalog, mock_ollama):
    """Library and CLI must not drift into two different answers."""
    from typer.testing import CliRunner

    from specjudge.cli import app

    with mock_ollama(models=["llama3.1:8b"]):
        comparison = api.analyze(
            project_sufficient, judge_model="llama3.1:8b", catalog_path=test_catalog
        )
    with mock_ollama(models=["llama3.1:8b"]):
        result = CliRunner().invoke(
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
    assert api.to_dict(comparison) == json.loads(result.output)
