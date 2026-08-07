"""Regenerate the worked example in the README from the real catalog.

The README used to carry a hand-written table with hand-copied prices, which went
stale every time `data/models.yaml` moved — the same rot issue #6 fixed for the
catalog itself. This script derives the whole block instead, and a contract test
fails when the README drifts from what it produces.

    uv run python scripts/render_example.py            # print the block
    uv run python scripts/render_example.py --write    # update README.md in place

What is real here: the catalog, the prices, the rating engine, the podium and every
figure below the table. What is pinned: the demand profile. Estimating demand needs
a local LLM judge, which CI does not have and which would not give byte-identical
answers twice — so the example fixes the profile a judge produced once, and says so
in the README rather than passing a synthesised run off as a live capture.
"""

from __future__ import annotations

import argparse
import io
import os
import re
import sys
from contextlib import redirect_stdout
from dataclasses import replace
from pathlib import Path

from specjudge.api import Comparison, DataState, DemandProfile, Evaluation, Rating
from specjudge.artifacts import read_project
from specjudge.catalog import load_catalog
from specjudge.rating import evaluate_all, load_rules
from specjudge.recommend import build_comparison
from specjudge.render.table import render_comparison

REPO_ROOT = Path(__file__).resolve().parents[1]
README = REPO_ROOT / "README.md"
EXAMPLE_PROJECT = REPO_ROOT / "examples" / "task-manager"

BEGIN = "<!-- BEGIN generated-example: run `uv run python scripts/render_example.py --write` -->"
END = "<!-- END generated-example -->"

# Fixed so the rendered table is byte-identical wherever this runs.
RENDER_WIDTH = 92

# The demand a judge estimated for examples/task-manager. Pinned, not re-judged.
JUDGE_MODEL = "devstral-small-2"
DEMAND = DemandProfile(
    dimensions={"reasoning": "medium", "size": "medium", "domain_specialization": "medium"},
    justification=(
        "A conventional CRUD web application: the requirements are explicit, the "
        "domain is familiar and the work is broken into small, independent tasks."
    ),
    judge_model=JUDGE_MODEL,
)


def build_full_comparison() -> Comparison:
    """The comparison exactly as the CLI would produce it for the example project."""
    models, _ = load_catalog()
    rules = load_rules()
    evaluations = evaluate_all(models, DEMAND, rules)
    # The sources are read for real, not pinned: which files exist in the example
    # project is a fact on disk, and the line the table prints should match it.
    analysis = read_project(EXAMPLE_PROJECT, rules)
    return build_comparison(
        evaluations,
        DataState.SUFFICIENT,
        JUDGE_MODEL,
        source_kinds=analysis.source_kinds,
        environment_only=analysis.environment_only,
    )


def reference_overkill(comparison: Comparison) -> Evaluation | None:
    """The priciest model rated `overkill` — the "frontier default" to compare against.

    Derived rather than pinned to a model id, so it survives catalog churn: whatever
    the most expensive over-powered option happens to be today is what the reader
    would have reached for, and what this example argues against.
    """
    overkill = [e for e in comparison.evaluations if e.rating is Rating.OVERKILL]
    if not overkill:
        return None
    return max(overkill, key=lambda e: e.price.sort_key)


def cheapest_paid_fit(comparison: Comparison) -> Evaluation | None:
    """Cheapest capable model that actually bills per token.

    The gold medal is often a self-hosted model at 0.00, which is a non-answer for
    a reader who will not run their own weights. This gives them a hosted figure.
    """
    paid = [e for e in comparison.evaluations if e.fits and not e.price.is_free]
    if not paid:
        return None
    return min(paid, key=lambda e: e.price.sort_key)


def abridge(comparison: Comparison, reference: Evaluation | None) -> Comparison:
    """Podium plus the reference overkill row.

    The real run lists every model in the catalog. That is the right behaviour for a
    terminal and useless in a README, so the block shows the rows that carry the
    argument and says it is abridged.
    """
    keep = list(comparison.podium)
    if reference is not None:
        keep.append(reference.model_id)
    rows = [e for e in comparison.evaluations if e.model_id in keep]
    return replace(comparison, evaluations=rows)


