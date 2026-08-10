"""Evaluate a real judge against the corpus (issue #5, live tier).

    uv run python scripts/eval_judge.py --judge llama3.1:8b
    uv run python scripts/eval_judge.py --judge llama3.1:8b --json report.json

This is the half of the regression suite that CI cannot run: measuring whether a
prompt change improved the *judgement* needs a real model, and CI has no Ollama.
The deterministic half lives in `tests/regression/` and runs on every PR — but a
green CI says the contract held, not that the judge got better. Only this does.

Two numbers, reported separately because they fail in opposite directions:

* **Accuracy** — did the level land inside the band the corpus expects? Reported
  as ordinal distance, plus the thing a user actually notices: whether the
  recommended model changed.
* **Abstention quality** — a 2x2 of should-answer/should-abstain against
  answered/abstained. `unsupported` is an easy way out, and a judge that abstains
  on everything would look flawless on accuracy alone while being useless.

Reproducible on one machine: sampling is pinned (see JUDGE_OPTIONS), but a
different Ollama release, quantisation or context size can still move answers.
Compare runs against your own baseline, not against someone else's numbers.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tests"))

from regression.corpus import ABSTAIN, Band, Case, load_corpus  # noqa: E402

from specjudge.artifacts import read_project  # noqa: E402
from specjudge.domain import UNSUPPORTED, DataState  # noqa: E402
from specjudge.errors import SpecJudgeError  # noqa: E402
from specjudge.judge.evaluator import estimate_demand  # noqa: E402
from specjudge.judge.ollama import OllamaClient  # noqa: E402
from specjudge.rating import load_rules  # noqa: E402


@dataclass
class Outcome:
    case: str
    category: str
    # Accuracy, per dimension that the corpus put a band on.
    hits: int = 0
    misses: list[str] = field(default_factory=list)
    distance: int = 0
    # Abstention, per dimension the corpus has an opinion about.
    correct_answer: int = 0
    correct_abstention: int = 0
    # Bulk accuracy, reported apart from the peak: a judge can be right about how
    # hard the hardest part is and wrong about how much of the work is like it.
    bulk_hits: int = 0
    bulk_misses: list[str] = field(default_factory=list)
    bulk_undistinguished: bool = False
    over_abstention: list[str] = field(default_factory=list)
    over_confidence: list[str] = field(default_factory=list)
    refused: bool = False
    error: str | None = None


def _evaluate(case: Case, client: OllamaClient, judge: str) -> Outcome:
    rules = load_rules()
    outcome = Outcome(case=case.name, category=case.category)

    analysis = read_project(case.path, rules)
    if analysis.data_state == DataState.INSUFFICIENT:
        outcome.refused = True
        return outcome

    try:
        demand = estimate_demand(analysis, rules, client, judge)
    except SpecJudgeError as exc:
        outcome.error = exc.message
        return outcome

    levels = rules.levels
    for dim, expectation in case.dimensions.items():
        answered = demand.dimensions.get(dim, UNSUPPORTED)
        abstained = answered == UNSUPPORTED

        if expectation == ABSTAIN:
            if abstained:
                outcome.correct_abstention += 1
            else:
                outcome.over_confidence.append(f"{dim}={answered}")
            continue

        assert isinstance(expectation, Band)
        if abstained:
            outcome.over_abstention.append(dim)
            continue

        outcome.correct_answer += 1
        if expectation.contains(answered, levels):
            outcome.hits += 1
        else:
            outcome.misses.append(f"{dim}={answered} (expected {expectation.describe()})")
            outcome.distance += _distance(answered, expectation, levels)

    _score_bulk(case, demand, outcome, levels)
    return outcome


def _score_bulk(case: Case, demand, outcome: Outcome, levels: list[str]) -> None:
    """Grade the bulk profile where the case has an opinion about it (issue #3).

    Kept apart from accuracy rather than folded in. A judge that never separates
    the bulk from the peak is not *wrong* about the levels it gave — it is giving a
    coarser answer than asked for, and those two failures deserve different
    reactions.
    """
    if not case.bulk_dimensions:
        return
    if not demand.distinguishes_bulk:
        outcome.bulk_undistinguished = True
        return

    bulk = demand.bulk_dimensions
    for dim, expectation in case.bulk_dimensions.items():
        if expectation == ABSTAIN:
            continue
        assert isinstance(expectation, Band)
        answered = bulk.get(dim)
        if answered is None:
            continue
        if expectation.contains(answered, levels):
            outcome.bulk_hits += 1
        else:
            outcome.bulk_misses.append(f"{dim}={answered} (expected {expectation.describe()})")


def _distance(level: str, band: Band, levels: list[str]) -> int:
    """How many ordinal steps outside the band the answer fell."""
    index = levels.index(level)
    if band.min is not None and index < levels.index(band.min):
        return levels.index(band.min) - index
    if band.max is not None and index > levels.index(band.max):
        return index - levels.index(band.max)
    return 0


def _report(outcomes: list[Outcome], judge: str) -> str:
    lines = [f"Judge evaluation — {judge}", "=" * 60, ""]

    errors = [o for o in outcomes if o.error]
    refused = [o for o in outcomes if o.refused]
    scored = [o for o in outcomes if not o.error and not o.refused]

    graded = sum(o.hits + len(o.misses) for o in scored)
    hits = sum(o.hits for o in scored)
    lines.append("ACCURACY (dimensions the corpus put a band on)")
    if graded:
        lines.append(f"  in band            {hits}/{graded}  ({100 * hits / graded:.0f}%)")
        lines.append(f"  ordinal distance   {sum(o.distance for o in scored)} steps outside")
    else:
        lines.append("  nothing graded — every judged dimension was abstained on")
    lines.append("")

    lines.append("ABSTENTION QUALITY")
    lines.append(f"  answered, should answer    {sum(o.correct_answer for o in scored)}")
    lines.append(f"  abstained, should abstain  {sum(o.correct_abstention for o in scored)}")
    lines.append(f"  abstained, should answer   {sum(len(o.over_abstention) for o in scored)}")
    lines.append(f"  answered, should abstain   {sum(len(o.over_confidence) for o in scored)}")
    lines.append("")

    labelled = [o for o in scored if o.bulk_hits or o.bulk_misses or o.bulk_undistinguished]
    if labelled:
        lines.append("BULK VS PEAK (cases that label the bulk of the work)")
        graded_bulk = sum(o.bulk_hits + len(o.bulk_misses) for o in labelled)
        lines.append(
            f"  bulk in band               {sum(o.bulk_hits for o in labelled)}/{graded_bulk}"
        )
        lines.append(
            f"  did not distinguish        {sum(1 for o in labelled if o.bulk_undistinguished)}"
        )
        lines.append("")

    lines.append("REFUSALS")
    lines.append(f"  refused before judging     {len(refused)} (expected: task-less cases)")
    lines.append(f"  judge unusable             {len(errors)}")
    lines.append("")

    lines.append("PER CASE")
    for o in outcomes:
        if o.error:
            detail = f"ERROR — {o.error}"
        elif o.refused:
            detail = "refused before the judge (as expected)"
        else:
            bits = [f"{o.hits} in band"]
            if o.misses:
                bits.append("missed " + "; ".join(o.misses))
            if o.over_abstention:
                bits.append("over-abstained on " + ", ".join(o.over_abstention))
            if o.over_confidence:
                bits.append("over-confident on " + ", ".join(o.over_confidence))
            if o.bulk_misses:
                bits.append("bulk missed " + "; ".join(o.bulk_misses))
            if o.bulk_undistinguished:
                bits.append("no bulk/peak split")
            detail = " | ".join(bits)
        lines.append(f"  [{o.category:14}] {o.case:30} {detail}")

    lines.append("")
    lines.append(
        "Sampling is pinned, but Ollama version, quantisation and context size are not.\n"
        "Compare against your own previous run, not against someone else's numbers."
    )
    return "\n".join(lines)


def markdown_row(outcomes: list[Outcome], judge: str, params_b: float | None) -> str:
    """The judge's result as one row of the table in `docs/judges.md` (issue #23).

    Numbers from other people's hardware are the part of that table a single
    maintainer cannot produce. Asking a contributor to transcribe four figures out
    of a report is asking for a table whose rows are not comparable — so the
    script emits the row itself, already formatted.
    """
    scored = [o for o in outcomes if not o.error and not o.refused]
    graded = sum(o.hits + len(o.misses) for o in scored)
    hits = sum(o.hits for o in scored)
    distance = sum(o.distance for o in scored)
    unusable = sum(1 for o in outcomes if o.error)

    accuracy = f"{hits}/{graded} ({100 * hits / graded:.0f}%)" if graded else "not graded"
    size = f"{params_b:.0f}B" if params_b else "?"
    steps = "0" if distance == 0 else f"{distance} steps"
    return f"| `{judge}` | {size} | {accuracy} | {steps} | {unusable} |"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--judge", required=True, help="Local model to evaluate, e.g. llama3.1:8b")
    parser.add_argument("--host", default="http://localhost:11434")
    parser.add_argument("--json", dest="json_out", help="Also write the raw outcomes here.")
    parser.add_argument(
        "--markdown-row",
        action="store_true",
        help="Also print the result as a row for the table in docs/judges.md.",
    )
    args = parser.parse_args(argv)

    client = OllamaClient(host=args.host)
    try:
        client.ensure_available(args.judge)
    except SpecJudgeError as exc:
        print(exc.render(), file=sys.stderr)
        return exc.exit_code

    outcomes = [_evaluate(case, client, args.judge) for case in load_corpus()]
    print(_report(outcomes, args.judge))

    if args.markdown_row:
        print("\nRow for docs/judges.md:")
        print(markdown_row(outcomes, args.judge, client.model_params_b(args.judge)))

    if args.json_out:
        payload = [o.__dict__ for o in outcomes]
        Path(args.json_out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"\nRaw outcomes written to {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
