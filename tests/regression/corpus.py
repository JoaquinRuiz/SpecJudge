"""Loading the evaluation corpus (issue #5).

Shared by the deterministic regression tests and by `scripts/eval_judge.py`, so
both read the expected profiles the same way and cannot drift apart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

CORPUS_ROOT = Path(__file__).resolve().parents[1] / "fixtures" / "corpus"

CATEGORIES = ("well_specified", "thin", "insufficient", "adversarial")
DATA_STATES = ("sufficient", "scarce", "insufficient")

# A dimension is either a tolerance band or the literal `abstain`.
ABSTAIN = "abstain"


@dataclass(frozen=True)
class Band:
    """The range of levels an answer may fall in and still count as correct.

    Bands rather than exact levels because the labels are human judgement on a
    four-point scale: asserting exactly `high` would fail on `top`, which is not
    a wrong answer. An open end means "no opinion in that direction".
    """

    min: str | None = None
    max: str | None = None

    def contains(self, level: str, levels: list[str]) -> bool:
        if level not in levels:
            return False
        index = levels.index(level)
        if self.min is not None and index < levels.index(self.min):
            return False
        return not (self.max is not None and index > levels.index(self.max))

    def describe(self) -> str:
        if self.min and self.max:
            return f"{self.min}..{self.max}"
        if self.min:
            return f">= {self.min}"
        if self.max:
            return f"<= {self.max}"
        return "any"


@dataclass
class Case:
    name: str
    path: Path
    category: str
    data_state: str
    rationale: str
    # dimension -> Band, or dimension -> ABSTAIN. Absent for insufficient cases,
    # where the judge never runs.
    dimensions: dict[str, Band | str] = field(default_factory=dict)

    @property
    def judged(self) -> bool:
        """Whether this case reaches the judge at all."""
        return self.data_state != "insufficient"


def _parse_dimension(raw: object, where: str) -> Band | str:
    if raw == ABSTAIN:
        return ABSTAIN
    if not isinstance(raw, dict):
        raise ValueError(f"{where}: expected a band mapping or '{ABSTAIN}', got {raw!r}")
    unknown = set(raw) - {"min", "max"}
    if unknown:
        raise ValueError(f"{where}: unknown band keys {sorted(unknown)}")
    return Band(min=raw.get("min"), max=raw.get("max"))


def load_case(directory: Path) -> Case:
    expected_path = directory / "expected.yaml"
    raw = yaml.safe_load(expected_path.read_text(encoding="utf-8"))
    where = str(expected_path)

    if not isinstance(raw, dict):
        raise ValueError(f"{where}: must be a YAML mapping")
    for required in ("category", "data_state", "rationale"):
        if not str(raw.get(required, "")).strip():
            raise ValueError(f"{where}: missing '{required}'")

    dimensions = {
        name: _parse_dimension(value, f"{where}:{name}")
        for name, value in (raw.get("dimensions") or {}).items()
    }

    return Case(
        name=directory.name,
        path=directory,
        category=str(raw["category"]),
        data_state=str(raw["data_state"]),
        rationale=str(raw["rationale"]).strip(),
        dimensions=dimensions,
    )


def load_corpus(root: Path | None = None) -> list[Case]:
    root = root or CORPUS_ROOT
    return [load_case(d) for d in sorted(root.iterdir()) if (d / "expected.yaml").is_file()]
