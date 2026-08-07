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


def test_the_payload_says_which_sources_it_read(project_sufficient, test_catalog, mock_ollama):
    """Added in 1.1: the answer now depends on which files existed (FR-024)."""
    payload = _run(project_sufficient, test_catalog, mock_ollama)
    assert payload["sources_read"]
    assert payload["environment_only"] is False


def test_an_environment_only_project_validates_and_says_so(tmp_path, test_catalog, mock_ollama):
    """A repository with an AGENTS.md and nothing else: the case issue #16 opened."""
    (tmp_path / "AGENTS.md").write_text(
        "# AGENTS.md\n\n## Rules\n"
        "- Money is integer minor units, never a float.\n"
        "- Netting must replay deterministically from the message log.\n",
        encoding="utf-8",
    )
    payload = _run(tmp_path, test_catalog, mock_ollama)
    jsonschema.validate(payload, SCHEMA)
    assert payload["sources_read"] == ["agents"]
    assert payload["environment_only"] is True
    assert payload["data_state"] == "scarce"


def test_sources_read_names_each_kind_once(tmp_path, test_catalog, mock_ollama):
    """A monorepo would otherwise put "agents" in the payload eight times."""
    for name in ("AGENTS.md", "packages/api/AGENTS.md", "packages/web/AGENTS.md"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# A\n\n- Money is integer minor units, never a float.\n", "utf-8")

    payload = _run(tmp_path, test_catalog, mock_ollama)
    jsonschema.validate(payload, SCHEMA)
    assert payload["sources_read"] == ["agents"]


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
