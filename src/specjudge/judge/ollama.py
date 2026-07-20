"""HTTP client for the local judge (Ollama).

All traffic goes to `localhost` (Principle I / NFR-1). Detects dependency
availability and translates failures into actionable errors (FR-011).
"""

from __future__ import annotations

import json

import httpx

from .. import errors


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

    def chat_json(self, model: str, prompt: str) -> dict:
        """Ask the model for a JSON response (POST /api/chat, stream=false)."""
        url = f"{self.host}/api/chat"
        payload = {
            "model": model,
            "stream": False,
            "format": "json",
            "messages": [{"role": "user", "content": prompt}],
        }
        try:
            resp = httpx.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise errors.ollama_not_running(self.host) from exc
        except httpx.HTTPError as exc:
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
