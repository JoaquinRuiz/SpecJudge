"""Shared fixtures for the SpecJudge suite.

Ollama is mocked at the HTTP level with respx so tests are deterministic and do not
depend on a locally installed model.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import httpx
import pytest
import respx

FIXTURES = Path(__file__).parent / "fixtures"
HOST = "http://localhost:11434"


@pytest.fixture(autouse=True)
def isolate_config(tmp_path, monkeypatch):
    """Isolate the user config to a temp directory across the whole suite."""
    cfg = tmp_path / "config.toml"
    monkeypatch.setattr("specjudge.config.config_path", lambda: cfg)
    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    return cfg


@pytest.fixture
def test_catalog() -> Path:
    """Synthetic catalog pinned by tests, so they don't depend on data/models.yaml."""
    return FIXTURES / "catalog-test.yaml"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def project_sufficient() -> Path:
    return FIXTURES / "project-sufficient"


@pytest.fixture
def project_scarce() -> Path:
    return FIXTURES / "project-scarce"


@pytest.fixture
def project_insufficient() -> Path:
    return FIXTURES / "project-insufficient"


_FRAGMENT_ID = re.compile(r"^ {2}(\S+) {2}\S", re.MULTILINE)


def _first_fragment_id(prompt: str) -> str | None:
    """The first id the prompt offered as citable, if any.

    The mock judge cites what it was actually shown, so the suite exercises the real
    validation path (issue #1) without any test needing to know which fragment ids a
    given fixture project happens to produce.
    """
    parts = prompt.split("=== CITABLE FRAGMENTS ===", 1)
    if len(parts) < 2:
        return None
    match = _FRAGMENT_ID.search(parts[1])
    return match.group(1) if match else None


def _demand_response(prompt: str, dimensions: dict[str, str], justification: str) -> httpx.Response:
    payload: dict[str, object] = {"dimensions": dimensions, "justification": justification}
    fragment_id = _first_fragment_id(prompt)
    if fragment_id is not None:
        payload["evidence"] = dict.fromkeys(dimensions, fragment_id)
    content = json.dumps(payload)
    return httpx.Response(200, json={"message": {"role": "assistant", "content": content}})


@pytest.fixture
def mock_ollama():
    """Return a configurable mocked Ollama.

    Usage:
        with mock_ollama(models=["m1"], demand={...}) as router:
            ...
    """

    class _Ctx:
        def __init__(self, models, demand, justification, down, chat_status):
            self.models = models
            self.demand = demand
            self.justification = justification
            self.down = down
            self.chat_status = chat_status
            self._router = respx.mock(base_url=HOST, assert_all_called=False)

        def __enter__(self):
            router = self._router
            router.start()
            if self.down:
                router.get("/api/tags").mock(side_effect=httpx.ConnectError("refused"))
                router.post("/api/chat").mock(side_effect=httpx.ConnectError("refused"))
                return router
            tags = {"models": [{"name": m} for m in self.models]}
            router.get("/api/tags").mock(return_value=httpx.Response(200, json=tags))
            if self.chat_status != 200:
                router.post("/api/chat").mock(
                    return_value=httpx.Response(self.chat_status, json={})
                )
            else:
                router.post("/api/chat").mock(
                    side_effect=lambda request: _demand_response(
                        json.loads(request.content)["messages"][0]["content"],
                        self.demand,
                        self.justification,
                    )
                )
            return router

        def __exit__(self, *exc):
            self._router.stop()
            return False

    def factory(
        *,
        models: list[str] | None = None,
        demand: dict[str, str] | None = None,
        justification: str = "Medium-demand project.",
        down: bool = False,
        chat_status: int = 200,
    ):
        return _Ctx(
            models=models if models is not None else ["llama3.1:8b"],
            demand=demand
            or {"reasoning": "medium", "size": "medium", "domain_specialization": "medium"},
            justification=justification,
            down=down,
            chat_status=chat_status,
        )

    return factory
