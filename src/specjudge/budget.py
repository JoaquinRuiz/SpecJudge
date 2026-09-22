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


# Below this many characters a truncated source stops being worth its room: what
# arrives is a cut clause rather than a statement anyone can reason from — and it is
# still citable, so it costs the judge attention and buys nothing.
_MIN_FLOOR_CHARS = 200
# The floor scales with the budget rather than being fixed, so the compact prompt —
# which works with a fraction of the full budget — does not lose every source to a
# floor sized for the full one.
_FLOOR_DIVISOR = 20


def _floor(budget: int) -> int:
    """The smallest allowance worth spending on a source.

    Derived from the budget rather than passed in, and that is the point. The prompt
    and the citable fragment set are built by two different call sites from the same
    `limit` (FR-020), so a floor threaded through as an argument would only have to
    be forgotten at one of them to make the judge cite text it was never shown.
    Deriving it makes the two structurally incapable of disagreeing.
    """
    return max(_MIN_FLOOR_CHARS, budget // _FLOOR_DIVISOR)


def _apply_floor(members: list[tuple[int, int]], budget: int, floor: int) -> dict[int, int]:
    """Allowances for one pool, dropping whatever the pool cannot fund properly.

    Water-filling divides what there is; it never asks whether a share is large
    enough to be worth anything. With enough sources competing it hands every one of
    them a sliver, which is the failure this exists to stop: four sources read
    properly tell the judge more than sixteen cut off mid-sentence.

    A source is only ever dropped for being *truncated* below the floor. One that
    fits entirely inside its share is complete, however short it is — a 40-character
    `.cursorrules` is the whole file, not a fragment of one.

    The last source in discovery order goes first, matching the file cap: context
    near the repository root governs the whole repository, context deep inside
    governs one corner of it. At least one always survives — a floor that silenced
    every source would answer "this budget is too small" by sending nothing at all.
    """
    kept = list(members)
    while len(kept) > 1:
        shares = _water_fill([natural for _, natural in kept], budget)
        starved = [
            position
            for position, ((_, natural), share) in enumerate(zip(kept, shares, strict=True))
            if share < floor and share < natural
        ]
        if not starved:
            break
        del kept[starved[-1]]

    allowances = {index: 0 for index, _ in members}
    if kept:
        shares = _water_fill([natural for _, natural in kept], budget)
        for (index, _), share in zip(kept, shares, strict=True):
            allowances[index] = share
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

    floor = _floor(budget)
    allowances: dict[int, int] = {}
    for key, group_budget in zip(present, group_budgets, strict=True):
        allowances.update(_apply_floor(groups[key], group_budget, floor))
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


def dropped_sources(
    analysis: ProjectAnalysis,
    limit: int,
    *,
    compact: bool = False,
    environment_budget: int | None = None,
) -> list[SDDArtifact]:
    """The sources the floor removed, so the run can say so rather than just do it.

    A cap the reader cannot see is indistinguishable from having read everything
    (FR-025), and that holds for this cap exactly as it did for the file one. Derived
    the same way the prompt is, from the same `limit` and the same shape, so it can
    only ever report what actually happened.
    """
    usable = [a for a in analysis.artifacts if a.readable and a.content]
    budget = limit if environment_budget is None else environment_budget

    counts: dict[str, int] = {}
    for artifact in usable:
        counts[artifact.type] = counts.get(artifact.type, 0) + 1
    labels = [_label(a, analysis.root, counts[a.type] > 1) for a in usable]

    environment = [i for i, a in enumerate(usable) if is_environment(a.type)]
    if compact:
        entries = [
            (i, digest_module.natural_size(usable[i], labels[i]), usable[i].type == "instructions")
            for i in environment
        ]
    else:
        entries = [
            (i, len(usable[i].content), usable[i].type == "instructions") for i in environment
        ]

    allowances = _environment_allowances(entries, budget)
    return [usable[i] for i in environment if allowances.get(i, 0) == 0]
