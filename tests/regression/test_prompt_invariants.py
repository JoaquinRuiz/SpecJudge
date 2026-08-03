"""Properties the judge prompt must keep, whatever a rewrite does to it (issue #5).

These do not measure whether a prompt is *good* — no test without a real model
can. They pin the structural decisions that were each paid for with a bug:
instructions repeated at the tail because small models otherwise continue the
document, a citable list because a digest leaves nothing to quote, every
dimension actually named.

A prompt edit that trips one of these is not necessarily wrong, but it is
undoing something deliberate, and the diff should say so out loud.
"""

from __future__ import annotations

import pytest

from specjudge.artifacts import read_project
from specjudge.domain import UNSUPPORTED
from specjudge.judge.evaluator import build_prompt
from specjudge.rating import load_rules

from .corpus import load_corpus

JUDGED = [c for c in load_corpus() if c.judged]
SHAPES = [True, False]


def _prompt(case, compact: bool) -> str:
    rules = load_rules()
    return build_prompt(read_project(case.path, rules), rules, compact=compact)


@pytest.mark.parametrize("compact", SHAPES, ids=["compact", "full"])
@pytest.mark.parametrize("case", JUDGED, ids=lambda c: c.name)
def test_instructions_bookend_the_prompt(case, compact):
    """The repeated tail is what stops a small judge continuing the document."""
    assert _prompt(case, compact).count("Calibration:") == 2


@pytest.mark.parametrize("compact", SHAPES, ids=["compact", "full"])
@pytest.mark.parametrize("case", JUDGED, ids=lambda c: c.name)
def test_every_dimension_is_named(case, compact):
    prompt = _prompt(case, compact)
    for dim in load_rules().dimensions:
        assert dim in prompt


@pytest.mark.parametrize("compact", SHAPES, ids=["compact", "full"])
@pytest.mark.parametrize("case", JUDGED, ids=lambda c: c.name)
def test_the_answer_shape_is_spelled_out(case, compact):
    """Ollama's json mode guarantees valid JSON, not the JSON we asked for."""
    prompt = _prompt(case, compact)
    assert '"dimensions"' in prompt
    assert '"justification"' in prompt


@pytest.mark.parametrize("compact", SHAPES, ids=["compact", "full"])
@pytest.mark.parametrize("case", JUDGED, ids=lambda c: c.name)
def test_citable_fragments_and_the_abstention_option_are_offered(case, compact):
    """Requiring a citation without offering ids — or an out — is a trap."""
    prompt = _prompt(case, compact)
    assert "CITABLE FRAGMENTS" in prompt
    assert UNSUPPORTED in prompt


@pytest.mark.parametrize("case", JUDGED, ids=lambda c: c.name)
def test_the_compact_prompt_stays_substantially_smaller(case):
    """The compact shape exists to fit small judges; losing that defeats it."""
    assert len(_prompt(case, compact=True)) < len(_prompt(case, compact=False))


@pytest.mark.parametrize("compact", SHAPES, ids=["compact", "full"])
@pytest.mark.parametrize("case", JUDGED, ids=lambda c: c.name)
def test_the_prompt_never_asks_the_judge_to_write_code(case, compact):
    """A judge that starts implementing has misread the task entirely."""
    prompt = _prompt(case, compact).lower()
    assert "do not output tasks, code or file lists" in prompt
