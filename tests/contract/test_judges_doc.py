"""The judge guide must not rot in silence (issue #23).

`docs/judges.md` publishes numbers measured against the corpus and names knobs that
live in code and YAML. Documentation of that kind decays invisibly: the corpus grows,
a knob is renamed, a minimum version moves, and the page keeps asserting yesterday's
facts with yesterday's confidence.

These are not tests of the prose. They pin the handful of claims that can be checked
against the thing they describe, which is exactly the set that goes stale without
anyone noticing.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest
import yaml

from specjudge.judge.ollama import MIN_OLLAMA_VERSION

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE = REPO_ROOT / "docs" / "judges.md"

sys.path.insert(0, str(REPO_ROOT / "tests"))
from regression.corpus import load_corpus  # noqa: E402


@pytest.fixture(scope="module")
def guide() -> str:
    return GUIDE.read_text(encoding="utf-8")


def test_the_guide_exists(guide):
    assert guide.strip()


def test_the_corpus_size_it_claims_is_the_corpus_size(guide):
    """The page says how many projects the numbers come from.

    Add a corpus case and that sentence becomes false — which is a fine thing to
    happen, as long as it happens loudly here rather than quietly in the README of
    someone deciding which model to download.
    """
    # Whitespace-tolerant: prose gets re-wrapped, and a line break between the number
    # and its noun is not the guide forgetting to state its sample size.
    claimed = {int(n) for n in re.findall(r"corpus of\s+\*{0,2}(\d+)\*{0,2}\s+projects", guide)}
    claimed |= {int(n) for n in re.findall(r"corpus of\s+(\d+)\s+cases", guide)}
    assert claimed, "the guide no longer states the corpus size"
    assert claimed == {len(load_corpus())}, (
        f"guide claims {claimed}, corpus has {len(load_corpus())} cases"
    )


def test_the_minimum_ollama_version_matches_the_code(guide):
    """A version written by hand drifts from the one the code enforces."""
    expected = ".".join(str(part) for part in MIN_OLLAMA_VERSION)
    assert f"Ollama {expected}" in guide


@pytest.mark.parametrize(
    ("mentioned", "path"),
    [
        ("evidence.require_spans", ("evidence", "require_spans")),
        (
            "judge.compact_prompt_at_or_below_params_b",
            ("judge", "compact_prompt_at_or_below_params_b"),
        ),
    ],
)
def test_the_knobs_it_names_still_exist(guide, mentioned, path):
    """Renaming a setting must not leave the guide pointing at nothing."""
    leaf = mentioned.split(".")[-1]
    assert leaf in guide, f"the guide no longer mentions {mentioned}"

    rules = yaml.safe_load((REPO_ROOT / "data" / "rating-rules.yaml").read_text("utf-8"))
    section, key = path
    assert key in (rules.get(section) or {}), f"{mentioned} is gone from rating-rules.yaml"


def test_the_measured_table_is_stamped(guide):
    """A number without its conditions is not reproducible, only quotable.

    The project's whole claim about judges is that anyone can re-measure. That needs
    the version, the runtime and the date attached to the figures.
    """
    stamp = guide[guide.index("| Judge |") :]
    assert re.search(r"SpecJudge \d+\.\d+", stamp), "no SpecJudge version next to the table"
    assert re.search(r"Ollama \d+\.\d+", stamp), "no Ollama version next to the table"
    assert re.search(r"measured\s+\d{4}-\d{2}-\d{2}", stamp), "no measurement date"


def test_the_readme_points_at_the_guide():
    """The guide only helps the people who are choosing, and they start at the README."""
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    assert "docs/judges.md" in readme


def test_contributing_explains_how_to_send_a_row():
    """The community table is the part a single maintainer cannot fill."""
    contributing = (REPO_ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "--markdown-row" in contributing
