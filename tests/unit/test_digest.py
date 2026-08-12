"""The compact digest describes the file, not its opening (issue #29 / FR-025).

The bug this replaces was invisible from inside: the digest was built from text that
had already been truncated, so it faithfully summarised the first 1,500 characters of
each document and said nothing false about them. On a real feature that meant zero
requirements and zero tasks reached the judge, which rated the project from the title
of its task list.

Everything here is about the two properties that failure violated — summarise the whole
source, and sample across it rather than from its head — plus the property the fix has
to keep: whatever the digest names must be citable, or the judge is picking labels out
of an inventory.
"""

from __future__ import annotations

import pytest

from specjudge.domain import DataState, ProjectAnalysis, SDDArtifact
from specjudge.judge.digest import SNIPPET_CHARS, render_source, shape_only

FILLER = "\n".join(f"Context paragraph {i}, of no consequence whatever." for i in range(40))


def _artifact(type_: str, content: str) -> SDDArtifact:
    return SDDArtifact(type_, f"{type_}.md", True, True, content)


def _block(content: str, budget: int = 1500, type_: str = "spec") -> str:
    return render_source(_artifact(type_, content), type_, budget)


# --------------------------------------------------- summarised from the whole source


def test_requirements_past_the_old_cut_are_reported():
    """The regression itself: `FR-001` at character 4,000 of a 4,700-character spec."""
    content = f"# Spec\n\n## Context\n\n{FILLER}\n\n- **FR-001**: It MUST hold.\n"
    assert len(content) > 1500
    assert content.index("FR-001") > 1500

    block = _block(content)
    assert "requirements: 1" in block
    assert "FR-001: It MUST hold." in block


def test_tasks_past_the_old_cut_are_reported():
    content = f"# Tasks\n\n## Format\n\n{FILLER}\n\n- [ ] T099 Rewrite the netting engine\n"
    block = _block(content, type_="tasks")
    assert "checklist items: 1" in block
    assert "T099 Rewrite the netting engine" in block


def test_the_count_is_of_the_file_and_not_of_the_sample():
    """ "29" is the most informative number about a task list, and it costs nothing."""
    content = "# Tasks\n" + "\n".join(f"- [ ] T{i:03d} Do the thing number {i}" for i in range(29))
    block = _block(content, budget=400, type_="tasks")
    assert "checklist items: 29" in block
    assert "shown" in block, "a truncated sample must say it is one"


# --------------------------------------------------- sampled across, not from the head


def test_the_sample_reaches_the_end_of_the_file():
    """A tasks.md opens with setup and closes with the hard part.

    A head sample describes the easy end and then decides the difficulty from it —
    which is the same failure as truncation, one order of magnitude smaller.
    """
    content = (
        "# Tasks\n"
        + "\n".join(f"- [ ] T{i:03d} Rename a label" for i in range(1, 26))
        + "\n- [ ] T026 Rewrite the access-control resolution\n"
    )

    block = _block(content, budget=600, type_="tasks")
    assert "T026 Rewrite the access-control resolution" in block


def test_the_sample_covers_the_middle_too():
    content = "# Tasks\n" + "\n".join(f"- [ ] T{i:03d} Task {i}" for i in range(1, 31))
    block = _block(content, budget=700, type_="tasks")
    import re as _re

    shown = [int(m.group(1)) for m in _re.finditer(r"\* T(\d{3}) Task", block)]
    assert min(shown) <= 5 and max(shown) >= 26, shown
    assert any(10 <= n <= 20 for n in shown), f"nothing from the middle: {shown}"


def test_the_sample_is_deterministic():
    content = "# Tasks\n" + "\n".join(f"- [ ] T{i:03d} Task {i}" for i in range(1, 31))
    assert _block(content, budget=700, type_="tasks") == _block(content, budget=700, type_="tasks")


# --------------------------------------------------- what goes when it does not fit


def test_requirements_survive_and_headings_go_first():
    """A heading names a topic; a requirement is what makes a project hard."""
    content = "# One\n## Two\n### Three\n#### Four\n" * 5 + "\n".join(
        f"- **FR-{i:03d}**: It MUST hold, in a way that takes room." for i in range(6)
    )
    block = _block(content, budget=420)
    assert "FR-000" in block
    assert block.count("* FR-") >= 2
    assert "sections:" in block, "the count is still reported even when nothing is shown"


