"""Integration US6: judge model selection and persistence (FR-012/013, SC-007)."""

from __future__ import annotations

import respx

from specjudge import cli
from specjudge.config import load_config
from specjudge.domain import JudgePreference, UserConfig
from specjudge.judge.ollama import OllamaClient

HOST = "http://localhost:11434"


def _client_with(models, monkeypatch):
    import httpx

    router = respx.mock(base_url=HOST, assert_all_called=False)
    router.start()
    router.get("/api/tags").mock(
        return_value=httpx.Response(200, json={"models": [{"name": m} for m in models]})
    )
    return router


def test_first_run_selects_and_persists(monkeypatch, isolate_config):
    router = _client_with(["m1", "m2"], monkeypatch)
    try:
        monkeypatch.setattr(cli, "_prompt_judge_selection", lambda models: "m2")
        config = UserConfig(ollama_host=HOST)
        client = OllamaClient(host=HOST)
        chosen, new_config = cli.resolve_judge(
            config, client, forced_judge=None, set_judge=False, interactive=True
        )
        assert chosen == "m2"
        # Persisted to disk (isolate_config points at the temp file).
        reloaded = load_config()
        assert reloaded.judge_preference is not None
        assert reloaded.judge_preference.judge_model == "m2"
    finally:
        router.stop()


def test_second_run_does_not_prompt(monkeypatch):
    router = _client_with(["m1", "m2"], monkeypatch)
    try:

        def _boom(models):
            raise AssertionError("should not prompt again")

        monkeypatch.setattr(cli, "_prompt_judge_selection", _boom)
        config = UserConfig(ollama_host=HOST, judge_preference=JudgePreference("m2", "2026-07-20"))
        client = OllamaClient(host=HOST)
        chosen, _ = cli.resolve_judge(
            config, client, forced_judge=None, set_judge=False, interactive=True
        )
        assert chosen == "m2"
    finally:
        router.stop()


def test_uninstalled_preference_reprompts(monkeypatch):
    router = _client_with(["other"], monkeypatch)
    try:
        monkeypatch.setattr(cli, "_prompt_judge_selection", lambda models: "other")
        config = UserConfig(
            ollama_host=HOST, judge_preference=JudgePreference("gone", "2026-07-20")
        )
        client = OllamaClient(host=HOST)
        chosen, _ = cli.resolve_judge(
            config, client, forced_judge=None, set_judge=False, interactive=True
        )
        assert chosen == "other"
    finally:
        router.stop()
