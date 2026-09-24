"""The privacy boundary, end to end (issue #4 / Principle I).

SpecJudge promises that a user's specs do not reach a third party during normal use.
Issue #4 makes a remote judge possible, which means that promise now depends on a
branch rather than on there being no other code path — so the branch is pinned here:
the default still goes nowhere, a remote judge only happens when asked for, and when
it does the run says so where the user will actually see it.
"""

from __future__ import annotations

import json
import re

import httpx
import respx
from typer.testing import CliRunner

from specjudge.cli import app

runner = CliRunner()
REMOTE = "https://judge.example.com"
_FRAGMENT_ID = re.compile(r"^\s*([A-Z]+:[A-Za-z0-9_.\-]+)", re.MULTILINE)


def _openai_reply(request: httpx.Request) -> httpx.Response:
    """A judge that cites what it was shown, over the OpenAI response shape."""
    prompt = json.loads(request.content)["messages"][0]["content"]
    dimensions = {"reasoning": "medium", "size": "medium", "domain_specialization": "low"}
    payload: dict[str, object] = {"dimensions": dimensions, "justification": "ok"}
    parts = prompt.split("=== CITABLE FRAGMENTS ===", 1)
    if len(parts) > 1:
        match = _FRAGMENT_ID.search(parts[1])
        if match:
            payload["evidence"] = dict.fromkeys(dimensions, match.group(1))
    return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})


def test_a_remote_judge_is_used_only_when_asked_for(project_sufficient, test_catalog):
    with respx.mock(assert_all_called=False) as router:
        models = router.get(f"{REMOTE}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "judge-x"}]})
        )
        chat = router.post(f"{REMOTE}/v1/chat/completions").mock(side_effect=_openai_reply)

        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge-url",
                REMOTE,
                "--judge",
                "judge-x",
                "--catalog",
                str(test_catalog),
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    assert models.called and chat.called
    # Every request went to the endpoint the user named, and nowhere else.
    for call in router.calls:
        assert call.request.url.host == "judge.example.com"


def test_a_remote_run_says_where_the_text_went(project_sufficient, test_catalog):
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{REMOTE}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "judge-x"}]})
        )
        router.post(f"{REMOTE}/v1/chat/completions").mock(side_effect=_openai_reply)

        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge-url",
                REMOTE,
                "--judge",
                "judge-x",
                "--catalog",
                str(test_catalog),
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    warnings = json.loads(result.stdout)["warnings"]
    assert warnings, "a remote run must carry a notice"
    assert REMOTE in warnings[0]
    assert "remote judge" in warnings[0]


def test_the_notice_is_first_so_it_cannot_be_buried(project_scarce, test_catalog):
    """A thin project produces several warnings; this one still leads."""
    with respx.mock(assert_all_called=False) as router:
        router.get(f"{REMOTE}/v1/models").mock(
            return_value=httpx.Response(200, json={"data": [{"id": "judge-x"}]})
        )
        router.post(f"{REMOTE}/v1/chat/completions").mock(side_effect=_openai_reply)

        result = runner.invoke(
            app,
            [
                str(project_scarce),
                "--judge-url",
                REMOTE,
                "--judge",
                "judge-x",
                "--catalog",
                str(test_catalog),
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    warnings = json.loads(result.stdout)["warnings"]
    assert len(warnings) > 1
    assert REMOTE in warnings[0]


def test_a_default_run_carries_no_such_notice(project_sufficient, test_catalog, mock_ollama):
    with mock_ollama(models=["llama3.1:8b"]):
        result = runner.invoke(
            app,
            [
                str(project_sufficient),
                "--judge",
                "llama3.1:8b",
                "--catalog",
                str(test_catalog),
                "--json",
            ],
        )

    assert result.exit_code == 0, result.output
    warnings = json.loads(result.stdout)["warnings"]
    assert not any("remote judge" in w for w in warnings)
