"""Finding whatever written context a project already has (FR-024).

SpecJudge used to read three files in `.specify/` and nothing else, which limited it
to people already running a full Spec-Driven Development workflow. Meanwhile most
repositories carry written context the tool ignored: `AGENTS.md` is in tens of
thousands of them, `CLAUDE.md` in many more.

Reading them is only safe because of FR-020. Before cited evidence existed, this
would have needed per-format trust rules — deciding in advance how much to believe a
`CLAUDE.md` versus a spec — which is unmaintainable across formats that each evolve
separately. Now the source does not matter: a dimension that cannot be grounded in a
citation comes back `unsupported` and leaves the calculation, so a thin source
produces a thin profile on its own.

Two kinds of source, carrying different signal and both worth reading:

* **environment** — `AGENTS.md`, `CLAUDE.md`. How hard this repository is to work in
  at all: domain, constraints, testing rigour. Identical whether you are fixing a
  typo or rewriting authentication.
* **work** — constitution, spec, tasks, plan. What is about to be built.

Picking one over the other would discard signal that does not overlap, so both are
read whenever both exist.
"""

from __future__ import annotations

from pathlib import Path

# kind -> whether the source describes the work, or the environment it happens in.
WORK_KINDS = ("constitution", "spec", "tasks", "plan")
ENVIRONMENT_KINDS = ("agents", "claude")

# Discovery order is stable so fragment ids and prompts do not shuffle between runs.
_ENVIRONMENT_FILES: tuple[tuple[str, str], ...] = (
    ("agents", "AGENTS.md"),
    ("claude", "CLAUDE.md"),
)


def is_environment(kind: str) -> bool:
    return kind in ENVIRONMENT_KINDS


def environment_paths(project_path: Path) -> list[tuple[str, Path]]:
    """Agent-context files at the repository root, in a fixed order.

    Root only in this release. Nested files (the Codex repo has 88 `AGENTS.md`)
    need per-source caps before they can be read without swamping the judge's
    prompt, which is the next piece of work rather than this one.
    """
    return [(kind, project_path / name) for kind, name in _ENVIRONMENT_FILES]


def plan_path(feature_dir: Path | None, project_path: Path) -> Path:
    """spec-kit's `plan.md`, which carries stack and architecture decisions.

    It sits beside the spec and the tasks and was simply never read.
    """
    return (feature_dir / "plan.md") if feature_dir else (project_path / "plan.md")
