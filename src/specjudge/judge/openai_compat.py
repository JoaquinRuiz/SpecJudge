"""HTTP client for any OpenAI-compatible judge endpoint (FR-011, issue #4).

The judge used to be Ollama and only Ollama. That was never a statement about
Ollama — it was the shortest path to a judge that runs on your own machine — but it
did exclude every other way of running one: llama.cpp's server, vLLM, LM Studio,
LocalAI, a model on a box you own on your own network. All of them speak the same
protocol, so all of them work here now, and so does a hosted endpoint for anyone who
decides that trade is theirs to make.

**This does not sit on top of Principle I, it sits underneath it.** Local stays the
default and nothing reaches a third party unless the user configures a non-local base
URL themselves. When they have, `is_remote` is true and every run says so out loud —
once in the report and once in the warnings — because a privacy guarantee that quietly
stops holding is worse than never having made it.

Two things the OpenAI protocol has no answer for, which is why `ollama.py` is still
here rather than replaced:

* **Model size.** `use_compact_prompt` needs a parameter count, and Ollama serves one
  from `/api/tags`. `/v1/models` carries no such field in any implementation, so a
  local Ollama keeps its native client and the size it reports. For an endpoint that
  cannot be asked, see `ASSUMED_PARAMS_B`.
* **Structured-output support.** Ollama's version gate (issue #14) is an Ollama
  version. Elsewhere the schema is simply sent, and a server that cannot honour it
  fails with its own message rather than one we invented for it.
"""

from __future__ import annotations

import json
import os

import httpx

from .. import errors

# What to assume about a judge whose size cannot be read. `/v1/models` does not carry
# a parameter count, so a remote endpoint has to be guessed at, and guessing "small"
# — which is what an unknown size means everywhere else — would send a compact digest
# to a frontier model and throw away the one advantage of using it. Anything reached
# over a network the user opted into is treated as large instead; `judge.params_b` in
# the config overrides this for a self-hosted endpoint serving something small.
ASSUMED_PARAMS_B = 1000.0

# Hosts that are the user's own machine, and therefore not a third party.
_LOCAL_HOSTS = frozenset({"localhost", "127.0.0.1", "::1", "0.0.0.0"})


def is_local_url(url: str) -> bool:
    """Whether a base URL points at this machine.

    Decides whether Principle I still holds untouched for this run, so it answers
    conservatively: anything it cannot parse counts as remote. A URL we failed to
    read is not evidence that it is safe.
    """
    try:
        host = httpx.URL(url).host
    except (httpx.InvalidURL, ValueError, TypeError):
        return False
    return host in _LOCAL_HOSTS


class OpenAICompatibleClient:
    """A judge behind `/v1/chat/completions`, wherever it is running.

    Mirrors `OllamaClient`'s surface rather than sharing a base class with it: the
    two agree on what the rest of the pipeline asks for and disagree on almost
    everything underneath, and a shared parent would only be a place to put the
    disagreements.
    """

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None = None,
        params_b: float | None = None,
        timeout: float = 120.0,
    ) -> None:
        self.host = base_url.rstrip("/")
        self.timeout = timeout
        self._api_key = api_key
        self._params_b = params_b

    @property
    def is_remote(self) -> bool:
        return not is_local_url(self.host)

    def _headers(self) -> dict[str, str]:
        if not self._api_key:
            return {}
        return {"Authorization": f"Bearer {self._api_key}"}

    def list_models(self) -> list[str]:
        """Model ids the endpoint serves (GET /v1/models)."""
        url = f"{self.host}/v1/models"
        try:
            resp = httpx.get(url, timeout=self.timeout, headers=self._headers())
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise errors.endpoint_unreachable(self.host) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise errors.endpoint_unauthorized(self.host) from exc
            raise errors.endpoint_failed(self.host, str(exc)) from exc
        except httpx.HTTPError as exc:
            raise errors.endpoint_failed(self.host, str(exc)) from exc

        data = resp.json()
        entries = data.get("data", []) if isinstance(data, dict) else []
        return [str(m.get("id", "")) for m in entries if m.get("id")]

    def model_params_b(self, model: str) -> float | None:
        """Size of the judge, which this protocol does not report.

        Returns whatever the user configured, then the remote assumption, and None
        for a local endpoint — where "unknown" already means "treat it as small",
        and where someone running llama.cpp on their laptop is far more likely to be
        serving an 8B than a frontier model.
        """
        if self._params_b is not None:
            return self._params_b
        return ASSUMED_PARAMS_B if self.is_remote else None

    def supports_structured_output(self) -> bool:
        """Assumed. There is no version endpoint to ask, so the request is the test."""
        return True

    def ensure_available(self, required_model: str | None = None) -> list[str]:
        """Availability check (FR-011), in the same shape `OllamaClient` uses.

        An endpoint that serves no listable models is not treated as broken: some
        gateways deliberately return an empty list while serving a model perfectly
        well, so only an explicitly missing *requested* model is an error.
        """
        models = self.list_models()
        if required_model is not None and models and required_model not in models:
            raise errors.endpoint_model_missing(required_model, self.host)
        return models

    def chat_json(
        self, model: str, prompt: str, schema: dict | None = None, seed: int | None = None
    ) -> dict:
        """Ask the model for JSON (POST /v1/chat/completions).

        A schema goes in `response_format` as `json_schema`, which is where the
        OpenAI protocol puts what Ollama puts in `format`. Servers that do not
        implement it fall back to their own error rather than to loose JSON: a judge
        that silently ignored the schema is how `[true]` once arrived where a
        fragment id belonged (issue #14), and that is worth failing over.
        """
        url = f"{self.host}/v1/chat/completions"
        payload: dict = {
            "model": model,
            "temperature": 0,
            "messages": [{"role": "user", "content": prompt}],
        }
        if seed is not None:
            payload["seed"] = seed
        if schema is not None:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "demand", "strict": True, "schema": schema},
            }
        else:
            payload["response_format"] = {"type": "json_object"}

        try:
            resp = httpx.post(url, json=payload, timeout=self.timeout, headers=self._headers())
            resp.raise_for_status()
        except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
            raise errors.endpoint_unreachable(self.host) from exc
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (401, 403):
                raise errors.endpoint_unauthorized(self.host) from exc
            raise errors.endpoint_failed(self.host, str(exc)) from exc
        except httpx.HTTPError as exc:
            raise errors.endpoint_failed(self.host, str(exc)) from exc

        body = resp.json()
        choices = body.get("choices") or []
        content = choices[0].get("message", {}).get("content", "") if choices else ""
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            raise errors.JudgeUnavailableError(
                f"The judge '{model}' at {self.host} did not return valid JSON.",
                hint="Try another judge model that supports structured output.",
            ) from exc


def api_key_from_env(var_name: str | None) -> str | None:
    """The key named by `judge.api_key_env`, read at run time and never stored.

    The config file holds the *name* of the variable, not the value. A key in a
    dotfile outlives the reason it was put there, and this tool has no business
    being the place someone's credentials leak from.
    """
    if not var_name:
        return None
    value = os.environ.get(var_name)
    return value or None
