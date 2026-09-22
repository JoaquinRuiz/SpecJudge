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
* **A file cap.** At most `MAX_CONTEXT_FILES` are read, with reserved room per kind
  so a repository with 88 `AGENTS.md` cannot crowd out its ADRs or its Copilot
  instructions. Whatever is dropped is counted and reported — a cap the user cannot
  see is indistinguishable from having read everything.

Ordering is stable and shallowest-first: context near the root describes the whole
repository, context deep inside describes one corner of it.
"""

from __future__ import annotations

import os
import re
import subprocess
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

# Copilot's path-specific instructions. The directory also holds `*.prompt.md` and
# `*.chatmode.md`, which are saved prompts and personas rather than project context.
_INSTRUCTIONS_DIR = ".github/instructions"
_INSTRUCTIONS_SUFFIX = ".instructions.md"

# How long to wait for `git ls-files` before falling back to walking the tree.
_GIT_TIMEOUT_SECONDS = 10

MAX_DEPTH = 4
MAX_CONTEXT_FILES = 12
# Reserved room, so neither kind can starve the other. The remainder of the cap is
# filled from whichever kind has files left over.
_RESERVED_AGENT_FILES = 8
_RESERVED_ADRS = 4
# Instruction files are already filtered by `applyTo` before they reach the cap, so
# the ones that arrive are relevant by construction and a small reservation is
# enough. It exists so a repository with many of them cannot push out its AGENTS.md
# — and vice versa.
_RESERVED_INSTRUCTIONS = 4


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


def instruction_files(project_path: Path) -> list[Path]:
    """Copilot's path-specific instruction files, in a stable order.

    Scanned directly rather than through the tree walk above, which prunes any
    directory starting with `.git` and so never reaches `.github` at all. The same
    reason `copilot-instructions.md` is listed as a root file.
    """
    directory = project_path / _INSTRUCTIONS_DIR
    if not directory.is_dir():
        return []
    found = [
        path
        for path in directory.rglob(f"*{_INSTRUCTIONS_SUFFIX}")
        if path.is_file() and not path.name.startswith(".")
    ]
    return sorted(found, key=lambda path: str(path.relative_to(project_path)))


def repository_paths(project_path: Path) -> list[str]:
    """Every file in the project, project-relative, for matching `applyTo` against.

    `git ls-files` rather than another walk. An `applyTo` of `**/*.java` has to see
    a file eight directories down, and `MAX_DEPTH` exists precisely to stop the
    context walk going that deep — raising it for everyone would make discovery pay
    for this feature on every repository. Git already holds the full list, is
    faster than any walk, and its list is the tracked one, so build output and
    anything else in `.gitignore` is excluded for free.

    Falls back to a pruned walk when there is no git, no repository, or git takes
    too long: a project that is not version controlled still deserves an answer.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(project_path), "ls-files", "-z"],
            capture_output=True,
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return _walked_paths(project_path)

    if result.returncode != 0:
        return _walked_paths(project_path)

    listed = result.stdout.decode("utf-8", errors="replace").split("\0")
    paths = [entry for entry in listed if entry]
    # An empty repository is indistinguishable here from a directory git does not
    # track, and the walk answers both correctly.
    return paths or _walked_paths(project_path)


def _walked_paths(project_path: Path) -> list[str]:
    """The fallback listing, pruned the same way the context walk is."""
    paths: list[str] = []
    for dirpath, dirnames, filenames in os.walk(project_path):
        current = Path(dirpath)
        dirnames[:] = sorted(d for d in dirnames if d not in _PRUNED and d != ".git")
        for name in sorted(filenames):
            paths.append(str((current / name).relative_to(project_path)).replace(os.sep, "/"))
    return paths


def _apply_cap(
    agent_files: list[tuple[str, Path]],
    adrs: list[tuple[str, Path]],
    instructions: list[tuple[str, Path]],
    max_files: int,
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """Split into what is read and what is dropped, honouring every reservation."""
    agent_room = min(_RESERVED_AGENT_FILES, max_files)
    adr_room = min(_RESERVED_ADRS, max(0, max_files - agent_room))
    instruction_room = min(_RESERVED_INSTRUCTIONS, max(0, max_files - agent_room - adr_room))

    kept = agent_files[:agent_room] + adrs[:adr_room] + instructions[:instruction_room]
    spare = max_files - len(kept)
    leftover = agent_files[agent_room:] + adrs[adr_room:] + instructions[instruction_room:]
    kept += leftover[:spare]

    everything = agent_files + adrs + instructions
    dropped = [item for item in everything if item not in kept]
    # Re-ordered to discovery order rather than reservation order, so the prompt
    # and the fragment ids follow the shape of the repository.
    order = {item: index for index, item in enumerate(everything)}
    return sorted(kept, key=lambda item: order[item]), dropped


def context_files(
    project_path: Path,
    max_files: int = MAX_CONTEXT_FILES,
    instructions: list[Path] | None = None,
) -> tuple[list[tuple[str, Path]], list[tuple[str, Path]]]:
    """(read, dropped) context files as `(kind, path)` pairs.

    Dropped files are returned rather than discarded so the caller can say how
    many were left out and of what kind. Reporting the cap is the price of having
    one.

    `instructions` arrives already filtered by `applyTo`, because deciding which
    of them apply needs the plan and the tasks — which this module does not read.
    """
    applicable = [("instructions", path) for path in (instructions or [])]
    return _apply_cap(
        _agent_context_files(project_path),
        _adr_files(project_path),
        applicable,
        max_files,
    )
