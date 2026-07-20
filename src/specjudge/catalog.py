"""Loading and validation of the model catalog (data/models.yaml).

The catalog is the community-editable reference source (FR-017/FR-018). A schema
error produces an actionable message pointing at file/model/field.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

import yaml

from .domain import LEVELS, CatalogModel, Price
from .errors import CatalogError


def default_catalog_path() -> Path:
    """Path to the catalog shipped with the distribution, falling back to the repo."""
    try:
        packaged = files("specjudge").joinpath("_data/models.yaml")
        if packaged.is_file():
            return Path(str(packaged))
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    # Fallback: running from the repository tree (development).
    return Path(__file__).resolve().parents[2] / "data" / "models.yaml"


def _require(cond: bool, msg: str) -> None:
    if not cond:
        raise CatalogError(msg)


def load_catalog(path: Path | str | None = None) -> tuple[list[CatalogModel], list[str]]:
    """Load and validate the catalog.

    Returns (models, warnings). Raises CatalogError if the file is missing or invalid.
    A catalog with an empty model list is considered valid here; the "empty catalog"
    degradation (exit 4) is decided by the orchestration layer.
    """
    catalog_path = Path(path) if path is not None else default_catalog_path()
    if not catalog_path.is_file():
        raise CatalogError(
            f"Model catalog not found at {catalog_path}.",
            hint="Create data/models.yaml following the catalog schema.",
        )

    try:
        raw = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CatalogError(f"Catalog {catalog_path} is not valid YAML: {exc}") from exc

    _require(isinstance(raw, dict), f"Catalog {catalog_path} must be a YAML mapping.")
    _require("version" in raw, f"Catalog {catalog_path} does not declare 'version'.")

    dimensions = raw.get("dimensions")
    _require(
        isinstance(dimensions, list) and len(dimensions) > 0,
        f"Catalog {catalog_path} must declare a non-empty 'dimensions' list.",
    )

    models_raw = raw.get("models")
    _require(
        isinstance(models_raw, list),
        f"Catalog {catalog_path} must declare a 'models' list.",
    )

    warnings: list[str] = []
    models: list[CatalogModel] = []
    seen_ids: set[str] = set()

    for idx, m in enumerate(models_raw):
        where = f"models[{idx}]"
        _require(isinstance(m, dict), f"{where} must be a mapping.")
        mid = m.get("id")
        _require(bool(mid), f"{where} has no 'id'.")
        _require(mid not in seen_ids, f"duplicate model id: '{mid}'.")
        seen_ids.add(mid)

        name = m.get("name")
        _require(bool(name), f"Model '{mid}' has no 'name'.")

        caps = m.get("capabilities")
        _require(isinstance(caps, dict), f"Model '{mid}' has no 'capabilities'.")
        for dim in dimensions:
            _require(
                dim in caps,
                f"Model '{mid}' does not declare a capability for dimension '{dim}'.",
            )
            _require(
                caps[dim] in LEVELS,
                f"Model '{mid}' has an invalid level for '{dim}': "
                f"'{caps[dim]}' (valid: {', '.join(LEVELS)}).",
            )

        price_raw = m.get("price")
        _require(isinstance(price_raw, dict), f"Model '{mid}' has no 'price'.")
        for field_name in ("input_per_million", "output_per_million", "currency"):
            _require(
                field_name in price_raw,
                f"Price of model '{mid}' has no '{field_name}'.",
            )

        pricing_date = price_raw.get("pricing_date")
        if pricing_date is not None:
            pricing_date = str(pricing_date)
        else:
            warnings.append(
                f"Model '{mid}' has no 'pricing_date': price freshness is not verifiable."
            )

        price = Price(
            input_per_million=float(price_raw["input_per_million"]),
            output_per_million=float(price_raw["output_per_million"]),
            currency=str(price_raw["currency"]),
            pricing_date=pricing_date,
        )

        models.append(
            CatalogModel(
                id=str(mid),
                name=str(name),
                capabilities={d: str(caps[d]) for d in dimensions},
                price=price,
                provider=m.get("provider"),
                notes=m.get("notes"),
            )
        )

    return models, warnings
