"""Polish integration (T052): no network calls outside localhost (NFR-1).

respx in strict mode: any unregistered HTTP request (to a non-local host) would
fail. Only localhost routes are registered; if the flow tried to reach a third
party, this test would fail.
"""

from __future__ import annotations

import httpx
import respx
from typer.testing import CliRunner

from specjudge.cli import app

runner = CliRunner()
HOST = "http://localhost:11434"


def test_no_calls_outside_localhost(project_sufficient):
    with respx.mock(assert_all_called=False) as router:
        # Only local Ollama routes are allowed.
        router.get(f"{HOST}/api/tags").mock(
            return_value=httpx.Response(200, json={"models": [{"name": "llama3.1:8b"}]})
        )
        content = '{"dimensions": {"reasoning": "medium", "size": "medium", "domain_specialization": "medium"}, "justification": "ok"}'
        router.post(f"{HOST}/api/chat").mock(
            return_value=httpx.Response(200, json={"message": {"content": content}})
        )
        # Any non-localhost host raises a connection error (never hits the real network).
        router.route(host="127.0.0.1").pass_through()

        result = runner.invoke(app, [str(project_sufficient), "--judge", "llama3.1:8b", "--json"])
    assert result.exit_code == 0, result.output
    # Every request made went to localhost:11434.
    for call in router.calls:
        assert call.request.url.host in ("localhost", "127.0.0.1")
