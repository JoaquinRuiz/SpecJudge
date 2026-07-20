"""Unit tests for user configuration (atomic roundtrip) - T049."""

from __future__ import annotations

from specjudge.config import load_config, save_config
from specjudge.domain import JudgePreference, UserConfig


def test_roundtrip(tmp_path):
    cfg_path = tmp_path / "config.toml"
    config = UserConfig(
        ollama_host="http://localhost:11434",
        judge_preference=JudgePreference(judge_model="llama3.1:8b", chosen_at="2026-07-20"),
    )
    save_config(config, cfg_path)
    loaded = load_config(cfg_path)
    assert loaded.judge_preference is not None
    assert loaded.judge_preference.judge_model == "llama3.1:8b"
    assert loaded.ollama_host == "http://localhost:11434"


def test_missing_file_returns_defaults(tmp_path):
    loaded = load_config(tmp_path / "nope.toml")
    assert loaded.judge_preference is None
    assert loaded.ollama_host == "http://localhost:11434"


def test_corrupt_config_degrades_gracefully(tmp_path):
    cfg_path = tmp_path / "config.toml"
    cfg_path.write_text("this is = = not valid toml [[[", encoding="utf-8")
    loaded = load_config(cfg_path)
    assert loaded.judge_preference is None


def test_atomic_write_no_tmp_left(tmp_path):
    cfg_path = tmp_path / "config.toml"
    save_config(UserConfig(judge_preference=JudgePreference("m")), cfg_path)
    assert cfg_path.is_file()
    assert not (tmp_path / "config.toml.tmp").exists()
