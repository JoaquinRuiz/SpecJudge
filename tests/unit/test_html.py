"""Unit tests for the HTML report — T043.

Self-containment (Principle I) means the page **loads** nothing from the network:
opening it must not emit a single request. Plain navigation links (`<a href>`) are
allowed — nothing is fetched until the user deliberately clicks — so the checks
below forbid resource-loading references specifically, not every external URL.
"""

from __future__ import annotations

import re

from specjudge.domain import Comparison, DataState, Evaluation, Price, Rating
from specjudge.render.html import render_html

# Attributes/at-rules the browser resolves automatically when the page opens.
_AUTO_LOADED = [
    re.compile(r'\bsrc\s*=\s*["\']https?://', re.I),  # img/script/iframe
    re.compile(r'<link\b[^>]*\bhref\s*=\s*["\']https?://', re.I),  # stylesheets, fonts
    re.compile(r"@import\b", re.I),  # CSS imports
    re.compile(r"url\(\s*[\"']?https?://", re.I),  # CSS background/font URLs
]


def _comp() -> Comparison:
    evals = [
        Evaluation("best", "Best", Rating.GOOD, "good fit", Price(0.5, 1.5, "USD", "2026-07-01")),
    ]
    return Comparison(evals, DataState.SUFFICIENT, "llama3.1:8b", "best", podium=["best"])


def test_html_loads_no_external_resources():
    """Opening the report must not trigger any network request."""
    html = render_html(_comp())
    for pattern in _AUTO_LOADED:
        assert not pattern.search(html), f"auto-loaded external resource: {pattern.pattern}"


def test_external_urls_appear_only_as_navigation_links():
    """Any external URL must be a plain <a href>, never an auto-loaded resource."""
    html = render_html(_comp())
    anchor_urls = set(re.findall(r'<a\b[^>]*\bhref\s*=\s*["\'](https?://[^"\']+)', html, re.I))
    all_urls = set(re.findall(r'["\'(](https?://[^"\'\s)]+)', html))
    assert all_urls - anchor_urls == set(), "external URL used outside a navigation link"


def test_html_marks_the_podium():
    html = render_html(_comp())
    assert 'class="gold"' in html
    assert "🥇" in html
    assert "Gold — Best" in html


def test_free_price_renders_as_open_source_in_html():
    evals = [
        Evaluation(
            "local", "Local Model", Rating.GOOD, "fits", Price(0.0, 0.0, "USD", "2026-07-20")
        ),
    ]
    comp = Comparison(evals, DataState.SUFFICIENT, "llama3.1:8b", "local", podium=["local"])
    html = render_html(comp)
    assert "open-source/free" in html
    assert "0.00 out" not in html


def test_footer_credits_the_author():
    from specjudge import about

    html = render_html(_comp())
    assert about.AUTHOR in html
    assert about.YOUTUBE_URL in html
    for book in about.BOOKS:
        assert book["title"] in html


def _mixed_comp() -> Comparison:
    evals = [
        Evaluation(
            "a",
            "Claude X",
            Rating.GOOD,
            "j",
            Price(1, 2, "USD", "2026-07-20"),
            family="Claude",
            open_source=False,
        ),
        Evaluation(
            "b",
            "Gemma Y",
            Rating.GOOD,
            "j",
            Price(0, 0, "USD", "2026-07-20"),
            family="Gemma",
            open_source=True,
        ),
        Evaluation(
            "c",
            "Gemma Z",
            Rating.OVERKILL,
            "j",
            Price(1, 3, "USD", "2026-07-20"),
            family="Gemma",
            open_source=True,
        ),
    ]
    return Comparison(evals, DataState.SUFFICIENT, "judge", "a", podium=["a", "b"])


def test_rows_carry_family_and_open_source_attributes():
    html = render_html(_mixed_comp())
    assert 'data-family="Claude" data-oss="no"' in html
    assert 'data-family="Gemma" data-oss="yes"' in html


def test_family_chips_are_rendered_with_counts():
    html = render_html(_mixed_comp())
    assert 'data-family="*"' in html  # the "All" chip
    assert 'data-family="Gemma"' in html
    assert 'data-family="Claude"' in html
    assert 'id="oss-chip"' in html


def test_filtering_script_is_inline_not_external():
    """Self-containment: the filter must not pull in any library."""
    html = render_html(_mixed_comp())
    assert "<script>" in html
    assert not re.search(r"<script[^>]+\bsrc\s*=", html, re.I)


def test_html_shows_the_gaps_after_the_table(tmp_path):
    """The report had the same problem as the terminal: caveat on top, table below."""
    from specjudge.gaps import Gap
    from specjudge.render.html import render_html

    gaps = [Gap(code="no_spec", what="no specification found", fix="write one")]
    html = render_html(_comp(), gaps)

    assert "This ranking rests on a thin definition" in html
    assert "no specification found" in html
    assert "write one" in html
    assert html.index("<table") < html.index("This ranking rests on")


def test_html_omits_the_block_when_there_is_nothing_to_report():
    from specjudge.render.html import render_html

    assert "This ranking rests on" not in render_html(_comp())


def test_html_escapes_gap_text():
    """Gap text is derived from user files; it must not become markup."""
    from specjudge.gaps import Gap
    from specjudge.render.html import render_html

    gaps = [Gap(code="x", what="<script>alert(1)</script>", fix="fix <b>it</b>")]
    html = render_html(_comp(), gaps)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_the_report_names_the_sources_it_was_built_from():
    comp = _comp()
    comp.sources_read = ["spec", "tasks", "claude"]
    html = render_html(comp)
    assert "Read:" in html
    assert "spec, tasks, CLAUDE.md" in html
