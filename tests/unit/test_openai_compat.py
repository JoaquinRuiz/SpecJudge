"""An OpenAI-compatible judge, and the promise that goes with it (issue #4 / FR-011).

Most of what is pinned here is about the boundary rather than the protocol: which
URLs count as this machine, that nothing reaches a third party unless the user asked
for it, and that when something does, the run says so.
"""

from __future__ import annotations

import httpx
import pytest
import respx

from specjudge import errors
from specjudge.domain import JudgeEndpoint, UserConfig
from specjudge.judge.client import build_client, is_remote, remote_notice
from specjudge.judge.ollama import OllamaClient
from specjudge.judge.openai_compat import (
    ASSUMED_PARAMS_B,
    OpenAICompatibleClient,
    api_key_from_env,
    is_local_url,
)

ENDPOINT = "https://api.example.com"


# ------------------------------------------------------------------ local vs remote


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:11434",
        "http://127.0.0.1:8080/v1",
        "http://[::1]:1234",
        "http://0.0.0.0:5000",
    ],
)
def test_these_are_this_machine(url):
    assert is_local_url(url)


@pytest.mark.parametrize(
    "url",
    ["https://api.openai.com", "http://192.168.1.50:8000", "https://llm.corp.internal"],
)
def test_these_are_not(url):
    assert not is_local_url(url)


def test_an_unparseable_url_counts_as_remote():
    """A URL we failed to read is not evidence that it is safe."""
    assert not is_local_url("not a url at all")


# ------------------------------------------------------------------ the default holds


def test_no_config_and_no_flag_means_local_ollama():
    client = build_client(UserConfig())
    assert isinstance(client, OllamaClient)
    assert not is_remote(client)
    assert remote_notice(client) is None


def test_a_remote_endpoint_is_only_ever_reached_when_configured():
    config = UserConfig(judge_endpoint=JudgeEndpoint(base_url=ENDPOINT))
    client = build_client(config)
    assert isinstance(client, OpenAICompatibleClient)
    assert is_remote(client)


def test_a_local_openai_endpoint_is_not_remote():
    """llama.cpp or vLLM on your own machine keeps Principle I untouched."""
    config = UserConfig(judge_endpoint=JudgeEndpoint(base_url="http://localhost:8000"))
    client = build_client(config)
    assert not is_remote(client)
    assert remote_notice(client) is None


def test_the_flag_overrides_the_config_without_persisting():
    config = UserConfig(judge_endpoint=JudgeEndpoint(base_url=ENDPOINT))
    client = build_client(config, base_url="http://localhost:8000")
    assert client.host == "http://localhost:8000"
    assert config.judge_endpoint.base_url == ENDPOINT


def test_naming_the_configured_endpoint_keeps_its_key_and_size():
    config = UserConfig(
        judge_endpoint=JudgeEndpoint(base_url=ENDPOINT, api_key_env="K", params_b=7.0)
    )
    client = build_client(config, base_url=ENDPOINT + "/")
    assert client.model_params_b("m") == 7.0


def test_a_remote_run_says_so():
    client = build_client(UserConfig(judge_endpoint=JudgeEndpoint(base_url=ENDPOINT)))
    notice = remote_notice(client)
    assert notice is not None
    assert ENDPOINT in notice


# ------------------------------------------------------------------ size and the prompt


def test_a_remote_judge_is_assumed_large():
    """Guessing 'small' would send a compact digest to a frontier model."""
    client = OpenAICompatibleClient(ENDPOINT)
    assert client.model_params_b("gpt-whatever") == ASSUMED_PARAMS_B


def test_a_local_endpoint_of_unknown_size_stays_unknown():
    client = OpenAICompatibleClient("http://localhost:8000")
    assert client.model_params_b("qwen") is None


def test_a_configured_size_wins():
    client = OpenAICompatibleClient(ENDPOINT, params_b=8.0)
    assert client.model_params_b("qwen") == 8.0


# ------------------------------------------------------------------ the key


def test_the_key_is_read_from_the_environment_never_the_config(monkeypatch):
    monkeypatch.setenv("MY_JUDGE_KEY", "sk-secret")
    assert api_key_from_env("MY_JUDGE_KEY") == "sk-secret"


def test_no_variable_named_means_no_key():
    assert api_key_from_env(None) is None


def test_an_unset_variable_is_not_an_empty_key(monkeypatch):
    monkeypatch.delenv("ABSENT_KEY", raising=False)
    assert api_key_from_env("ABSENT_KEY") is None


# ------------------------------------------------------------------ the protocol


def test_models_are_listed_from_the_v1_endpoint():
    with respx.mock() as router:
        router.get(f"{ENDPOINT}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "gpt-x"}, {"id": "gpt-y"}]})
        )
        assert OpenAICompatibleClient(ENDPOINT).list_models() == ["gpt-x", "gpt-y"]


def test_the_key_travels_as_a_bearer_header():
    with respx.mock() as router:
        route = router.get(f"{ENDPOINT}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        OpenAICompatibleClient(ENDPOINT, api_key="sk-secret").list_models()
        assert route.calls[0].request.headers["authorization"] == "Bearer sk-secret"


def test_no_key_means_no_authorization_header():
    with respx.mock() as router:
        route = router.get(f"{ENDPOINT}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        OpenAICompatibleClient(ENDPOINT).list_models()
        assert "authorization" not in route.calls[0].request.headers


def test_a_schema_is_sent_as_json_schema():
    with respx.mock() as router:
        route = router.post(f"{ENDPOINT}/v1/chat/completions").mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": '{"ok": true}'}}]}
            )
        )
        schema = {"type": "object"}
        result = OpenAICompatibleClient(ENDPOINT).chat_json("m", "prompt", schema=schema)
        sent = route.calls[0].request.content.decode()
        assert '"json_schema"' in sent
        assert result == {"ok": True}


def test_rejected_credentials_say_so():
    with respx.mock() as router:
        router.get(f"{ENDPOINT}/v1/models").mock(return_value=httpx.Response(401))
        with pytest.raises(errors.JudgeUnavailableError) as exc:
            OpenAICompatibleClient(ENDPOINT).list_models()
        assert "rejected the credentials" in str(exc.value)


def test_an_unreachable_endpoint_says_so():
    with respx.mock() as router:
        router.get(f"{ENDPOINT}/v1/models").mock(side_effect=httpx.ConnectError("nope"))
        with pytest.raises(errors.JudgeUnavailableError) as exc:
            OpenAICompatibleClient(ENDPOINT).list_models()
        assert "Could not connect" in str(exc.value)


def test_an_empty_model_list_is_not_treated_as_broken():
    """Some gateways serve a model perfectly well and list nothing."""
    with respx.mock() as router:
        router.get(f"{ENDPOINT}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        assert OpenAICompatibleClient(ENDPOINT).ensure_available("gpt-x") == []


def test_a_model_the_endpoint_does_list_but_lacks_is_an_error():
    with respx.mock() as router:
        router.get(f"{ENDPOINT}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "gpt-y"}]})
        )
        with pytest.raises(errors.JudgeUnavailableError):
            OpenAICompatibleClient(ENDPOINT).ensure_available("gpt-x")
