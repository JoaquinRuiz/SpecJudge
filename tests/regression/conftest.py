"""Snapshot-update flag for the golden ranking tests (issue #5)."""

from __future__ import annotations


def pytest_addoption(parser):
    parser.addoption(
        "--snapshot-update",
        action="store_true",
        default=False,
        help="Rewrite the golden ranking snapshot instead of comparing against it.",
    )
