"""Renders the comparison as a terminal table (Rich) — FR-006.

The best-fitting model is highlighted and listed first; every rating comes with a
human-readable justification (FR-014).
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from ..about import TERMINAL_CREDIT
from ..domain import Comparison, Evaluation, Rating

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


def render_comparison(comparison: Comparison, *, no_color: bool = False) -> None:
    console = Console(no_color=no_color, highlight=False)

    if comparison.data_state.value == "scarce":
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

    console.print()
    console.print(Text(TERMINAL_CREDIT, style=None if no_color else "dim"))
