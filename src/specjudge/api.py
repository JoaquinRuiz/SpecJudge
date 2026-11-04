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

from .domain import (
    Comparison,
    Constraint,
    DataState,
    DemandProfile,
    Envelope,
    Evaluation,
    Evidence,
    EvidenceStatus,
    ExecutionModel,
    Price,
    Rating,
    UserConfig,
)
from .errors import (
    CatalogError,
    InsufficientInfoError,
    JudgeUnavailableError,
    SpecJudgeError,
)
from .judge.client import build_client
from .judge.ollama import OllamaClient
from .pipeline import assess, prepare
from .rating import load_rules
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
    execution_model: ExecutionModel | None = None,
    judge_url: str | None = None,
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
    prepared = prepare(project_path, rules, catalog_path)

    # Local Ollama unless the caller names an OpenAI-compatible endpoint. A non-local
    # one puts a notice at the head of `warnings` (issue #4). No user config is read:
    # a library call is answered from its arguments alone.
    client = (
        build_client(UserConfig(ollama_host=host), base_url=judge_url)
        if judge_url
        else OllamaClient(host=host)
    )
    return assess(prepared, rules, client, judge_model, execution_model or rules.execution_model)


def to_dict(comparison: Comparison) -> dict:
    """The comparison as the documented JSON payload (see `json_schema`)."""
    return comparison_to_dict(comparison)


def json_schema() -> dict:
    """The JSON Schema describing `to_dict` output.

    The same document `specjudge --print-schema` emits, so a non-Python consumer
    can target the contract without importing anything.
    """
    return load_schema()
