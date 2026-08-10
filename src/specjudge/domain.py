"""SpecJudge domain types (data-model.md).

Enums and dataclasses representing artifacts, catalog, evaluations and configuration.
No business logic: just the shape of the data and its basic invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class Rating(str, Enum):
    """Closed rating scale (FR-004).

    poor     -> not capable enough for the project
    fair     -> falls somewhat short
    good     -> right fit (the sweet spot)
    overkill -> capable, but likely overpriced for this work
    """

    POOR = "poor"
    FAIR = "fair"
    GOOD = "good"
    OVERKILL = "overkill"

    @property
    def order(self) -> int:
        return {"poor": 0, "fair": 1, "good": 2, "overkill": 3}[self.value]


class DataState(str, Enum):
    """State of the project information (FR-009/010)."""

    INSUFFICIENT = "insufficient"
    SCARCE = "scarce"
    SUFFICIENT = "sufficient"


class ExecutionModel(str, Enum):
    """How the project is going to be implemented (FR-028).

    Not a property of the project: a property of whoever executes it. Whether one
    unusually demanding task is decisive depends entirely on whether the person
    implementing can switch models halfway through.

    * `single` — one model does all the work, so it must clear the hardest part.
      Ordering by the peak is correct here, and it is the conservative default.
    * `escalating` — the model can change per task, so the bulk of the work sets
      the default and the outliers become explicit escalation triggers.
    """

    SINGLE = "single"
    ESCALATING = "escalating"


class JudgeAvailability(str, Enum):
    """Availability of the judge dependency (FR-011)."""

    OK = "ok"
    DEPENDENCY_MISSING = "dependency_missing"
    NO_LOCAL_MODELS = "no_local_models"
    SELECTED_MODEL_MISSING = "selected_model_missing"


# Ordinal vocabulary of capability/demand levels.
LEVELS = ["low", "medium", "high", "top"]

# The judge may answer this instead of a level when it cannot point at a fragment
# supporting one (FR-020).
#
# It is a peer value in the *judge's answer vocabulary* but deliberately NOT a
# member of LEVELS: LEVELS is an ordinal scale shared with model capabilities, and
# `unsupported` has no position on it. A model cannot be "unsupported" at reasoning,
# and giving the word an index would silently make it compare as better or worse
# than a real level.
UNSUPPORTED = "unsupported"


def answer_levels(levels: list[str]) -> list[str]:
    """The values the judge is allowed to return for a dimension."""
    return [*levels, UNSUPPORTED]


# Enough for a root file plus a handful of per-package ones, few enough that the
# shared character budget still leaves each of them something worth reading.
DEFAULT_MAX_CONTEXT_FILES = 12

# Below this, asking for a bulk/peak split makes a judge worse at the levels it was
# already getting right. Measured, not assumed: see docs/judges.md.
DEFAULT_BULK_ABOVE_PARAMS_B = 20.0

# Prices move every few weeks, so a quarter-old catalog is worth flagging. Short
# enough to catch real drift, long enough not to cry wolf on every run.
DEFAULT_MAX_PRICING_AGE_DAYS = 90


@dataclass
class Price:
    input_per_million: float
    output_per_million: float
    currency: str
    pricing_date: str | None = None  # YYYY-MM-DD; None => freshness not verifiable

    @property
    def stale(self) -> bool:
        """True when there is no date at all: freshness cannot be verified (FR-018).

        This is NOT "the price is old" — for that, see `age_days`. The two are
        reported separately and must not be collapsed: a missing date is
        *unverifiable*, an old date is *verifiably out of date*.
        """
        return self.pricing_date is None

    def age_days(self, today: date) -> int | None:
        """Days elapsed since `pricing_date` (FR-019).

        Returns None when the date is absent or not a parseable ISO date — an
        unusable date is treated as unverifiable, never as age zero. A date in
        the future clamps to 0 rather than going negative.
        """
        if self.pricing_date is None:
            return None
        try:
            priced_on = date.fromisoformat(self.pricing_date)
        except ValueError:
            return None
        return max(0, (today - priced_on).days)

    @property
    def is_free(self) -> bool:
        """No per-token cost: open-weight models you self-host, or a free tier."""
        return self.input_per_million == 0 and self.output_per_million == 0

    @property
    def sort_key(self) -> tuple[float, float]:
        """Price ordering metric (data-model.md): output as proxy, input breaks ties."""
        return (self.output_per_million, self.input_per_million)


@dataclass
class SDDArtifact:
    """One written source of project context.

    `type` is open, not a closed set: alongside the spec-kit artifacts
    ("constitution", "spec", "tasks", "plan") it carries agent-context files
    ("agents", "claude") and whatever discovery grows to support (FR-024). The
    class keeps its name because it is reachable through the public API.
    """

    type: str
    path: str
    present: bool
    readable: bool
    content: str = ""
    task_count: int = 0  # only meaningful for type == "tasks"

    @property
    def usable(self) -> bool:
        """Present, readable, and carrying something worth sending to a judge."""
        return self.present and self.readable and bool(self.content.strip())


@dataclass
class ProjectAnalysis:
    artifacts: list[SDDArtifact]
    data_state: DataState
    warnings: list[str] = field(default_factory=list)
    # Where the project was read from. Kept so a source can be named to the judge
    # by its path within the project ("packages/api/AGENTS.md" says which corner of
    # a monorepo it governs) rather than by an absolute path from this machine.
    root: str = ""

    def artifact(self, type_: str) -> SDDArtifact | None:
        for a in self.artifacts:
            if a.type == type_:
                return a
        return None

    @property
    def source_kinds(self) -> list[str]:
        """One entry per source file that contributed content, in read order."""
        return [a.type for a in self.artifacts if a.usable]

    @property
    def sources_read(self) -> list[str]:
        """Kinds of source that contributed content, deduplicated, in read order.

        Deduplicated because this is the payload's answer to "what fed this?", and
        a repository with 88 `AGENTS.md` would otherwise put the word "agents" in
        the JSON 88 times — no more informative, and awkward for a consumer that
        renders the list as-is. How many of each there were is a presentation
        concern; `source_kinds` keeps it.
        """
        seen: list[str] = []
        for kind in self.source_kinds:
            if kind not in seen:
                seen.append(kind)
        return seen

    @property
    def environment_only(self) -> bool:
        """Context describes the repository, but nothing describes the work (FR-024).

        The honest output here is a floor — "given these standards, you need at
        least this much" — not a ranking with the confidence of one built on a
        described project. Reported as its own field rather than by redefining
        `data_state`, so no existing value changes meaning.
        """
        from .sources import is_environment

        usable = self.sources_read
        return bool(usable) and all(is_environment(t) for t in usable)


@dataclass
class Fragment:
    """A citable unit of the project text, offered to the judge by id (FR-020).

    Fragments are derived from exactly the text sent to the judge, so an id the
    judge returns can be checked against a closed set rather than fuzzy-matched.
    """

    id: str
    artifact_type: str  # "constitution" | "spec" | "tasks"
    text: str


class EvidenceStatus(str, Enum):
    """How well a dimension's citation held up against the input (FR-020)."""

    GROUNDED = "grounded"  # cited fragment exists; quote (if any) found in it
    QUOTE_UNVERIFIED = "quote_unverified"  # fragment exists, quote did not match
    UNSUPPORTED = "unsupported"  # judge found no fragment to cite


