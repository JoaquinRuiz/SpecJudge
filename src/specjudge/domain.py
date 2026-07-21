"""SpecJudge domain types (data-model.md).

Enums and dataclasses representing artifacts, catalog, evaluations and configuration.
No business logic: just the shape of the data and its basic invariants.
"""

from __future__ import annotations

from dataclasses import dataclass, field
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


class JudgeAvailability(str, Enum):
    """Availability of the judge dependency (FR-011)."""

    OK = "ok"
    DEPENDENCY_MISSING = "dependency_missing"
    NO_LOCAL_MODELS = "no_local_models"
    SELECTED_MODEL_MISSING = "selected_model_missing"


# Ordinal vocabulary of capability/demand levels.
LEVELS = ["low", "medium", "high", "top"]


@dataclass
class Price:
    input_per_million: float
    output_per_million: float
    currency: str
    pricing_date: str | None = None  # YYYY-MM-DD; None => freshness not verifiable

    @property
    def stale(self) -> bool:
        return self.pricing_date is None

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
    type: str  # "constitution" | "spec" | "tasks"
    path: str
    present: bool
    readable: bool
    content: str = ""
    task_count: int = 0  # only meaningful for type == "tasks"


@dataclass
class ProjectAnalysis:
    artifacts: list[SDDArtifact]
    data_state: DataState
    warnings: list[str] = field(default_factory=list)

    def artifact(self, type_: str) -> SDDArtifact | None:
        for a in self.artifacts:
            if a.type == type_:
                return a
        return None


@dataclass
class DemandProfile:
    dimensions: dict[str, str]  # dimension -> level (low..top)
    justification: str
    judge_model: str


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
    # Top three by fit: gold, silver, bronze. Shorter than 3 when fewer models
    # are capable enough; empty when none is. `best_choice` is podium[0].
    podium: list[str] = field(default_factory=list)

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
