"""Detecting what a project is missing, concretely (issue #11 / FR-023).

Each signal is pinned on its own, and — just as important — the well-specified end
is pinned too. A gap detector that fires on a good project trains people to ignore
it, which would leave the tool worse off than the vague warning it replaced.
"""

from __future__ import annotations

import pytest

from specjudge.domain import DataState, ProjectAnalysis, RatingRules, SDDArtifact
from specjudge.gaps import find_gaps


def _rules(**thresholds) -> RatingRules:
    return RatingRules(
        version=1,
        dimensions=["reasoning", "size", "domain_specialization"],
        scarce_thresholds={"min_detailed_tasks": 3, **thresholds},
        per_dimension={"exact": "good"},
        aggregation="worst_dimension",
    )


def _analysis(constitution: str = "", spec: str = "", tasks: str = "") -> ProjectAnalysis:
    return ProjectAnalysis(
        artifacts=[
            SDDArtifact("constitution", "c.md", bool(constitution), True, constitution),
            SDDArtifact("spec", "s.md", bool(spec), True, spec),
            SDDArtifact("tasks", "t.md", bool(tasks), True, tasks),
        ],
        data_state=DataState.SCARCE,
    )


def _codes(analysis: ProjectAnalysis, rules: RatingRules | None = None) -> set[str]:
    return {g.code for g in find_gaps(analysis, rules or _rules())}


# A project that should trip nothing.
_GOOD_SPEC = (
    "# Feature Specification: Thing\n\n## Summary\n"
    + "A well described feature with real scope and explicit boundaries. " * 8
    + "\n\n## Requirements\n- **FR-001**: It must do the thing.\n"
    "- **FR-002**: It must not do the other thing.\n\n"
    "## Success Criteria\n- **SC-001**: The thing happens in under a second.\n"
)
_GOOD_TASKS = (
    "# Tasks\n"
    "- [ ] T001 Implement the thing in src/thing.py\n"
    "- [ ] T002 Add tests in tests/test_thing.py\n"
    "- [ ] T003 Wire the entrypoint in src/cli.py\n"
)
_GOOD_CONSTITUTION = "# Constitution\n\n## I. Simplicity\nKeep it simple.\n"


# ------------------------------------------------------------------ no gaps


def test_a_well_defined_project_trips_nothing():
    assert _codes(_analysis(_GOOD_CONSTITUTION, _GOOD_SPEC, _GOOD_TASKS)) == set()


@pytest.mark.parametrize("name", ["well-crud-blog", "well-payment-ledger", "well-cli-linter"])
def test_no_false_positives_on_the_corpus_requirements(name):
    """The corpus' well-specified projects must not be told their specs are thin.

    They may legitimately lack acceptance criteria — that is a real finding, not a
    false positive — but they must never be accused of having no requirements or
    of being too short to read.
    """
    from pathlib import Path

    from specjudge.artifacts import read_project
    from specjudge.rating import load_rules

    project = Path(__file__).resolve().parents[1] / "fixtures" / "corpus" / name
    rules = load_rules()
    codes = {g.code for g in find_gaps(read_project(project, rules), rules)}
    assert "no_requirements" not in codes
    assert "spec_too_short" not in codes
    assert "no_spec" not in codes


# ------------------------------------------------------------ single signals


def test_a_missing_spec_is_the_first_thing_reported():
    gaps = find_gaps(_analysis(_GOOD_CONSTITUTION, "", _GOOD_TASKS), _rules())
    assert gaps[0].code == "no_spec"


def test_a_spec_without_numbered_requirements():
    spec = _GOOD_SPEC.replace("**FR-001**", "one").replace("**FR-002**", "two")
    assert "no_requirements" in _codes(_analysis(_GOOD_CONSTITUTION, spec, _GOOD_TASKS))


def test_a_spec_without_acceptance_criteria():
    spec = _GOOD_SPEC.replace("**SC-001**", "it is fast")
    assert "no_acceptance_criteria" in _codes(_analysis(_GOOD_CONSTITUTION, spec, _GOOD_TASKS))


def test_alternative_criterion_prefixes_count():
    """NFR-NNN is as good as SC-NNN; only inventing a third convention trips this."""
    spec = _GOOD_SPEC.replace("SC-001", "NFR-001")
    assert "no_acceptance_criteria" not in _codes(_analysis(_GOOD_CONSTITUTION, spec, _GOOD_TASKS))


def test_a_one_paragraph_spec_is_too_short():
    codes = _codes(_analysis(_GOOD_CONSTITUTION, "# Spec\n\nShow some charts.\n", _GOOD_TASKS))
    assert "spec_too_short" in codes


def test_the_length_threshold_comes_from_the_rules():
    short = _analysis(_GOOD_CONSTITUTION, "# Spec\n\nFR-001 SC-001 short.\n", _GOOD_TASKS)
    assert "spec_too_short" in _codes(short, _rules(min_spec_chars=400))
    assert "spec_too_short" not in _codes(short, _rules(min_spec_chars=10))


def test_an_invalid_length_threshold_falls_back_to_the_default():
    short = _analysis(_GOOD_CONSTITUTION, "# Spec\n\nFR-001 SC-001 short.\n", _GOOD_TASKS)
    for bad in ("not-a-number", 0, -5):
        assert "spec_too_short" in _codes(short, _rules(min_spec_chars=bad))


def test_tasks_that_never_say_where_the_work_lands():
    tasks = "# Tasks\n- [ ] T001 Build the thing\n- [ ] T002 Test it\n- [ ] T003 Ship it\n"
    assert "tasks_without_location" in _codes(_analysis(_GOOD_CONSTITUTION, _GOOD_SPEC, tasks))


def test_tasks_naming_files_do_not_trip_it():
    assert "tasks_without_location" not in _codes(
        _analysis(_GOOD_CONSTITUTION, _GOOD_SPEC, _GOOD_TASKS)
    )


def test_a_missing_constitution():
    assert "no_constitution" in _codes(_analysis("", _GOOD_SPEC, _GOOD_TASKS))


# --------------------------------------------------------------- phrasing


def test_every_gap_says_what_to_do_about_it():
    gaps = find_gaps(_analysis("", "# Spec\n\nShort.\n", "# Tasks\n- [ ] T001 Do it\n"), _rules())
    assert gaps
    for gap in gaps:
        assert gap.what and gap.fix
        assert gap.render() == f"{gap.what} — {gap.fix}"


@pytest.mark.parametrize(
    ("code", "expected"),
    [("no_requirements", "FR-NNN"), ("no_acceptance_criteria", "SC-NNN")],
)
def test_convention_based_gaps_say_what_they_looked_for(code, expected):
    """Otherwise a project numbering its criteria differently is simply accused.

    Naming the pattern lets a user dismiss a false positive in a second instead of
    doubting work they actually did.
    """
    gaps = find_gaps(_analysis("", "# Spec\n\nProse only, no identifiers.\n", ""), _rules())
    (gap,) = [g for g in gaps if g.code == code]
    assert expected in gap.what
