"""The assessment, once (issue #38).

`cli.py` and `api.analyze` used to orchestrate this pipeline side by side, by hand, and
they drifted the way two copies always do: a step added to one and missed on the other,
silently. Three times, all in the same direction:

* the warning naming the context files the budget left out (0.6.1) was wired into the
  API only, so terminal users never saw it;
* `instructions_considered` (0.6.0) was never passed by the CLI, so `--json` reported
  an empty list for every project, three releases running;
* the two warning lists were assembled in different orders.

The entry points genuinely differ, so they are not merged — they are reduced to what
actually differs. The CLI reads `config.toml`, prompts for a judge, persists the choice,
renders, and maps errors to exit codes; `analyze` takes explicit arguments and reads no
user config. Both of those stay outside. Everything between "here is a project, a
catalog and a judge" and "here is a `Comparison`" lives here, and nowhere else.

Not exported from `specjudge.api`: this is the shared middle, not a third entry point.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import errors
from .artifacts import read_project
from .catalog import check_freshness, load_catalog
from .domain import (
    CatalogModel,
    Comparison,
    DataState,
    ExecutionModel,
    ProjectAnalysis,
    RatingRules,
)
from .envelope import build as build_envelope
from .envelope import envelope_warnings
from .judge.client import JudgeClient, remote_notice
from .judge.evaluator import (
    budget_warnings,
    envelope_fragments,
    estimate_demand,
    evidence_warnings,
)
from .rating import assert_dimensions_match, evaluate_all
from .recommend import build_comparison


@dataclass(frozen=True)
class Prepared:
    """A project and a catalog that have both been checked, before any judge is asked.

    Split from `assess` because the CLI has to resolve its judge in between — which
    may mean prompting the user — and a project with no tasks should fail before that
    prompt, not after the user has answered it.
    """

    analysis: ProjectAnalysis
    models: list[CatalogModel]
    catalog_warnings: list[str]


def prepare(
    project_path: str | Path, rules: RatingRules, catalog_path: str | Path | None
) -> Prepared:
    """Read the project and the catalog, refusing early on either being unusable."""
    analysis = read_project(project_path, rules)
    if analysis.data_state == DataState.INSUFFICIENT:
        raise errors.insufficient_project()

    models, catalog_warnings = load_catalog(catalog_path)
    if not models:
        raise errors.catalog_empty(str(catalog_path) if catalog_path else "data/models.yaml")
    assert_dimensions_match(models, rules)
    # Stale prices don't block a recommendation, they qualify it (FR-019).
    catalog_warnings = list(catalog_warnings) + check_freshness(models, rules.max_pricing_age_days)
    return Prepared(analysis=analysis, models=models, catalog_warnings=catalog_warnings)


def assess(
    prepared: Prepared,
    rules: RatingRules,
    client: JudgeClient,
    judge_model: str,
    execution: ExecutionModel,
) -> Comparison:
    """Ask the judge, rate the catalog, and assemble the one `Comparison` both paths return."""
    analysis = prepared.analysis

    demand = estimate_demand(analysis, rules, client, judge_model)
    # No dimension the judge could ground means no demand profile to rank against —
    # the same "not enough information" outcome as a project without tasks.
    if not demand.scored_dimensions:
        raise errors.no_supported_dimensions(judge_model)

    fragments = envelope_fragments(analysis, rules, client, judge_model)
    envelope = build_envelope(demand, fragments, execution)

    # The single place warnings are assembled. Order follows what `api.analyze`
    # emitted before the two paths were merged, since that is the semver-covered one.
    warnings = (
        list(analysis.warnings)
        + prepared.catalog_warnings
        + evidence_warnings(demand)
        + budget_warnings(analysis, rules, client, judge_model)
        + envelope_warnings(demand, execution)
    )
    # Ahead of every other warning: it is the only one about where the project's text
    # went, rather than about how good the answer is (issue #4).
    notice = remote_notice(client)
    if notice:
        warnings.insert(0, notice)

    # Ungrounded dimensions make the assessment thinner than it looks, which is
    # exactly what `scarce` communicates (FR-020).
    data_state = analysis.data_state
    if demand.unsupported_dimensions and data_state == DataState.SUFFICIENT:
        data_state = DataState.SCARCE

    return build_comparison(
        evaluate_all(prepared.models, demand, rules, envelope.default_demand),
        data_state,
        judge_model,
        warnings=warnings,
        demand=demand,
        source_kinds=analysis.source_kinds,
        environment_only=analysis.environment_only,
        envelope=envelope,
        instructions=analysis.instructions,
    )
