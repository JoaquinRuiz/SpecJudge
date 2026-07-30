"""Citable fragment extraction (issue #1 / FR-020).

The extractor is the single source of truth shared by both prompt shapes and the
validator. If it drifts, the judge is offered ids the validator rejects — or worse,
accepts ids the judge never saw.
"""

from __future__ import annotations

from specjudge.domain import DataState, Fragment, ProjectAnalysis, SDDArtifact
from specjudge.judge.fragments import (
    MAX_FRAGMENT_CHARS,
    extract_fragments,
    quote_matches,
    render_catalogue,
)

LIMIT = 8000


def _analysis(*artifacts: SDDArtifact) -> ProjectAnalysis:
    return ProjectAnalysis(artifacts=list(artifacts), data_state=DataState.SUFFICIENT)


def _artifact(type_: str, content: str) -> SDDArtifact:
    return SDDArtifact(type_, f"{type_}.md", True, True, content)


def _ids(analysis: ProjectAnalysis, limit: int = LIMIT) -> list[str]:
    return [f.id for f in extract_fragments(analysis, limit)]


# ------------------------------------------------------------------ id scheme


def test_requirement_ids_become_fragment_ids():
    analysis = _analysis(_artifact("spec", "- **FR-001**: do it\n- **SC-002**: fast\n"))
    assert _ids(analysis) == ["S:FR-001", "S:SC-002"]


def test_task_ids_become_fragment_ids():
    analysis = _analysis(_artifact("tasks", "- [ ] T001 Build it\n- [ ] T002 Test it\n"))
    assert _ids(analysis) == ["T:T001", "T:T002"]


def test_artifact_prefix_keeps_same_named_units_apart():
    """A spec and a tasks file can both mention T001; the ids must not collide."""
    analysis = _analysis(
        _artifact("spec", "- [ ] T001 In the spec\n"),
        _artifact("tasks", "- [ ] T001 In the tasks\n"),
    )
    assert _ids(analysis) == ["S:T001", "T:T001"]


def test_unnamed_units_get_positional_ids():
    analysis = _analysis(_artifact("constitution", "## Simplicity First\n## Tested Behavior\n"))
    assert _ids(analysis) == ["C:1", "C:2"]


def test_ids_are_stable_across_calls():
    analysis = _analysis(_artifact("tasks", "- [ ] T001 a\n- [ ] T002 b\n## Heading\n"))
    assert _ids(analysis) == _ids(analysis)


def test_duplicate_ids_are_kept_once():
    analysis = _analysis(_artifact("spec", "- **FR-001**: first\n- **FR-001**: repeated\n"))
    assert _ids(analysis) == ["S:FR-001"]


# ------------------------------------------------------- what counts as citable


def test_unreadable_and_empty_artifacts_contribute_nothing():
    analysis = _analysis(
        SDDArtifact("spec", "s.md", True, False, "- **FR-001**: unreadable"),
        SDDArtifact("tasks", "t.md", True, True, ""),
    )
    assert _ids(analysis) == []


def test_prose_without_units_yields_no_fragments():
    """Nothing citable is a real outcome, not an error — it becomes `unsupported`."""
    analysis = _analysis(_artifact("spec", "Just a paragraph of prose with no structure.\n"))
    assert _ids(analysis) == []


def test_fragment_text_is_capped():
    analysis = _analysis(_artifact("tasks", f"- [ ] T001 {'x' * 900}\n"))
    (fragment,) = extract_fragments(analysis, LIMIT)
    assert len(fragment.text) <= MAX_FRAGMENT_CHARS


# -------------------------------------------------------------------- truncation


def test_truncated_content_is_not_citable():
    """A fragment cut from the prompt must not be in the set the judge may cite.

    Otherwise the validator would accept a citation the judge could not possibly
    have read — the exact hole this feature is meant to close.
    """
    content = "- [ ] T001 Early item\n" + "filler. " * 400 + "\n- [ ] T999 Late item\n"
    analysis = _analysis(_artifact("tasks", content))

    assert "T:T999" in _ids(analysis, limit=100_000)
    assert "T:T999" not in _ids(analysis, limit=60)


# ---------------------------------------------------------------------- quotes


def _fragment(text: str) -> Fragment:
    return Fragment(id="T:T001", artifact_type="tasks", text=text)


def test_quote_matches_exact_text():
    assert quote_matches("Build the parser", _fragment("T001 Build the parser now"))


def test_quote_matching_ignores_whitespace_and_case():
    assert quote_matches("build   THE\nparser", _fragment("T001 Build the parser now"))


def test_quote_matching_folds_smart_punctuation():
    assert quote_matches("the user's spec", _fragment("T001 Read the user’s spec"))


def test_quote_matching_rejects_absent_text():
    assert not quote_matches("something else entirely", _fragment("T001 Build the parser"))


def test_empty_quote_never_matches():
    assert not quote_matches("   ", _fragment("T001 Build the parser"))


# -------------------------------------------------------------------- rendering


def test_catalogue_lists_every_fragment_with_its_id():
    analysis = _analysis(_artifact("tasks", "- [ ] T001 Build it\n"))
    rendered = render_catalogue(extract_fragments(analysis, LIMIT))
    assert "[T:T001]" in rendered
    assert "Build it" in rendered


def test_catalogue_says_so_when_there_is_nothing_to_cite():
    assert "no citable fragments" in render_catalogue([])
