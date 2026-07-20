"""SpecJudge: local-first AI model recommender for Spec-Driven Development projects."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    # Single source of truth: the version declared in pyproject.toml.
    __version__ = version("specjudge")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0+unknown"
