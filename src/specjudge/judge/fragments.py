"""Citable fragments of the project text (FR-020).

The judge is asked to cite the fragment supporting each dimension. For that to be
verifiable rather than decorative, three things must agree on what "the fragments"
are: the compact prompt, the full prompt, and the validator that checks the answer.
This module is that single source.

Two consequences shape the design:

* **Fragments are derived from the text actually sent**, truncation included. A
  fragment that was cut from the prompt is not in the set, so citing it is a
  fabrication from the judge's point of view — and is treated as one.
* **Ids are short and closed.** The judge picks from an enumerated list instead of
  reproducing prose, which is what makes validation set membership rather than
  fuzzy matching. It is also the only shape that survives the compact prompt,
  which sends a digest and no prose at all.
"""

from __future__ import annotations

import re
import unicodedata

from ..budget import prompt_sources
from ..domain import Fragment, ProjectAnalysis

# Natural identifiers the SDD artifacts already carry.
_REQUIREMENT = re.compile(r"\b((?:FR|SC|RF|RNF|NFR)-\d+)\b")
_TASK_ID = re.compile(r"\b(T\d{3,})\b")
_HEADING = re.compile(r"^#{1,3}\s+(.*\S)\s*$", re.MULTILINE)
# Start-of-line markers. Bullet text is gathered by `_bullet_blocks` rather than by
# the regex, because a requirement wrapped across lines must not be cut in half.
_CHECKLIST_START = re.compile(r"^(\s*)-\s*\[[ xX]\]\s+(.*\S)\s*$")
_BULLET_START = re.compile(r"^(\s*)[-*]\s+(?!\[[ xX]\])(.*\S)\s*$")
_HEADING_START = re.compile(r"^\s*#{1,6}\s")

# Fragment text is capped so the prompt stays affordable; the cap is applied
# identically when validating a quote, so the two never disagree.
MAX_FRAGMENT_CHARS = 240

# Explicit per-source prefixes. Deriving them from the first letter used to be enough
# for three sources; with agent-context files it is not — `claude` and `constitution`
# both start with C, and two sources sharing a prefix would silently drop each other's
# fragments when ids are deduplicated (FR-024).
_ARTIFACT_PREFIX = {
    "constitution": "C",
    "spec": "S",
    "tasks": "T",
    "plan": "P",
    "agents": "AG",
    "claude": "CL",
    "cursor": "CU",
    "copilot": "CP",
    "adr": "AD",
}


def _assign_prefixes(artifact_types: list[str]) -> list[str]:
    """One distinct prefix per source *file*, in the order given.

    Per file, not per type: a repository can carry many sources of the same kind
    (the Codex repo has 88 `AGENTS.md`), and they are separate documents whose
    fragments must stay apart.

    Uniqueness is enforced rather than assumed, because a collision does not fail
    loudly. Two sources sharing a prefix produce the same positional ids, the
    later one overwrites the earlier in the lookup, and the judge is then either
    rejected for citing something that "does not exist" or validated against text
    it was never shown.

    A kind that appears once keeps its bare prefix (`AG`); several of a kind are
    numbered (`AG1`, `AG2`). Ids therefore stay stable for any given input.
    """
    counts: dict[str, int] = {}
    for artifact_type in artifact_types:
        counts[artifact_type] = counts.get(artifact_type, 0) + 1

    seen: dict[str, int] = {}
    taken: set[str] = set()
    prefixes: list[str] = []
    for artifact_type in artifact_types:
        base = _ARTIFACT_PREFIX.get(artifact_type) or artifact_type[:2].upper() or "X"
        if counts[artifact_type] > 1:
            seen[artifact_type] = seen.get(artifact_type, 0) + 1
            base = f"{base}{seen[artifact_type]}"

        # Two different kinds can still land on the same base (an unknown type
        # abbreviating to "AG", say), so the last word on uniqueness is here.
        prefix, suffix = base, 2
        while prefix in taken:
            prefix = f"{base}_{suffix}"
            suffix += 1
        taken.add(prefix)
        prefixes.append(prefix)
    return prefixes


def _normalize(text: str) -> str:
    """Fold the differences a model routinely introduces when copying text.

    Collapses whitespace, unifies the punctuation that word processors and models
    swap freely (curly quotes, dashes), and lowercases. Deliberately conservative:
    it must never make two genuinely different fragments compare equal.
    """
    text = unicodedata.normalize("NFKC", text)
    for fancy, plain in (("‘", "'"), ("’", "'"), ("“", '"'), ("”", '"')):
        text = text.replace(fancy, plain)
    for dash in ("–", "—", "−"):
        text = text.replace(dash, "-")
    return " ".join(text.split()).lower()


