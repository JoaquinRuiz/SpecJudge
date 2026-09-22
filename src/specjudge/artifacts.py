"""Locating, reading and classifying the SDD artifacts.

Determines the project data state (FR-009/010 / Clarifications Q2):
- insufficient: tasks missing / unreadable / empty -> no recommendation.
- scarce: tasks present but constitution or spec missing, or thin detail -> with warning.
- sufficient: all three present, readable and with content.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .discovery import context_files, instruction_files, repository_paths
from .domain import (
    DataState,
    InstructionFile,
    InstructionsMode,
    ProjectAnalysis,
    RatingRules,
    SDDArtifact,
)
from .instructions import decide, planned_paths
from .sources import is_generated, plan_path, summarize_kinds

# A task "with a description" = checklist line with substantial text after the id.
_TASK_LINE = re.compile(r"^\s*-\s*\[[ xX]\]\s+(.*\S.*)$")


def _resolve_feature_dir(project_path: Path) -> Path | None:
    feature_json = project_path / ".specify" / "feature.json"
    if feature_json.is_file():
        try:
            data = json.loads(feature_json.read_text(encoding="utf-8"))
            fd = data.get("feature_directory")
            if fd:
                return project_path / fd
        except (json.JSONDecodeError, OSError):
            return None
    return None


def _find_latest_spec_dir(project_path: Path) -> Path | None:
    specs = project_path / "specs"
    if not specs.is_dir():
        return None
    candidates = sorted(p for p in specs.iterdir() if p.is_dir())
    return candidates[-1] if candidates else None


def _read_artifact(type_: str, path: Path) -> SDDArtifact:
    if not path.is_file():
        return SDDArtifact(type=type_, path=str(path), present=False, readable=False)
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return SDDArtifact(type=type_, path=str(path), present=True, readable=False)
    return SDDArtifact(type=type_, path=str(path), present=True, readable=True, content=content)


def _count_detailed_tasks(content: str) -> int:
    count = 0
    for line in content.splitlines():
        m = _TASK_LINE.match(line)
        if m and len(m.group(1).strip()) >= 10:
            count += 1
    return count


def read_project(project_path: Path | str, rules: RatingRules) -> ProjectAnalysis:
    project_path = Path(project_path)

    feature_dir = _resolve_feature_dir(project_path) or _find_latest_spec_dir(project_path)

    constitution_path = project_path / ".specify" / "memory" / "constitution.md"
    spec_path = (feature_dir / "spec.md") if feature_dir else (project_path / "spec.md")
    tasks_path = (feature_dir / "tasks.md") if feature_dir else (project_path / "tasks.md")

    constitution = _read_artifact("constitution", constitution_path)
    spec = _read_artifact("spec", spec_path)
    tasks = _read_artifact("tasks", tasks_path)
    plan = _read_artifact("plan", plan_path(feature_dir, project_path))

    if tasks.readable:
        tasks.task_count = _count_detailed_tasks(tasks.content)

    warnings: list[str] = []

    # Decided before the rest of the context is read, because `applyTo` is matched
    # against what the plan and the tasks say will be built — so those have to be
    # on hand first (FR-024).
    instructions = _decide_instructions(project_path, plan, tasks, rules.instructions_mode)
    applicable = [project_path / i.path for i in instructions if i.included]

    # Context files are read alongside the SDD artifacts, never instead of them:
    # they describe the environment, the artifacts describe the work, and the two
    # do not overlap (FR-024).
    environment = _read_environment(project_path, rules.max_context_files, warnings, applicable)

    artifacts = [constitution, spec, tasks, plan, *environment]

    excluded = [i for i in instructions if not i.included]
    if excluded:
        names = ", ".join(f"{i.path} ({i.reason})" for i in excluded)
        warnings.append(
            f"Skipped {len(excluded)} path-specific instruction file(s): {names}. "
            f"Set sources.instructions: all in the rating rules to read them anyway."
        )

    data_state = _classify(constitution, spec, tasks, environment, rules, warnings)

    return ProjectAnalysis(
        artifacts=artifacts,
        data_state=data_state,
        warnings=warnings,
        root=str(project_path),
        instructions=instructions,
    )


def _decide_instructions(
    project_path: Path,
    plan: SDDArtifact,
    tasks: SDDArtifact,
    mode: InstructionsMode,
) -> list[InstructionFile]:
    """Every `*.instructions.md` found, with the verdict on each (FR-024)."""
    found = instruction_files(project_path)
    if not found:
        return []

    contents: list[tuple[Path, str]] = []
    for path in found:
        try:
            contents.append((path, path.read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            # Unreadable here means unreadable later too; skipping it keeps the
            # verdict list honest rather than promising content that never arrives.
            continue

    planned = planned_paths([a.content for a in (plan, tasks) if a.usable])
    # Only worth the subprocess when something might still match on disk.
    existing = repository_paths(project_path) if mode is InstructionsMode.MATCHING else []
    return decide(contents, existing, planned, mode, project_path)


def _read_environment(
    project_path: Path,
    max_files: int,
    warnings: list[str],
    instructions: list[Path] | None = None,
) -> list[SDDArtifact]:
    """Every context file that survives discovery, the cap and the generated check."""
    found, dropped = context_files(project_path, max_files, instructions)

    if dropped:
        # A cap the user cannot see reads as "we read everything" (FR-025).
        warnings.append(
            f"Read {len(found)} context files; {len(dropped)} more were found and left "
            f"out ({summarize_kinds([kind for kind, _ in dropped])}). Context near the "
            f"repository root is kept first."
        )

    environment: list[SDDArtifact] = []
    generated: list[tuple[str, Path]] = []
    for kind, path in found:
        artifact = _read_artifact(kind, path)
        if artifact.usable and is_generated(artifact.content):
            generated.append((kind, path))
            continue
        environment.append(artifact)

    if generated:
        names = ", ".join(str(p.relative_to(project_path)) for _, p in generated)
        warnings.append(
            f"Ignored {len(generated)} generated context file(s) ({names}): they say a "
            f"tool wrote them, and generated context mostly restates what the code "
            f"already shows. Remove the generated marker if you wrote it yourself."
        )

    return environment


def _classify(
    constitution: SDDArtifact,
    spec: SDDArtifact,
    tasks: SDDArtifact,
    environment: list[SDDArtifact],
    rules: RatingRules,
    warnings: list[str],
) -> DataState:
    has_tasks = tasks.present and tasks.readable and tasks.task_count > 0

    if not has_tasks:
        # Without tasks there is nothing describing the work. That used to end the
        # run — which shut the door on every repository that documents itself with
        # an AGENTS.md instead of a spec, i.e. most of them.
        #
        # If the repository does describe its environment, there is enough for a
        # floor: how demanding this codebase is to work in at all. That is `scarce`,
        # not `sufficient` — a real answer, openly a weak one (FR-024).
        if any(a.usable for a in environment):
            names = summarize_kinds([a.type for a in environment if a.usable])
            warnings.append(
                f"No tasks or specification found; judged from environment context only "
                f"({names}). This is a floor — how demanding this repository is to work "
                f"in — not a recommendation for a specific piece of work."
            )
            return DataState.SCARCE
        return DataState.INSUFFICIENT

    min_detailed = int(rules.scarce_thresholds.get("min_detailed_tasks", 3))

    missing = []
    if not (constitution.present and constitution.readable and constitution.content.strip()):
        missing.append("constitution")
    if not (spec.present and spec.readable and spec.content.strip()):
        missing.append("specification")

    scarce = False
    if missing:
        warnings.append(
            "Missing artifacts (" + ", ".join(missing) + "); the recommendation could improve."
        )
        scarce = True
    if tasks.task_count < min_detailed:
        warnings.append(
            f"Tasks are thin on detail ({tasks.task_count} with a description; "
            f"recommended minimum {min_detailed}); the recommendation could improve."
        )
        scarce = True

    return DataState.SCARCE if scarce else DataState.SUFFICIENT
