"""Unit tests for the judge evaluator: never invent a demand profile (Principle IV).

A judge that answers with the wrong shape must produce an explicit error, not a
default. Before this was covered, a missing level silently became the weakest one
and made every project look trivial.
"""

from __future__ import annotations

import pytest

from specjudge.domain import (
    DataState,
    EvidenceStatus,
    ProjectAnalysis,
    RatingRules,
    SDDArtifact,
)
from specjudge.errors import JudgeUnavailableError
from specjudge.judge.evaluator import (
    build_prompt,
    estimate_demand,
    evidence_warnings,
    use_compact_prompt,
)


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
        self.schemas: list[dict | None] = []

    def model_params_b(self, model):  # noqa: ARG002
        return self._params_b

    def chat_json(self, model, prompt, schema=None):  # noqa: ARG002
        self.prompts.append(prompt)
        self.schemas.append(schema)
        return self._responses.pop(0)


# A fragment id that _analysis() really produces. Asserted below, so a change to the
# id scheme fails loudly here instead of quietly making every judge answer invalid.
_CITED = "T:T001"

_VALID = {
    "dimensions": {"reasoning": "high", "size": "medium", "domain_specialization": "low"},
    "evidence": dict.fromkeys(["reasoning", "size", "domain_specialization"], _CITED),
    "justification": "because",
}


def test_analysis_fixture_offers_the_cited_fragment():
    """Guards the id scheme the rest of this module hardcodes."""
    from specjudge.judge.evaluator import artifact_limit
    from specjudge.judge.fragments import extract_fragments

    rules = _rules()
    ids = {f.id for f in extract_fragments(_analysis(), artifact_limit(rules, compact=True))}
    assert _CITED in ids


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


# ----------------------------------------------- evidence spans (issue #1 / FR-020)


def _answer(dimensions, evidence=None, quotes=None, justification="because"):
    payload = {"dimensions": dimensions, "justification": justification}
    if evidence is not None:
        payload["evidence"] = evidence
    if quotes is not None:
        payload["quotes"] = quotes
    return payload


_ALL_DIMS = ["reasoning", "size", "domain_specialization"]


def test_prompt_offers_a_citable_fragment_list():
    prompt = build_prompt(_analysis(), _rules(), compact=True)
    assert "CITABLE FRAGMENTS" in prompt
    assert _CITED in prompt


def test_prompt_omits_the_list_when_spans_are_not_required():
    rules = _rules()
    rules.require_spans = False
    prompt = build_prompt(_analysis(), rules, compact=True)
    assert "CITABLE FRAGMENTS" not in prompt
    assert "unsupported" not in prompt


def test_rated_dimension_without_evidence_is_rejected():
    """A level with no citation is exactly what this feature exists to stop."""
    client = _FakeClient([_answer(dict.fromkeys(_ALL_DIMS, "medium"))])
    with pytest.raises(JudgeUnavailableError) as exc:
        estimate_demand(_analysis(), _rules(), client, "judge")
    assert "no evidence" in exc.value.render()


def test_fabricated_fragment_id_is_rejected():
    client = _FakeClient(
        [_answer(dict.fromkeys(_ALL_DIMS, "medium"), dict.fromkeys(_ALL_DIMS, "S:FR-999"))]
    )
    with pytest.raises(JudgeUnavailableError) as exc:
        estimate_demand(_analysis(), _rules(), client, "judge")
    rendered = exc.value.render()
    assert "S:FR-999" in rendered
    assert "not in the text" in rendered


def test_one_fabricated_citation_rejects_the_whole_profile():
    """Whole-profile rejection: a judge that invents one citation is not trustworthy."""
    evidence = {"reasoning": _CITED, "size": _CITED, "domain_specialization": "T:NOPE"}
    client = _FakeClient([_answer(dict.fromkeys(_ALL_DIMS, "medium"), evidence)])
    with pytest.raises(JudgeUnavailableError):
        estimate_demand(_analysis(), _rules(), client, "judge")


def test_unsupported_needs_no_citation():
    dims = {"reasoning": "unsupported", "size": "medium", "domain_specialization": "high"}
    client = _FakeClient([_answer(dims, {"size": _CITED, "domain_specialization": _CITED})])
    demand = estimate_demand(_analysis(), _rules(), client, "judge")

    assert demand.dimensions["reasoning"] == "unsupported"
    assert demand.unsupported_dimensions == ["reasoning"]
    assert demand.scored_dimensions == {"size": "medium", "domain_specialization": "high"}
    assert demand.evidence["reasoning"].status is EvidenceStatus.UNSUPPORTED
    assert demand.evidence["reasoning"].fragment_id is None


