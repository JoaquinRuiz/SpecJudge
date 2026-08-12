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
from ..budget import PromptSource, digest_sources, prompt_sources
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
from . import digest
from .fragments import (
    extract_fragments,
    normalize_citation,
    quote_matches,
    render_catalogue,
)

_DEFAULT_MAX_CHARS = 8000
_DEFAULT_MAX_CHARS_COMPACT = 1500
_DEFAULT_COMPACT_AT_OR_BELOW_B = 70.0

_HEADING = re.compile(r"^#{1,3}\s+(.*\S)\s*$", re.MULTILINE)
_CHECKLIST = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.*\S)\s*$", re.MULTILINE)
_REQUIREMENT = re.compile(r"\b((?:FR|SC|RF|RNF|NFR)-\d+)\b")

# Absence of these is worth telling the judge about; absence of anything else is not.
_REPORTED_WHEN_MISSING = frozenset({"constitution", "spec", "tasks"})

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


def use_bulk_prompt(params_b: float | None, rules: RatingRules) -> bool:
    """Whether this judge is asked to separate the bulk of the work from the peak.

    Same shape as `use_compact_prompt`, and for the same measured reason: capacity
    the judge does not have is not free. On the evaluation corpus the extra fields
    cost an 8B judge about five points of accuracy and doubled its refused answers,
    while a 24B judge answered them correctly and lost nothing.

    An unknown size counts as small. A judge that cannot be sized is more likely to
    be small than large, and the failure of guessing wrong in that direction is a
    coarser answer rather than a worse one.
    """
    if not rules.request_bulk:
        return False
    if params_b is None:
        return False
    return params_b > rules.request_bulk_above_params_b


def _instructions(rules: RatingRules, request_bulk: bool) -> str:
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
    bulk_shape = ", ".join(f'"{d}": "<level>"' for d in rules.dimensions)
    bulk_ask = (
        "\nA project is rarely uniform. After rating the hardest part above, also give\n"
        f'"bulk": {{{bulk_shape}}} — the level the MAJORITY of the work needs — and\n'
        '"outliers": ["<fragment id>", ...] — the few fragments that make the hardest\n'
        "part harder than the rest. If the work is uniform, repeat the same levels and\n"
        "return an empty list. Do not guess: omit both if you cannot tell them apart.\n"
        if request_bulk
        else ""
    )
    return (
        "You are assessing HOW DEMANDING a software project is to implement.\n"
        f"Rate each dimension ({dims}) on this scale: {levels}.\n\n"
        f"{_CALIBRATION}\n"
        "EVIDENCE IS REQUIRED. For each dimension, FIRST pick the id of the ONE\n"
        "fragment from the CITABLE FRAGMENTS list most relevant to that dimension,\n"
        "THEN give the level. The fragment anchors your answer in the project; it\n"
        "does not have to prove the level on its own. Use only ids that appear in\n"
        "that list, exactly as written. Do not invent ids.\n\n"
        f'Answer "{UNSUPPORTED}" for a dimension, and give no id, when either:\n'
        "  - nothing in the project bears on it at all, or\n"
        "  - the requirements that bear on it CONTRADICT each other, so the project\n"
        "    cannot be built as written. A project that cannot be built has no\n"
        "    difficulty to estimate; say so rather than pick a level.\n\n"
        "Answer with THIS JSON object and nothing else. Do not copy, continue or\n"
        "summarise the project documents; do not output tasks, code or file lists:\n"
        f"{bulk_ask}"
        f'{{"evidence": {{{ev_shape}}}, "dimensions": {{{dim_shape}}}, '
        '"justification": "<one or two sentences>"}'
    )


