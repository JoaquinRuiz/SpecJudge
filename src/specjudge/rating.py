"""Rating rules: loading (data/rating-rules.yaml) and the evaluation engine.

Separates "how demanding the project is" (DemandProfile, from the judge) from "how
that translates into a per-model label" (declarative rules), for auditability
(Principle II) and evolvability (FR-017).
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml

from .domain import LEVELS, CatalogModel, DemandProfile, Evaluation, Rating, RatingRules
from .errors import CatalogError


def default_rules_path() -> Path:
    try:
        packaged = files("specjudge").joinpath("_data/rating-rules.yaml")
        if packaged.is_file():
            return Path(str(packaged))
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    return Path(__file__).resolve().parents[2] / "data" / "rating-rules.yaml"


def load_rules(path: Path | str | None = None) -> RatingRules:
    rules_path = Path(path) if path is not None else default_rules_path()
    if not rules_path.is_file():
        raise CatalogError(
            f"Rating rules not found at {rules_path}.",
            hint="Create data/rating-rules.yaml following the schema.",
        )
    try:
        raw = yaml.safe_load(rules_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CatalogError(f"Rating rules at {rules_path} are not valid YAML: {exc}") from exc

    if not isinstance(raw, dict):
        raise CatalogError(f"Rating rules at {rules_path} must be a YAML mapping.")

    dimensions = raw.get("dimensions")
    if not isinstance(dimensions, list) or not dimensions:
        raise CatalogError(f"Rating rules at {rules_path} must declare a non-empty 'dimensions'.")

    mapping = raw.get("mapping") or {}
    per_dimension = mapping.get("per_dimension") or {}
    levels = mapping.get("levels") or list(LEVELS)

    return RatingRules(
        version=int(raw.get("version", 1)),
        dimensions=[str(d) for d in dimensions],
        scarce_thresholds=raw.get("scarce_thresholds") or {},
        per_dimension={str(k): str(v) for k, v in per_dimension.items()},
        aggregation=str(mapping.get("aggregation", "worst_dimension")),
        levels=[str(x) for x in levels],
        judge=raw.get("judge") or {},
    )


def assert_dimensions_match(models: list[CatalogModel], rules: RatingRules) -> None:
    """Verify catalog and rules use the same dimension set (contract check)."""
    rule_dims = set(rules.dimensions)
    for m in models:
        model_dims = set(m.capabilities.keys())
        if model_dims != rule_dims:
            raise CatalogError(
                f"Model '{m.id}' declares dimensions {sorted(model_dims)}, which do not "
                f"match the rules {sorted(rule_dims)}."
            )


def _rating_for_diff(diff: int, per_dimension: dict[str, str]) -> Rating:
    """Translate the ordinal difference (capability - demand) into a partial Rating."""
    if diff <= -2:
        key = "below_by_2_or_more"
    elif diff == -1:
        key = "below_by_1"
    elif diff == 0:
        key = "exact"
    else:
        key = "above_by_1_or_more"
    return Rating(per_dimension.get(key, "fair"))


def evaluate_model(model: CatalogModel, demand: DemandProfile, rules: RatingRules) -> Evaluation:
    """Cross demand x capability per dimension and aggregate to the worst rating."""
    levels = rules.levels
    partials: dict[str, Rating] = {}
    deficit = 0
    excess = 0
    for dim in rules.dimensions:
        demand_level = demand.dimensions.get(dim, levels[0])
        cap_level = model.capabilities.get(dim, levels[0])
        d_idx = levels.index(demand_level) if demand_level in levels else 0
        c_idx = levels.index(cap_level) if cap_level in levels else 0
        diff = c_idx - d_idx
        deficit += max(0, -diff)
        excess += max(0, diff)
        partials[dim] = _rating_for_diff(diff, rules.per_dimension)

    if rules.aggregation == "worst_dimension":
        global_rating = min(partials.values(), key=lambda r: r.order)
    else:  # conservative fallback
        global_rating = min(partials.values(), key=lambda r: r.order)

    justification = _justify(model, demand, partials, global_rating, deficit, excess)
    return Evaluation(
        model_id=model.id,
        model_name=model.name,
        rating=global_rating,
        justification=justification,
        price=model.price,
        deficit=deficit,
        excess=excess,
        family=model.family,
        open_source=model.open_source,
    )


def _justify(
    model: CatalogModel,
    demand: DemandProfile,
    partials: dict[str, Rating],
    global_rating: Rating,
    deficit: int,
    excess: int,
) -> str:
    """Human-readable justification per model (FR-014)."""
    dim, part = min(partials.items(), key=lambda kv: kv[1].order)
    demand_level = demand.dimensions.get(dim, "?")
    cap_level = model.capabilities.get(dim, "?")
    verdict = {
        Rating.POOR: "falls well below what this project demands",
        Rating.FAIR: "falls somewhat short for this project",
        Rating.GOOD: "is a good fit for this project",
        Rating.OVERKILL: "exceeds what this project needs",
    }[global_rating]
    if deficit == 0 and excess == 0:
        fit = "Right-sized: capability matches demand exactly in every dimension."
    elif deficit == 0:
        fit = f"Capable everywhere, but {excess} step(s) more capable than needed."
    else:
        fit = f"Short by {deficit} step(s) across dimensions."
    return (
        f"{model.name} {verdict}. {fit} Deciding dimension: '{dim}' "
        f"(demand={demand_level}, capability={cap_level} -> {part.value})."
    )


def evaluate_all(
    models: list[CatalogModel], demand: DemandProfile, rules: RatingRules
) -> list[Evaluation]:
    return [evaluate_model(m, demand, rules) for m in models]
