"""How much of each source reaches the judge (FR-025).

While a project had one file per kind, "cap each artifact at N characters" was a
whole policy. It stops being one as soon as a repository can contribute a dozen
environment files: twelve caps of 8000 is a 96k-character prompt, which is not a
cap at all.

So the environment sources share a single budget between them, and the work
artifacts keep their existing per-artifact cap. The asymmetry is deliberate — the
spec and the tasks describe what is about to be built and there is exactly one of
each, while agent-context files are numerous and largely repeat one another.

The budget is shared by water-filling: everyone is offered an equal share, whoever
needs less than their share takes only what they need, and what they leave is
redistributed among the rest. A 200-character `.cursorrules` therefore costs 200
characters rather than a twelfth of the budget, and a long root `AGENTS.md` gets
the room that frees up.

One rule holds this together: **the text sent to the judge and the text fragments
are derived from must be the same text**. Both go through `prompt_sources`, so a
fragment cut by the budget is not citable — exactly as with the older per-artifact
truncation it generalises.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .domain import ProjectAnalysis, SDDArtifact
from .sources import is_environment


@dataclass(frozen=True)
class PromptSource:
    """One source as the judge will actually see it."""

    artifact: SDDArtifact
    text: str
    label: str

    @property
    def type(self) -> str:
        return self.artifact.type

    @property
    def path(self) -> str:
        return self.artifact.path


def _label(artifact: SDDArtifact, root: str, ambiguous: bool) -> str:
    """How this source is announced in the prompt.

    A kind alone stopped being enough once a repository can contribute several
    files of it: three blocks all headed `agents` read as one contradictory
    document. The path within the project is the label that carries information —
    `packages/api/AGENTS.md` says which corner of a monorepo it governs — while an
    absolute path would leak this machine's directory layout into the prompt for
    nothing.

    Only when it is needed, though. Measured on the corpus, adding a path to an
    unambiguous `spec` moved a judgement that had been correct: prompt text is an
    input, and changing it for projects that gained nothing from the change is a
    cost with no benefit.
    """
    if not ambiguous or not root:
        return artifact.type
    try:
        relative = Path(artifact.path).relative_to(root)
    except ValueError:
        return artifact.type
    return f"{artifact.type} ({relative.as_posix()})"


def _water_fill(lengths: list[int], budget: int) -> list[int]:
    """Per-source allowances summing to at most `budget`.

    Shortest first, so the sources that cannot use their share release it early
    and the long ones benefit. Deterministic for a given input, which matters:
    fragment ids are derived from what survives this.
    """
    allowances = [0] * len(lengths)
    order = sorted(range(len(lengths)), key=lambda i: (lengths[i], i))

    remaining = budget
    left = len(order)
    for index in order:
        if left <= 0:
            break
        share = remaining // left
        taken = min(lengths[index], share)
        allowances[index] = taken
        remaining -= taken
        left -= 1
    return allowances


def _truncate(content: str, allowed: int) -> str:
    """Cut at a line boundary when there is one, rather than mid-word.

    The judge is shown, and asked to cite, whatever survives this. A cut in the
    middle of a sentence produces a fragment that means less than the line it came
    from — the same failure #19 fixed for wrapped bullets, arriving by a different
    route. Falls back to the hard cut when the allowance does not even reach the
    first line break.
    """
    if len(content) <= allowed:
        return content
    head = content[:allowed]
    boundary = head.rfind("\n")
    return head[:boundary] if boundary > 0 else head


def prompt_sources(
    analysis: ProjectAnalysis,
    limit: int,
    environment_budget: int | None = None,
) -> list[PromptSource]:
    """Every usable source, truncated to what its budget allows (FR-025).

    `limit` is the per-artifact cap for work artifacts; the environment sources
    share `environment_budget`, which defaults to that same number so adding
    agent-context files cannot grow the prompt beyond what one artifact could
    already cost.
    """
    usable = [a for a in analysis.artifacts if a.readable and a.content]
    budget = limit if environment_budget is None else environment_budget

    environment = [i for i, a in enumerate(usable) if is_environment(a.type)]
    allowances = _water_fill([len(usable[i].content) for i in environment], budget)
    per_index = dict(zip(environment, allowances, strict=True))

    # A kind carried by a single file needs no disambiguation.
    counts: dict[str, int] = {}
    for artifact in usable:
        counts[artifact.type] = counts.get(artifact.type, 0) + 1

    sources: list[PromptSource] = []
    for index, artifact in enumerate(usable):
        allowed = per_index.get(index, limit)
        text = _truncate(artifact.content, allowed)
        if text.strip():
            sources.append(
                PromptSource(
                    artifact=artifact,
                    text=text,
                    label=_label(artifact, analysis.root, counts[artifact.type] > 1),
                )
            )
    return sources
