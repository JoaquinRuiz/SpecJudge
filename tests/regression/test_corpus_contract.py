"""The corpus itself must stay well-formed (issue #5).

A regression corpus with a malformed or unlabelled case is worse than none: it
reports a number that nobody can trace back to an intention.
"""

from __future__ import annotations

import pytest

from specjudge.domain import LEVELS
from specjudge.rating import load_rules

from .corpus import ABSTAIN, CATEGORIES, DATA_STATES, Band, load_corpus

CASES = load_corpus()
MIN_PER_CATEGORY = 3


def test_corpus_is_not_empty():
    assert CASES


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_case_declares_a_known_category_and_state(case):
    assert case.category in CATEGORIES
    assert case.data_state in DATA_STATES


@pytest.mark.parametrize("category", CATEGORIES)
def test_every_category_is_represented(category):
    """All four categories the issue asks for, with enough cases to mean something."""
    cases = [c for c in CASES if c.category == category]
    assert len(cases) >= MIN_PER_CATEGORY, f"{category} has {len(cases)} cases"


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_rationale_explains_the_label(case):
    """Without a rationale nobody can maintain the label six months from now."""
    assert len(case.rationale) >= 40


@pytest.mark.parametrize(
    "case", [c for c in CASES if c.category == "adversarial"], ids=lambda c: c.name
)
def test_adversarial_cases_say_what_is_hidden(case):
    """The whole point of the category is the part that does not look hard."""
    assert "HIDDEN DIFFICULTY" in case.rationale or "CONTRADICTION" in case.rationale


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_dimensions_are_known_and_bands_are_ordered(case):
    rules = load_rules()
    for dim, expectation in case.dimensions.items():
        assert dim in rules.dimensions, f"{case.name}: unknown dimension '{dim}'"
        if expectation == ABSTAIN:
            continue
        assert isinstance(expectation, Band)
        if expectation.min is not None:
            assert expectation.min in LEVELS
        if expectation.max is not None:
            assert expectation.max in LEVELS
        if expectation.min is not None and expectation.max is not None:
            assert LEVELS.index(expectation.min) <= LEVELS.index(expectation.max), (
                f"{case.name}:{dim} has an inverted band"
            )


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.name)
def test_insufficient_cases_carry_no_expected_profile(case):
    """The judge never runs on them, so an expected profile would be fiction."""
    if case.data_state == "insufficient":
        assert not case.dimensions
