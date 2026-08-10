"""The demand as an envelope rather than a single verdict (FR-027).

One project-wide level flattens real heterogeneity. A task set routinely contains one
architecture decision that genuinely needs the strongest model alongside twenty
mechanical edits that do not, and a single answer either overpays on most of the work
or under-serves the part that decides whether it works at all.

The fix is not per-task scoring — that produces noise and loses the relationships
between tasks, and it would cost a call per task. The single-pass read is precisely
what lets a judge notice that three of twenty-one tasks are the outliers. What was too
coarse was the *output shape*.

So the same read produces three things:

* a **constraint table** — per dimension, the level demanded, the fragment that
  demands it, and whether that fragment states a requirement or merely a habit;
* a **default level** for the bulk of the work;
* **escalation triggers** for the outliers, each naming the fragment behind it.

Which of those orders the podium is not something the project can answer: it depends on
whether the person implementing can switch models halfway through. That is the
execution model (FR-028), and it is an input.

Everything here is deterministic. The judge supplies levels and citations; this module
only arranges them, so a reader can disagree with a fragment rather than with a verdict.
"""

from __future__ import annotations

import re

from .domain import Constraint, DemandProfile, Envelope, ExecutionModel, Fragment

# RFC 2119 obligation, or a numbered requirement id. Either means the project wrote
# this down as a rule rather than describing what it usually does.
_OBLIGATION = re.compile(r"\b(MUST NOT|MUST|SHALL NOT|SHALL|REQUIRED|MAY NOT)\b")
_REQUIREMENT_ID = re.compile(r"\b(?:FR|SC|RF|RNF|NFR)-\d+\b")


def is_hard_requirement(text: str) -> bool:
    """Whether a cited fragment states an obligation rather than a tendency.

    Derived from the text on purpose, and not asked of the judge. A user who thinks
    this call is wrong can open the fragment and see the same words the rule saw;
    an opinion returned by a model offers nothing to argue with. It also costs no
    prompt slot, and slots are what small judges run out of first.

    Case-sensitive for the RFC 2119 keywords, which the conventions capitalise —
    "the export must be fast" in prose is not the same claim as "MUST".
    """
    return bool(_OBLIGATION.search(text) or _REQUIREMENT_ID.search(text))


def _constraint(
    dimension: str,
    level: str,
    profile: DemandProfile,
    by_id: dict[str, Fragment],
) -> Constraint:
    evidence = profile.evidence.get(dimension)
    fragment = by_id.get(evidence.fragment_id or "") if evidence else None
    text = fragment.text if fragment else ""
    return Constraint(
        dimension=dimension,
        level=level,
        fragment_id=evidence.fragment_id if evidence else None,
        text=text,
        hard=is_hard_requirement(text),
    )


def build(
    profile: DemandProfile,
    fragments: list[Fragment],
    execution_model: ExecutionModel,
) -> Envelope:
    """The envelope for a judged project.

    `default_demand` is what the ranking is built on: the bulk when the caller can
    escalate per task, the peak when one model has to carry everything. Both are
    reported either way, so switching the execution model changes the recommendation
    without changing what was measured.
    """
    by_id = {f.id: f for f in fragments}
    peak = profile.scored_dimensions
    bulk = profile.bulk_dimensions

    escalating = execution_model is ExecutionModel.ESCALATING
    default = bulk if escalating else peak

    constraints = [_constraint(dim, level, profile, by_id) for dim, level in peak.items()]
    escalations = [
        constraint
        for constraint in constraints
        if escalating and _exceeds(peak.get(constraint.dimension), bulk.get(constraint.dimension))
    ]

    return Envelope(
        execution_model=execution_model,
        default_demand=dict(default),
        peak_demand=dict(peak),
        constraints=constraints,
        escalations=escalations,
    )


def _exceeds(peak: str | None, bulk: str | None) -> bool:
    """Whether the peak genuinely sits above the bulk for this dimension.

    Compared through the ordinal scale rather than by inequality of strings: a
    dimension whose bulk the judge did not distinguish falls back to the peak and
    must not read as an escalation.
    """
    from .domain import LEVELS

    if peak is None or bulk is None or peak == bulk:
        return False
    if peak not in LEVELS or bulk not in LEVELS:
        return False
    return LEVELS.index(peak) > LEVELS.index(bulk)


def envelope_warnings(profile: DemandProfile, execution_model: ExecutionModel) -> list[str]:
    """What the envelope could not establish, said out loud (Principle IV).

    A caller who asked for escalation triggers and got none deserves to know whether
    that means "the work is uniform" or "the judge did not tell us".
    """
    if execution_model is not ExecutionModel.ESCALATING:
        return []
    if profile.distinguishes_bulk:
        return []
    return [
        "No separate estimate of the bulk of the work was available — the judge did not "
        "distinguish it from the hardest part, or is too small to be asked — so the "
        "default level is the peak and no escalation trigger is offered. The ranking is "
        "the conservative one; a larger judge may rank lower."
    ]