def response_schema(rules: RatingRules, request_bulk: bool = False) -> dict:
    """JSON schema constraining the judge's answer (issue #14).

    Ollama's `format: "json"` guarantees valid JSON, not the JSON we asked for.
    The shape only ever lived in the prompt text, and an 8B judge does not honour
    it: measured on the evaluation corpus, `llama3.1` rated every project
    correctly and then put `[true]` where a fragment id belongs, so every run was
    rejected. Constraining generation fixes the type outright.
    """
    dims = list(rules.dimensions)
    levels = answer_levels(rules.levels)

    properties: dict[str, object] = {
        "dimensions": {
            "type": "object",
            "properties": {d: {"type": "string", "enum": levels} for d in dims},
            "required": dims,
        },
        "justification": {"type": "string"},
    }
    required = ["dimensions", "justification"]

    if rules.require_spans:
        # Required so the model fills every slot; a dimension it answers
        # `unsupported` may carry anything here, since the parser ignores
        # evidence for abstained dimensions.
        properties["evidence"] = {
            "type": "object",
            "properties": {d: {"type": "string"} for d in dims},
            "required": dims,
        }
        properties["quotes"] = {
            "type": "object",
            "properties": {d: {"type": "string"} for d in dims},
        }
        required.append("evidence")

    if request_bulk:
        # Deliberately NOT required. A judge that cannot separate the bulk from the
        # peak degrades to the conservative single-level answer, which is the
        # behaviour that existed before this asked. Forcing the slot would make a
        # small judge fill it with something, and an invented bulk is worse than
        # none: it silently lowers the recommendation (FR-027).
        properties["bulk"] = {
            "type": "object",
            "properties": {d: {"type": "string", "enum": levels} for d in dims},
        }
        properties["outliers"] = {"type": "array", "items": {"type": "string"}}

    return {"type": "object", "properties": properties, "required": required}


def _digest(analysis: ProjectAnalysis, sources: list[PromptSource]) -> str:
    """The compact body: what each source contains, built over the whole source.

    A missing spec or task list is signal — the judge should know the work was never
    described. A missing CLAUDE.md is not: most repositories have none, and listing
    every absent optional source would pad the prompt with nothing (FR-024).
    """
    present = {s.type for s in sources}
    parts = digest.missing_lines(analysis, _REPORTED_WHEN_MISSING, present)
    parts.extend(digest.shape_only(source.text) for source in sources)
    return "\n".join(parts)


def artifact_limit(rules: RatingRules, *, compact: bool) -> int:
    """Per-artifact character cap for a prompt shape.

    Exposed because the fragment set must be derived from exactly the text the
    prompt sent — the validator reads this same value.
    """
    if compact:
        return int(rules.judge.get("max_chars_per_artifact_compact", _DEFAULT_MAX_CHARS_COMPACT))
    return int(rules.judge.get("max_chars_per_artifact", _DEFAULT_MAX_CHARS))


def build_prompt(
    analysis: ProjectAnalysis,
    rules: RatingRules,
    *,
    compact: bool = False,
    request_bulk: bool = False,
) -> str:
    head = _instructions(rules, request_bulk)
    limit = artifact_limit(rules, compact=compact)
    # One place decides how much of each source is sent, so the prompt and the
    # citable set cannot disagree about what the judge was shown (FR-025).
    if compact:
        sources = digest_sources(analysis, limit)
        body = _digest(analysis, sources)
        label = "=== PROJECT SUMMARY ==="
    else:
        sources = prompt_sources(analysis, limit)
        body = "".join(f"\n--- {s.label} ---\n{s.text}" for s in sources)
        label = "=== PROJECT ARTIFACTS ==="

    # The citable list goes in both prompt shapes. The compact prompt sends a digest
    # and no prose, so without an explicit list of ids a small judge would have
    # nothing it could legitimately cite.
    citable = ""
    if rules.require_spans:
        fragments = extract_fragments(analysis, limit, compact=compact)
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
    request_bulk: bool = False,
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
        bulk=_parse_bulk(raw, dimensions, rules, request_bulk),
        outliers=_parse_outliers(raw),
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

        cited = normalize_citation(str(raw_evidence.get(dim, "")))
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


