"""Finding the context files a repository carries, wherever they are (FR-024).

The root of a repository is where a small project keeps its context and where a
large one keeps only some of it. A monorepo puts an `AGENTS.md` next to each
package — the Codex repository has 88 — and those nested files are frequently the
only place the per-area constraints are written down.

So the tree is walked. Three things keep that from being reckless:

* **Pruning.** Directories that never hold hand-written project context but do hold
  enormous amounts of text (`node_modules`, `.venv`, build output) are skipped
  outright, so the cost of the walk scales with the project rather than with its
  dependencies.
* **Depth.** Four levels is deep enough for `packages/<name>/src/`, shallow enough
  that a pathological tree cannot turn discovery into a crawl.
* **A file cap.** At most `MAX_CONTEXT_FILES` are read, with reserved room for both
  kinds so a repository with 88 `AGENTS.md` cannot crowd out its ADRs. Whatever is
  dropped is counted and reported — a cap the user cannot see is indistinguishable
  from having read everything.

Ordering is stable and shallowest-first: context near the root describes the whole
repository, context deep inside describes one corner of it.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# Kind -> filename, for the files that only ever live at the repository root.
_ROOT_FILES: tuple[tuple[str, str], ...] = (
    ("agents", "AGENTS.md"),
    ("claude", "CLAUDE.md"),
    ("cursor", ".cursorrules"),
    ("copilot", ".github/copilot-instructions.md"),
)

# Kind -> filename, for the files that also appear deeper in the tree.
_NESTED_FILES: tuple[tuple[str, str], ...] = (
    ("agents", "AGENTS.md"),
    ("claude", "CLAUDE.md"),
)

# Directories where hand-written context does not live and machine-generated text does.
_PRUNED = frozenset(
    {
        ".git",
        ".hg",
        ".svn",
        ".tox",
        ".venv",
        ".mypy_cache",
        ".ruff_cache",
        ".pytest_cache",
        ".next",
        ".idea",
        ".vscode",
        "__pycache__",
        "node_modules",
        "venv",
        "env",
        "dist",
        "build",
        "target",
        "vendor",
        "site-packages",
        "coverage",
        "htmlcov",
    }
)

# Where a project keeps its architecture decision records, by convention.
_ADR_DIRS = (
    "docs/adr",
    "docs/adrs",
    "docs/decisions",
    "docs/architecture/decisions",
    "adr",
    "decisions",
)
# `0007-use-postgres.md`, `ADR-012-caching.md`. A README or a template is not a decision.
_ADR_FILE = re.compile(r"^(?:adr[-_]?)?\d{1,4}[-_].+\.md$", re.IGNORECASE)
_ADR_SKIP = re.compile(r"^(readme|index|template)", re.IGNORECASE)

MAX_DEPTH = 4
MAX_CONTEXT_FILES = 12
# Reserved room, so neither kind can starve the other. The remainder of the cap is
# filled from whichever kind has files left over.
_RESERVED_AGENT_FILES = 8
_RESERVED_ADRS = 4


def _agent_context_files(project_path: Path) -> list[tuple[str, Path]]:
    """Agent-context files, root first and then by depth, in a stable order."""
    found: list[tuple[str, Path]] = []
    seen: set[Path] = set()

    for kind, name in _ROOT_FILES:
        path = project_path / name
        if path.is_file():
            found.append((kind, path))
            seen.add(path)

    nested: list[tuple[int, str, str, Path]] = []
    for dirpath, dirnames, filenames in os.walk(project_path):
        current = Path(dirpath)
        depth = len(current.relative_to(project_path).parts)
        if depth >= MAX_DEPTH:
            dirnames.clear()
            continue
        # Pruned in place, which is what stops os.walk descending into them at all.
        dirnames[:] = sorted(d for d in dirnames if d not in _PRUNED and not d.startswith(".git"))

        present = set(filenames)
        for kind, name in _NESTED_FILES:
            if name not in present:
                continue
            path = current / name
            if path in seen:
                continue
            nested.append((depth, str(path.relative_to(project_path)), kind, path))

    for _, _, kind, path in sorted(nested, key=lambda item: (item[0], item[1])):
        found.append((kind, path))
    return found


def _adr_files(project_path: Path) -> list[tuple[str, Path]]:
    """Architecture decision records, in the order their numbering implies."""
    found: list[tuple[str, Path]] = []
    for relative in _ADR_DIRS:
        directory = project_path / relative
        if not directory.is_dir():
            continue
        for path in sorted(directory.iterdir()):
            if not path.is_file() or not _ADR_FILE.match(path.name):
                continue
            if _ADR_SKIP.match(path.name):
                continue
            found.append(("adr", path))
    return found


def _apply_cap(
    agent_files: list[tuple[str, Path]],
    adrs: list[tuple[str, Path]],
    max_files: int,
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """Split into what is read and what is dropped, honouring both reservations."""
    agent_room = min(_RESERVED_AGENT_FILES, max_files)
    adr_room = min(_RESERVED_ADRS, max(0, max_files - agent_room))
    kept = agent_files[:agent_room] + adrs[:adr_room]
    spare = max_files - len(kept)
    leftover = agent_files[agent_room:] + adrs[adr_room:]
    kept += leftover[:spare]

    dropped = [item for item in agent_files + adrs if item not in kept]
    # Re-ordered to discovery order rather than reservation order, so the prompt
    # and the fragment ids follow the shape of the repository.
    order = {item: index for index, item in enumerate(agent_files + adrs)}
    return sorted(kept, key=lambda item: order[item]), dropped


def context_files(
    project_path: Path, max_files: int = MAX_CONTEXT_FILES
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """(read, dropped) context files as `(kind, path)` pairs.

    Dropped files are returned rather than discarded so the caller can say how
    many were left out and of what kind. Reporting the cap is the price of having
    one.
    """
    return _apply_cap(_agent_context_files(project_path), _adr_files(project_path), max_files)
