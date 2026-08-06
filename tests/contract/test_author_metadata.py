"""The book list lives in two places, so the two are pinned together.

`about.BOOKS` feeds the HTML report and the README lists the same books for readers.
They drifted: the README was updated when a book was published, `about.py` was not,
and the generated report advertised it as forthcoming across two releases.

Duplication is the actual defect here. Until one of the two is derived from the
other, this test is what keeps them honest.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from specjudge import about

README = Path(__file__).resolve().parents[2] / "README.md"

# Markdown links in the author section: 📗 [Title](https://…)
_BOOK_LINK = re.compile(r"^[^\S\n]*[\U0001F300-\U0001FAFF]\s*\[([^\]]+)\]\(([^)]+)\)\s*$", re.M)


def _readme_books() -> list[tuple[str, str]]:
    text = README.read_text(encoding="utf-8")
    section = text.split("## About the author", 1)
    assert len(section) == 2, "README lost its author section"
    return _BOOK_LINK.findall(section[1])


def test_readme_lists_some_books():
    """Guards the parser: an empty match would make every assertion below vacuous."""
    assert len(_readme_books()) >= 3


def test_the_two_lists_hold_the_same_books():
    assert [(b["title"], b["url"]) for b in about.BOOKS] == _readme_books()


@pytest.mark.parametrize("book", about.BOOKS, ids=lambda b: b["title"])
def test_every_book_has_a_link(book):
    assert book["url"].startswith("http"), f"{book['title']} has no link"


@pytest.mark.parametrize("book", about.BOOKS, ids=lambda b: b["title"])
def test_a_linked_book_is_not_also_announced_as_forthcoming(book):
    """The exact contradiction that shipped: a buyable link plus 'próximamente'."""
    if book["url"]:
        assert not book["note"], f"{book['title']} is linked but still carries a note"
