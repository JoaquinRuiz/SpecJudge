"""Unit tests for data-state classification (FR-009/010 / Q2)."""

from __future__ import annotations

from specjudge.artifacts import read_project
from specjudge.domain import DataState
from specjudge.rating import load_rules


def test_sufficient_project(project_sufficient):
    analysis = read_project(project_sufficient, load_rules())
    assert analysis.data_state == DataState.SUFFICIENT
    tasks = analysis.artifact("tasks")
    assert tasks is not None and tasks.task_count >= 3


def test_scarce_project(project_scarce):
    # Tasks present but no constitution or spec -> scarce.
    analysis = read_project(project_scarce, load_rules())
    assert analysis.data_state == DataState.SCARCE
    assert analysis.warnings


def test_insufficient_project(project_insufficient):
    # tasks.md exists but has no tasks -> insufficient.
    analysis = read_project(project_insufficient, load_rules())
    assert analysis.data_state == DataState.INSUFFICIENT


def test_missing_tasks_file_is_insufficient(tmp_path):
    (tmp_path / "specs" / "x").mkdir(parents=True)
    analysis = read_project(tmp_path, load_rules())
    assert analysis.data_state == DataState.INSUFFICIENT


def test_scarce_threshold_low_detail(tmp_path):
    feat = tmp_path / "specs" / "001"
    feat.mkdir(parents=True)
    # Only 1 task with a description -> below the minimum -> scarce.
    (feat / "tasks.md").write_text(
        "# Tasks\n- [ ] T001 Build the whole thing here\n", encoding="utf-8"
    )
    (feat / "spec.md").write_text("# Spec\ncontent", encoding="utf-8")
    (tmp_path / ".specify" / "memory").mkdir(parents=True)
    (tmp_path / ".specify" / "memory" / "constitution.md").write_text("# C\nx", encoding="utf-8")
    analysis = read_project(tmp_path, load_rules())
    assert analysis.data_state == DataState.SCARCE