def test_the_block_stays_within_its_budget():
    content = "# Spec\n" + "\n".join(
        f"- **FR-{i:03d}**: A requirement of some length." for i in range(60)
    )
    for budget in (200, 500, 1500):
        assert len(_block(content, budget=budget)) <= budget, budget


def test_nothing_dropped_is_dropped_silently():
    """FR-025: a cap the reader cannot see reads as "this was everything"."""
    content = "# Tasks\n" + "\n".join(f"- [ ] T{i:03d} Task {i}" for i in range(40))
    block = _block(content, budget=400, type_="tasks")
    assert "checklist items: 40" in block
    assert "shown" in block


# --------------------------------------------------- the body and the catalogue


def test_the_body_carries_the_shape_and_not_the_contents():
    """The units are sent in the citable list, where they carry their ids.

    Printing them in both places doubles a prompt whose entire purpose is being small.
    """
    content = "# Spec\n- **FR-001**: It MUST hold.\n"
    body = shape_only(_block(content))
    assert "requirements: 1" in body
    assert "FR-001" not in body


def test_snippets_are_capped():
    content = "# Spec\n- **FR-001**: " + "x" * 500 + "\n"
    line = next(line for line in _block(content).splitlines() if "FR-001" in line)
    assert len(line.strip("* ")) <= SNIPPET_CHARS


def test_the_snippet_is_exactly_the_fragment_text():
    """One cap, not two.

    In this shape the snippet the judge reads *is* the fragment its citation is
    validated against. A shorter snippet would show it half a requirement and check
    it against the other half; a longer one would let it quote text it never saw.
    """
    from specjudge.judge.fragments import MAX_FRAGMENT_CHARS

    assert SNIPPET_CHARS == MAX_FRAGMENT_CHARS


def test_a_wrapped_requirement_arrives_whole():
    """The failure #19 fixed, one module over: the demanding half is the second one."""
    content = (
        "# Spec\n\n- **FR-002**: Report generation MUST run entirely on the device, since no\n"
        "  personal data may leave it.\n"
    )
    assert "personal data may leave it." in _block(content)


def test_plain_bullets_are_units_of_their_own():
    """An AGENTS.md states its constraints as bullets and numbers nothing.

    Without this, an environment-only project reaches the judge as a list of section
    titles — which is how every such case in the corpus collapsed into abstention.
    """
    content = "# AGENTS.md\n\n## Rules\n- Money is integer minor units, never a float.\n"
    block = _block(content, type_="agents")
    assert "stated rules: 1" in block
    assert "Money is integer minor units" in block


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("- **FR-001**: It MUST hold.", "FR-001: It MUST hold."),
        ("* __SC-002__: Under a second.", "SC-002: Under a second."),
    ],
)
def test_emphasis_is_dropped_rather_than_half_stripped(raw, expected):
    """`FR-001**:` reads as damage; the digest is prose, not a copy of the source."""
    assert expected in _block(f"# Spec\n{raw}\n")


# --------------------------------------------------- the invariant the fix must keep


def test_everything_the_digest_names_is_citable():
    """A digest naming a fragment the validator would reject is worse than the bug.

    The judge would be shown `FR-015`, cite it, and have its whole profile rejected as
    a fabrication.
    """
    from specjudge.judge.fragments import extract_fragments

    content = f"# Spec\n\n{FILLER}\n\n- **FR-001**: It MUST hold.\n- **FR-002**: So MUST this.\n"
    analysis = ProjectAnalysis(
        artifacts=[_artifact("spec", content)], data_state=DataState.SUFFICIENT
    )
    block = _block(content)
    citable = {f.id.split(":", 1)[1] for f in extract_fragments(analysis, 1500, compact=True)}

    named = [line for line in block.splitlines() if line.strip().startswith("* ")]
    assert named
    for line in named:
        label = line.strip("* ").split(":")[0]
        if label.startswith(("FR-", "SC-")):
            assert label in citable, f"{label} is named in the digest but not citable"
