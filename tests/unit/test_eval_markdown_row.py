"""The pasteable result row from the evaluation harness (issue #23).

Contributed numbers are only worth having if they are comparable, and a row a human
transcribed out of a report is not: people round, drop the denominator, or quote the
per-case line that happens to look best. The script emits the row, so every one of
them is computed the same way.
"""

from __future__ import annotations

import eval_judge
from eval_judge import Outcome, markdown_row


def _row(outcomes: list[Outcome], judge: str = "some:8b", params: float | None = 8.0) -> str:
    return markdown_row(outcomes, judge, params)


def test_a_clean_run_reports_a_full_score():
    row = _row([Outcome("a", "thin", hits=3), Outcome("b", "well_specified", hits=2)])
    assert row == "| `some:8b` | 8B | 5/5 (100%) | 0 | 0 |"


def test_misses_carry_their_ordinal_distance():
    outcomes = [Outcome("a", "thin", hits=2, misses=["size=top (expected <= low)"], distance=2)]
    assert "2/3 (67%)" in _row(outcomes)
    assert "2 steps" in _row(outcomes)


def test_refused_answers_are_counted_and_not_graded():
    """An answer SpecJudge rejects is a different failure from a wrong level.

    It has to survive into the table: it is the number that tells a reader what a
    small judge actually does when it cannot cope.
    """
    outcomes = [Outcome("a", "thin", hits=2), Outcome("b", "thin", error="unusable")]
    row = _row(outcomes)
    assert "2/2 (100%)" in row
    assert row.endswith("| 1 |")


def test_cases_refused_before_the_judge_are_not_failures():
    """The corpus contains projects SpecJudge must refuse; that is the pass condition."""
    outcomes = [Outcome("a", "thin", hits=1), Outcome("b", "insufficient", refused=True)]
    assert _row(outcomes) == "| `some:8b` | 8B | 1/1 (100%) | 0 | 0 |"


def test_an_unknown_parameter_count_is_admitted_not_invented():
    assert "| ? |" in _row([Outcome("a", "thin", hits=1)], params=None)


def test_a_run_with_nothing_graded_says_so():
    """Every dimension abstained on: a real outcome, and 0/0 would read as a score."""
    outcomes = [Outcome("a", "thin", over_abstention=["reasoning"])]
    assert "not graded" in _row(outcomes)


def test_the_row_matches_the_table_it_is_pasted_into():
    """Same column count as docs/judges.md, or the table breaks on merge."""
    from pathlib import Path

    guide = Path(eval_judge.REPO_ROOT / "docs" / "judges.md").read_text(encoding="utf-8")
    header = next(line for line in guide.splitlines() if line.startswith("| Judge |"))
    row = _row([Outcome("a", "thin", hits=1)])
    assert row.count("|") == header.count("|")
