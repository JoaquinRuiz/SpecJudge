"""Renders the matrix as self-contained HTML and opens it in the browser — FR-007.

The HTML references no external resources (local-first / Principle I): all CSS is
inlined. Opening the browser is safe in headless environments (it does not break).
"""

from __future__ import annotations

import tempfile
import webbrowser
from importlib.resources import files
from pathlib import Path

from jinja2 import Environment, select_autoescape

from .. import about
from ..domain import Comparison


def _template_source() -> str:
    try:
        packaged = files("specjudge").joinpath("_templates/matrix.html.j2")
        if packaged.is_file():
            return packaged.read_text(encoding="utf-8")
    except (ModuleNotFoundError, FileNotFoundError):
        pass
    repo_template = Path(__file__).resolve().parents[3] / "templates" / "matrix.html.j2"
    return repo_template.read_text(encoding="utf-8")


def _families(comparison: Comparison) -> list[tuple[str, int]]:
    """Families present in this comparison, with a count, ordered by size."""
    counts: dict[str, int] = {}
    for e in comparison.evaluations:
        counts[e.family or "Other"] = counts.get(e.family or "Other", 0) + 1
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def render_html(comparison: Comparison) -> str:
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    template = env.from_string(_template_source())
    return template.render(
        about=about,
        comparison=comparison,
        by_id={e.model_id: e for e in comparison.evaluations},
        families=_families(comparison),
        open_source_count=sum(1 for e in comparison.evaluations if e.open_source),
        evaluations=comparison.evaluations,
        best_choice=comparison.best_choice,
        judge_model=comparison.judge_model,
        data_state=comparison.data_state.value,
        warnings=comparison.warnings,
    )


def write_html(comparison: Comparison, path: Path | None = None) -> Path:
    html = render_html(comparison)
    if path is None:
        fd, name = tempfile.mkstemp(suffix=".html", prefix="specjudge-")
        path = Path(name)
        import os

        os.close(fd)
    path.write_text(html, encoding="utf-8")
    return path


def open_in_browser(comparison: Comparison, path: Path | None = None) -> Path:
    """Write the HTML and try to open it. Headless-safe (just returns the path)."""
    out = write_html(comparison, path)
    try:
        webbrowser.open(out.as_uri())
    except Exception:
        # No browser available (headless): the terminal table already covers this.
        pass
    return out