def _parse_bulk(
    raw: dict, dimensions: dict[str, str], rules: RatingRules, request_bulk: bool
) -> dict[str, str]:
    """The level the bulk of the work needs, where the judge gave a usable one.

    Silently permissive on purpose: a missing or malformed bulk degrades to "same as
    the peak" (see `DemandProfile.bulk_dimensions`), which is the conservative
    answer and the behaviour that existed before this was asked. Rejecting the whole
    profile over an optional field would trade a better output shape for a run that
    fails, which is a bad trade.

    A bulk *above* the peak is dropped rather than kept: the peak is by definition
    the hardest part, so a higher bulk is a judge contradicting itself, and the
    conservative reading is that it did not distinguish them at all.
    """
    if not request_bulk:
        return {}
    raw_bulk = _as_mapping(raw.get("bulk"))
    if not raw_bulk:
        return {}

    bulk: dict[str, str] = {}
    for dim, peak in dimensions.items():
        if peak == UNSUPPORTED:
            continue
        value = str(raw_bulk.get(dim, "")).strip().lower()
        if value not in rules.levels or peak not in rules.levels:
            continue
        if rules.levels.index(value) > rules.levels.index(peak):
            continue
        bulk[dim] = value
    return bulk


def _parse_outliers(raw: dict) -> list[str]:
    """Fragment ids the judge blamed for the peak, normalised and deduplicated.

    Not validated against the citable set. An id that does not exist is noise in a
    presentational list, whereas a fabricated *citation* is a reason to reject the
    profile — the two deserve different reactions, and conflating them would make
    an optional field able to fail a run.
    """
    values = raw.get("outliers")
    if not isinstance(values, list):
        return []
    seen: list[str] = []
    for value in values:
        cited = normalize_citation(str(value))
        if cited and cited not in seen:
            seen.append(cited)
    return seen


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


def envelope_fragments(
    analysis: ProjectAnalysis,
    rules: RatingRules,
    client: OllamaClient,
    judge_model: str,
) -> list[Fragment]:
    """The fragment set the judge was shown, for looking its citations up afterwards.

    Lives here because it has to follow the same shape decision the prompt did. The
    callers used to build it with the compact limit unconditionally, so for a judge
    large enough to receive the full prose every citation missed the lookup and the
    constraint table came out with no text and every row marked customary — silently,
    which is the part that matters (issue #29).
    """
    compact = use_compact_prompt(client.model_params_b(judge_model), rules)
    return extract_fragments(analysis, artifact_limit(rules, compact=compact), compact=compact)


def estimate_demand(
    analysis: ProjectAnalysis,
    rules: RatingRules,
    client: OllamaClient,
    judge_model: str,
) -> DemandProfile:
    params_b = client.model_params_b(judge_model)
    compact = use_compact_prompt(params_b, rules)
    request_bulk = use_bulk_prompt(params_b, rules)

    # Try the chosen shape; if it comes back unusable, retry once with the compact
    # shape before giving up (a long prompt is the usual cause of a bad answer).
    attempts = [compact] if compact else [False, True]
    detail = ""
    for is_compact in attempts:
        # The fragment set must come from the same text this attempt sends, so it is
        # rebuilt per attempt: the two shapes truncate at different limits.
        fragments = extract_fragments(
            analysis, artifact_limit(rules, compact=is_compact), compact=is_compact
        )
        raw = client.chat_json(
            judge_model,
            build_prompt(analysis, rules, compact=is_compact, request_bulk=request_bulk),
            schema=response_schema(rules, request_bulk),
        )
        parsed = _parse_demand(raw, rules, fragments, request_bulk)
        if isinstance(parsed, DemandProfile):
            parsed.judge_model = judge_model
            return parsed
        detail = parsed

    raise errors.judge_response_unusable(judge_model, detail)
