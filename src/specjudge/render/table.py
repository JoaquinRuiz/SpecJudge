"""Renders the comparison as a terminal table (Rich) — FR-006.

The best-fitting model is highlighted and listed first; every rating comes with a
human-readable justification (FR-014).
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..about import TERMINAL_CREDIT
from ..domain import Comparison, Evaluation, EvidenceStatus, Rating
from ..gaps import Gap

_MEDAL = {"gold": ("🥇", "bold yellow"), "silver": ("🥈", "bold white"), "bronze": ("🥉", "bold")}

_RATING_STYLE = {
    Rating.POOR: "red",
    Rating.FAIR: "yellow",
    Rating.GOOD: "green",
    Rating.OVERKILL: "cyan",
}


def _price_str(e: Evaluation) -> str:
    p = e.price
    if p.is_free:
        return "open-source/free"
    return f"{p.output_per_million:.2f} out / {p.input_per_million:.2f} in {p.currency}/1M"


def _pricing_date_str(e: Evaluation) -> str:
    return e.price.pricing_date if e.price.pricing_date else "no date"


def render_comparison(
    comparison: Comparison,
    *,
    no_color: bool = False,
    gaps: list[Gap] | None = None,
) -> None:
    """Render the comparison, and what would make it more trustworthy (FR-023).

    Output order is deliberate. Warnings used to print above the table and lose:
    one line of caveat against a ranked table is not a fair fight, and the table
    is what people act on. The gaps now print *last*, because that is where
    reading actually ends.
    """
    console = Console(no_color=no_color, highlight=False)

    # Every warning is printed, whatever the data state. Gating this on "scarce"
    # silently swallowed catalog warnings (missing or stale pricing dates) on
    # exactly the healthy projects where the price data still matters.
    if comparison.warnings:
        for w in comparison.warnings:
            console.print(Text(f"⚠  {w}", style="yellow" if not no_color else None))
        console.print()

    title = "Model comparison (SpecJudge)"
    if comparison.judge_model:
        title += f" - judge: {comparison.judge_model}"
    table = Table(title=title)
    table.add_column("", width=2)
    table.add_column("Model", no_wrap=True)
    table.add_column("Rating")
    table.add_column("Price")
    table.add_column("Priced on")

    for e in comparison.evaluations:
        medal = comparison.medal(e.model_id)
        marker, marker_style = _MEDAL.get(medal or "", ("", None))
        rating_text = Text(e.rating.value, style=None if no_color else _RATING_STYLE.get(e.rating))
        row_style = marker_style if (medal and not no_color) else None
        table.add_row(
            marker,
            e.model_name,
            rating_text,
            _price_str(e),
            _pricing_date_str(e),
            style=row_style,
        )

    console.print(table)

    by_id = {e.model_id: e for e in comparison.evaluations}
    if comparison.podium:
        console.print()
        labels = [("gold", "🥇", "Gold"), ("silver", "🥈", "Silver"), ("bronze", "🥉", "Bronze")]
        for (_, glyph, label), model_id in zip(labels, comparison.podium, strict=False):
            e = by_id[model_id]
            head = Text(f"{glyph} {label}: {e.model_name}", style=None if no_color else "bold")
            console.print(head)
            console.print(Text(f"   {e.justification}", style=None if no_color else "dim"))
    if not comparison.podium:
        console.print()
        for w in comparison.warnings:
            if "No model" in w:
                console.print(Text(f"⚠  {w}", style=None if no_color else "yellow"))

    _print_evidence(console, comparison, no_color=no_color)
    _print_gaps(console, gaps, no_color=no_color)

    console.print()
    console.print(Text(TERMINAL_CREDIT, style=None if no_color else "dim"))


def _print_gaps(console: Console, gaps: list[Gap] | None, *, no_color: bool) -> None:
    """What to go and write, printed after the podium (FR-023).

    Last on purpose. A caveat above a ranked table competes with the exact thing
    the reader came for and loses every time; a reader who gets to the end of the
    output gets this instead.
    """
    if not gaps:
        return

    console.print()
    console.print(
        Text(
            "This ranking rests on a thin definition. Before acting on it:",
            style=None if no_color else "bold yellow",
        )
    )
    for gap in gaps:
        console.print(Text(f"   • {gap.what}", style=None if no_color else "yellow"))
        console.print(Text(f"     → {gap.fix}", style=None if no_color else "dim"))


def _print_evidence(console: Console, comparison: Comparison, *, no_color: bool) -> None:
    """Show what the judge's assessment was grounded in (FR-020).

    The coverage line is the point: a rating nobody could trace back to the spec is
    worth less than one that cites it, and the user should be able to see which
    they got without reaching for --json.
    """
    demand = comparison.demand
    if demand is None or not demand.evidence:
        return

    console.print()
    console.print(Text(f"Evidence: {demand.coverage}", style=None if no_color else "bold"))
    for dim, level in demand.dimensions.items():
        ev = demand.evidence.get(dim)
        if ev is None:
            continue
        if ev.status is EvidenceStatus.UNSUPPORTED:
            detail = "no supporting fragment found"
        elif ev.status is EvidenceStatus.QUOTE_UNVERIFIED:
            detail = f"cites {ev.fragment_id} (quoted wording unconfirmed)"
        else:
            detail = f"cites {ev.fragment_id}"
        console.print(Text(f"   {dim}: {level} — {detail}", style=None if no_color else "dim"))