@dataclass
class Evidence:
    """The judge's citation for one dimension."""

    status: EvidenceStatus
    fragment_id: str | None = None
    quote: str | None = None


@dataclass
class Constraint:
    """One row of the constraint table (FR-027).

    What is being demanded, how much, and the piece of the project that demands
    it — so a reader who disagrees can argue with a fragment rather than with a
    verdict.
    """

    dimension: str
    level: str
    fragment_id: str | None = None
    text: str = ""
    # Whether the citation is a stated requirement (RFC 2119 wording, or a
    # numbered requirement id) rather than something merely customary. Derived
    # from the text, never asked of the judge: a user can inspect a fragment and
    # disagree with it; they cannot inspect an opinion.
    hard: bool = False


@dataclass
class Envelope:
    """The demand as a range with named causes, not a single verdict (FR-027).

    A task set with twenty mechanical edits and one architecture decision does not
    have *a* complexity. Reporting only the peak makes the architecture decision
    get paid for twenty-one times; reporting only the bulk under-serves the one
    part that decides whether the project works.
    """

    execution_model: ExecutionModel
    # The levels the ranking is built on: the bulk when escalation is possible,
    # the peak when one model has to do everything.
    default_demand: dict[str, str] = field(default_factory=dict)
    peak_demand: dict[str, str] = field(default_factory=dict)
    constraints: list[Constraint] = field(default_factory=list)
    # Constraints whose peak exceeds the default: the parts you would escalate for.
    escalations: list[Constraint] = field(default_factory=list)

    @property
    def is_uniform(self) -> bool:
        """The project asks the same of every part of the work."""
        return not self.escalations


