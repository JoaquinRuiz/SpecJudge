"""HTTP client for the local judge (Ollama).

All traffic goes to `localhost` (Principle I / NFR-1). Detects dependency
availability and translates failures into actionable errors (FR-011).
"""

from __future__ import annotations

import json

import httpx

from .. import errors

# Sampling is pinned so the same project yields the same assessment twice (FR-021).
# Two runs disagreeing about which model to buy is hard to defend in a tool about
# spending money, and without it the judge evaluation suite cannot tell a prompt
# change from sampling noise.
#
# This pins *sampling*, not the world: a different Ollama release, quantisation or
# context size can still move the answer. Reproducible on one machine, not
# comparable across two.
JUDGE_SEED = 20260803
JUDGE_OPTIONS = {"temperature": 0, "seed": JUDGE_SEED}

# Structured outputs — a JSON schema in `format` rather than the string "json" —
# arrived in Ollama 0.5.0. Below that the schema is rejected, so the requirement is
# stated up front instead of surfacing as a 400 mid-run (issue #14).
MIN_OLLAMA_VERSION = (0, 5, 0)


def parse_version(raw: str) -> tuple[int, ...] | None:
    """Ollama's version string as comparable integers, or None if unrecognisable.

    Unrecognisable is not an error: a fork or a dev build should not be blocked
    from running on the strength of a version string we failed to parse.
    """
    cleaned = raw.strip().lstrip("v").split("-")[0].split("+")[0]
    parts = cleaned.split(".")
    try:
        return tuple(int(p) for p in parts[:3])
    except ValueError:
        return None


class OllamaClient:
    def __init__(self, host: str = "http://localhost:11434", timeout: float = 120.0) -> None:
        self.host = host.rstrip("/")
        self.timeout = timeout

    def list_models(self) -> list[str]:
        """List the installed local models (GET /api/tags).

        Raises JudgeUnavailableError if Ollama does not respond (dependency_missing).
        """
        url = f"{self.host}/api/tags"
        try:
            resp = httpx.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise errors.ollama_not_running(self.host) from exc
        except httpx.HTTPError as exc:
            raise errors.JudgeUnavailableError(
                f"Ollama returned an error at {url}: {exc}",
                hint="Check that Ollama is running:  ollama serve",
            ) from exc

        data = resp.json()
        models = [m.get("name", "") for m in data.get("models", []) if m.get("name")]
        return models

    def model_params_b(self, model: str) -> float | None:
        """Parameter count of a local model, in billions (None if unknown).

        Read from Ollama's `details.parameter_size` (e.g. "8.0B"). Used to decide
        how much project text the judge can be trusted to handle.
        """
        try:
            resp = httpx.get(f"{self.host}/api/tags", timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        for entry in resp.json().get("models", []):
            if entry.get("name") != model:
                continue
            raw = str(entry.get("details", {}).get("parameter_size", "")).strip()
            try:
                return float(raw.rstrip("Bb"))
            except ValueError:
                return None
        return None

    def version(self) -> str | None:
        """Ollama's reported version (GET /api/version), or None if unavailable."""
        try:
            resp = httpx.get(f"{self.host}/api/version", timeout=self.timeout)
            resp.raise_for_status()
        except httpx.HTTPError:
            return None
        raw = resp.json().get("version")
        return str(raw) if raw else None

    def supports_structured_output(self) -> bool:
        """Whether this Ollama accepts a JSON schema in `format` (issue #14).

        An unreadable or unparseable version is treated as supported: refusing to
        run because a version string was not recognised would be worse than
        letting the request fail with the actionable error in `chat_json`.
        """
        raw = self.version()
        if raw is None:
            return True
        parsed = parse_version(raw)
        if parsed is None:
            return True
        return parsed >= MIN_OLLAMA_VERSION

    def ensure_available(self, required_model: str | None = None) -> list[str]:
        """Full availability check (FR-011). Returns the list of models.

        - No connection -> ollama_not_running (dependency_missing).
        - Connected but empty list -> ollama_no_models (no_local_models).
        - required_model not installed -> selected_model_missing.
        """
        models = self.list_models()
        if not models:
            raise errors.ollama_no_models(self.host)
        if required_model is not None and required_model not in models:
            raise errors.selected_model_missing(required_model)
        return models

    def chat_json(self, model: str, prompt: str, schema: dict | None = None) -> dict:
        """Ask the model for a JSON response (POST /api/chat, stream=false).

        With a `schema`, generation is constrained to it (Ollama structured
        outputs). Without one, `format: "json"` only guarantees *some* valid JSON
        — which is how an 8B judge came to answer with `[true]` where a fragment
        id belonged (issue #14).
        """
        url = f"{self.host}/api/chat"
        payload = {
            "model": model,
            "stream": False,
            "format": schema if schema is not None else "json",
            "options": dict(JUDGE_OPTIONS),
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = httpx.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise errors.ollama_not_running(self.host) from exc
        except httpx.HTTPError as exc:
            if schema is not None:
                # The likeliest cause by far: an Ollama too old to accept a schema
                # in `format`. Saying so beats echoing a bare 400 (Principle IV).
                raise errors.ollama_too_old_for_schema(self.host, self.version()) from exc
            raise errors.JudgeUnavailableError(
                f"Ollama failed to evaluate with model '{model}': {exc}",
                hint="Check that the model is installed:  ollama pull " + model,
            ) from exc

        body = resp.json()
        content = body.get("message", {}).get("content", "")
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise errors.JudgeUnavailableError(
                f"The judge '{model}' did not return valid JSON.",
                hint="Try another judge model (--set-judge) that supports structured output.",
            ) from exc
