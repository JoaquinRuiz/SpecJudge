"""Catalog contract tests and dimension consistency - T014."""

from __future__ import annotations

import pytest

from specjudge.catalog import load_catalog
from specjudge.errors import CatalogError
from specjudge.rating import assert_dimensions_match, load_rules


def test_shipped_catalog_is_valid():
    models, warnings = load_catalog()
    assert models
    assert all(m.price.pricing_date for m in models), "Every price must have a date"


def test_shipped_dimensions_match_rules():
    models, _ = load_catalog()
    rules = load_rules()
    assert_dimensions_match(models, rules)  # must not raise


def test_invalid_catalog_missing_capability(tmp_path):
    bad = tmp_path / "models.yaml"
    bad.write_text(
        "version: 1\n"
        "dimensions: [reasoning, size]\n"
        "models:\n"
        "  - id: x\n"
        "    name: X\n"
        "    capabilities: {reasoning: high}\n"  # missing 'size'
        "    price: {input_per_million: 1, output_per_million: 2, currency: USD, pricing_date: 2026-01-01}\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError):
        load_catalog(bad)


def test_missing_pricing_date_warns(tmp_path):
    cat = tmp_path / "models.yaml"
    cat.write_text(
        "version: 1\n"
        "dimensions: [reasoning]\n"
        "models:\n"
        "  - id: x\n"
        "    name: X\n"
        "    capabilities: {reasoning: high}\n"
        "    price: {input_per_million: 1, output_per_million: 2, currency: USD}\n",
        encoding="utf-8",
    )
    models, warnings = load_catalog(cat)
    assert models[0].price.stale
    assert any("pricing_date" in w for w in warnings)


def test_duplicate_id_rejected(tmp_path):
    cat = tmp_path / "models.yaml"
    cat.write_text(
        "version: 1\n"
        "dimensions: [reasoning]\n"
        "models:\n"
        "  - {id: dup, name: A, capabilities: {reasoning: low}, price: {input_per_million: 1, output_per_million: 1, currency: USD, pricing_date: 2026-01-01}}\n"
        "  - {id: dup, name: B, capabilities: {reasoning: low}, price: {input_per_million: 1, output_per_million: 1, currency: USD, pricing_date: 2026-01-01}}\n",
        encoding="utf-8",
    )
    with pytest.raises(CatalogError):
        load_catalog(cat)


def test_shipped_models_declare_family_and_open_source():
    """The HTML report filters on these, so the shipped catalog must set them."""
    models, _ = load_catalog()
    missing_family = [m.id for m in models if not m.family]
    assert not missing_family, f"models without a family: {missing_family}"
    # open_source defaults to False; assert the flag is at least a real bool.
    assert all(isinstance(m.open_source, bool) for m in models)


def test_family_falls_back_to_provider_when_absent(tmp_path):
    """A catalog predating the `family` field still filters sensibly."""
    cat = tmp_path / "models.yaml"
    cat.write_text(
        "version: 1\n"
        "dimensions: [reasoning]\n"
        "models:\n"
        "  - id: x\n"
        "    name: X\n"
        "    provider: SomeVendor\n"
        "    capabilities: {reasoning: low}\n"
        "    price: {input_per_million: 1, output_per_million: 1, currency: USD, "
        "pricing_date: 2026-01-01}\n",
        encoding="utf-8",
    )
    models, _ = load_catalog(cat)
    assert models[0].family == "SomeVendor"
    assert models[0].open_source is False
