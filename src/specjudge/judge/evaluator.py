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
from ..domain import (
    UNSUPPORTED,
    DemandProfile,
    Evidence,
    EvidenceStatus,
    Fragment,
    ProjectAnalysis,
    RatingRules,
    answer_levels,
)
from ..judge.ollama import OllamaClient
from .fragments import extract_fragments, quote_matches, render_catalogue

_DEFAULT_MAX_CHARS = 8000
_DEFAULT_MAX_CHARS_COMPACT = 1500
_DEFAULT_COMPACT_AT_OR_BELOW_B = 70.0

_HEADING = re.compile(r"^#{1,3}\s+(.*\S)\s*$", re.MULTILINE)
_CHECKLIST = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.*\S)\s*$", re.MULTILINE)
_REQUIREMENT = re.compile(r"\b((?:FR|SC|RF|RNF|NFR)-\d+)\b")

_CALIBRATION = (
    "Calibration:\n"
    "  low    - a script or a handful of simple, well-understood pieces\n"
    "  medium - a normal application: several components, some real logic\n"
    "  high   - many interacting parts, non-trivial rules, careful edge cases\n"
    "  top    - large or novel systems, deep domain expertise, heavy constraints\n\n"
)


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
    dim_shape = ", ".join(f'"{d}": "<level>"' for d in rules.dimensions)

    if not rules.require_spans:
        return (
            "You are assessing HOW DEMANDING a software project is to implement.\n"
            f"Rate each dimension ({dims}) on this scale: {levels}.\n\n"
            f"{_CALIBRATION}\n"
            "Answer with THIS JSON object and nothing else. Do not copy, continue or\n"
            "summarise the project documents; do not output tasks, code or file lists:\n"
            f'{{"dimensions": {{{dim_shape}}}, "justification": "<one or two sentences>"}}'
        )

    ev_shape = ", ".join(f'"{d}": "<fragment id>"' for d in rules.dimensions)
    return (
        "You are assessing HOW DEMANDING a software project is to implement.\n"
        f"Rate each dimension ({dims}) on this scale: {levels}.\n\n"
        f"{_CALIBRATION}\n"
        "EVIDENCE IS REQUIRED. For each dimension, FIRST pick the id of the ONE\n"
        "fragment from the CITABLE FRAGMENTS list that best supports your rating,\n"
        "THEN give the level. Use only ids that appear in that list, exactly as\n"
        f'written. If no fragment supports a level, answer "{UNSUPPORTED}" for that\n'
        "dimension and give no id for it. Do not invent ids.\n\n"
        "Answer with THIS JSON object and nothing else. Do not copy, continue or\n"
        "summarise the project documents; do not output tasks, code or file lists:\n"
        f'{{"evidence": {{{ev_shape}}}, "dimensions": {{{dim_shape}}}, '
        '"justification": "<one or two sentences>"}'
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


def artifact_limit(rules: RatingRules, *, compact: bool) -> int:
    """Per-artifact character cap for a prompt shape.

    Exposed because the fragment set must be derived from exactly the text the
    prompt sent — the validator reads this same value.
    """
    if compact:
        return int(rules.judge.get("max_chars_per_artifact_compact", _DEFAULT_MAX_CHARS_COMPACT))
    return int(rules.judge.get("max_chars_per_artifact", _DEFAULT_MAX_CHARS))


def build_prompt(analysis: ProjectAnalysis, rules: RatingRules, *, compact: bool = False) -> str:
    head = _instructions(rules)
    limit = artifact_limit(rules, compact=compact)
    if compact:
        body = _summarize(analysis, limit)
        label = "=== PROJECT SUMMARY ==="
    else:
        chunks = [
            f"\n--- {a.type} ---\n{a.content[:limit]}"
            for a in analysis.artifacts
            if a.readable and a.content
        ]
        body = "".join(chunks)
        label = "=== PROJECT ARTIFACTS ==="

    # The citable list goes in both prompt shapes. The compact prompt sends a digest
    # and no prose, so without an explicit list of ids a small judge would have
    # nothing it could legitimately cite.
    citable = ""
    if rules.require_spans:
        fragments = extract_fragments(analysis, limit)
        citable = f"\n\n=== CITABLE FRAGMENTS ===\n{render_catalogue(fragments)}"

    # Instructions are repeated after the body: small models attend to the end of
    # the prompt, and the tail is what stops them continuing the document.
    return f"{head}\n\n{label}\n{body}{citable}\n\n=== END OF PROJECT ===\n\n{head}"


def _as_mapping(value: object) -> dict:
    """A dict-shaped side map from the judge, or an empty one.

    Judges omit optional maps or send them as null; treating that as "nothing
    cited" keeps the missing-evidence check in one place below.
    """
    return value if isinstance(value, dict) else {}


def _parse_demand(
    raw: object,
    rules: RatingRules,
    fragments: list[Fragment],
) -> DemandProfile | str:
    """Validated profile, or a string describing why the answer is unusable.

    Rejection is deliberately whole-profile, per the design in issue #1: a judge
    that invents one citation has not earned trust in the fields that happen to
    look plausible.
    """
    if not isinstance(raw, dict):
        return f"Expected a JSON object, got {type(raw).__name__}."
    raw_dims = raw.get("dimensions")
    if not isinstance(raw_dims, dict):
        keys = ", ".join(sorted(str(k) for k in raw)[:8]) or "(none)"
        return f"Response has no 'dimensions' object. Keys returned: {keys}."

    allowed = answer_levels(rules.levels)
    dimensions: dict[str, str] = {}
    bad: list[str] = []
    for dim in rules.dimensions:
        value = raw_dims.get(dim)
        text = str(value).strip().lower()
        if text in allowed:
            dimensions[dim] = text
        else:
            bad.append(f"{dim}={value!r}")
    if bad:
        return (
            f"Missing or invalid demand level for: {', '.join(bad)}. "
            f"Expected one of: {', '.join(allowed)}."
        )

    justification = str(raw.get("justification", "")).strip()
    profile = DemandProfile(
        dimensions=dimensions,
        justification=justification or "Demand profile estimated from the project artifacts.",
        judge_model="",  # filled in by the caller, which knows the model
    )

    if not rules.require_spans:
        return profile

    by_id = {f.id: f for f in fragments}
    raw_evidence = _as_mapping(raw.get("evidence"))
    raw_quotes = _as_mapping(raw.get("quotes"))

    for dim, level in dimensions.items():
        if level == UNSUPPORTED:
            profile.evidence[dim] = Evidence(status=EvidenceStatus.UNSUPPORTED)
            continue

        cited = str(raw_evidence.get(dim, "")).strip()
        if not cited:
            return (
                f"Dimension '{dim}' was rated '{level}' with no evidence. Every rated "
                f"dimension must cite a fragment id, or be answered '{UNSUPPORTED}'."
            )

        fragment = by_id.get(cited)
        if fragment is None:
            known = ", ".join(sorted(by_id)[:10]) or "(none)"
            return (
                f"Dimension '{dim}' cites fragment '{cited}', which is not in the text "
                f"the judge was given. Citable ids were: {known}. A fragment that was "
                "truncated out of the prompt is not citable either."
            )

        quote = str(raw_quotes.get(dim, "")).strip() or None
        status = EvidenceStatus.GROUNDED
        if quote is not None and not quote_matches(quote, fragment):
            # The id is the load-bearing citation; a mismatched quote is reported,
            # not fatal, because paraphrase while copying is ordinary model behaviour.
            status = EvidenceStatus.QUOTE_UNVERIFIED
        profile.evidence[dim] = Evidence(status=status, fragment_id=cited, quote=quote)

    return profile


def evidence_warnings(profile: DemandProfile) -> list[str]:
    """User-facing warnings implied by the profile's grounding (FR-020).

    Derived from the profile rather than accumulated during parsing, so the same
    facts are reported wherever a profile comes from.
    """
    warnings: list[str] = []

    unsupported = profile.unsupported_dimensions
    if unsupported:
        warnings.append(
            f"The judge found no supporting evidence for: {', '.join(unsupported)}. "
            f"Those dimensions were left out of the fit calculation, so the "
            f"recommendation rests on the remaining ones."
        )

    unverified = [
        dim for dim, ev in profile.evidence.items() if ev.status is EvidenceStatus.QUOTE_UNVERIFIED
    ]
    if unverified:
        warnings.append(
            f"Quoted wording did not match the cited fragment for: "
            f"{', '.join(unverified)}. The citation itself is valid; only the quote "
            f"could not be confirmed verbatim."
        )

    return warnings


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
        # The fragment set must come from the same text this attempt sends, so it is
        # rebuilt per attempt: the two shapes truncate at different limits.
        fragments = extract_fragments(analysis, artifact_limit(rules, compact=is_compact))
        raw = client.chat_json(judge_model, build_prompt(analysis, rules, compact=is_compact))
        parsed = _parse_demand(raw, rules, fragments)
        if isinstance(parsed, DemandProfile):
            parsed.judge_model = judge_model
            return parsed
        detail = parsed

    raise errors.judge_response_unusable(judge_model, detail)
