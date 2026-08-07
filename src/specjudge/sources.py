"""What counts as a source of project context, and how far to trust it (FR-024).

SpecJudge used to read three files in `.specify/` and nothing else, which limited it
to people already running a full Spec-Driven Development workflow. Meanwhile most
repositories carry written context the tool ignored: `AGENTS.md` is in tens of
thousands of them, `CLAUDE.md` in many more, and Cursor, Copilot and ADR conventions
each cover another slice.

Reading them is only safe because of FR-020. Before cited evidence existed, this
would have needed per-format trust rules — deciding in advance how much to believe a
`.cursorrules` file versus a spec — which is unmaintainable across formats that each
evolve separately. Now the source does not matter: a dimension that cannot be grounded
in a citation comes back `unsupported` and leaves the calculation, so a thin source
produces a thin profile on its own. That is why there is no weighting here, and why a
nested `AGENTS.md` is worth exactly what a root one is.

Two kinds of source, carrying different signal and both worth reading:

* **environment** — `AGENTS.md`, `CLAUDE.md`, `.cursorrules`,
  `.github/copilot-instructions.md`, ADRs. How hard this repository is to work in at
  all: domain, constraints, testing rigour, decisions already made. Identical whether
  you are fixing a typo or rewriting authentication.
* **work** — constitution, spec, tasks, plan. What is about to be built.

Picking one over the other would discard signal that does not overlap, so both are
read whenever both exist. Where they are found is `discovery.py`; how much of each
one reaches the judge is `budget.py`.
"""

from __future__ import annotations

from pathlib import Path

# kind -> whether the source describes the work, or the environment it happens in.
WORK_KINDS = ("constitution", "spec", "tasks", "plan")
ENVIRONMENT_KINDS = ("agents", "claude", "cursor", "copilot", "adr")

# How each kind is named to a reader, who thinks in filenames rather than in kinds.
LABELS = {
    "constitution": "constitution",
    "spec": "spec",
    "tasks": "tasks",
    "plan": "plan",
    "agents": "AGENTS.md",
    "claude": "CLAUDE.md",
    "cursor": ".cursorrules",
    "copilot": "copilot-instructions.md",
    "adr": "ADR",
}


def label(kind: str, count: int = 1) -> str:
    """'AGENTS.md', or '3× AGENTS.md' when a repository carries several."""
    name = LABELS.get(kind, kind)
    return name if count == 1 else f"{count}× {name}"


def summarize_kinds(kinds: list[str]) -> str:
    """'2× AGENTS.md, .cursorrules, 3× ADR', in first-seen order."""
    counts: dict[str, int] = {}
    for kind in kinds:
        counts[kind] = counts.get(kind, 0) + 1
    return ", ".join(label(kind, n) for kind, n in counts.items())


def is_environment(kind: str) -> bool:
    return kind in ENVIRONMENT_KINDS


def plan_path(feature_dir: Path | None, project_path: Path) -> Path:
    """spec-kit's `plan.md`, which carries stack and architecture decisions.

    It sits beside the spec and the tasks and was simply never read.
    """
    return (feature_dir / "plan.md") if feature_dir else (project_path / "plan.md")
