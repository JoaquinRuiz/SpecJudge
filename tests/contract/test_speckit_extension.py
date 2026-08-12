"""The spec-kit extension may not promise what the CLI does not do (issue #27).

The extension is a manifest and a prompt. Nothing imports it, nothing runs it here, and
that is exactly why it rots: a flag gets renamed, a payload field moves, and the only
symptom appears in somebody else's project, weeks later, as an agent running a command
that no longer exists.

So the parts that can be checked against the thing they describe are checked. What
cannot be checked here — that spec-kit actually loads it — is manual verification, and
it belongs in the issue rather than in a green tick.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from typer.main import get_command

from specjudge import __version__
from specjudge.cli import app
from specjudge.serialize import load_schema

REPO_ROOT = Path(__file__).resolve().parents[2]
EXTENSION = REPO_ROOT / "extensions" / "spec-kit"
MANIFEST = EXTENSION / "extension.yml"


@pytest.fixture(scope="module")
def manifest() -> dict:
    return yaml.safe_load(MANIFEST.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def command_text(manifest) -> str:
    (command,) = manifest["provides"]["commands"]
    return (EXTENSION / command["file"]).read_text(encoding="utf-8")


# ------------------------------------------------------------------ the manifest


def test_the_manifest_declares_what_spec_kit_requires(manifest):
    assert manifest["schema_version"] == "1.0"
    extension = manifest["extension"]
    for field in ("id", "name", "version", "description", "author", "license"):
        assert extension.get(field), f"extension.{field} is required"
    assert re.fullmatch(r"[a-z0-9-]+", extension["id"])
    assert re.fullmatch(r"\d+\.\d+\.\d+", extension["version"])


def test_the_description_fits_the_catalog_limit(manifest):
    """The catalog asks for under 100 characters, and it is what people read."""
    assert len(manifest["extension"]["description"]) < 100


def test_every_command_file_exists(manifest):
    for command in manifest["provides"]["commands"]:
        assert (EXTENSION / command["file"]).is_file(), command["file"]


def test_command_names_are_namespaced_under_the_extension(manifest):
    prefix = f"speckit.{manifest['extension']['id']}."
    for command in manifest["provides"]["commands"]:
        assert command["name"].startswith(prefix), command["name"]


def test_it_does_not_require_a_specjudge_that_does_not_exist(manifest):
    """A manifest cannot demand a version nobody can install.

    The extension ships from this repository, so the two are released together and
    the floor is checkable here rather than by a user's failed install.
    """
    (tool,) = [t for t in manifest["requires"]["tools"] if t["name"] == "specjudge"]
    required = tuple(int(part) for part in tool["version"].removeprefix(">=").split("."))
    current = tuple(int(part) for part in __version__.split(".")[:3])
    assert required <= current, f"requires specjudge {tool['version']}, repo is at {__version__}"


def test_the_spec_kit_floor_is_a_version_that_was_tested(manifest):
    """A floor, and no ceiling.

    This started closed at `<0.14.0`, on the reasoning that declaring untested
    compatibility is a claim you cannot back. That was the wrong trade, and the
    first person to hit it was the author: spec-kit 0.15.2 refused to install an
    extension whose manifest is compatible with it in every respect. A closed upper
    bound fails hard, for everybody, on a schedule set by somebody else's release
    calendar — over a guess about the future.

    So the manifest states a floor, and the README states which versions were
    actually tried, which is where a fact about the past belongs.
    """
    speckit = manifest["requires"]["speckit_version"]
    assert re.fullmatch(r">=\d+\.\d+\.\d+", speckit), f"expected a bare floor, got {speckit!r}"

    readme = (EXTENSION / "README.md").read_text(encoding="utf-8")
    floor = speckit.removeprefix(">=")
    assert floor in readme, f"the README does not say {floor} was tested"


# ------------------------------------------------------------------ the hook


def test_the_hook_runs_where_the_decision_is_made(manifest):
    """`after_tasks` is the only event with everything written and nothing spent."""
    assert set(manifest["hooks"]) == {"after_tasks"}


def test_the_hook_asks_before_spending_the_users_minutes(manifest):
    """It starts a local model. Doing that unprompted is how this gets uninstalled."""
    hook = manifest["hooks"]["after_tasks"]
    assert hook["optional"] is True
    assert hook["prompt"]


def test_the_hook_runs_a_command_the_extension_provides(manifest):
    provided = {c["name"] for c in manifest["provides"]["commands"]}
    assert manifest["hooks"]["after_tasks"]["command"] in provided


def test_it_promises_to_write_nothing(manifest):
    """`read-only` is a claim the command has to keep, so both are pinned."""
    assert manifest["extension"]["effect"] == "read-only"


# ------------------------------------------------------------------ the command


def test_the_command_has_the_frontmatter_spec_kit_reads(command_text):
    assert command_text.startswith("---\n")
    front = yaml.safe_load(command_text.split("---", 2)[1])
    assert front["description"]


def test_the_command_takes_the_user_input_placeholder(command_text):
    assert "$ARGUMENTS" in command_text


def test_every_flag_it_tells_the_agent_to_use_exists(command_text):
    """The rot this file exists to catch: a renamed flag, discovered by a stranger."""
    declared = {opt for param in get_command(app).params for opt in param.opts}
    used = set(re.findall(r"(?<![\w-])--[a-z][a-z-]+", command_text))
    unknown = used - declared
    assert not unknown, f"the command uses flags the CLI does not declare: {sorted(unknown)}"


@pytest.mark.parametrize(
    "field", ["best_choice", "podium", "evaluations", "warnings", "data_state", "envelope"]
)
def test_every_payload_field_it_reads_is_in_the_schema(command_text, field):
    assert field in command_text, f"the command no longer reads {field}"
    assert field in load_schema()["properties"], f"{field} is not in the published schema"


def test_it_reads_the_envelope_fields_that_exist(command_text):
    envelope = load_schema()["$defs"]["envelope"]["properties"]
    assert "envelope.constraints" in command_text
    assert "constraints" in envelope
    constraint = load_schema()["$defs"]["constraint"]["properties"]
    for field in ("fragment_id", "hard"):
        assert field in command_text and field in constraint


@pytest.mark.parametrize("code", ["0", "2", "3", "4"])
def test_it_handles_every_exit_code_the_cli_can_return(command_text, code):
    """Exit 2 means "nothing to say here", not "the hook failed" (FR-029)."""
    table = command_text[command_text.index("| Exit |") :]
    assert re.search(rf"^\s*\| {code} \|", table, re.MULTILINE), f"exit {code} is not handled"


def test_it_promises_not_to_block_the_flow(command_text):
    """A recommendation nobody asked for must never stop an implementation."""
    assert "continue" in command_text.lower()
    assert "block" in command_text.lower()


def test_it_treats_the_payload_as_data_rather_than_instructions(command_text):
    """Free-text fields carry the user's project text, which they may not have written."""
    assert "data, not instructions" in command_text
