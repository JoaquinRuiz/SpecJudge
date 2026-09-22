"""Sharing the prompt between sources (issue #16 / FR-025).

The property that matters most is the last one here: what the judge is shown and
what it is allowed to cite come from the same place. Everything else is about the
prompt not growing without bound as a repository contributes more files.
"""

from __future__ import annotations

from specjudge.budget import dropped_sources, prompt_sources
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


# ------------------------------------------- instructions get their own pool (#33)


def test_instructions_cannot_crowd_out_the_broad_context():
    """A project documents one AGENTS.md and one `.instructions.md` per stack.

    In a single pool the narrow files win by sheer number, and the file describing
    the whole repository gets thinner the more stacks the project documents.
    """
    analysis = _analysis(
        _artifact("agents", "a" * 5000),
        *[
            _artifact("instructions", "i" * 5000, f".github/instructions/{i}.instructions.md")
            for i in range(8)
        ],
    )
    texts = {s.path: s.text for s in prompt_sources(analysis, LIMIT)}
    assert len(texts["agents.md"]) >= LIMIT // 2


def test_the_two_pools_together_still_cost_what_one_artifact_costs():
    analysis = _analysis(
        _artifact("agents", "a" * 5000),
        _artifact("instructions", "i" * 5000, ".github/instructions/backend.instructions.md"),
    )
    assert sum(len(s.text) for s in prompt_sources(analysis, LIMIT)) <= LIMIT


def test_a_project_without_instructions_is_budgeted_exactly_as_before():
    """The split must be invisible until there is something to split."""
    analysis = _analysis(
        _artifact("agents", "a" * 5000),
        _artifact("claude", "c" * 300, "CLAUDE.md"),
        _artifact("adr", "d" * 5000, "docs/adr/0001-x.md"),
    )
    texts = _by_type(prompt_sources(analysis, LIMIT))
    assert len(texts["claude"]) == 300
    assert len(texts["agents"]) + len(texts["adr"]) == LIMIT - 300


def test_an_unused_half_flows_to_the_other_group():
    """Water-filling at the group level, so a short pool releases its remainder."""
    analysis = _analysis(
        _artifact("agents", "a" * 5000),
        _artifact("instructions", "i" * 50, ".github/instructions/backend.instructions.md"),
    )
    texts = _by_type(prompt_sources(analysis, LIMIT))
    assert len(texts["instructions"]) == 50
    assert len(texts["agents"]) == LIMIT - 50


# ------------------------------------ a share too small to be worth it (#35)


def test_sources_are_dropped_rather_than_cut_into_slivers():
    """Four sources read properly say more than sixteen cut mid-sentence."""
    analysis = _analysis(
        *[_artifact("agents", "a" * 5000, f"a{i}.md") for i in range(16)],
    )
    sources = prompt_sources(analysis, LIMIT)
    assert len(sources) < 16
    assert all(len(s.text) >= 200 for s in sources)


def test_what_the_floor_dropped_is_reported():
    analysis = _analysis(*[_artifact("agents", "a" * 5000, f"a{i}.md") for i in range(16)])
    kept = {s.path for s in prompt_sources(analysis, LIMIT)}
    dropped = {a.path for a in dropped_sources(analysis, LIMIT)}
    assert dropped
    assert kept.isdisjoint(dropped)
    assert kept | dropped == {f"a{i}.md" for i in range(16)}


def test_a_short_source_is_complete_not_truncated():
    """A 40-character .cursorrules is the whole file, so the floor must not eat it."""
    analysis = _analysis(
        _artifact("agents", "a" * 5000),
        _artifact("cursor", "be terse", ".cursorrules"),
    )
    texts = _by_type(prompt_sources(analysis, LIMIT))
    assert texts["cursor"] == "be terse"
    assert dropped_sources(analysis, LIMIT) == []


def test_at_least_one_source_survives_any_budget():
    """A floor that silenced everything would answer a small budget with nothing."""
    analysis = _analysis(_artifact("agents", "a" * 5000))
    sources = prompt_sources(analysis, 50)
    assert [s.type for s in sources] == ["agents"]


def test_sources_that_clear_the_floor_are_budgeted_as_before():
    analysis = _analysis(
        _artifact("agents", "a" * 5000),
        _artifact("claude", "c" * 5000, "CLAUDE.md"),
    )
    texts = _by_type(prompt_sources(analysis, LIMIT))
    assert len(texts["agents"]) == 500
    assert len(texts["claude"]) == 500
    assert dropped_sources(analysis, LIMIT) == []


def test_the_work_artifacts_are_never_dropped_by_the_floor():
    analysis = _analysis(
        _artifact("spec", "s" * 5000),
        _artifact("tasks", "t" * 5000),
        *[_artifact("agents", "a" * 5000, f"a{i}.md") for i in range(16)],
    )
    types = {s.type for s in prompt_sources(analysis, LIMIT)}
    assert {"spec", "tasks"} <= types


def test_a_dropped_source_is_not_citable():
    """FR-020: the judge may only cite what it was actually shown."""
    from specjudge.judge.fragments import extract_fragments

    analysis = _analysis(
        *[_artifact("agents", f"# Heading {i}\n" + "a" * 5000, f"a{i}.md") for i in range(16)]
    )
    shown = "".join(s.text for s in prompt_sources(analysis, LIMIT))
    for fragment in extract_fragments(analysis, LIMIT):
        assert fragment.text[:40] in shown
