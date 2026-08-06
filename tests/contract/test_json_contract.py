"""The `--json` payload is a contract, so it is validated against its schema (FR-022).

Validation lives here rather than at runtime: it catches our own drift, not a user's
mistake, so making every run pay for it — and adding a mandatory dependency to do so —
would be charging the wrong person.
"""

from __future__ import annotations

import json

import jsonschema
import pytest
from typer.testing import CliRunner

from specjudge.cli import app
from specjudge.serialize import SCHEMA_VERSION, load_schema

runner = CliRunner()
SCHEMA = load_schema()


def _run(project, catalog, mock_ollama, demand=None) -> dict:
    with mock_ollama(models=["llama3.1:8b"], demand=demand) as _:
        result = runner.invoke(
            app,
            [str(project), "--judge", "llama3.1:8b", "--json", "--catalog", str(catalog)],
        )
    assert result.exit_code == 0, result.output
    return json.loads(result.output)


def test_the_schema_is_itself_valid():
    """A malformed schema would validate nothing while looking like it did."""
    jsonschema.Draft202012Validator.check_schema(SCHEMA)


def test_a_full_run_validates(project_sufficient, test_catalog, mock_ollama):
    jsonschema.validate(_run(project_sufficient, test_catalog, mock_ollama), SCHEMA)


def test_a_scarce_project_validates(project_scarce, test_catalog, mock_ollama):
    payload = _run(project_scarce, test_catalog, mock_ollama)
    assert payload["data_state"] == "scarce"
    assert payload["warnings"]
    jsonschema.validate(payload, SCHEMA)


@pytest.mark.parametrize(
    "demand",
    [
        {"reasoning": "top", "size": "top", "domain_specialization": "top"},
        {"reasoning": "low", "size": "low", "domain_specialization": "low"},
        {"reasoning": "unsupported", "size": "medium", "domain_specialization": "medium"},
    ],
    ids=["nothing-fits", "everything-overkill", "partially-grounded"],
)
def test_degraded_shapes_validate(project_sufficient, test_catalog, mock_ollama, demand):
    """Empty podium, null best_choice and unsupported dimensions are where a
    hand-written schema usually turns out to be wrong."""
    jsonschema.validate(_run(project_sufficient, test_catalog, mock_ollama, demand), SCHEMA)


def test_the_payload_declares_the_schema_version(project_sufficient, test_catalog, mock_ollama):
    payload = _run(project_sufficient, test_catalog, mock_ollama)
    assert payload["schema_version"] == SCHEMA_VERSION


def test_the_schema_documents_the_version_it_describes():
    """Schema and code must not disagree about which contract this is."""
    assert f"Version {SCHEMA_VERSION}." in SCHEMA["description"]


def test_unknown_fields_are_rejected(project_sufficient, test_catalog, mock_ollama):
    """`additionalProperties: false` is what makes an accidental addition visible."""
    payload = _run(project_sufficient, test_catalog, mock_ollama)
    payload["surprise"] = True
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(payload, SCHEMA)


def test_print_schema_emits_the_packaged_document():
    """The escape hatch for consumers who will never import Python."""
    result = runner.invoke(app, ["--print-schema"])
    assert result.exit_code == 0
    assert json.loads(result.output) == SCHEMA


def test_the_rating_vocabulary_is_the_constitutional_one():
    """The scale is fixed by the constitution; the schema must not quietly widen it."""
    ratings = SCHEMA["$defs"]["evaluation"]["properties"]["rating"]["enum"]
    assert ratings == ["poor", "fair", "good", "overkill"]
