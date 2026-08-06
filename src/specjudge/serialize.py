"""The machine-readable output contract (FR-022).

This lives outside `cli.py` on purpose. The payload is consumed by `--json`, by the
Python API and by anything wrapping either, so it is not the CLI's private business.

`SCHEMA_VERSION` is independent of the package version. Tying them would make the
payload appear to change on every catalog-only release, which is exactly the noise a
consumer pins a version to avoid.

Change rules, enforced by review rather than by code:

* adding a field  -> MINOR
* removing a field, changing its type, or changing what an existing value means
  -> MAJOR

0.1.x and 0.2.0 emitted this same payload without the `schema_version` field. Adding
it is additive, so a consumer written against those releases keeps working.
"""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path

from .domain import Comparison, DemandProfile

SCHEMA_VERSION = "1.0"


def schema_path() -> Path:
    """The packaged JSON Schema, falling back to the repo tree in development."""
    try:
        packaged = files("specjudge").joinpath("_schema/output.schema.json")
        if packaged.is_file():
            return Path(str(packaged))
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    return Path(__file__).resolve().parent / "_schema" / "output.schema.json"


def load_schema() -> dict:
    """The JSON Schema describing `comparison_to_dict` output."""
    return json.loads(schema_path().read_text(encoding="utf-8"))


def demand_to_dict(demand: DemandProfile | None) -> dict | None:
    """The judge's assessment and how well it was grounded.

    Null when there is no profile — the CLI always has one by the time it renders,
    but the field is nullable so a caller building a Comparison by hand is not
    forced to invent an assessment.
    """
    if demand is None:
        return None
    return {
        "dimensions": dict(demand.dimensions),
        "justification": demand.justification,
        "coverage": demand.coverage,
        "evidence": {
            dim: {
                "status": ev.status.value,
                "fragment_id": ev.fragment_id,
                "quote": ev.quote,
            }
            for dim, ev in demand.evidence.items()
        },
    }


def comparison_to_dict(comparison: Comparison) -> dict:
    """The full `--json` payload for a comparison."""
    return {
        "schema_version": SCHEMA_VERSION,
        "data_state": comparison.data_state.value,
        "judge_model": comparison.judge_model,
        "best_choice": comparison.best_choice,
        "podium": list(comparison.podium),
        "demand": demand_to_dict(comparison.demand),
        "warnings": list(comparison.warnings),
        "evaluations": [
            {
                "model_id": e.model_id,
                "model_name": e.model_name,
                "rating": e.rating.value,
                "justification": e.justification,
                "price": {
                    "input_per_million": e.price.input_per_million,
                    "output_per_million": e.price.output_per_million,
                    "currency": e.price.currency,
                    "pricing_date": e.price.pricing_date,
                },
                "price_stale": e.price_stale,
            }
            for e in comparison.evaluations
        ],
    }
