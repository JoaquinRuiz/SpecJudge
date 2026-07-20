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
from .catalog import load_catalog
from .config import DEFAULT_HOST, load_config, save_config
from .domain import Comparison, DataState, JudgePreference, UserConfig
from .judge.evaluator import estimate_demand
from .judge.ollama import OllamaClient
from .rating import assert_dimensions_match, evaluate_all, load_rules
from .recommend import build_comparison
from .render.html import open_in_browser
from .render.table import render_comparison

app = typer.Typer(
    add_completion=False,
    help="Recommend the AI model that best fits your SDD project's complexity.",
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"specjudge {__version__}")
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


def _comparison_to_dict(comparison: Comparison) -> dict:
    return {
        "data_state": comparison.data_state.value,
        "judge_model": comparison.judge_model,
        "best_choice": comparison.best_choice,
        "podium": comparison.podium,
        "warnings": comparison.warnings,
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


@app.command()
def main(
    project_path: Path = typer.Argument(
        Path("."), help="Root of the SDD project to analyze."
    ),
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
    as_json: bool = typer.Option(
        False, "--json", help="Emit the result as JSON on stdout."
    ),
    no_color: bool = typer.Option(
        False, "--no-color", help="Disable color/highlighting."
    ),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True,
        help="Show the version and exit."
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

    # 3. Resolve the local judge (critical dependency).
    config = load_config()
    client = OllamaClient(host=config.ollama_host or DEFAULT_HOST)
    interactive = sys.stdin.isatty()
    judge_model, config = resolve_judge(
        config, client, forced_judge=judge, set_judge=set_judge, interactive=interactive
    )

    # 4. Estimate demand and rate the catalog.
    demand = estimate_demand(analysis, rules, client, judge_model)
    evaluations = evaluate_all(models, demand, rules)

    warnings = list(analysis.warnings) + list(catalog_warnings)
    comparison = build_comparison(
        evaluations, analysis.data_state, judge_model, warnings=warnings
    )

    # 5. Output.
    if as_json:
        typer.echo(json.dumps(_comparison_to_dict(comparison), ensure_ascii=False, indent=2))
    else:
        render_comparison(comparison, no_color=no_color)

    if open_browser:
        out = open_in_browser(comparison)
        if not as_json:
            typer.echo(f"\nHTML matrix: {out}")


if __name__ == "__main__":
    app()
