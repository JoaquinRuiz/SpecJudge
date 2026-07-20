"""Unit tests for the judge evaluator: never invent a demand profile (Principle IV).

A judge that answers with the wrong shape must produce an explicit error, not a
default. Before this was covered, a missing level silently became the weakest one
and made every project look trivial.
"""

from __future__ import annotations

import pytest

from specjudge.domain import DataState, ProjectAnalysis, RatingRules, SDDArtifact
from specjudge.errors import JudgeUnavailableError
from specjudge.judge.evaluator import build_prompt, estimate_demand, use_compact_prompt


def _rules(**judge) -> RatingRules:
    return RatingRules(
        version=1,
        dimensions=["reasoning", "size", "domain_specialization"],
        scarce_thresholds={"min_detailed_tasks": 3},
        per_dimension={
            "below_by_2_or_more": "poor",
            "below_by_1": "fair",
            "exact": "good",
            "above_by_1_or_more": "overkill",
        },
        aggregation="worst_dimension",
        levels=["low", "medium", "high", "top"],
        judge=judge,
    )


def _analysis() -> ProjectAnalysis:
    tasks = "# Tasks\n" + "".join(f"- [ ] T{i:03d} Do the thing number {i}\n" for i in range(1, 12))
    return ProjectAnalysis(
        artifacts=[
            SDDArtifact("constitution", "c.md", True, True, "# C\n## Principle I\ntext"),
            SDDArtifact("spec", "s.md", True, True, "# Spec\n- **FR-001**: do it\n"),
            SDDArtifact("tasks", "t.md", True, True, tasks, task_count=11),
        ],
        data_state=DataState.SUFFICIENT,
    )


class _FakeClient:
    """Stands in for OllamaClient, returning canned judge responses."""

    def __init__(self, responses, params_b=8.0):
        self._responses = list(responses)
        self._params_b = params_b
        self.prompts: list[str] = []

    def model_params_b(self, model):  # noqa: ARG002
        return self._params_b

    def chat_json(self, model, prompt):  # noqa: ARG002
        self.prompts.append(prompt)
        return self._responses.pop(0)


_VALID = {
    "dimensions": {"reasoning": "high", "size": "medium", "domain_specialization": "low"},
    "justification": "because",
}


def test_valid_response_is_parsed():
    client = _FakeClient([_VALID])
    demand = estimate_demand(_analysis(), _rules(), client, "judge")
    assert demand.dimensions == {
        "reasoning": "high",
        "size": "medium",
        "domain_specialization": "low",
    }
    assert demand.justification == "because"


def test_missing_dimensions_key_raises_instead_of_defaulting():
    """The real-world failure: the judge continued the document instead of answering."""
    client = _FakeClient([{"task": "T028", "title": "Implement something", "status": "pending"}])
    with pytest.raises(JudgeUnavailableError) as exc:
        estimate_demand(_analysis(), _rules(), client, "small-judge")
    assert exc.value.exit_code == 3
    assert "dimensions" in exc.value.render()


def test_invalid_level_raises_instead_of_defaulting():
    client = _FakeClient(
        [
            {
                "dimensions": {
                    "reasoning": "very high",
                    "size": "medium",
                    "domain_specialization": "low",
                }
            }
        ]
    )
    with pytest.raises(JudgeUnavailableError):
        estimate_demand(_analysis(), _rules(), client, "judge")


def test_partial_dimensions_raise():
    """A missing dimension must not silently become the weakest level."""
    client = _FakeClient([{"dimensions": {"reasoning": "top"}}])
    with pytest.raises(JudgeUnavailableError):
        estimate_demand(_analysis(), _rules(), client, "judge")


def test_non_object_response_raises():
    client = _FakeClient([["not", "an", "object"]])
    with pytest.raises(JudgeUnavailableError):
        estimate_demand(_analysis(), _rules(), client, "judge")


def test_large_judge_retries_with_compact_prompt():
    """A big judge gets the full prompt first, then one compact retry."""
    client = _FakeClient([{"oops": True}, _VALID], params_b=200.0)
    demand = estimate_demand(_analysis(), _rules(), client, "big-judge")
    assert demand.dimensions["reasoning"] == "high"
    assert len(client.prompts) == 2
    assert "PROJECT ARTIFACTS" in client.prompts[0]
    assert "PROJECT SUMMARY" in client.prompts[1]


def test_small_judge_uses_compact_prompt_only():
    client = _FakeClient([_VALID], params_b=8.0)
    estimate_demand(_analysis(), _rules(), client, "small-judge")
    assert len(client.prompts) == 1
    assert "PROJECT SUMMARY" in client.prompts[0]


def test_compact_threshold_comes_from_rules():
    rules = _rules(compact_prompt_at_or_below_params_b=10)
    assert use_compact_prompt(8.0, rules) is True
    assert use_compact_prompt(24.0, rules) is False
    # Unknown size is treated as small — the compact prompt is the safe default.
    assert use_compact_prompt(None, rules) is True


def _realistic_analysis() -> ProjectAnalysis:
    """A project with real prose volume — the case the compact prompt targets."""
    prose = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 120  # ~7K chars
    tasks = "# Tasks\n" + "".join(
        f"- [ ] T{i:03d} Implement the component number {i} with validation\n" for i in range(1, 56)
    )
    return ProjectAnalysis(
        artifacts=[
            SDDArtifact("constitution", "c.md", True, True, f"# C\n## Principle I\n{prose}"),
            SDDArtifact("spec", "s.md", True, True, f"# Spec\n- **FR-001**: do it\n{prose}"),
            SDDArtifact("tasks", "t.md", True, True, tasks + prose, task_count=55),
        ],
        data_state=DataState.SUFFICIENT,
    )


def test_compact_prompt_is_much_shorter_on_a_realistic_project():
    rules = _rules()
    analysis = _realistic_analysis()
    full = build_prompt(analysis, rules, compact=False)
    compact = build_prompt(analysis, rules, compact=True)
    # Measured on this repo: 25.6K -> 4.5K chars. Assert a conservative margin.
    assert len(compact) < len(full) / 2


def test_instructions_appear_at_both_ends_of_every_prompt():
    """The repeated tail is what stops small models continuing the document."""
    rules = _rules()
    for compact in (True, False):
        prompt = build_prompt(_realistic_analysis(), rules, compact=compact)
        assert prompt.count("Calibration:") == 2
        assert prompt.rstrip().endswith('"<one or two sentences>"}')
