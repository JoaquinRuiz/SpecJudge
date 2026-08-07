"""Finding context files across the tree (issue #16 / FR-024, FR-025).

Discovery is the one part of the pipeline that touches arbitrary user directories,
so most of what is pinned here is what it must *not* do: descend into dependency
trees, walk forever, or read more than it said it would.
"""

from __future__ import annotations

from pathlib import Path

from specjudge.discovery import MAX_CONTEXT_FILES, context_files


def _write(root: Path, relative: str, content: str = "- a rule\n") -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def _read(root: Path, **kwargs) -> list[str]:
    found, _ = context_files(root, **kwargs)
    return [str(p.relative_to(root)) for _, p in found]


def _kinds(root: Path) -> list[str]:
    found, _ = context_files(root)
    return [kind for kind, _ in found]


# ------------------------------------------------------------------ formats


def test_the_root_formats_are_found(tmp_path):
    _write(tmp_path, "AGENTS.md")
    _write(tmp_path, "CLAUDE.md")
    _write(tmp_path, ".cursorrules")
    _write(tmp_path, ".github/copilot-instructions.md")
    assert _kinds(tmp_path) == ["agents", "claude", "cursor", "copilot"]


def test_nested_agent_files_are_found(tmp_path):
    """A monorepo writes its per-area constraints next to the area."""
    _write(tmp_path, "AGENTS.md")
    _write(tmp_path, "packages/api/AGENTS.md")
    _write(tmp_path, "packages/web/CLAUDE.md")
    assert _read(tmp_path) == [
        "AGENTS.md",
        str(Path("packages/api/AGENTS.md")),
        str(Path("packages/web/CLAUDE.md")),
    ]


def test_the_root_file_comes_first(tmp_path):
    """Shallowest first: root context governs the repository, nested context a corner."""
    _write(tmp_path, "a/b/AGENTS.md")
    _write(tmp_path, "AGENTS.md")
    assert _read(tmp_path)[0] == "AGENTS.md"


def test_discovery_order_is_stable(tmp_path):
    for name in ("z", "a", "m"):
        _write(tmp_path, f"packages/{name}/AGENTS.md")
    assert _read(tmp_path) == _read(tmp_path)
    assert _read(tmp_path) == [str(Path(f"packages/{name}/AGENTS.md")) for name in ("a", "m", "z")]


# ------------------------------------------------------------------ limits


def test_dependency_directories_are_never_walked(tmp_path):
    """`node_modules` holds megabytes of other people's AGENTS.md."""
    _write(tmp_path, "node_modules/dep/AGENTS.md")
    _write(tmp_path, ".venv/lib/AGENTS.md")
    _write(tmp_path, "dist/AGENTS.md")
    assert _read(tmp_path) == []


def test_the_walk_stops_at_the_depth_limit(tmp_path):
    _write(tmp_path, "a/b/c/AGENTS.md")
    _write(tmp_path, "a/b/c/d/e/AGENTS.md")
    assert _read(tmp_path) == [str(Path("a/b/c/AGENTS.md"))]


def test_the_file_cap_is_enforced_and_the_rest_reported(tmp_path):
    for i in range(20):
        _write(tmp_path, f"packages/pkg{i:02d}/AGENTS.md")
    found, dropped = context_files(tmp_path)
    assert len(found) == MAX_CONTEXT_FILES
    assert len(dropped) == 20 - MAX_CONTEXT_FILES


def test_the_cap_is_configurable(tmp_path):
    for i in range(6):
        _write(tmp_path, f"packages/pkg{i}/AGENTS.md")
    assert len(_read(tmp_path, max_files=3)) == 3


def test_adrs_are_not_crowded_out_by_agent_files(tmp_path):
    """Reserved room, or a monorepo's 88 AGENTS.md would bury its decisions."""
    for i in range(20):
        _write(tmp_path, f"packages/pkg{i:02d}/AGENTS.md")
    for i in range(3):
        _write(tmp_path, f"docs/adr/000{i + 1}-decision.md", f"# {i}\n\n- Decided.\n")
    assert _kinds(tmp_path).count("adr") == 3


# ------------------------------------------------------------------ ADRs


def test_numbered_decision_records_are_read(tmp_path):
    _write(tmp_path, "docs/adr/0001-use-postgres.md", "# 1\n\n- Postgres it is.\n")
    _write(tmp_path, "docs/decisions/ADR-002-caching.md", "# 2\n\n- Cache it.\n")
    assert len([k for k in _kinds(tmp_path) if k == "adr"]) == 2


def test_indexes_and_templates_are_not_decisions(tmp_path):
    _write(tmp_path, "docs/adr/README.md", "index\n")
    _write(tmp_path, "docs/adr/template.md", "template\n")
    _write(tmp_path, "docs/adr/notes.md", "loose notes\n")
    assert _read(tmp_path) == []


def test_a_docs_directory_is_not_swallowed_whole(tmp_path):
    """Only ADRs, by convention. A user guide is length without signal."""
    _write(tmp_path, "docs/getting-started.md", "# Guide\n\n- Install it.\n")
    _write(tmp_path, "docs/api/reference.md", "# Reference\n")
    assert _read(tmp_path) == []