def _bullet_blocks(text: str, checklist: bool) -> list[str]:
    """Bullet items with their wrapped continuation lines joined back on.

    Markdown wraps long items across lines:

        - **FR-002**: Report generation MUST run entirely on the user's device, since no
          personal data may leave it.

    A line-anchored regex captures only the first line, so the judge was shown
    requirements cut off mid-clause — and in one corpus case the half that was
    dropped was the half that contradicted another requirement. Everything the
    judge could not read, it could not reason about.

    A continuation line is non-blank, indented deeper than its bullet, and is not
    itself a bullet or a heading. A more-indented bullet starts its own fragment
    rather than being swallowed: a sub-item is a citable thing in its own right.
    """
    start = _CHECKLIST_START if checklist else _BULLET_START
    other = _BULLET_START if checklist else _CHECKLIST_START

    blocks: list[str] = []
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        match = start.match(lines[index])
        if match is None:
            index += 1
            continue

        indent = len(match.group(1))
        parts = [match.group(2).strip()]
        index += 1
        while index < len(lines):
            line = lines[index]
            if not line.strip():
                break
            if start.match(line) or other.match(line) or _HEADING_START.match(line):
                break
            if len(line) - len(line.lstrip()) <= indent:
                break
            parts.append(line.strip())
            index += 1
        blocks.append(" ".join(parts))
    return blocks


def _label(line: str) -> str | None:
    """The natural id carried by a line of text, if it has one."""
    req = _REQUIREMENT.search(line)
    if req:
        return req.group(1)
    task = _TASK_ID.search(line)
    if task:
        return task.group(1)
    return None


def _artifact_fragments(artifact_type: str, text: str, prefix: str) -> list[Fragment]:
    """Citable units of one artifact, in document order, deduplicated by id."""
    found: dict[str, Fragment] = {}
    counter = 0

    # Requirement- and task-bearing items first: they are the units a reader would
    # cite, and they already have stable names in the document. Headings come last
    # and never wrap, so they stay a plain line match.
    sources = [
        _bullet_blocks(text, checklist=True),
        _bullet_blocks(text, checklist=False),
        _HEADING.findall(text),
    ]
    for raw_items in sources:
        for raw in raw_items:
            body = " ".join(raw.split())
            if not body:
                continue
            natural = _label(body)
            if natural:
                frag_id = f"{prefix}:{natural}"
            else:
                counter += 1
                frag_id = f"{prefix}:{counter}"
            if frag_id in found:
                continue
            found[frag_id] = Fragment(
                id=frag_id,
                artifact_type=artifact_type,
                text=body[:MAX_FRAGMENT_CHARS],
            )
    return list(found.values())


def extract_fragments(analysis: ProjectAnalysis, limit: int) -> list[Fragment]:
    """Every citable fragment, derived from the artifact text truncated to `limit`.

    `limit` must be the same per-artifact cap the prompt uses: both go through
    `prompt_sources`, so the fragment set is derived from exactly the text the
    judge is shown. Any other route would accept ids the judge never saw — or
    reject ids it did.
    """
    sources = prompt_sources(analysis, limit)
    prefixes = _assign_prefixes([s.type for s in sources])

    fragments: list[Fragment] = []
    for source, prefix in zip(sources, prefixes, strict=True):
        fragments.extend(_artifact_fragments(source.type, source.text, prefix))
    return fragments


def render_catalogue(fragments: list[Fragment]) -> str:
    """The citable list as shown to the judge.

    Ids are rendered bare, with no brackets around them. They used to be written
    `[S:FR-001]`, and `llama3.1` cited them back with the brackets attached —
    a valid id the validator then rejected. Offering nothing to copy is a surer
    fix than teaching the parser to forgive it (issue #14).
    """
    if not fragments:
        return "(no citable fragments were found in this project)"
    return "\n".join(f"  {f.id}  {f.text}" for f in fragments)


def normalize_citation(cited: str) -> str:
    """Fold the decoration a model may wrap an id in before looking it up.

    Belt and braces alongside the bare rendering above: a model that decides to
    add brackets, quotes or backticks on its own has still identified the right
    fragment, and rejecting it over punctuation would be pedantry rather than
    validation.
    """
    return cited.strip().strip("[]()<>\"'`").strip()


def quote_matches(quote: str, fragment: Fragment) -> bool:
    """Whether a quoted phrase is genuinely present in the cited fragment.

    Compared after normalization, so trivial copying differences do not read as
    fabrication. A quote that still does not match is reported rather than fatal:
    the fragment id is the load-bearing citation.
    """
    needle = _normalize(quote)
    if not needle:
        return False
    return needle in _normalize(fragment.text)
