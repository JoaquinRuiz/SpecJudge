"""How much of each source reaches the judge (FR-025).

While a project had one file per kind, "cap each artifact at N characters" was a
whole policy. It stops being one as soon as a repository can contribute a dozen
environment files: twelve caps of 8000 is a 96k-character prompt, which is not a
cap at all.

So the environment sources share a single budget between them, and the work
artifacts keep their existing per-artifact cap. The asymmetry is deliberate — the
spec and the tasks describe what is about to be built and there is exactly one of
each, while agent-context files are numerous and largely repeat one another.

That single pool is split once more, between path-specific Copilot instructions and
everything else, because the two scale differently: a project documents one
`AGENTS.md` and as many `*.instructions.md` as it has stacks, so leaving them in one
pool would let the narrow files crowd out the broad one.

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
from .judge import digest as digest_module
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


def _environment_allowances(entries: list[tuple[int, int, bool]], budget: int) -> dict[int, int]:
    """Per-source allowances for the environment sources, filled in two stages.

    One flat water-fill across every environment file was right while they were
    interchangeable, and stops being right once path-specific instructions join
    them. Those arrive in numbers — a repository can easily have a dozen, several
    of which match — and a flat fill lets them take an arbitrary share of the
    budget, so the root `AGENTS.md` gets thinner the more stacks a project
    documents. That is a bad trade: the instructions are narrow by construction
    and `AGENTS.md` describes the whole repository.

    So the budget is split between two groups first — instructions, and everything
    else — and then within each. Water-filling at the group level keeps the
    property that makes it worth doing: a group that cannot use its half releases
    the remainder to the other, so a project with no instructions gets exactly the
    single-pool behaviour it had before, to the character.
    """
    groups: dict[bool, list[tuple[int, int]]] = {False: [], True: []}
    for index, natural, is_instruction in entries:
        groups[is_instruction].append((index, natural))

    present = [key for key in (False, True) if groups[key]]
    if not present:
        return {}

    totals = [sum(natural for _, natural in groups[key]) for key in present]
    group_budgets = _water_fill(totals, budget)

    allowances: dict[int, int] = {}
    for key, group_budget in zip(present, group_budgets, strict=True):
        members = groups[key]
        shares = _water_fill([natural for _, natural in members], group_budget)
        for (index, _), share in zip(members, shares, strict=True):
            allowances[index] = share
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


def digest_sources(
    analysis: ProjectAnalysis,
    limit: int,
    environment_budget: int | None = None,
) -> list[PromptSource]:
    """Every usable source as a digest block, within the same budget as the prose.

    The compact prompt sends these instead of the artifacts, so *this* is the text the
    judge is shown — and therefore the text the citable fragments come from (FR-020).
    Built over the whole source rather than a truncated head, which is the whole point
    of issue #29.

    Environment sources share their allowance as they do for prose, and the share is
    computed on how long each block *would* be unbudgeted, so a source with little to
    say releases room to one with a lot rather than to whichever came first.
    """
    usable = [a for a in analysis.artifacts if a.readable and a.content]
    budget = limit if environment_budget is None else environment_budget

    counts: dict[str, int] = {}
    for artifact in usable:
        counts[artifact.type] = counts.get(artifact.type, 0) + 1
    labels = [_label(a, analysis.root, counts[a.type] > 1) for a in usable]

    environment = [i for i, a in enumerate(usable) if is_environment(a.type)]
    per_index = _environment_allowances(
        [
            (i, digest_module.natural_size(usable[i], labels[i]), usable[i].type == "instructions")
            for i in environment
        ],
        budget,
    )

    sources: list[PromptSource] = []
    for index, artifact in enumerate(usable):
        allowed = per_index.get(index, limit)
        text = digest_module.render_source(artifact, labels[index], allowed)
        if text.strip():
            sources.append(PromptSource(artifact=artifact, text=text, label=labels[index]))
    return sources


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
    per_index = _environment_allowances(
        [(i, len(usable[i].content), usable[i].type == "instructions") for i in environment],
        budget,
    )

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
