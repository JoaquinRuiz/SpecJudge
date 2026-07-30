"""The README's worked example must stay in step with the catalog (issue #7).

Lives in tests/contract/ on purpose: the "Catalog schema" CI job runs only this
directory, so a PR that touches nothing but `data/models.yaml` still gets told
that the README now advertises prices the catalog no longer charges.
"""

from __future__ import annotations

import re
from pathlib import Path

import render_example

from specjudge.domain import Rating

README = Path(__file__).resolve().parents[2] / "README.md"


def _readme_block() -> str:
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(render_example.BEGIN) + ".*?" + re.escape(render_example.END),
        re.DOTALL,
    )
    match = pattern.search(text)
    assert match, "README lost its generated-example markers"
    return match.group(0)


def test_readme_example_matches_the_catalog():
    """Byte-compare, so a price change cannot land without refreshing the README."""
    assert _readme_block() == render_example.render_block(), (
        "The README's worked example is out of date with data/models.yaml.\n"
        "Regenerate it: uv run python scripts/render_example.py --write"
    )


def test_readme_example_shows_an_overkill_row():
    """Done-when criterion: the example must demonstrate the overpay case."""
    assert " overkill " in _readme_block()


def test_readme_cost_figure_is_derived_from_the_catalog():
    """Recompute the headline multiple straight from the catalog, not via render_block.

    An independent path to the same number: if someone hand-edits the figure in the
    README, the byte-compare above catches it, and this says what the number should
    have been.
    """
    comparison = render_example.build_full_comparison()
    reference = render_example.reference_overkill(comparison)
    paid = render_example.cheapest_paid_fit(comparison)
    assert reference is not None and paid is not None

    expected = reference.price.output_per_million / paid.price.output_per_million
    assert f"{expected:.0f}× cheaper on output" in _readme_block()


def test_example_project_ships_with_the_repo():
    """The example input is part of the repo, so a reader can run it themselves."""
    project = render_example.EXAMPLE_PROJECT
    assert (project / "specs" / "001-task-manager" / "spec.md").is_file()
    assert (project / "specs" / "001-task-manager" / "tasks.md").is_file()
    assert (project / ".specify" / "memory" / "constitution.md").is_file()


def test_reference_overkill_is_actually_overkill():
    comparison = render_example.build_full_comparison()
    reference = render_example.reference_overkill(comparison)
    assert reference is not None
    assert reference.rating is Rating.OVERKILL
