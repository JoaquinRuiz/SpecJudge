"""Sampling is pinned on every judge call (issue #5).

Without this the same project can recommend different models on two consecutive
runs, and the judge evaluation cannot tell a prompt change from sampling noise.
"""

from __future__ import annotations

import json

import httpx
import respx

from specjudge.judge.ollama import JUDGE_OPTIONS, OllamaClient

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
