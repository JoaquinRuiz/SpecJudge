"""Copilot path-specific instructions, and deciding which of them apply (FR-024).

`.github/instructions/*.instructions.md` is where Copilot keeps the guidance that
only holds for part of a repository — the Java conventions, the React conventions —
each file carrying an `applyTo` glob naming the files it governs. Projects that use
them do so precisely to keep the constitution short, which means the guidance
SpecJudge most wants to read is the guidance it was ignoring.

Reading them raises a question the other context formats never posed: `applyTo`
selects by *file*, and SpecJudge runs before the files exist. There is no diff to
match against, and asking the judge to guess applicability would put an inference
in front of the evidence — the opposite of FR-020.

So applicability is decided deterministically, against two sources of paths:

* **what the repository already contains** — accurate for a mature codebase, and
  silent on a feature whose code has not been written;
* **what `plan.md` and `tasks.md` say will be written** — a task promising
  `src/main/java/.../FooService.java` makes `**/*.java` apply before that file
  exists, which is the greenfield half the repository alone cannot answer.

Neither is sufficient alone and together they cover the realistic cases, so a file
applies when *either* matches. A file whose glob matches nothing is not silently
dropped: it is reported as excluded, with the reason, because context that vanishes
without a trace is indistinguishable from context that was never there.

One deliberate non-default: an instructions file with no `applyTo` is excluded.
VS Code does not auto-apply those either — "If not specified, the instructions are
not applied automatically, but you can still add them manually to a chat request" —
so treating a missing glob as "applies to everything" would feed the judge context
the coding agent itself would not have used. `sources.instructions: all` overrides
the whole decision for the greenfield case where nothing matches yet.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

from .domain import InstructionFile, InstructionsMode

# `---\n...\n---` at the very top of the file. Anywhere else it is a horizontal rule.
_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)

# A path-shaped token in prose: `src/main/java/FooService.java`, `tests/test_api.py`.
# Requires a real extension, which is what separates a path from an ordinary word.
_PATH_TOKEN = re.compile(r"[A-Za-z0-9_@\-./]*[A-Za-z0-9_@\-]\.[A-Za-z][A-Za-z0-9_+]{0,11}")
# `v1.2` and `0.5.5` are path-shaped and are not paths.
_VERSION = re.compile(r"\A[vV]?[\d.]+\Z")


def parse_apply_to(text: str) -> str | None:
    """The raw `applyTo` string, or None when the file declares no glob.

    None and `""` mean the same thing to the caller and both are reported as a
    missing glob, so a malformed frontmatter degrades to "not auto-applied"
    rather than to "applies everywhere" — the safe direction of the two.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        return None
    try:
        data = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None
    if not isinstance(data, dict):
        return None
    value = data.get("applyTo")
    if value is None:
        return None
    # A YAML list is not the documented shape, but it is the obvious mistake to
    # make and carries the same meaning as the comma-separated string.
    if isinstance(value, list):
        return ",".join(str(v).strip() for v in value if str(v).strip())
    return str(value).strip()


def split_patterns(apply_to: str) -> list[str]:
    """`"**/*.ts,**/*.tsx"` -> the two globs it holds.

    Comma-separated is the form the VS Code docs show, so brace expansion is not
    supported: `{ts,tsx}` would be cut in half by the same separator.
    """
    return [p.strip() for p in apply_to.split(",") if p.strip()]


