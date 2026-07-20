"""Unit tests for error -> actionable message mapping (FR-011 / Principle IV)."""

from __future__ import annotations

from specjudge import errors


def test_exit_codes():
    assert errors.InsufficientInfoError("x").exit_code == 2
    assert errors.JudgeUnavailableError("x").exit_code == 3
    assert errors.CatalogError("x").exit_code == 4


def test_ollama_not_running_is_actionable():
    err = errors.ollama_not_running("http://localhost:11434")
    rendered = err.render()
    # Actionable message, not a technical dump.
    assert "ollama" in rendered.lower()
    assert "http://localhost:11434" in rendered
    assert "Traceback" not in rendered


def test_ollama_no_models_suggests_pull():
    err = errors.ollama_no_models("http://localhost:11434")
    assert "pull" in err.render().lower()


def test_selected_model_missing_names_model():
    err = errors.selected_model_missing("llama3.1:8b")
    assert "llama3.1:8b" in err.render()


def test_insufficient_project_message():
    err = errors.insufficient_project()
    assert err.exit_code == 2
    assert "not enough" in err.render().lower()
