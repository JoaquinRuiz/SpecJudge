"""Domain errors and their mapping to exit codes (contracts/cli.md).

Degradation is explicit (Principle IV): every exceptional situation produces an
actionable message and a distinct exit code, never a raw technical dump.
"""

from __future__ import annotations


class SpecJudgeError(Exception):
    """Base class for actionable SpecJudge errors.

    `message` is suitable for direct display to the user. `exit_code` sets the
    process exit status.
    """

    exit_code: int = 1

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint

    def render(self) -> str:
        if self.hint:
            return f"{self.message}\n\n{self.hint}"
        return self.message


class InsufficientInfoError(SpecJudgeError):
    """Not enough project information (FR-009). No recommendation is issued."""

    exit_code = 2


class JudgeUnavailableError(SpecJudgeError):
    """The local judge dependency is unavailable or unresolvable (FR-011)."""

    exit_code = 3


class CatalogError(SpecJudgeError):
    """The model catalog is missing, empty or invalid."""

    exit_code = 4


# ---- Actionable message factories (keeps wording out of the call sites) ----


def ollama_not_running(host: str) -> JudgeUnavailableError:
    return JudgeUnavailableError(
        f"Could not connect to Ollama at {host}.",
        hint=(
            "Ollama is required to run the local judge.\n"
            "  1. Install it from https://ollama.com/download\n"
            "  2. Start it with:  ollama serve\n"
            "  3. Pull at least one model, e.g.:  ollama pull llama3.1:8b"
        ),
    )


def ollama_no_models(host: str) -> JudgeUnavailableError:
    return JudgeUnavailableError(
        f"Ollama is running at {host} but has no local models installed.",
        hint="Pull a model before continuing, for example:  ollama pull llama3.1:8b",
    )


def selected_model_missing(model: str) -> JudgeUnavailableError:
    return JudgeUnavailableError(
        f"The configured judge model ('{model}') is no longer installed in Ollama.",
        hint=(
            "Run again with --set-judge to pick another one, "
            f"or reinstall it with:  ollama pull {model}"
        ),
    )


def judge_response_unusable(model: str, detail: str) -> JudgeUnavailableError:
    """The judge replied, but not with an assessment we can use (Principle IV).

    Guessing here would silently bias the recommendation — a missing demand level
    would fall back to the weakest one and make any project look trivial. Refusing
    to answer is the correct behaviour.
    """
    return JudgeUnavailableError(
        f"The judge '{model}' did not return a usable assessment of this project.",
        hint=(
            f"{detail}\n\n"
            "Small models often lose the instructions in a long prompt and start\n"
            "continuing the document instead of evaluating it. Options:\n"
            "  1. Pick a different judge:      specjudge --set-judge\n"
            "  2. Force one for this run:      specjudge --judge <model>\n\n"
            "No recommendation was produced on purpose: a guess built on an unusable\n"
            "answer would be worse than no answer."
        ),
    )


def catalog_empty(path: str) -> CatalogError:
    return CatalogError(
        f"The model catalog ({path}) contains no models to compare.",
        hint="Add at least one model to data/models.yaml (see the catalog schema).",
    )


def insufficient_project() -> InsufficientInfoError:
    return InsufficientInfoError(
        "Not enough project information to issue a recommendation.",
        hint=(
            "The task list is missing (or empty/unreadable). Generate the project tasks "
            "(e.g. with /speckit-tasks) and run again."
        ),
    )