def test_matching_quote_is_grounded():
    quotes = dict.fromkeys(_ALL_DIMS, "Do the thing number 1")
    client = _FakeClient(
        [_answer(dict.fromkeys(_ALL_DIMS, "medium"), dict.fromkeys(_ALL_DIMS, _CITED), quotes)]
    )
    demand = estimate_demand(_analysis(), _rules(), client, "judge")
    assert all(e.status is EvidenceStatus.GROUNDED for e in demand.evidence.values())


def test_mismatched_quote_warns_but_is_accepted():
    """The id is the load-bearing citation; a paraphrased quote is reported, not fatal."""
    quotes = dict.fromkeys(_ALL_DIMS, "something the fragment never said")
    client = _FakeClient(
        [_answer(dict.fromkeys(_ALL_DIMS, "medium"), dict.fromkeys(_ALL_DIMS, _CITED), quotes)]
    )
    demand = estimate_demand(_analysis(), _rules(), client, "judge")

    assert all(e.status is EvidenceStatus.QUOTE_UNVERIFIED for e in demand.evidence.values())
    assert any("did not match" in w for w in evidence_warnings(demand))


def test_quote_survives_whitespace_and_smart_punctuation():
    quotes = dict.fromkeys(_ALL_DIMS, "do   the THING   number 1")
    client = _FakeClient(
        [_answer(dict.fromkeys(_ALL_DIMS, "medium"), dict.fromkeys(_ALL_DIMS, _CITED), quotes)]
    )
    demand = estimate_demand(_analysis(), _rules(), client, "judge")
    assert all(e.status is EvidenceStatus.GROUNDED for e in demand.evidence.values())


def test_require_spans_off_accepts_the_older_shape():
    """The escape hatch for judges too small for the citation schema."""
    rules = _rules()
    rules.require_spans = False
    client = _FakeClient([_answer(dict.fromkeys(_ALL_DIMS, "medium"))])
    demand = estimate_demand(_analysis(), rules, client, "judge")
    assert demand.dimensions == dict.fromkeys(_ALL_DIMS, "medium")
    assert demand.evidence == {}


def test_all_unsupported_is_reported_as_zero_coverage():
    client = _FakeClient([_answer(dict.fromkeys(_ALL_DIMS, "unsupported"))])
    demand = estimate_demand(_analysis(), _rules(), client, "judge")
    assert demand.scored_dimensions == {}
    assert "0 of 3" in demand.coverage


def test_coverage_counts_only_grounded_dimensions():
    dims = {"reasoning": "unsupported", "size": "medium", "domain_specialization": "high"}
    client = _FakeClient([_answer(dims, {"size": _CITED, "domain_specialization": _CITED})])
    demand = estimate_demand(_analysis(), _rules(), client, "judge")
    assert "2 of 3" in demand.coverage


def test_evidence_warnings_are_silent_on_a_fully_grounded_profile():
    client = _FakeClient([_VALID])
    demand = estimate_demand(_analysis(), _rules(), client, "judge")
    assert evidence_warnings(demand) == []


# ----------------------------------------------- response schema (issue #14)


def test_the_schema_constrains_levels_to_the_answer_vocabulary():
    from specjudge.judge.evaluator import response_schema

    rules = _rules()
    schema = response_schema(rules)
    levels = schema["properties"]["dimensions"]["properties"]["reasoning"]["enum"]
    assert set(levels) == set(rules.levels) | {"unsupported"}


def test_the_schema_types_evidence_as_strings():
    """The whole bug: an 8B answered `[true]` where a fragment id belonged."""
    from specjudge.judge.evaluator import response_schema

    evidence = response_schema(_rules())["properties"]["evidence"]
    assert all(prop["type"] == "string" for prop in evidence["properties"].values())
    assert set(evidence["required"]) == set(_rules().dimensions)


def test_the_schema_drops_evidence_when_spans_are_not_required():
    from specjudge.judge.evaluator import response_schema

    rules = _rules()
    rules.require_spans = False
    schema = response_schema(rules)
    assert "evidence" not in schema["properties"]
    assert "evidence" not in schema["required"]


def test_the_schema_is_sent_with_every_judge_call():
    from specjudge.judge.evaluator import response_schema

    client = _FakeClient([_VALID])
    estimate_demand(_analysis(), _rules(), client, "judge")
    assert client.schemas == [response_schema(_rules())]


def test_a_bracketed_citation_of_a_real_fragment_is_accepted():
    """llama3.1 copies the brackets it sees; punctuation should not fail a valid id."""
    evidence = dict.fromkeys(_ALL_DIMS, f"[{_CITED}]")
    client = _FakeClient([_answer(dict.fromkeys(_ALL_DIMS, "medium"), evidence)])
    demand = estimate_demand(_analysis(), _rules(), client, "judge")

    assert all(e.status is EvidenceStatus.GROUNDED for e in demand.evidence.values())
    assert demand.evidence["reasoning"].fragment_id == _CITED


