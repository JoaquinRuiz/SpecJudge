"""Builds the comparison and designates the best-fitting model.

Rule FR-008: pick the model that best MATCHES the project's complexity — neither
under-capable nor more capable than needed. Price is NOT a factor in the choice:

  1. discard models that are under-capable in any dimension (deficit > 0);
  2. among the rest, pick the smallest excess capability (excess == 0 is a
     perfect fit; larger excess means an over-powered model);
  3. if every model is under-capable, designate none and warn.

Price is still shown for every model, but it never overrides fit. It only breaks
ties between models whose fit is *identical*, so a cheaper model can never win
over a better-fitting one.
"""

from __future__ import annotations

from .domain import Comparison, DataState, Evaluation


def _fit_key(e: Evaluation) -> tuple[int, int, tuple[float, float], str]:
    """Ordering key: most optimal first.

    Fit dominates (deficit, then excess). Price and model_id only disambiguate
    models that fit the project equally well.
    """
    return (e.deficit, e.excess, e.price.sort_key, e.model_id)


PODIUM_SIZE = 3


def choose_podium(evaluations: list[Evaluation], size: int = PODIUM_SIZE) -> list[str]:
    """The best-fitting models, gold first (FR-008).

    Only capable models are eligible — a model that cannot do the job does not
    belong on the podium even if nothing else is left. So the podium is shorter
    than `size` when fewer models qualify, and empty when none does.
    """
    capable = sorted((e for e in evaluations if e.fits), key=_fit_key)
    return [e.model_id for e in capable[:size]]


def choose_best(evaluations: list[Evaluation]) -> str | None:
    """The single best-fitting model — the gold medal (FR-008)."""
    podium = choose_podium(evaluations, size=1)
    return podium[0] if podium else None


def build_comparison(
    evaluations: list[Evaluation],
    data_state: DataState,
    judge_model: str | None,
    warnings: list[str] | None = None,
) -> Comparison:
    warnings = list(warnings or [])
    podium = choose_podium(evaluations)
    if not podium and evaluations:
        warnings.append(
            "No model in the catalog is capable enough for this project in every "
            "dimension; no best option is designated."
        )

    ordered = sorted(evaluations, key=_fit_key)

    return Comparison(
        evaluations=ordered,
        data_state=data_state,
        judge_model=judge_model,
        best_choice=podium[0] if podium else None,
        warnings=warnings,
        podium=podium,
    )
