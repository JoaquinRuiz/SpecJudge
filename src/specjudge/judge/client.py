"""Choosing a judge backend, and saying so when it is not local (issue #4).

One place decides which client the run uses, because the decision carries a promise
with it. Principle I says a user's specs never reach a third party during normal use;
that stays true by construction while the judge is local, and the moment it is not,
this is where the tool starts having to say so out loud.

The default is unchanged and deliberately so: no config, no flag, local Ollama. A
remote endpoint is never inferred, never fallen back to, and never reached because
something local failed — it happens only when the user wrote a base URL down.
"""

from __future__ import annotations

from typing import Protocol

from ..domain import JudgeEndpoint, UserConfig
from .ollama import OllamaClient
from .openai_compat import OpenAICompatibleClient, api_key_from_env, is_local_url


class JudgeClient(Protocol):
    """What the pipeline asks of a judge, whichever protocol it speaks."""

    host: str

    def list_models(self) -> list[str]: ...
    def model_params_b(self, model: str) -> float | None: ...
    def supports_structured_output(self) -> bool: ...
    def ensure_available(self, required_model: str | None = None) -> list[str]: ...
    def chat_json(
        self, model: str, prompt: str, schema: dict | None = None, seed: int | None = None
    ) -> dict: ...


def is_remote(client: JudgeClient) -> bool:
    """Whether this run sends the project's text off the machine."""
    return bool(getattr(client, "is_remote", False))


def build_client(
    config: UserConfig,
    *,
    base_url: str | None = None,
    default_host: str = "http://localhost:11434",
) -> JudgeClient:
    """The judge client for this run: local Ollama unless told otherwise.

    `base_url` is the per-run override (`--judge-url`), which beats the config so a
    one-off against some endpoint does not require editing a file — and, more to the
    point, does not persist afterwards.
    """
    endpoint: JudgeEndpoint | None = None
    if base_url:
        endpoint = JudgeEndpoint(base_url=base_url.strip())
        if config.judge_endpoint is not None:
            # Same endpoint named twice: keep the key and size the config carries.
            saved = config.judge_endpoint
            if saved.base_url.rstrip("/") == endpoint.base_url.rstrip("/"):
                endpoint = saved
    elif config.judge_endpoint is not None:
        endpoint = config.judge_endpoint

    if endpoint is None:
        return OllamaClient(host=config.ollama_host or default_host)

    return OpenAICompatibleClient(
        endpoint.base_url,
        api_key=api_key_from_env(endpoint.api_key_env),
        params_b=endpoint.params_b,
    )


def remote_notice(client: JudgeClient) -> str | None:
    """The line every remote run has to carry, or None when the judge is local.

    Stated on each run rather than once at setup. A base URL written months ago is
    still in the config today, and a guarantee that stopped holding silently is worse
    than one that was never made (Principle IV).
    """
    if not is_remote(client):
        return None
    return (
        f"Your project's text is being sent to a remote judge at {client.host}. "
        f"This is not the default: SpecJudge runs its judge locally unless a "
        f"non-local judge.base_url is configured. Clear it to go back to local Ollama."
    )


__all__ = [
    "JudgeClient",
    "build_client",
    "is_local_url",
    "is_remote",
    "remote_notice",
]
