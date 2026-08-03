"""Frozen rankings, so a rules edit cannot change a verdict unnoticed (issue #5).

For a fixed demand profile and a fixed catalog the whole ranking is deterministic.
Snapshotting it turns any edit to `data/rating-rules.yaml` into a readable diff:
the question stops being "did I break something?" and becomes "is this the change
I meant?".

Deliberately snapshotted against `tests/fixtures/catalog-test.yaml`, not the
shipped catalog. The shipped one changes every few weeks through community price
PRs; a golden over it would break on every one of them, and contributors would
learn to regenerate the snapshot without reading it — which is how a regression
test quietly stops testing anything.

To regenerate after an intended rules change:

    uv run python -m pytest tests/regression/test_rules_golden.py --snapshot-update
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specjudge.catalog import load_catalog
from specjudge.domain import DataState, DemandProfile
from specjudge.rating import evaluate_all, load_rules
from specjudge.recommend import build_comparison

SNAPSHOT = Path(__file__).parent / "__snapshots__" / "rankings.json"
CATALOG = Path(__file__).resolve().parents[1] / "fixtures" / "catalog-test.yaml"

# Profiles chosen to exercise the whole ladder: one per level, plus a mixed one
# where dimensions disagree and `worst_dimension` has to arbitrate.
PROFILES: dict[str, dict[str, str]] = {
    "all_low": {"reasoning": "low", "size": "low", "domain_specialization": "low"},
    "all_medium": {"reasoning": "medium", "size": "medium", "domain_specialization": "medium"},
    "all_top": {"reasoning": "top", "size": "top", "domain_specialization": "top"},
    "mixed_high_reasoning": {
        "reasoning": "high",
        "size": "low",
        "domain_specialization": "medium",
    },
}


def _ranking(dimensions: dict[str, str]) -> dict:
    models, _ = load_catalog(CATALOG)
    rules = load_rules()
    demand = DemandProfile(dimensions=dimensions, justification="fixed", judge_model="fixed")
    comparison = build_comparison(
        evaluate_all(models, demand, rules), DataState.SUFFICIENT, "fixed", demand=demand
    )
    return {
        "best_choice": comparison.best_choice,
        "podium": comparison.podium,
        "order": [e.model_id for e in comparison.evaluations],
        "ratings": {e.model_id: e.rating.value for e in comparison.evaluations},
        "fit": {e.model_id: [e.deficit, e.excess] for e in comparison.evaluations},
    }


def _current() -> dict:
    return {name: _ranking(dims) for name, dims in PROFILES.items()}


def test_rankings_match_the_snapshot(request):
    current = _current()

    if request.config.getoption("--snapshot-update"):
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_text(json.dumps(current, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        pytest.skip("snapshot updated")

    assert SNAPSHOT.is_file(), (
        f"No snapshot at {SNAPSHOT}. Create it with:\n"
        "  uv run python -m pytest tests/regression/test_rules_golden.py --snapshot-update"
    )
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert current == expected, (
        "The rating rules now produce a different ranking.\n"
        "If that is the change you meant, regenerate the snapshot:\n"
        "  uv run python -m pytest tests/regression/test_rules_golden.py --snapshot-update"
    )


def test_snapshot_covers_every_profile():
    """A profile silently dropped from the snapshot stops being protected."""
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert set(expected) == set(PROFILES)


def test_demanding_profiles_rule_out_the_weakest_model():
    """A sanity check independent of the snapshot, so a bad regeneration is caught.

    If someone regenerates the golden after breaking the rules, the file agrees
    with the code and proves nothing. This asserts a property that must hold
    whatever the rules say.
    """
    top = _ranking(PROFILES["all_top"])
    low = _ranking(PROFILES["all_low"])
    assert top["ratings"]["budget-small"] == "poor"
    assert low["ratings"]["budget-small"] in ("good", "overkill")
