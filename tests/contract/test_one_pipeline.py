"""The CLI and the library are one pipeline, and this proves it on every output (#38).

`test_analyze_matches_what_the_cli_would_print` already compared the two paths field
for field, and still missed two real divergences: the budget warning wired into the API
only (0.6.1), and `instructions_considered` never passed by the CLI (0.6.0 to 0.7.0).
Both comparisons were strict. Both were of empty lists. A fixture with no instruction
files and no budget pressure has nothing in those fields on either side, and `[] == []`.

So this test does two things, and the first is the one that matters: it asserts the
project actually exercises every optional output *before* comparing them. If a future
change makes the fixture stop producing one of them, the test fails on that — loudly —
instead of quietly going back to comparing nothing.
"""

from __future__ import annotations

import json
import shutil

from typer.testing import CliRunner

from specjudge import api
from specjudge.cli import app
from specjudge.domain import ExecutionModel


# Bullets, not prose: the compact digest is built from units — headings, bullets, checklist
# items — so a file of plain paragraphs digests to a couple of lines and never comes near
# the budget floor, however long it is.
def _rules(i: int) -> str:
    return "".join(
        f"- Rule {i}.{k}: every change ships with an integration test and a migration note.\n"
        for k in range(40)
    )


def _project_with_every_output(src, dst):
    """A project that makes every optional output non-empty.

    Instruction files that apply and one that does not fill `instructions_considered`
    both ways; enough long ones to exceed the compact budget make the floor leave some
    out (the budget warning); a glob that matches nothing produces the skip warning.
    """
    shutil.copytree(src, dst)
    instructions = dst / ".github" / "instructions"
    instructions.mkdir(parents=True)
    for i in range(10):
        (instructions / f"rule{i:02d}.instructions.md").write_text(
            f'---\napplyTo: "**"\n---\n# Rule {i}\n\n' + _rules(i), encoding="utf-8"
        )
    (instructions / "react.instructions.md").write_text(
        '---\napplyTo: "**/*.tsx"\n---\nFunction components only.\n', encoding="utf-8"
    )
    return dst


def test_cli_and_library_agree_on_every_output(
    project_sufficient, test_catalog, mock_ollama, tmp_path
):
    project = _project_with_every_output(project_sufficient, tmp_path / "project")

    with mock_ollama(models=["llama3.1:8b"]):
        library = api.to_dict(
            api.analyze(
                project,
                judge_model="llama3.1:8b",
                catalog_path=test_catalog,
                execution_model=ExecutionModel.ESCALATING,
            )
        )
    with mock_ollama(models=["llama3.1:8b"]):
        result = CliRunner().invoke(
            app,
            [
                str(project),
                "--judge",
                "llama3.1:8b",
                "--catalog",
                str(test_catalog),
                "--execution-model",
                "escalating",
                "--json",
            ],
        )
    assert result.exit_code == 0, result.output
    cli = json.loads(result.stdout)

    # First: the fixture really does exercise what it claims. Each of these is a field
    # one of the paths has previously left empty without anything noticing.
    considered = library["instructions_considered"]
    assert any(i["included"] for i in considered), "no instruction file was included"
    assert any(not i["included"] for i in considered), "no instruction file was excluded"
    assert any("left" in w.lower() and "out of the prompt" in w for w in library["warnings"]), (
        "the budget floor dropped nothing, so its warning is untested"
    )
    assert any("path-specific instruction" in w for w in library["warnings"]), (
        "no instruction file was skipped, so that warning is untested"
    )
    assert library["envelope"]["execution_model"] == "escalating"

    # Then: the two paths give the same answer, every field, warnings in the same order.
    assert cli == library


def test_the_warnings_are_assembled_in_one_place():
    """Both entry points delegate the assessment, so neither assembles warnings itself.

    A structural check rather than a behavioural one: the behavioural test above can
    only cover the outputs its fixture exercises, and the next warning someone adds
    will not be in it. If either entry point starts building its own list again, this
    is what fails.
    """
    import inspect

    from specjudge import cli

    for source in (inspect.getsource(api.analyze), inspect.getsource(cli._run)):
        assert "evidence_warnings(" not in source
        assert "budget_warnings(" not in source
        assert "build_comparison(" not in source
        assert "assess(" in source
