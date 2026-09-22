"""Copilot path-specific instructions and the `applyTo` decision (issue #33 / FR-024).

Two things are pinned here. The glob semantics, because `applyTo` uses VS Code's
rules rather than `fnmatch`'s and the difference is silent: under `fnmatch` every
pattern would be recursive and every file would look applicable. And the verdicts,
because "not applicable" and "not found" produce the same visible result — nothing
in the prompt — and only the reported reason separates them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specjudge.artifacts import read_project
from specjudge.discovery import instruction_files, repository_paths
from specjudge.domain import InstructionsMode
from specjudge.instructions import (
    compile_patterns,
    decide,
    first_match,
    parse_apply_to,
    planned_paths,
    split_patterns,
)
from specjudge.rating import load_rules


def _write(root: Path, relative: str, content: str) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _instructions(
    root: Path, name: str, apply_to: str | None, body: str = "Use records.\n"
) -> Path:
    front = "---\n" + (f'applyTo: "{apply_to}"\n' if apply_to is not None else "") + "---\n"
    return _write(root, f".github/instructions/{name}", front + body)


def _matches(pattern: str, path: str) -> bool:
    return first_match(compile_patterns(pattern), [path]) is not None


# ------------------------------------------------------------------ frontmatter


def test_apply_to_is_read_from_the_frontmatter(tmp_path):
    path = _instructions(tmp_path, "backend.instructions.md", "**/*.java")
    assert parse_apply_to(path.read_text()) == "**/*.java"


def test_a_file_without_apply_to_reports_none(tmp_path):
    path = _instructions(tmp_path, "general.instructions.md", None)
    assert parse_apply_to(path.read_text()) is None


def test_a_file_without_frontmatter_reports_none(tmp_path):
    path = _write(tmp_path, ".github/instructions/bare.instructions.md", "Just prose.\n")
    assert parse_apply_to(path.read_text()) is None


def test_a_horizontal_rule_further_down_is_not_frontmatter():
    assert parse_apply_to('# Title\n\n---\napplyTo: "**"\n---\n') is None


def test_broken_frontmatter_degrades_to_no_glob():
    assert parse_apply_to('---\napplyTo: "unclosed\n---\n') is None


def test_a_yaml_list_carries_the_same_meaning_as_the_comma_form():
    assert (
        parse_apply_to("---\napplyTo:\n  - '**/*.ts'\n  - '**/*.tsx'\n---\n") == "**/*.ts,**/*.tsx"
    )


def test_comma_separated_patterns_are_split():
    assert split_patterns("**/*.tsx,**/*.jsx") == ["**/*.tsx", "**/*.jsx"]


# ------------------------------------------------------------------ glob semantics


@pytest.mark.parametrize(
    "pattern,path",
    [
        ("**/*.java", "src/main/java/com/acme/FooService.java"),
        # `**/` spans zero directories too, so a root-level file still matches.
        ("**/*.java", "Foo.java"),
        ("**", "anything/at/all.txt"),
        ("src/**", "src/a/b/c.ts"),
        ("*.md", "README.md"),
        ("src/*.ts", "src/index.ts"),
        ("**/*.tsx,**/*.jsx", "app/ui/Button.jsx"),
        ("./src/**/*.py", "src/pkg/mod.py"),
    ],
)
def test_globs_that_must_match(pattern, path):
    assert _matches(pattern, path)


@pytest.mark.parametrize(
    "pattern,path",
    [
        # The bug `fnmatch` would introduce: a single star must not cross a slash.
        ("*.java", "src/main/java/Foo.java"),
        ("src/*.ts", "src/nested/index.ts"),
        ("**/*.java", "src/main/java/Foo.kt"),
        ("docs/**", "src/index.ts"),
    ],
)
def test_globs_that_must_not_match(pattern, path):
    assert not _matches(pattern, path)


def test_a_dot_in_the_pattern_is_literal():
    assert not _matches("**/*.java", "src/mainxjava")


# ------------------------------------------------------------------ planned paths


def test_paths_the_tasks_promise_are_extracted():
    tasks = "- [ ] T004 Create `src/main/java/com/acme/FooService.java` with the port\n"
    assert "src/main/java/com/acme/FooService.java" in planned_paths([tasks])


def test_version_numbers_are_not_paths():
    assert planned_paths(["Bump to v1.2 and then 0.5.5 for the release"]) == []


def test_a_bare_filename_still_counts():
    assert "Dockerfile.dev" in planned_paths(["Add Dockerfile.dev for local runs"])


# ------------------------------------------------------------------ the verdicts


def _decide(tmp_path, apply_to, repo=(), planned=(), mode=InstructionsMode.MATCHING):
    path = _instructions(tmp_path, "backend.instructions.md", apply_to)
    return decide([(path, path.read_text())], list(repo), list(planned), mode, tmp_path)[0]


def test_an_existing_repository_file_makes_it_apply(tmp_path):
    verdict = _decide(tmp_path, "**/*.java", repo=["src/main/java/com/acme/Foo.java"])
    assert verdict.included
    assert "repository" in verdict.reason


def test_a_planned_path_makes_it_apply_before_the_file_exists(tmp_path):
    verdict = _decide(tmp_path, "**/*.java", planned=["src/main/java/com/acme/FooService.java"])
    assert verdict.included
    assert "plan or tasks" in verdict.reason


def test_an_unrelated_stack_does_not_apply(tmp_path):
    verdict = _decide(tmp_path, "**/*.tsx", repo=["src/main/java/com/acme/Foo.java"])
    assert not verdict.included
    assert verdict.reason == "applyTo matched no repository file and no planned path"


def test_a_missing_apply_to_is_not_auto_applied(tmp_path):
    """VS Code does not auto-apply these, so neither does SpecJudge."""
    verdict = _decide(tmp_path, None, repo=["src/main/java/Foo.java"])
    assert not verdict.included
    assert verdict.reason == "no applyTo, not auto-applied"


def test_all_mode_includes_everything_including_the_glob_less(tmp_path):
    verdict = _decide(tmp_path, None, mode=InstructionsMode.ALL)
    assert verdict.included
    assert verdict.reason == "sources.instructions: all"


def test_every_file_gets_a_verdict_whether_or_not_it_applies(tmp_path):
    java = _instructions(tmp_path, "backend.instructions.md", "**/*.java")
    react = _instructions(tmp_path, "frontend.instructions.md", "**/*.tsx")
    verdicts = decide(
        [(p, p.read_text()) for p in (java, react)],
        ["src/main/java/Foo.java"],
        [],
        InstructionsMode.MATCHING,
        tmp_path,
    )
    assert [(v.path, v.included) for v in verdicts] == [
        (".github/instructions/backend.instructions.md", True),
        (".github/instructions/frontend.instructions.md", False),
    ]


# ------------------------------------------------------------------ discovery


def test_only_instructions_files_are_discovered(tmp_path):
    _instructions(tmp_path, "backend.instructions.md", "**/*.java")
    _write(tmp_path, ".github/instructions/review.prompt.md", "A saved prompt\n")
    _write(tmp_path, ".github/instructions/architect.chatmode.md", "A persona\n")
    found = [p.name for p in instruction_files(tmp_path)]
    assert found == ["backend.instructions.md"]


def test_nested_instruction_files_are_found(tmp_path):
    _instructions(tmp_path, "java/backend.instructions.md", "**/*.java")
    assert [p.name for p in instruction_files(tmp_path)] == ["backend.instructions.md"]


def test_no_directory_is_not_an_error(tmp_path):
    assert instruction_files(tmp_path) == []


def test_repository_paths_falls_back_to_a_walk_without_git(tmp_path):
    _write(tmp_path, "src/main/java/com/acme/deep/nested/Foo.java", "class Foo {}\n")
    _write(tmp_path, "node_modules/pkg/index.js", "// vendored\n")
    paths = repository_paths(tmp_path)
    assert "src/main/java/com/acme/deep/nested/Foo.java" in paths
    assert not any(p.startswith("node_modules/") for p in paths)


def test_the_walk_fallback_goes_deeper_than_the_context_walk(tmp_path):
    """`MAX_DEPTH` bounds the context walk; `**/*.java` has to see past it."""
    _write(tmp_path, "a/b/c/d/e/f/Deep.java", "class Deep {}\n")
    assert "a/b/c/d/e/f/Deep.java" in repository_paths(tmp_path)


# ------------------------------------------------------------------ end to end


def _project(tmp_path) -> Path:
    _write(tmp_path, ".specify/memory/constitution.md", "# Constitution\n\nKeep it short.\n")
    _write(tmp_path, "specs/001-feature/spec.md", "# Spec\n\nA Java service.\n")
    _write(
        tmp_path,
        "specs/001-feature/tasks.md",
        "- [ ] T001 Create src/main/java/com/acme/FooService.java with the port\n"
        "- [ ] T002 Wire the controller into the existing module\n"
        "- [ ] T003 Add the integration test for the new endpoint\n",
    )
    return tmp_path


def test_an_applicable_file_reaches_the_judge_as_context(tmp_path):
    _project(tmp_path)
    _instructions(
        tmp_path, "backend.instructions.md", "**/*.java", "Prefer constructor injection.\n"
    )
    analysis = read_project(tmp_path, load_rules())

    assert "instructions" in analysis.source_kinds
    content = " ".join(a.content for a in analysis.artifacts if a.type == "instructions")
    assert "constructor injection" in content


def test_an_inapplicable_file_is_reported_rather_than_dropped(tmp_path):
    _project(tmp_path)
    _instructions(tmp_path, "frontend.instructions.md", "**/*.tsx", "Prefer function components.\n")
    analysis = read_project(tmp_path, load_rules())

    assert "instructions" not in analysis.source_kinds
    assert [(i.path, i.included) for i in analysis.instructions] == [
        (".github/instructions/frontend.instructions.md", False)
    ]
    assert any("frontend.instructions.md" in w for w in analysis.warnings)


def test_a_project_without_instructions_reports_nothing(tmp_path):
    _project(tmp_path)
    analysis = read_project(tmp_path, load_rules())
    assert analysis.instructions == []
