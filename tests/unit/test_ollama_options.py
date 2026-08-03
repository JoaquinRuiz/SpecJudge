"""Sampling is pinned on every judge call (issue #5).

Without this the same project can recommend different models on two consecutive
runs, and the judge evaluation cannot tell a prompt change from sampling noise.
"""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from specjudge.errors import JudgeUnavailableError
from specjudge.judge.ollama import JUDGE_OPTIONS, OllamaClient, parse_version

HOST = "http://localhost:11434"


def _capture(prompt: str = "hi") -> dict:
    with respx.mock(base_url=HOST, assert_all_called=False) as router:
        route = router.post("/api/chat").mock(
            return_value=httpx.Response(200, json={"message": {"content": "{}"}})
        )
        OllamaClient(host=HOST).chat_json("some-model", prompt)
        return json.loads(route.calls[0].request.content)


def test_chat_pins_temperature_and_seed():
    options = _capture()["options"]
    assert options["temperature"] == 0
    assert isinstance(options["seed"], int)


def test_pinned_options_are_the_documented_ones():
    assert _capture()["options"] == JUDGE_OPTIONS


def test_pinning_does_not_disturb_the_rest_of_the_request():
    payload = _capture(prompt="assess this")
    assert payload["format"] == "json"
    assert payload["stream"] is False
    assert payload["messages"][0]["content"] == "assess this"


def test_the_module_constant_cannot_be_mutated_through_a_request():
    """The payload gets a copy, so a caller poking at it cannot leak across runs."""
    payload = _capture()
    payload["options"]["temperature"] = 0.9
    assert JUDGE_OPTIONS["temperature"] == 0


# ------------------------------------------ structured outputs (issue #14)


def test_chat_sends_the_schema_when_given_one():
    schema = {"type": "object", "properties": {"x": {"type": "string"}}}
    with respx.mock(base_url=HOST, assert_all_called=False) as router:
        route = router.post("/api/chat").mock(
            return_value=httpx.Response(200, json={"message": {"content": "{}"}})
        )
        OllamaClient(host=HOST).chat_json("m", "p", schema=schema)
    assert json.loads(route.calls[0].request.content)["format"] == schema


def test_chat_falls_back_to_plain_json_without_a_schema():
    with respx.mock(base_url=HOST, assert_all_called=False) as router:
        route = router.post("/api/chat").mock(
            return_value=httpx.Response(200, json={"message": {"content": "{}"}})
        )
        OllamaClient(host=HOST).chat_json("m", "p")
    assert json.loads(route.calls[0].request.content)["format"] == "json"


def test_a_rejected_schema_names_the_likely_cause():
    """A bare 400 would send the user hunting; the version requirement is the answer."""
    with respx.mock(base_url=HOST, assert_all_called=False) as router:
        router.get("/api/version").mock(return_value=httpx.Response(200, json={"version": "0.3.1"}))
        router.post("/api/chat").mock(return_value=httpx.Response(400, json={}))
        with pytest.raises(JudgeUnavailableError) as exc:
            OllamaClient(host=HOST).chat_json("m", "p", schema={"type": "object"})
    rendered = exc.value.render()
    assert "0.5.0" in rendered
    assert "0.3.1" in rendered
    assert "require_spans" in rendered


def test_a_failure_without_a_schema_keeps_the_old_message():
    with respx.mock(base_url=HOST, assert_all_called=False) as router:
        router.post("/api/chat").mock(return_value=httpx.Response(500, json={}))
        with pytest.raises(JudgeUnavailableError) as exc:
            OllamaClient(host=HOST).chat_json("m", "p")
    assert "ollama pull" in exc.value.render()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("0.5.0", (0, 5, 0)),
        ("v0.32.5", (0, 32, 5)),
        ("0.6.1-rc1", (0, 6, 1)),
        ("1.0", (1, 0)),
        ("not-a-version", None),
        ("", None),
    ],
)
def test_version_parsing(raw, expected):
    assert parse_version(raw) == expected


@pytest.mark.parametrize(
    ("reported", "supported"),
    [("0.32.5", True), ("0.5.0", True), ("0.4.9", False), ("0.3.1", False)],
)
def test_structured_output_support_follows_the_version(reported, supported):
    with respx.mock(base_url=HOST, assert_all_called=False) as router:
        router.get("/api/version").mock(
            return_value=httpx.Response(200, json={"version": reported})
        )
        assert OllamaClient(host=HOST).supports_structured_output() is supported


@pytest.mark.parametrize("body", [{"version": "custom-build"}, {}])
def test_an_unreadable_version_is_assumed_supported(body):
    """Refusing to run because a version string was odd would be worse than trying."""
    with respx.mock(base_url=HOST, assert_all_called=False) as router:
        router.get("/api/version").mock(return_value=httpx.Response(200, json=body))
        assert OllamaClient(host=HOST).supports_structured_output() is True
