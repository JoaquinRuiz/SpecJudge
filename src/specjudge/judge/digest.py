"""The compact prompt's view of a project: what it contains, not how it opens (FR-025).

A small judge cannot be handed the artifacts, so it is handed a digest — counts,
requirement ids, task titles. That digest used to be built from the *truncated* text,
which meant it described the first 1,500 characters of each file rather than the file.
In a real `spec.md` the first 1,500 characters are the front matter, the context and the
user scenarios; the requirements start later. In a real `tasks.md` they are the format
legend and the path conventions.

Measured on a live feature (issue #29): of 28 citable fragments, 22 were headings and
**none** was a requirement or a task, because `FR-001` sat at line 82 and `T001` at line
41. The judge rated the project from the title of the tasks file. It had nothing else.

So the digest is built over the whole source and the budget is applied to the digest,
which is the right way round: a digest is bounded by its own structure — so many ids, so
many titles — not by the length of the document it describes.

Three rules follow, and they are the module:

* **Every named unit carries its own text.** A catalogue of bare ids would let the judge
  pick a label out of an inventory and call it evidence; `S:FR-001  FR-001` is a citation
  that verifies nothing. The snippet is what makes `grounded` mean the same thing here as
  it does when the full prose is sent.
* **Samples span the source.** A `tasks.md` starts with setup and ends with the hard part.
  A sample taken from the head describes the easy end and then decides the difficulty
  from it.
* **Under pressure, headings go first and requirements go last.** A heading names a topic
  and asserts nothing; a requirement is the thing that makes a project hard.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ..domain import ProjectAnalysis, SDDArtifact
from .fragments import MAX_FRAGMENT_CHARS, _bullet_blocks

_REQUIREMENT_LINE = re.compile(r"^(?:FR|SC|RF|RNF|NFR)-\d+")
_HEADING = re.compile(r"^#{1,3}\s+(.*\S)\s*$", re.MULTILINE)

# The snippet *is* the fragment text in this shape, so the two caps must be the same
# number or the judge would be shown one thing and validated against another. Anything
# shorter also re-creates the failure #19 fixed: a requirement's demanding half is
# usually its second one ("…across every supported market").
SNIPPET_CHARS = MAX_FRAGMENT_CHARS

# Rendered entries are bullets so the fragment extractor picks them up unchanged;
# structural lines deliberately are not, or the digest's own scaffolding would become
# citable ("spec: 13535 chars" is not evidence about anything).
_BULLET = "    * "


@dataclass(frozen=True)
class Unit:
    """One thing the digest names, with the text that makes it citable."""

    kind: str  # "requirement" | "task" | "heading"
    text: str

    def render(self) -> str:
        return f"{_BULLET}{self.text}"


_EMPHASIS = re.compile(r"\*\*|__")


def _snippet(text: str) -> str:
    """Plain text for the digest: no list markers, no emphasis, one line.

    Markdown emphasis is dropped rather than half-stripped — leaving `FR-001**:` from a
    `- **FR-001**:` bullet reads as damage, and the digest is prose for a reader, not a
    copy of the source.
    """
    return " ".join(_EMPHASIS.sub("", text).split()).strip(" -*")[:SNIPPET_CHARS]


def _spread(items: list[Unit], keep: int) -> list[Unit]:
    """`keep` items covering the whole list, last one included.

    Evenly spaced rather than stratified by section, because stratifying depends on a
    heading convention that not every project follows — and when the convention is
    absent it fails silently, back to a head sample. Position is always there.
    """
    if keep >= len(items) or keep <= 0:
        return items[:keep] if keep > 0 else []
    if keep == 1:
        return [items[-1]]
    step = (len(items) - 1) / (keep - 1)
    return [items[round(index * step)] for index in range(keep)]


def _units(content: str) -> dict[str, list[Unit]]:
    """Every citable unit in a source, by kind, in document order.

    Bullets come from the same block extraction the fragment catalogue uses, so a
    requirement wrapped across lines arrives whole. Reading it line by line would
    re-create the bug #19 fixed, quietly, in a different module.

    Plain bullets are a kind of their own because they are the *substance* of an
    agent-context file: an `AGENTS.md` states its constraints as bullets and carries
    almost no numbered requirements. Dropping them left environment-only projects with
    nothing but section titles to cite.
    """
    requirements: list[Unit] = []
    bullets: list[Unit] = []

    for raw in _bullet_blocks(content, checklist=False):
        # Classified on the normalised text rather than the raw markdown: one project
        # writes `- **FR-001**:` and the next `* __FR-001__:`.
        text = _snippet(raw)
        if _REQUIREMENT_LINE.match(text):
            requirements.append(Unit("requirement", text))
        elif text:
            bullets.append(Unit("bullet", text))

    return {
        "requirement": requirements,
        "task": [Unit("task", _snippet(raw)) for raw in _bullet_blocks(content, checklist=True)],
        "bullet": bullets,
        "heading": [Unit("heading", _snippet(h)) for h in _HEADING.findall(content)],
    }


# Dropped in this order when the budget runs out (FR-025).
_PRIORITY = ("requirement", "task", "bullet", "heading")
_LABEL = {
    "requirement": "requirements",
    "task": "checklist items",
    "bullet": "stated rules",
    "heading": "sections",
}


def render_source(artifact: SDDArtifact, label: str, budget: int) -> str:
    """One source's block of the digest, within `budget` characters.

    The counts are written first and never dropped. They are what makes a cap visible
    (FR-025) — "checklist items: 29 (4 shown)" is a different statement from silently
    showing four — and they cost a line each, so letting them compete with the units
    they describe would be the wrong economy.

    Counts come from the whole file even when the sample does not. "29" is the most
    informative number available about the size of a task list, and it is free.
    """
    units = _units(artifact.content)
    kinds = [kind for kind in _PRIORITY if units[kind]]

    shown: dict[str, list[Unit]] = {kind: [] for kind in kinds}

    def render() -> str:
        lines = [f"{label}: {len(artifact.content)} chars"]
        for kind in kinds:
            total = len(units[kind])
            picked = shown[kind]
            if len(picked) == total:
                note = ""
            elif picked:
                note = f" ({len(picked)} shown, spread across the file)"
            else:
                note = " (none shown, no room left)"
            lines.append(f"  {_LABEL[kind]}: {total}{note}")
            lines.extend(unit.render() for unit in picked)
        return "\n".join(lines)

    # Fill by priority: requirements first because they are what makes a project hard,
    # headings last because they name a topic and assert nothing. Each candidate is
    # measured rather than estimated — the note text depends on how many units survive,
    # which is the kind of arithmetic that ends up quietly wrong by two characters.
    for kind in _PRIORITY:
        if kind not in kinds:
            continue
        keep = len(units[kind])
        while keep > 0:
            shown[kind] = _spread(units[kind], keep)
            if len(render()) <= budget:
                break
            keep -= 1
        else:
            shown[kind] = []

    return render()


def shape_only(block: str) -> str:
    """A source's block without its units: what it contains, not the contents.

    The units are sent too, but in the CITABLE FRAGMENTS list, where each one carries
    the id the judge has to cite. Printing them twice would double the compact prompt
    to say the same thing — and the compact prompt exists to be small.
    """
    return "\n".join(line for line in block.splitlines() if not line.startswith(_BULLET))


def natural_size(artifact: SDDArtifact, label: str) -> int:
    """How long this source's block would be with nothing dropped.

    Used to share a budget between sources before any of them is rendered, so the
    sharing is decided by how much each source has to say rather than by its order.
    """
    return len(render_source(artifact, label, budget=10**9))


def missing_lines(analysis: ProjectAnalysis, reported: set[str], present: set[str]) -> list[str]:
    """Absent work artifacts, stated plainly and not as bullets.

    Not bullets because everything bulleted in this digest is citable, and
    "constitution: MISSING" is not evidence about a project — it is the absence of it.
    """
    return [f"{kind}: MISSING" for kind in sorted(reported - present)]