def test_decoration_does_not_rescue_a_fabricated_id():
    """Normalising punctuation must not become forgiving about the id itself."""
    evidence = dict.fromkeys(_ALL_DIMS, "[S:FR-999]")
    client = _FakeClient([_answer(dict.fromkeys(_ALL_DIMS, "medium"), evidence)])
    with pytest.raises(JudgeUnavailableError):
        estimate_demand(_analysis(), _rules(), client, "judge")


# ------------------------------------------- bulk and outliers (issue #3)


def _judge_answer(**extra):
    """A well-formed answer with citations, plus whatever the test is about."""
    answer = {
        "dimensions": {"reasoning": "top", "size": "medium", "domain_specialization": "low"},
        "evidence": {
            "reasoning": "S:FR-001",
            "size": "S:FR-001",
            "domain_specialization": "S:FR-001",
        },
        "justification": "because",
    }
    answer.update(extra)
    return answer


def _parsed(answer, request_bulk=True, **rule_kwargs):
    from specjudge.domain import Fragment
    from specjudge.judge.evaluator import _parse_demand

    rules = _rules()
    for key, value in rule_kwargs.items():
        setattr(rules, key, value)
    fragments = [Fragment("S:FR-001", "spec", "**FR-001**: it MUST hold")]
    return _parse_demand(answer, rules, fragments, request_bulk)


def test_a_bulk_below_the_peak_is_kept():
    profile = _parsed(
        _judge_answer(
            bulk={"reasoning": "medium", "size": "medium", "domain_specialization": "low"}
        )
    )
    assert profile.bulk["reasoning"] == "medium"
    assert profile.distinguishes_bulk is True


def test_a_missing_bulk_is_not_invented():
    """Degrading to the peak is conservative; interpolating one is not (FR-027)."""
    profile = _parsed(_judge_answer())
    assert profile.bulk == {}
    assert profile.bulk_dimensions == profile.scored_dimensions


def test_a_bulk_above_the_peak_is_dropped():
    """The peak is the hardest part by definition, so this is self-contradiction.

    Keeping it would let a confused judge raise the floor of the recommendation.
    """
    profile = _parsed(
        _judge_answer(bulk={"reasoning": "top", "size": "top", "domain_specialization": "top"})
    )
    assert "size" not in profile.bulk
    assert "domain_specialization" not in profile.bulk


def test_a_malformed_bulk_does_not_fail_the_run():
    """An optional field must never be able to reject an otherwise good profile."""
    profile = _parsed(_judge_answer(bulk=["not", "a", "map"]))
    assert profile.dimensions["reasoning"] == "top"
    assert profile.bulk == {}


def test_outliers_are_normalised_and_deduplicated():
    profile = _parsed(_judge_answer(outliers=["[S:FR-001]", "S:FR-001", " T:T009 "]))
    assert profile.outliers == ["S:FR-001", "T:T009"]


def test_an_outlier_that_does_not_exist_is_not_fatal():
    """A fabricated *citation* rejects the profile; a stray id in a list is noise.

    Conflating them would let an optional field fail a run that is otherwise sound.
    """
    profile = _parsed(_judge_answer(outliers=["S:NOPE"]))
    assert profile.outliers == ["S:NOPE"]
    assert profile.dimensions["reasoning"] == "top"


def test_a_bulk_offered_by_a_judge_that_was_not_asked_is_ignored():
    """A small judge answers the fields it was not given; none of that is kept."""
    profile = _parsed(
        _judge_answer(bulk={"reasoning": "low", "size": "low", "domain_specialization": "low"}),
        request_bulk=False,
    )
    assert profile.bulk == {}


def test_the_prompt_asks_for_the_bulk_only_when_requested():
    analysis = ProjectAnalysis(
        artifacts=[SDDArtifact("spec", "s.md", True, True, "- **FR-001**: it MUST hold\n")],
        data_state=DataState.SUFFICIENT,
    )
    assert '"bulk"' in build_prompt(analysis, _rules(), request_bulk=True)
    assert '"bulk"' not in build_prompt(analysis, _rules())


# ------------------------------------------- who gets asked (measured, issue #3)


@pytest.mark.parametrize(
    ("params_b", "asked"),
    [(24.0, True), (70.0, True), (8.0, False), (20.0, False), (None, False)],
)
def test_only_judges_big_enough_are_asked_for_the_split(params_b, asked):
    """Measured on the corpus: the extra fields make an 8B judge worse.

    It loses about five points of accuracy on the levels it was already getting
    right, and refuses two to three times as often. Capacity a judge does not have
    is not free, so it is not spent — the same reasoning as the compact prompt.
    """
    from specjudge.judge.evaluator import use_bulk_prompt

    assert use_bulk_prompt(params_b, _rules()) is asked


def test_the_master_switch_overrides_the_threshold():
    from specjudge.judge.evaluator import use_bulk_prompt

    rules = _rules()
    rules.request_bulk = False
    assert use_bulk_prompt(70.0, rules) is False
