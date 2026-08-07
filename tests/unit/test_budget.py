"""Sharing the prompt between sources (issue #16 / FR-025).

The property that matters most is the last one here: what the judge is shown and
what it is allowed to cite come from the same place. Everything else is about the
prompt not growing without bound as a repository contributes more files.
"""

from __future__ import annotations

from specjudge.budget import prompt_sources
from specjudge.domain import DataState, ProjectAnalysis, SDDArtifact

LIMIT = 1000


def _artifact(type_: str, content: str, path: str | None = None) -> SDDArtifact:
    return SDDArtifact(type_, path or f"{type_}.md", True, True, content)


def _analysis(*artifacts: SDDArtifact, root: str = "") -> ProjectAnalysis:
    return ProjectAnalysis(artifacts=list(artifacts), data_state=DataState.SUFFICIENT, root=root)


def _by_type(sources) -> dict[str, str]:
    return {s.type: s.text for s in sources}


# ------------------------------------------------------------------ the budget


def test_work_artifacts_keep_the_full_per_artifact_cap():
    analysis = _analysis(_artifact("spec", "s" * 5000), _artifact("tasks", "t" * 5000))
    texts = _by_type(prompt_sources(analysis, LIMIT))
    assert len(texts["spec"]) == LIMIT
    assert len(texts["tasks"]) == LIMIT


def test_environment_sources_share_one_budget():
    """Twelve caps of N is not a cap. Together they cost what one artifact costs."""
    analysis = _analysis(*[_artifact("agents", "a" * 5000, f"a{i}.md") for i in range(4)])
    sources = prompt_sources(analysis, LIMIT)
    assert sum(len(s.text) for s in sources) <= LIMIT


def test_a_short_source_costs_only_what_it_is():
    """Equal shares would charge a 20-character .cursorrules a quarter of the budget."""
    analysis = _analysis(
        _artifact("claude", "short rule"),
        _artifact("agents", "a" * 5000),
    )
    texts = _by_type(prompt_sources(analysis, LIMIT))
    assert texts["claude"] == "short rule"
    # What the short one did not need went to the long one, rather than being lost.
    assert len(texts["agents"]) == LIMIT - len("short rule")


def test_the_work_budget_is_not_spent_on_the_environment():
    analysis = _analysis(_artifact("spec", "s" * 5000), _artifact("agents", "a" * 5000))
    texts = _by_type(prompt_sources(analysis, LIMIT))
    assert len(texts["spec"]) == LIMIT
    assert len(texts["agents"]) == LIMIT


def test_allocation_is_deterministic():
    """Fragment ids are derived from what survives this, so it cannot wobble."""
    analysis = _analysis(*[_artifact("agents", "a" * (100 * i), f"a{i}.md") for i in range(1, 6)])
    first = [len(s.text) for s in prompt_sources(analysis, LIMIT)]
    assert first == [len(s.text) for s in prompt_sources(analysis, LIMIT)]


def test_a_source_squeezed_to_nothing_is_not_offered():
    analysis = _analysis(*[_artifact("agents", "a" * 500, f"a{i}.md") for i in range(20)])
    sources = prompt_sources(analysis, 10)
    assert all(s.text.strip() for s in sources)


def test_truncation_lands_on_a_line_boundary():
    """A fragment cut mid-sentence says less than the line it came from."""
    content = "- first rule about money\n- second rule about ordering\n- third rule\n"
    analysis = _analysis(_artifact("agents", content))
    (source,) = prompt_sources(analysis, 40)
    assert source.text == "- first rule about money"


def test_a_budget_too_small_for_one_line_still_cuts():
    analysis = _analysis(_artifact("agents", "a single very long line with no break at all"))
    (source,) = prompt_sources(analysis, 10)
    assert source.text == "a single v"


# ------------------------------------------------------------------ labelling


def test_sources_are_labelled_by_their_path_within_the_project():
    analysis = _analysis(
        _artifact("agents", "- root", "/repo/AGENTS.md"),
        _artifact("agents", "- api", "/repo/packages/api/AGENTS.md"),
        root="/repo",
    )
    assert [s.label for s in prompt_sources(analysis, LIMIT)] == [
        "agents (AGENTS.md)",
        "agents (packages/api/AGENTS.md)",
    ]


def test_a_path_outside_the_project_falls_back_to_the_kind():
    """Never leak this machine's directory layout into the prompt."""
    analysis = _analysis(
        _artifact("agents", "- rule", "/elsewhere/AGENTS.md"),
        _artifact("agents", "- other", "/elsewhere/other/AGENTS.md"),
        root="/repo",
    )
    assert [s.label for s in prompt_sources(analysis, LIMIT)] == ["agents", "agents"]


def test_a_lone_file_of_its_kind_is_labelled_by_kind_alone():
    """Nothing to disambiguate, and changing a prompt that worked has a cost."""
    analysis = _analysis(_artifact("spec", "- **FR-001**: it", "/repo/spec.md"), root="/repo")
    assert prompt_sources(analysis, LIMIT)[0].label == "spec"


# ------------------------------------------------- agreement with the citable set


def test_fragments_come_from_exactly_the_budgeted_text():
    """A fragment the budget cut is not citable, or the validator accepts fiction."""
    from specjudge.judge.fragments import extract_fragments

    analysis = _analysis(
        _artifact("agents", "- **FR-001**: early rule\n" + "x" * 4000, "a1.md"),
        _artifact("agents", "- **FR-999**: late rule\n" + "y" * 4000, "a2.md"),
    )
    sent = "".join(s.text for s in prompt_sources(analysis, 60))
    for fragment in extract_fragments(analysis, 60):
        assert fragment.text[:20] in sent