@dataclass
class DemandProfile:
    # dimension -> level (a member of LEVELS) or UNSUPPORTED.
    dimensions: dict[str, str]
    justification: str
    judge_model: str
    # dimension -> citation. Parallel map rather than nesting inside `dimensions`:
    # a flat shape is markedly easier for a small local judge to emit correctly,
    # and it keeps `dimensions` the same type the rating engine already consumes.
    evidence: dict[str, Evidence] = field(default_factory=dict)
    # The level the *bulk* of the work needs, where the judge distinguished it
    # from the peak (FR-027). Empty means it did not, and the envelope degrades
    # to a single level rather than inventing a second one.
    bulk: dict[str, str] = field(default_factory=dict)
    # Fragment ids the judge named as the outliers driving the peak.
    outliers: list[str] = field(default_factory=list)

    @property
    def bulk_dimensions(self) -> dict[str, str]:
        """Bulk levels where the judge gave them, peak levels where it did not."""
        scored = self.scored_dimensions
        return {dim: self.bulk.get(dim, level) for dim, level in scored.items()}

    @property
    def distinguishes_bulk(self) -> bool:
        return bool(self.bulk)

    @property
    def scored_dimensions(self) -> dict[str, str]:
        """Only the dimensions the judge actually put a level on."""
        return {d: lvl for d, lvl in self.dimensions.items() if lvl != UNSUPPORTED}

    @property
    def unsupported_dimensions(self) -> list[str]:
        return [d for d, lvl in self.dimensions.items() if lvl == UNSUPPORTED]

    @property
    def coverage(self) -> str:
        """Human-readable grounding ratio, e.g. '2 of 3 dimensions grounded'."""
        total = len(self.dimensions)
        grounded = sum(1 for e in self.evidence.values() if e.status is EvidenceStatus.GROUNDED)
        return f"{grounded} of {total} dimensions grounded in cited evidence"


@dataclass
class CatalogModel:
    id: str
    name: str
    capabilities: dict[str, str]  # dimension -> level
    price: Price
    provider: str | None = None
    notes: str | None = None
    # Model line the user thinks in terms of (Claude, GPT, Gemini, Qwen...). Used
    # to filter the report; falls back to the provider when the catalog omits it.
    family: str | None = None
    # Open weights: downloadable and self-hostable, regardless of what a hosted
    # API charges for it.
    open_source: bool = False