def _translate(pattern: str) -> str:
    """One glob as a regex, with `**` crossing directories and `*` not.

    `fnmatch` is the obvious tool and the wrong one: there `*` matches separators
    too, so `*.java` would match `src/main/Foo.java` and every glob would be
    effectively recursive. `PurePath.full_match` has the right semantics and
    arrived in 3.13, which is past the floor this project supports.
    """
    p = pattern.strip().replace("\\", "/")
    if p.startswith("./"):
        p = p[2:]
    p = p.lstrip("/")

    out: list[str] = []
    i, n = 0, len(p)
    while i < n:
        char = p[i]
        if char == "*":
            j = i
            while j < n and p[j] == "*":
                j += 1
            if j - i >= 2:
                if j < n and p[j] == "/":
                    # `**/` spans zero or more directories, so `**/*.java` has to
                    # match a root-level `Foo.java` as well as a deeply nested one.
                    out.append("(?:[^/]*/)*")
                    i = j + 1
                    continue
                out.append(".*")
            else:
                out.append("[^/]*")
            i = j
            continue
        if char == "?":
            out.append("[^/]")
            i += 1
            continue
        out.append(re.escape(char))
        i += 1
    return "".join(out)


def compile_patterns(apply_to: str) -> list[re.Pattern[str]]:
    return [re.compile(f"(?s:{_translate(p)})\\Z") for p in split_patterns(apply_to)]


def _normalize(path: str) -> str:
    """A project-relative path in the form the globs are written against.

    The VS Code docs define `applyTo` as "relative to the workspace root", so
    matching happens on forward slashes with no leading `./`.
    """
    clean = path.strip().replace("\\", "/")
    while clean.startswith("./"):
        clean = clean[2:]
    return clean.lstrip("/")


def first_match(patterns: list[re.Pattern[str]], paths: list[str]) -> str | None:
    """The first path any pattern accepts — the evidence for including a file."""
    for path in paths:
        for pattern in patterns:
            if pattern.match(path):
                return path
    return None


def planned_paths(texts: list[str]) -> list[str]:
    """Paths a plan or a task list says will exist, in first-seen order.

    Matching only against files already on disk would answer "which instructions
    govern this repository" when the question is "which govern this feature", and
    on a new feature the two differ completely: the Java conventions apply because
    a task promises a `.java` file, not because one is already there.
    """
    seen: list[str] = []
    for text in texts:
        for token in _PATH_TOKEN.findall(text):
            candidate = _normalize(token.strip("./"))
            if not candidate or _VERSION.match(candidate):
                continue
            if candidate not in seen:
                seen.append(candidate)
    return seen


def decide(
    files: list[tuple[Path, str]],
    repository_paths: list[str],
    planned: list[str],
    mode: InstructionsMode,
    root: Path,
) -> list[InstructionFile]:
    """Which instruction files apply, and the reason for every verdict.

    `files` is `(path, text)` for each discovered `*.instructions.md`. The reasons
    are part of the output contract, not debugging output: an `applyTo` that
    matches nothing is a silent no-op otherwise, and the fix — a wrong glob, or a
    task that never names the file it creates — is only visible if the tool says
    which of the two happened.
    """
    decisions: list[InstructionFile] = []
    for path, text in files:
        relative = _normalize(str(path.relative_to(root)))
        apply_to = parse_apply_to(text) or ""

        if mode is InstructionsMode.ALL:
            decisions.append(
                InstructionFile(
                    path=relative,
                    apply_to=apply_to,
                    included=True,
                    reason="sources.instructions: all",
                )
            )
            continue

        if not apply_to:
            decisions.append(
                InstructionFile(
                    path=relative,
                    apply_to="",
                    included=False,
                    reason="no applyTo, not auto-applied",
                )
            )
            continue

        patterns = compile_patterns(apply_to)
        planned_hit = first_match(patterns, planned)
        if planned_hit:
            decisions.append(
                InstructionFile(
                    path=relative,
                    apply_to=apply_to,
                    included=True,
                    reason=f"matches a path the plan or tasks will create: {planned_hit}",
                )
            )
            continue

        repo_hit = first_match(patterns, repository_paths)
        if repo_hit:
            decisions.append(
                InstructionFile(
                    path=relative,
                    apply_to=apply_to,
                    included=True,
                    reason=f"matches a file in the repository: {repo_hit}",
                )
            )
            continue

        decisions.append(
            InstructionFile(
                path=relative,
                apply_to=apply_to,
                included=False,
                reason="applyTo matched no repository file and no planned path",
            )
        )
    return decisions
