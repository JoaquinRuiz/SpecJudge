"""The public Python API (FR-022).

Everything exported here is covered by semantic versioning. Everything else under
`specjudge.*` is internal and may change in any release, including patch ones.

    from specjudge import api

    comparison = api.analyze("path/to/project", judge_model="llama3.1:8b")
    print(comparison.best_choice)
    payload = api.to_dict(comparison)

Deliberately small. A wide surface is a wide promise, and the useful thing to
promise is the result, not the machinery that produced it — the pipeline internals
are where this project actually iterates.

Like the CLI, `analyze` needs Ollama with a local model: the assessment comes from
a judge running on your machine, not from a bundled heuristic. It raises the same
typed errors the CLI turns into exit codes, so a caller can distinguish "not enough
project" from "no judge available" without parsing strings.
"""

from __future__ import annotations

from pathlib import Path

from .artifacts import read_project
from .catalog import check_freshness, load_catalog
from .domain import (
    Comparison,
    DataState,
    DemandProfile,
    Evaluation,
    Evidence,
    EvidenceStatus,
    Price,
    Rating,
)
from .errors import (
    CatalogError,
    InsufficientInfoError,
    JudgeUnavailableError,
    SpecJudgeError,
    catalog_empty,
    insufficient_project,
    no_supported_dimensions,
)
from .judge.evaluator import estimate_demand, evidence_warnings
from .judge.ollama import OllamaClient
from .rating import assert_dimensions_match, evaluate_all, load_rules
from .recommend import build_comparison
from .serialize import SCHEMA_VERSION, comparison_to_dict, load_schema

__all__ = [
    # Entry point
    "analyze",
    # Serialisation
    "SCHEMA_VERSION",
    "to_dict",
    "json_schema",
    # Result types (read-only data)
    "Comparison",
    "DataState",
    "DemandProfile",
    "Evaluation",
    "Evidence",
    "EvidenceStatus",
    "Price",
    "Rating",
    # Errors, each carrying the CLI's exit code
    "SpecJudgeError",
    "CatalogError",
    "InsufficientInfoError",
    "JudgeUnavailableError",
]

DEFAULT_HOST = "http://localhost:11434"


def analyze(
    project_path: str | Path,
    *,
    judge_model: str,
    catalog_path: str | Path | None = None,
    rules_path: str | Path | None = None,
    host: str = DEFAULT_HOST,
) -> Comparison:
    """Analyse an SDD project and return the model comparison.

    The same pipeline the CLI runs, minus rendering and minus the interactive judge
    picker: `judge_model` is required here, because a library has no terminal to
    ask in.

    Raises:
        InsufficientInfoError: the project has no tasks to evaluate, or the judge
            could not ground a single dimension (exit code 2).
        JudgeUnavailableError: Ollama is missing, too old, has no models, or
            answered unusably (exit code 3).
        CatalogError: the catalog is missing, empty or malformed (exit code 4).
    """
    rules = load_rules(rules_path)

    analysis = read_project(project_path, rules)
    if analysis.data_state == DataState.INSUFFICIENT:
        raise insufficient_project()

    models, catalog_warnings = load_catalog(catalog_path)
    if not models:
        raise catalog_empty(str(catalog_path) if catalog_path else "data/models.yaml")
    assert_dimensions_match(models, rules)
    catalog_warnings = catalog_warnings + check_freshness(models, rules.max_pricing_age_days)

    client = OllamaClient(host=host)
    demand = estimate_demand(analysis, rules, client, judge_model)
    if not demand.scored_dimensions:
        raise no_supported_dimensions(judge_model)

    warnings = list(analysis.warnings) + catalog_warnings + evidence_warnings(demand)
    data_state = analysis.data_state
    if demand.unsupported_dimensions and data_state == DataState.SUFFICIENT:
        data_state = DataState.SCARCE

    return build_comparison(
        evaluate_all(models, demand, rules),
        data_state,
        judge_model,
        warnings=warnings,
        demand=demand,
        source_kinds=analysis.source_kinds,
        environment_only=analysis.environment_only,
    )


def to_dict(comparison: Comparison) -> dict:
    """The comparison as the documented JSON payload (see `json_schema`)."""
    return comparison_to_dict(comparison)


def json_schema() -> dict:
    """The JSON Schema describing `to_dict` output.

    The same document `specjudge --print-schema` emits, so a non-Python consumer
    can target the contract without importing anything.
    """
    return load_schema()
