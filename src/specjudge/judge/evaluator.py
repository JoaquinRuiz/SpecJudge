"""Judge evaluator: estimates the project's global demand profile (FR-002).

A single call to the local judge per run, over the whole artifact set, producing a
DemandProfile with a justification.

Two prompt shapes are used, chosen by the judge's size (see `judge` in
data/rating-rules.yaml):

* **compact** — a structured summary (counts, headings, task titles). Small models
  lose the instructions inside a long dump of markdown and start *continuing* the
  document instead of evaluating it, so they get the short shape.
* **full** — the artifact text itself, for judges large enough to handle it.

If the judge does not return usable demand levels, this raises rather than falling
back to a default. A missing level would silently become the weakest one and make
any project look trivial — exactly the silent degradation Principle IV forbids.
"""

from __future__ import annotations

import re

from .. import errors
from ..domain import DemandProfile, ProjectAnalysis, RatingRules
from ..judge.ollama import OllamaClient

_DEFAULT_MAX_CHARS = 8000
_DEFAULT_MAX_CHARS_COMPACT = 1500
_DEFAULT_COMPACT_AT_OR_BELOW_B = 70.0

_HEADING = re.compile(r"^#{1,3}\s+(.*\S)\s*$", re.MULTILINE)
_CHECKLIST = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.*\S)\s*$", re.MULTILINE)
_REQUIREMENT = re.compile(r"\b((?:FR|SC|RF|RNF|NFR)-\d+)\b")


def use_compact_prompt(params_b: float | None, rules: RatingRules) -> bool:
    """Whether this judge should get the compact prompt.

    An unknown size is treated as small: the compact prompt is the safe default,
    since it works for large judges too — it just gives them less literal context.
    """
    threshold = float(
        rules.judge.get("compact_prompt_at_or_below_params_b", _DEFAULT_COMPACT_AT_OR_BELOW_B)
    )
    if params_b is None:
        return True
    return params_b <= threshold


def _instructions(rules: RatingRules) -> str:
    dims = ", ".join(rules.dimensions)
    levels = " | ".join(rules.levels)
    shape = ", ".join(f'"{d}": "<level>"' for d in rules.dimensions)
    return (
        "You are assessing HOW DEMANDING a software project is to implement.\n"
        f"Rate each dimension ({dims}) on this scale: {levels}.\n\n"
        "Calibration:\n"
        "  low    - a script or a handful of simple, well-understood pieces\n"
        "  medium - a normal application: several components, some real logic\n"
        "  high   - many interacting parts, non-trivial rules, careful edge cases\n"
        "  top    - large or novel systems, deep domain expertise, heavy constraints\n\n"
        "Answer with THIS JSON object and nothing else. Do not copy, continue or\n"
        "summarise the project documents; do not output tasks, code or file lists:\n"
        f'{{"dimensions": {{{shape}}}, "justification": "<one or two sentences>"}}'
    )


def _summarize(analysis: ProjectAnalysis, limit: int) -> str:
    """Structured digest of the artifacts: shape of the work, not its prose."""
    parts: list[str] = []
    for art in analysis.artifacts:
        if not (art.readable and art.content):
            parts.append(f"- {art.type}: MISSING")
            continue
        text = art.content
        headings = _HEADING.findall(text)
        tasks = _CHECKLIST.findall(text)
        reqs = sorted(set(_REQUIREMENT.findall(text)))

        lines = [f"- {art.type}: {len(text)} chars"]
        if reqs:
            lines.append(f"  requirements ({len(reqs)}): {', '.join(reqs[:40])}")
        if tasks:
            lines.append(f"  checklist items: {len(tasks)}")
            sample = [t[:90] for t in tasks[:15]]
            lines.extend(f"    * {t}" for t in sample)
        if headings:
            names = " | ".join(h[:60] for h in headings[:20])
            lines.append(f"  sections ({len(headings)}): {names}")
        block = "\n".join(lines)
        parts.append(block[:limit])
    return "\n".join(parts)


def build_prompt(
    analysis: ProjectAnalysis, rules: RatingRules, *, compact: bool = False
) -> str:
    head = _instructions(rules)
    if compact:
        limit = int(
            rules.judge.get("max_chars_per_artifact_compact", _DEFAULT_MAX_CHARS_COMPACT)
        )
        body = _summarize(analysis, limit)
        label = "=== PROJECT SUMMARY ==="
    else:
        limit = int(rules.judge.get("max_chars_per_artifact", _DEFAULT_MAX_CHARS))
        chunks = [
            f"\n--- {a.type} ---\n{a.content[:limit]}"
            for a in analysis.artifacts
            if a.readable and a.content
        ]
        body = "".join(chunks)
        label = "=== PROJECT ARTIFACTS ==="

    # Instructions are repeated after the body: small models attend to the end of
    # the prompt, and the tail is what stops them continuing the document.
    return f"{head}\n\n{label}\n{body}\n\n=== END OF PROJECT ===\n\n{head}"


def _parse_demand(raw: object, rules: RatingRules) -> tuple[dict[str, str], str] | str:
    """Return (dimensions, justification) or a string describing why it is unusable."""
    if not isinstance(raw, dict):
        return f"Expected a JSON object, got {type(raw).__name__}."
    raw_dims = raw.get("dimensions")
    if not isinstance(raw_dims, dict):
        keys = ", ".join(sorted(str(k) for k in raw)[:8]) or "(none)"
        return f"Response has no 'dimensions' object. Keys returned: {keys}."

    dimensions: dict[str, str] = {}
    bad: list[str] = []
    for dim in rules.dimensions:
        value = raw_dims.get(dim)
        text = str(value).strip().lower()
        if text in rules.levels:
            dimensions[dim] = text
        else:
            bad.append(f"{dim}={value!r}")
    if bad:
        return (
            f"Missing or invalid demand level for: {', '.join(bad)}. "
            f"Expected one of: {', '.join(rules.levels)}."
        )

    justification = str(raw.get("justification", "")).strip()
    return dimensions, justification


def estimate_demand(
    analysis: ProjectAnalysis,
    rules: RatingRules,
    client: OllamaClient,
    judge_model: str,
) -> DemandProfile:
    compact = use_compact_prompt(client.model_params_b(judge_model), rules)

    # Try the chosen shape; if it comes back unusable, retry once with the compact
    # shape before giving up (a long prompt is the usual cause of a bad answer).
    attempts = [compact] if compact else [False, True]
    detail = ""
    for is_compact in attempts:
        raw = client.chat_json(judge_model, build_prompt(analysis, rules, compact=is_compact))
        parsed = _parse_demand(raw, rules)
        if isinstance(parsed, tuple):
            dimensions, justification = parsed
            return DemandProfile(
                dimensions=dimensions,
                justification=justification
                or "Demand profile estimated from the project artifacts.",
                judge_model=judge_model,
            )
        detail = parsed

    raise errors.judge_response_unusable(judge_model, detail)