def render_table(comparison: Comparison) -> str:
    """Capture `render_comparison` at a fixed width, minus the terminal credit.

    The credit line is real output, but inside the author's own README it is noise
    rather than information — the page already carries the byline.
    """
    previous = os.environ.get("COLUMNS")
    os.environ["COLUMNS"] = str(RENDER_WIDTH)
    try:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            render_comparison(comparison, no_color=True)
    finally:
        if previous is None:
            os.environ.pop("COLUMNS", None)
        else:
            os.environ["COLUMNS"] = previous

    lines = buffer.getvalue().rstrip("\n").split("\n")
    while lines and (not lines[-1].strip() or lines[-1].startswith("SpecJudge by ")):
        lines.pop()
    return "\n".join(lines)


def _price_phrase(evaluation: Evaluation) -> str:
    price = evaluation.price
    return f"${price.output_per_million:.2f}/M output, ${price.input_per_million:.2f}/M input"


def cost_summary(comparison: Comparison, reference: Evaluation | None) -> str:
    """One paragraph putting a number on the gap, computed from the catalog."""
    gold = next((e for e in comparison.evaluations if e.model_id == comparison.best_choice), None)
    if gold is None or reference is None:
        return ""

    if gold.price.is_free:
        # A multiple is undefined against zero, so state the gap directly.
        lead = (
            f"**{gold.model_name}** is right-sized for this project and costs nothing "
            f"per token — it runs on your own hardware. **{reference.model_name}**, the "
            f"priciest option this project does not need, bills {_price_phrase(reference)}."
        )
        paid = cheapest_paid_fit(comparison)
        if paid is not None and paid.model_id != reference.model_id:
            factor = reference.price.output_per_million / paid.price.output_per_million
            lead += (
                f" If you would rather not self-host, the cheapest hosted model that "
                f"still fits is **{paid.model_name}** at {_price_phrase(paid)} — "
                f"**{factor:.0f}× cheaper on output** than reaching for the frontier."
            )
        return lead

    factor = reference.price.output_per_million / gold.price.output_per_million
    return (
        f"**{gold.model_name}** is right-sized for this project at {_price_phrase(gold)}. "
        f"**{reference.model_name}**, the priciest option this project does not need, "
        f"bills {_price_phrase(reference)} — **{factor:.0f}× more on output** for "
        f"capability the work never uses."
    )


def render_block() -> str:
    comparison = build_full_comparison()
    reference = reference_overkill(comparison)
    total = len(comparison.evaluations)
    table = render_table(abridge(comparison, reference))
    summary = cost_summary(comparison, reference)

    return "\n".join(
        [
            BEGIN,
            "```console",
            "$ specjudge examples/task-manager",
            "",
            table,
            "```",
            "",
            f"Abridged: the real run scores all {total} models in the catalog and lists "
            f"every one of them. Prices and ratings above are generated from "
            f"[`data/models.yaml`](./data/models.yaml), so they cannot go stale silently.",
            "",
            summary,
            END,
        ]
    )


def update_readme(block: str) -> bool:
    """Replace the delimited block in README.md. Returns True when it changed."""
    text = README.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(BEGIN) + ".*?" + re.escape(END),
        re.DOTALL,
    )
    if not pattern.search(text):
        raise SystemExit(
            f"Markers not found in {README}. Expected a block delimited by:\n  {BEGIN}\n  {END}"
        )
    updated = pattern.sub(lambda _: block, text, count=1)
    if updated == text:
        return False
    README.write_text(updated, encoding="utf-8")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument(
        "--write", action="store_true", help="Update README.md in place instead of printing."
    )
    args = parser.parse_args(argv)

    block = render_block()
    if not args.write:
        print(block)
        return 0

    changed = update_readme(block)
    print("README.md updated." if changed else "README.md already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