@dataclass
class RatingRules:
    version: int
    dimensions: list[str]
    scarce_thresholds: dict[str, int]
    per_dimension: dict[str, str]
    aggregation: str
    levels: list[str] = field(default_factory=lambda: list(LEVELS))
    # How the project is presented to the judge (see data/rating-rules.yaml).
    judge: dict = field(default_factory=dict)
    # Days since pricing_date before the catalog is called out as stale (FR-019).
    max_pricing_age_days: int = DEFAULT_MAX_PRICING_AGE_DAYS
    # Whether the judge is also asked to separate the bulk of the work from its
    # hardest part (FR-027). Turning it off restores the single-level answer for
    # judges too small to manage the extra slots, at the cost of the envelope.
    request_bulk: bool = True
    # Only judges above this size are asked for it: measured, the extra fields cost a
    # small judge more accuracy than the envelope is worth to it (FR-027).
    request_bulk_above_params_b: float = DEFAULT_BULK_ABOVE_PARAMS_B
    # How the project is assumed to be implemented when the caller does not say
    # (FR-028). Conservative by default: one model must clear the hardest part.
    execution_model: ExecutionModel = ExecutionModel.SINGLE
    # How many context files (AGENTS.md, ADRs, ...) may feed one run (FR-025).
    # A monorepo can carry dozens; reading all of them would swamp the prompt with
    # near-duplicates of one another.
    max_context_files: int = DEFAULT_MAX_CONTEXT_FILES
    # Whether the judge must cite a fragment per dimension (FR-020). Turning this
    # off restores the pre-evidence behaviour for judges too small to manage the
    # citation schema — at the cost of the grounding check.
    require_spans: bool = True


@dataclass
class Evaluation:
    model_id: str
    model_name: str
    rating: Rating
    justification: str
    price: Price
    # Fit against the project's demand, summed over dimensions (in ordinal steps).
    # deficit > 0 => under-capable somewhere (cannot do the job).
    # excess  > 0 => more capable than needed (right-sized when excess == 0).
    deficit: int = 0
    excess: int = 0
    family: str | None = None
    open_source: bool = False

    @property
    def price_stale(self) -> bool:
        return self.price.stale

    @property
    def fits(self) -> bool:
        """Capable enough in every dimension."""
        return self.deficit == 0


@dataclass
class Comparison:
    evaluations: list[Evaluation]
    data_state: DataState
    judge_model: str | None
    best_choice: str | None  # model_id or None
    warnings: list[str] = field(default_factory=list)
    # The judge's assessment, carried through so the evidence behind the
    # recommendation is auditable in the output rather than discarded (FR-020).
    demand: DemandProfile | None = None
    # Top three by fit: gold, silver, bronze. Shorter than 3 when fewer models
    # are capable enough; empty when none is. `best_choice` is podium[0].
    podium: list[str] = field(default_factory=list)
    # One entry per source file that fed the assessment, in read order (FR-024).
    # Reported because the answer now depends on it: the same repository judged
    # from an AGENTS.md and judged from a spec are two different claims, and only
    # one of them says so. Repeats are meaningful here — four AGENTS.md is a
    # different input from one — while the JSON payload publishes the deduplicated
    # view, which is the part a consumer can branch on.
    source_kinds: list[str] = field(default_factory=list)
    # True when nothing described the work — see ProjectAnalysis.environment_only.
    environment_only: bool = False
    # The demand as a range with named causes (FR-027). None when there is no
    # profile to build one from.
    envelope: Envelope | None = None

    @property
    def sources_read(self) -> list[str]:
        """Kinds of source that fed the assessment, deduplicated, in read order."""
        seen: list[str] = []
        for kind in self.source_kinds:
            if kind not in seen:
                seen.append(kind)
        return seen

    def medal(self, model_id: str) -> str | None:
        """'gold' | 'silver' | 'bronze' for a podium model, else None."""
        names = ("gold", "silver", "bronze")
        for position, mid in enumerate(self.podium[: len(names)]):
            if mid == model_id:
                return names[position]
        return None


@dataclass
class JudgePreference:
    judge_model: str
    chosen_at: str | None = None


@dataclass
class UserConfig:
    ollama_host: str = "http://localhost:11434"
    judge_preference: JudgePreference | None = None
