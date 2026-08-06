"""SpecJudge command-line interface (contracts/cli.md).

Orchestrates the flow: read artifacts -> classify state -> resolve local judge ->
estimate demand -> rate the catalog -> recommend -> render. Degradation is explicit,
with distinct exit codes (Principle IV).
"""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import typer

from . import __version__, errors
from .artifacts import read_project
from .catalog import check_freshness, load_catalog
from .config import DEFAULT_HOST, load_config, save_config
from .domain import DataState, JudgePreference, UserConfig
from .gaps import find_gaps
from .judge.evaluator import estimate_demand, evidence_warnings
from .judge.ollama import OllamaClient
from .rating import assert_dimensions_match, evaluate_all, load_rules
from .recommend import build_comparison
from .render.html import open_in_browser
from .render.table import render_comparison
from .serialize import comparison_to_dict, load_schema

app = typer.Typer(
    add_completion=False,
    help="Recommend the AI model that best fits your SDD project's complexity.",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"specjudge {__version__}")
        raise typer.Exit()


def _print_schema_callback(value: bool) -> None:
    """Emit the output contract so a non-Python consumer can target it (FR-022)."""
    if value:
        typer.echo(json.dumps(load_schema(), indent=2))
        raise typer.Exit()


def resolve_judge(
    config: UserConfig,
    client: OllamaClient,
    *,
    forced_judge: str | None,
    set_judge: bool,
    interactive: bool,
) -> tuple[str, UserConfig]:
    """Determine the judge model (FR-012/013). May raise JudgeUnavailableError."""
    # 1. --judge forces the model for this run (not persisted).
    if forced_judge:
        client.ensure_available(forced_judge)
        return forced_judge, config

    # 2. Valid saved preference (unless --set-judge is requested).
    if not set_judge and config.judge_preference is not None:
        wanted = config.judge_preference.judge_model
        models = client.list_models()
        if not models:
            raise errors.ollama_no_models(client.host)
        if wanted in models:
            return wanted, config
        # Preference points at an uninstalled model: re-select.
        if not interactive:
            raise errors.selected_model_missing(wanted)

    # 3. Interactive selection on first run or --set-judge.
    models = client.ensure_available()
    if not interactive:
        raise errors.JudgeUnavailableError(
            "No judge model is configured and the session is not interactive.",
            hint="Run again in an interactive terminal, or use --judge <model>.",
        )
    chosen = _prompt_judge_selection(models)
    new_config = dataclasses.replace(
        config, judge_preference=JudgePreference(judge_model=chosen, chosen_at=None)
    )
    save_config(new_config)
    return chosen, new_config


def _prompt_judge_selection(models: list[str]) -> str:
    typer.echo("Local models available to act as judge:")
    for i, m in enumerate(models, start=1):
        typer.echo(f"  {i}. {m}")
    while True:
        raw = typer.prompt("Pick the number of the judge model")
        try:
            idx = int(raw)
            if 1 <= idx <= len(models):
                return models[idx - 1]
        except ValueError:
            pass
        typer.echo("Invalid selection, please try again.")


@app.command()
def main(
    project_path: Path = typer.Argument(Path("."), help="Root of the SDD project to analyze."),
    open_browser: bool = typer.Option(
        False, "--open", "-o", help="Also open the HTML matrix in your browser."
    ),
    judge: str | None = typer.Option(
        None, "--judge", help="Force the judge model for this run (not persisted)."
    ),
    set_judge: bool = typer.Option(
        False, "--set-judge", help="Re-run judge selection and save it."
    ),
    catalog: Path | None = typer.Option(
        None, "--catalog", help="Alternative model catalog (YAML)."
    ),
    as_json: bool = typer.Option(False, "--json", help="Emit the result as JSON on stdout."),
    no_color: bool = typer.Option(False, "--no-color", help="Disable color/highlighting."),
    print_schema: bool = typer.Option(
        False,
        "--print-schema",
        callback=_print_schema_callback,
        is_eager=True,
        help="Print the JSON Schema of the --json output and exit.",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        callback=_version_callback,
        is_eager=True,
        help="Show the version and exit.",
    ),
) -> None:
    """Analyze the project and show the model comparison."""
    try:
        _run(project_path, open_browser, judge, set_judge, catalog, as_json, no_color)
    except errors.SpecJudgeError as exc:
        typer.echo(exc.render(), err=True)
        raise typer.Exit(code=exc.exit_code) from exc


def _run(
    project_path: Path,
    open_browser: bool,
    judge: str | None,
    set_judge: bool,
    catalog: Path | None,
    as_json: bool,
    no_color: bool,
) -> None:
    rules = load_rules()

    # 1. Read and classify the artifacts.
    analysis = read_project(project_path, rules)
    if analysis.data_state == DataState.INSUFFICIENT:
        raise errors.insufficient_project()

    # 2. Load and validate the catalog.
    models, catalog_warnings = load_catalog(catalog)
    if not models:
        raise errors.catalog_empty(str(catalog) if catalog else "data/models.yaml")
    assert_dimensions_match(models, rules)
    # Stale prices don't block a recommendation, they qualify it (FR-019).
    catalog_warnings += check_freshness(models, rules.max_pricing_age_days)

    # 3. Resolve the local judge (critical dependency).
    config = load_config()
    client = OllamaClient(host=config.ollama_host or DEFAULT_HOST)
    interactive = sys.stdin.isatty()
    judge_model, config = resolve_judge(
        config, client, forced_judge=judge, set_judge=set_judge, interactive=interactive
    )

    # 4. Estimate demand and rate the catalog.
    demand = estimate_demand(analysis, rules, client, judge_model)

    # No dimension the judge could ground means no demand profile to rank against.
    # That is the same "not enough information" outcome as a project without tasks.
    if not demand.scored_dimensions:
        raise errors.no_supported_dimensions(judge_model)

    evaluations = evaluate_all(models, demand, rules)

    warnings = list(analysis.warnings) + list(catalog_warnings) + evidence_warnings(demand)
    # Ungrounded dimensions make the assessment thinner than it looks, which is
    # exactly what `scarce` communicates (FR-020).
    data_state = analysis.data_state
    if demand.unsupported_dimensions and data_state == DataState.SUFFICIENT:
        data_state = DataState.SCARCE

    comparison = build_comparison(
        evaluations, data_state, judge_model, warnings=warnings, demand=demand
    )

    # 5. Output.
    # Gaps are a presentation concern for a thin project, so they are computed here
    # and passed to the renderers rather than added to Comparison: the JSON contract
    # is frozen at 1.0 (FR-022) and this issue is about how the caveat lands, not
    # about what the payload carries.
    gaps = find_gaps(analysis, rules) if data_state == DataState.SCARCE else []

    if as_json:
        typer.echo(json.dumps(comparison_to_dict(comparison), ensure_ascii=False, indent=2))
    else:
        render_comparison(comparison, no_color=no_color, gaps=gaps)

    if open_browser:
        out = open_in_browser(comparison, gaps=gaps)
        if not as_json:
            typer.echo(f"\nHTML matrix: {out}")


if __name__ == "__main__":
    app()
