"""Blended cost at an explicit input:output ratio (issue #41).

Comparing on output alone was the most flattering reading for a cheap model and the
least representative of how coding agents are billed, which is mostly on input. The
ratio is an assumption, so every place that uses it has to say which one it used.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from specjudge.domain import (
    DEFAULT_INPUT_OUTPUT_RATIO,
    Comparison,
    DataState,
    Evaluation,
    Price,
    Rating,
    format_ratio,
)
from specjudge.rating import default_rules_path, load_rules
from specjudge.recommend import build_comparison
from specjudge.render.html import render_html
from specjudge.render.table import render_comparison
from specjudge.serialize import comparison_to_dict


def _price(out: float, inp: float) -> Price:
    return Price(input_per_million=inp, output_per_million=out, currency="USD")


def _eval(model_id: str, out: float, inp: float) -> Evaluation:
    return Evaluation(model_id, model_id, Rating.GOOD, "fits", _price(out, inp))


# --- the arithmetic ----------------------------------------------------------------


def test_blended_is_the_token_weighted_mean():
    # 5 input tokens at 1.00 and 1 output token at 7.00, per million: (5 + 7) / 6.
    assert _price(7.0, 1.0).blended(5) == pytest.approx(2.0)


def test_a_zero_ratio_is_output_alone():
    assert _price(7.0, 1.0).blended(0) == pytest.approx(7.0)


def test_the_default_ratio_is_five_to_one():
    assert DEFAULT_INPUT_OUTPUT_RATIO == 5.0
    assert _price(7.0, 1.0).blended() == pytest.approx(2.0)


def test_sort_key_keeps_its_old_meaning_for_api_callers():
    """`Price` is public. Changing what `sort_key` returns would break callers silently."""
    assert _price(7.0, 1.0).sort_key == (7.0, 1.0)


@pytest.mark.parametrize(("ratio", "text"), [(5.0, "5:1"), (7.5, "7.5:1"), (0.0, "0:1")])
def test_ratio_formatting(ratio, text):
    assert format_ratio(ratio) == text


# --- the ordering --------------------------------------------------------------------


def test_equal_fits_are_ordered_by_blended_cost_not_output():
    """Cheap output and pricey input used to win; for an agent it costs more."""
    cheap_output = _eval("cheap-output", out=1.0, inp=2.0)  # blended 11/6 ≈ 1.83
    cheap_input = _eval("cheap-input", out=2.0, inp=0.5)  # blended 4.5/6 = 0.75
    comparison = build_comparison([cheap_output, cheap_input], DataState.SUFFICIENT, "j")
    assert comparison.podium == ["cheap-input", "cheap-output"]


def test_a_zero_ratio_restores_the_output_ordering():
    cheap_output = _eval("cheap-output", out=1.0, inp=2.0)
    cheap_input = _eval("cheap-input", out=2.0, inp=0.5)
    comparison = build_comparison(
        [cheap_output, cheap_input], DataState.SUFFICIENT, "j", input_output_ratio=0
    )
    assert comparison.podium == ["cheap-output", "cheap-input"]


def test_price_still_never_beats_fit():
    """The ratio changes only the tie-break, never FR-008."""
    exact = _eval("exact", out=50.0, inp=10.0)
    overpowered = _eval("over", out=0.1, inp=0.1)
    overpowered.excess = 1
    comparison = build_comparison([overpowered, exact], DataState.SUFFICIENT, "j")
    assert comparison.best_choice == "exact"


# --- the configuration --------------------------------------------------------------


def _rules_with(tmp_path: Path, cost: object) -> float:
    raw = yaml.safe_load(default_rules_path().read_text(encoding="utf-8"))
    if cost is None:
        raw.pop("cost", None)
    else:
        raw["cost"] = cost
    path = tmp_path / "rules.yaml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return load_rules(path).input_output_ratio


def test_shipped_rules_declare_five_to_one():
    assert load_rules().input_output_ratio == 5.0


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (8, 8.0),
        (7.5, 7.5),
        ("10:1", 10.0),
        ("15:2", 7.5),
        (" 8 : 1 ", 8.0),
        (0, 0.0),
        ("0:1", 0.0),
    ],
)
def test_the_ratio_is_read_as_a_number_or_as_written(tmp_path, value, expected):
    assert _rules_with(tmp_path, {"input_output_ratio": value}) == expected


@pytest.mark.parametrize(
    "value", [-1, "-3:1", "five", "5:0", True, None, [5], float("inf"), float("nan")]
)
def test_a_bad_ratio_degrades_to_the_default(tmp_path, value):
    """A broken pricing knob must not stop a recommendation."""
    assert _rules_with(tmp_path, {"input_output_ratio": value}) == DEFAULT_INPUT_OUTPUT_RATIO


@pytest.mark.parametrize("cost", [None, {}, "5:1"])
def test_a_missing_section_degrades_to_the_default(tmp_path, cost):
    assert _rules_with(tmp_path, cost) == DEFAULT_INPUT_OUTPUT_RATIO


# --- the output ----------------------------------------------------------------------


def _comparison(ratio: float = 5.0, *evaluations: Evaluation) -> Comparison:
    rows = list(evaluations) or [_eval("paid", out=7.0, inp=1.0)]
    return build_comparison(rows, DataState.SUFFICIENT, "j", input_output_ratio=ratio)


def test_the_table_names_the_ratio_and_what_blended_means(capsys):
    render_comparison(_comparison(8.0), no_color=True)
    out = capsys.readouterr().out
    assert "@ 8:1" in out
    assert "it does not estimate a project" in " ".join(out.split())
    assert "Prompt caching" in out


def test_the_table_prints_the_blended_figure(capsys):
    render_comparison(_comparison(5.0), no_color=True)
    assert "2.00" in capsys.readouterr().out  # (5·1 + 7) / 6


def test_no_note_when_nothing_is_billed(capsys):
    render_comparison(_comparison(5.0, _eval("local", out=0.0, inp=0.0)), no_color=True)
    assert "Blended =" not in capsys.readouterr().out


def test_the_html_matrix_names_the_ratio_too():
    html = render_html(_comparison(8.0))
    assert "Blended @ 8:1" in html
    assert "does not estimate a project" in html


def test_the_payload_carries_the_ratio_and_each_blended_price():
    payload = comparison_to_dict(_comparison(5.0))
    assert payload["input_output_ratio"] == 5.0
    assert payload["evaluations"][0]["price"]["blended_per_million"] == pytest.approx(2.0)
