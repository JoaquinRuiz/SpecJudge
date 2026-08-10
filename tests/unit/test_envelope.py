"""The demand as an envelope rather than a single verdict (issue #3 / FR-027).

Two failure modes are worse here than being coarse, and most of these tests are
about them:

* **inventing a range.** A judge that did not separate the bulk from the peak must
  produce one level, not an interpolated two.
* **inventing a trigger.** "Escalate for this" when the work is uniform teaches
  people to ignore the block, the same way four false gap warnings did in #11.
"""

from __future__ import annotations

import pytest

from specjudge.domain import (
    DemandProfile,
    Evidence,
    EvidenceStatus,
    ExecutionModel,
    Fragment,
)
from specjudge.envelope import build, envelope_warnings, is_hard_requirement

FRAGMENTS = [
    Fragment("S:FR-001", "spec", "**FR-001**: The export MUST reconcile before it is written."),
    Fragment("T:T002", "tasks", "T002 Add the export button to the toolbar"),
    Fragment("S:3", "spec", "The team usually reviews migrations together."),
]


def _profile(
    dimensions: dict[str, str],
    bulk: dict[str, str] | None = None,
    evidence: dict[str, str] | None = None,
) -> DemandProfile:
    cited = evidence or {}
    return DemandProfile(
        dimensions=dimensions,
        justification="because",
        judge_model="judge",
        evidence={
            dim: Evidence(status=EvidenceStatus.GROUNDED, fragment_id=frag)
            for dim, frag in cited.items()
        },
        bulk=bulk or {},
    )


# ------------------------------------------------------- hard vs customary


@pytest.mark.parametrize(
    "text",
    [
        "**FR-001**: The export MUST reconcile first.",
        "The report SHALL be signed.",
        "A downgrade path is REQUIRED.",
        "SC-002 defines the bar.",
    ],
)
def test_stated_obligations_are_hard(text):
    assert is_hard_requirement(text)


@pytest.mark.parametrize(
    "text",
    [
        "The team usually reviews migrations together.",
        "T002 Add the export button to the toolbar",
        "We must be careful here, historically.",
    ],
)
def test_habits_and_prose_are_not(text):
    """Lowercase "must" in prose is a description, not a stated requirement.

    The distinction is the whole value of the column: a reader deciding what to pay
    for needs to know which constraints the project actually committed to.
    """
    assert not is_hard_requirement(text)


# ------------------------------------------------------- building the table


def test_every_rated_dimension_becomes_a_row():
    profile = _profile({"reasoning": "high", "size": "low"}, evidence={"reasoning": "S:FR-001"})
    envelope = build(profile, FRAGMENTS, ExecutionModel.SINGLE)
    assert [c.dimension for c in envelope.constraints] == ["reasoning", "size"]


def test_a_row_carries_the_fragment_behind_it():
    profile = _profile({"reasoning": "high"}, evidence={"reasoning": "S:FR-001"})
    (row,) = build(profile, FRAGMENTS, ExecutionModel.SINGLE).constraints
    assert row.fragment_id == "S:FR-001"
    assert "MUST reconcile" in row.text
    assert row.hard is True


def test_a_dimension_with_no_citation_still_appears_without_one():
    """Dropping the row would hide a level that the ranking is using."""
    profile = _profile({"reasoning": "high"})
    (row,) = build(profile, FRAGMENTS, ExecutionModel.SINGLE).constraints
    assert row.fragment_id is None
    assert row.hard is False


def test_unsupported_dimensions_are_not_constraints():
    """They left the fit calculation; a constraint table is not where they return."""
    profile = _profile({"reasoning": "high", "size": "unsupported"})
    envelope = build(profile, FRAGMENTS, ExecutionModel.SINGLE)
    assert [c.dimension for c in envelope.constraints] == ["reasoning"]


# ------------------------------------------------------- default vs peak


def test_a_single_model_run_is_ranked_on_the_peak():
    profile = _profile({"reasoning": "top"}, bulk={"reasoning": "low"})
    envelope = build(profile, FRAGMENTS, ExecutionModel.SINGLE)
    assert envelope.default_demand == {"reasoning": "top"}
    assert envelope.peak_demand == {"reasoning": "top"}


def test_an_escalating_run_is_ranked_on_the_bulk():
    """The point of the issue: stop paying for the architecture decision 21 times."""
    profile = _profile({"reasoning": "top"}, bulk={"reasoning": "low"})
    envelope = build(profile, FRAGMENTS, ExecutionModel.ESCALATING)
    assert envelope.default_demand == {"reasoning": "low"}
    assert envelope.peak_demand == {"reasoning": "top"}


def test_a_single_model_run_never_offers_an_escalation():
    """There is nothing to escalate to when one model implements everything."""
    profile = _profile({"reasoning": "top"}, bulk={"reasoning": "low"})
    assert build(profile, FRAGMENTS, ExecutionModel.SINGLE).escalations == []


def test_escalations_name_the_dimension_that_rises():
    profile = _profile(
        {"reasoning": "top", "size": "low"},
        bulk={"reasoning": "medium", "size": "low"},
        evidence={"reasoning": "S:FR-001"},
    )
    envelope = build(profile, FRAGMENTS, ExecutionModel.ESCALATING)
    assert [c.dimension for c in envelope.escalations] == ["reasoning"]
    assert envelope.is_uniform is False


def test_uniform_work_produces_no_trigger():
    """A trigger on work that is all the same trains people to ignore the block."""
    profile = _profile({"reasoning": "medium"}, bulk={"reasoning": "medium"})
    envelope = build(profile, FRAGMENTS, ExecutionModel.ESCALATING)
    assert envelope.escalations == []
    assert envelope.is_uniform is True


def test_a_missing_bulk_degrades_to_the_peak_rather_than_being_invented():
    """The judge did not distinguish them, so neither do we (FR-027)."""
    profile = _profile({"reasoning": "top", "size": "medium"})
    envelope = build(profile, FRAGMENTS, ExecutionModel.ESCALATING)
    assert envelope.default_demand == {"reasoning": "top", "size": "medium"}
    assert envelope.escalations == []


# ------------------------------------------------------- saying so


def test_a_degraded_envelope_says_why_it_has_no_triggers():
    """ "No triggers" must not be read as "the work is uniform" (Principle IV)."""
    profile = _profile({"reasoning": "top"})
    (warning,) = envelope_warnings(profile, ExecutionModel.ESCALATING)
    assert "too small to be asked" in warning
    assert "conservative" in warning


def test_a_distinguished_profile_warns_about_nothing():
    profile = _profile({"reasoning": "top"}, bulk={"reasoning": "low"})
    assert envelope_warnings(profile, ExecutionModel.ESCALATING) == []


def test_a_single_model_run_warns_about_nothing():
    """It never asked for a bulk, so its absence is not a degradation."""
    profile = _profile({"reasoning": "top"})
    assert envelope_warnings(profile, ExecutionModel.SINGLE) == []
