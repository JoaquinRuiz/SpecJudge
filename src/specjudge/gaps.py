"""What is missing *inside* the artifacts, not just which file is absent (FR-023).

Classification already told you a project was thin. It could not tell you what to do
about it: "thin on detail" is a diagnosis with no prescription, and a user who reads it
is no closer to a better answer than before.

These checks look at content — are there requirements, acceptance criteria, tasks that
say where the work lands — and phrase the answer as something to go and write.

They are heuristics over Spec Kit conventions, and they will occasionally be wrong: a
project that numbers its criteria some other way genuinely has them and will be told it
does not. That is why every message says **what it looked for**. A user who can see the
tool searched for `SC-NNN` can dismiss the warning in a second; one who is only told
"no acceptance criteria" is being accused of something they may not have done.

Deterministic on purpose. Asking the judge would be richer and less trustworthy, would
cost a second call the spec forbids (FR-002), and could not be tested.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .domain import ProjectAnalysis, RatingRules

# Spec Kit numbers requirements and criteria; these are the conventions we search for.
_REQUIREMENT = re.compile(r"\b(?:FR|RF)-\d+\b")
_CRITERION = re.compile(r"\b(?:SC|NFR|RNF)-\d+\b")
_CHECKLIST = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.*\S)\s*$", re.MULTILINE)
# A task that says where the work lands: a path, a dotted filename, or a directory.
_LOCATION = re.compile(r"[\w./-]+\.\w{1,5}\b|\b(?:src|tests|lib|app)/[\w./-]+")

DEFAULT_MIN_SPEC_CHARS = 400
DEFAULT_MIN_LOCATED_TASKS_RATIO = 0.5


@dataclass(frozen=True)
class Gap:
    """One concrete thing the project is missing, and what to do about it."""

    code: str
    what: str  # what is missing, naming what was searched for
    fix: str  # what to write to close it

    def render(self) -> str:
        return f"{self.what} — {self.fix}"


def _text(analysis: ProjectAnalysis, artifact_type: str) -> str:
    artifact = analysis.artifact(artifact_type)
    if artifact is None or not (artifact.readable and artifact.content):
        return ""
    return artifact.content


def _min_spec_chars(rules: RatingRules) -> int:
    raw = rules.scarce_thresholds.get("min_spec_chars", DEFAULT_MIN_SPEC_CHARS)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_MIN_SPEC_CHARS
    return value if value >= 1 else DEFAULT_MIN_SPEC_CHARS


def find_gaps(analysis: ProjectAnalysis, rules: RatingRules) -> list[Gap]:
    """Concrete, actionable gaps in the project's definition (FR-023).

    Ordered by how much closing one would improve the assessment: requirements
    first, then criteria, then task detail.
    """
    gaps: list[Gap] = []
    spec = _text(analysis, "spec")
    tasks = _text(analysis, "tasks")
    constitution = _text(analysis, "constitution")

    if not spec.strip():
        # Listed first: nothing else about the spec can be said, and this is the
        # single most useful thing the user could go and write.
        gaps.append(
            Gap(
                code="no_spec",
                what="no specification found for this feature",
                fix="write a spec: what the system must do, and how you will know it works",
            )
        )

    if spec and not _REQUIREMENT.search(spec):
        gaps.append(
            Gap(
                code="no_requirements",
                what="the spec declares no numbered requirements (looked for FR-NNN)",
                fix="state what the system must do, one numbered requirement per behaviour",
            )
        )

    if spec and not _CRITERION.search(spec):
        gaps.append(
            Gap(
                code="no_acceptance_criteria",
                what="no acceptance criteria found (looked for SC-NNN or NFR-NNN)",
                fix="say how you will know it works — the measurable bar each requirement meets",
            )
        )

    if spec and len(spec.strip()) < _min_spec_chars(rules):
        gaps.append(
            Gap(
                code="spec_too_short",
                what=f"the spec is {len(spec.strip())} characters long",
                fix="describe the scope, and say explicitly what is out of it",
            )
        )

    located, total = _task_locations(tasks)
    if total and located / total < DEFAULT_MIN_LOCATED_TASKS_RATIO:
        gaps.append(
            Gap(
                code="tasks_without_location",
                what=f"only {located} of {total} tasks say where the work lands",
                fix="name the file or module each task touches, so its size is visible",
            )
        )

    if not constitution.strip():
        gaps.append(
            Gap(
                code="no_constitution",
                what="no project constitution found",
                fix="write down the principles the implementation must respect",
            )
        )

    return gaps


def _task_locations(tasks: str) -> tuple[int, int]:
    """How many checklist items name a file or directory, out of how many."""
    items = _CHECKLIST.findall(tasks)
    if not items:
        return 0, 0
    located = sum(1 for item in items if _LOCATION.search(item))
    return located, len(items)
