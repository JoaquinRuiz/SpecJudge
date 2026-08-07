"""Reading whatever written context a project has (issue #16 / FR-024).

Two properties matter here and they pull in opposite directions:

* a repository with only an `AGENTS.md` must now get an answer, where before it
  got a refusal;
* that answer must not pretend to be the same answer a described project gets.

So most of these tests are about what the output *says about itself* — which
sources were read, and whether anything described the work — as much as about
whether a recommendation came out.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specjudge.artifacts import read_project
from specjudge.domain import DataState, RatingRules
from specjudge.sources import is_environment


def _rules() -> RatingRules:
    return RatingRules(
        version=1,
        dimensions=["reasoning", "size", "domain_specialization"],
        scarce_thresholds={"min_detailed_tasks": 3},
        per_dimension={"exact": "good"},
        aggregation="worst_dimension",
    )


_AGENTS = (
    "# AGENTS.md\n\n## Rules\n"
    "- Money is integer minor units, never a float.\n"
    "- Netting must replay deterministically from the message log.\n"
)
_CLAUDE = "# CLAUDE.md\n\n## Conventions\n- Run the golden suite before pushing.\n"
_TASKS = (
    "# Tasks\n"
    "- [ ] T001 Implement the loader in src/loader.py\n"
    "- [ ] T002 Add the rule registry in src/rules.py\n"
    "- [ ] T003 Wire the CLI entrypoint in src/cli.py\n"
)
_SPEC = "# Spec\n\n## Requirements\n- **FR-001**: It must do the thing.\n"
_CONSTITUTION = "# Constitution\n\n### I. Simplicity\nKeep it simple.\n"
_PLAN = "# Plan\n\n## Stack\n- Kotlin on Android, no third-party crypto.\n"


def _project(tmp_path: Path, files: dict[str, str]) -> Path:
    """Write a project from `relative path -> content`."""
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    return tmp_path


# ------------------------------------------------------------------ discovery


def test_agent_context_files_are_read(tmp_path):
    analysis = read_project(_project(tmp_path, {"AGENTS.md": _AGENTS}), _rules())
    agents = analysis.artifact("agents")
    assert agents is not None and agents.usable
    assert "integer minor units" in agents.content


def test_claude_md_is_read_too(tmp_path):
    analysis = read_project(_project(tmp_path, {"CLAUDE.md": _CLAUDE}), _rules())
    assert analysis.sources_read == ["claude"]


def test_the_plan_is_read_alongside_the_spec(tmp_path):
    """`plan.md` sat beside the spec all along and was simply never opened."""
    project = _project(
        tmp_path,
        {
            ".specify/memory/constitution.md": _CONSTITUTION,
            "specs/001-f/spec.md": _SPEC,
            "specs/001-f/tasks.md": _TASKS,
            "specs/001-f/plan.md": _PLAN,
        },
    )
    analysis = read_project(project, _rules())
    assert "plan" in analysis.sources_read
    plan = analysis.artifact("plan")
    assert plan is not None and "no third-party crypto" in plan.content


def test_a_missing_source_is_not_reported_as_read(tmp_path):
    analysis = read_project(_project(tmp_path, {"AGENTS.md": _AGENTS}), _rules())
    assert analysis.sources_read == ["agents"]


def test_both_kinds_of_source_are_read_when_both_exist(tmp_path):
    """Neither wins: the environment and the work carry signal that does not overlap."""
    project = _project(
        tmp_path,
        {
            ".specify/memory/constitution.md": _CONSTITUTION,
            "specs/001-f/spec.md": _SPEC,
            "specs/001-f/tasks.md": _TASKS,
            "AGENTS.md": _AGENTS,
        },
    )
    analysis = read_project(project, _rules())
    assert analysis.sources_read == ["constitution", "spec", "tasks", "agents"]
    assert analysis.environment_only is False


# ------------------------------------------------------------------ classification


def test_environment_context_alone_yields_a_floor_rather_than_a_refusal(tmp_path):
    """The case the issue is about: a repository that documents itself, no spec."""
    analysis = read_project(_project(tmp_path, {"AGENTS.md": _AGENTS}), _rules())
    assert analysis.data_state is DataState.SCARCE
    assert analysis.environment_only is True


def test_the_floor_says_out_loud_that_it_is_a_floor(tmp_path):
    """Degrading quietly would be worse than refusing (Principle IV)."""
    analysis = read_project(_project(tmp_path, {"AGENTS.md": _AGENTS}), _rules())
    assert any("floor" in w for w in analysis.warnings)
    # Named as the file the user would go and look at, not as an internal kind.
    assert any("AGENTS.md" in w for w in analysis.warnings)


def test_an_empty_repository_is_still_insufficient(tmp_path):
    """Reading more sources must not turn "nothing to go on" into a guess."""
    analysis = read_project(tmp_path, _rules())
    assert analysis.data_state is DataState.INSUFFICIENT
    assert analysis.sources_read == []
    assert analysis.environment_only is False


def test_an_unreadable_agents_file_does_not_count_as_context(tmp_path):
    (tmp_path / "AGENTS.md").write_text("   \n\n", encoding="utf-8")
    analysis = read_project(tmp_path, _rules())
    assert analysis.data_state is DataState.INSUFFICIENT


def test_tasks_still_decide_the_state_when_they_exist(tmp_path):
    """Environment context is additive; it never lowers a described project."""
    project = _project(
        tmp_path,
        {
            ".specify/memory/constitution.md": _CONSTITUTION,
            "specs/001-f/spec.md": _SPEC,
            "specs/001-f/tasks.md": _TASKS,
            "AGENTS.md": _AGENTS,
        },
    )
    analysis = read_project(project, _rules())
    assert analysis.data_state is DataState.SUFFICIENT
    assert analysis.warnings == []


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("agents", True),
        ("claude", True),
        ("cursor", True),
        ("copilot", True),
        ("adr", True),
        ("spec", False),
        ("tasks", False),
        ("plan", False),
    ],
)
def test_environment_kinds_are_classified(kind, expected):
    assert is_environment(kind) is expected
