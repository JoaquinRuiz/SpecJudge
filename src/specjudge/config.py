"""Persistent user configuration (config.toml via platformdirs).

Stores the judge preference across runs (FR-012/013). Atomic writes so a failure
cannot corrupt the config. Never contains artifact content.
"""

from __future__ import annotations

import os
import tomllib
from pathlib import Path

from platformdirs import user_config_dir

from .domain import JudgePreference, UserConfig

APP_NAME = "specjudge"
DEFAULT_HOST = "http://localhost:11434"


def config_path() -> Path:
    return Path(user_config_dir(APP_NAME)) / "config.toml"


def load_config(path: Path | None = None) -> UserConfig:
    cfg_path = path or config_path()
    host = os.environ.get("OLLAMA_HOST", DEFAULT_HOST)

    if not cfg_path.is_file():
        return UserConfig(ollama_host=host)

    try:
        raw = tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError):
        # Corrupt config: degrade to defaults instead of breaking.
        return UserConfig(ollama_host=host)

    # Environment OLLAMA_HOST wins; then the config value; then the default.
    host = os.environ.get("OLLAMA_HOST") or raw.get("ollama_host") or DEFAULT_HOST

    pref = None
    jp = raw.get("judge_preference")
    if isinstance(jp, dict) and jp.get("judge_model"):
        pref = JudgePreference(
            judge_model=str(jp["judge_model"]),
            chosen_at=str(jp["chosen_at"]) if jp.get("chosen_at") else None,
        )

    return UserConfig(ollama_host=str(host), judge_preference=pref)


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def save_config(config: UserConfig, path: Path | None = None) -> Path:
    """Write the config atomically (temp file + rename)."""
    cfg_path = path or config_path()
    cfg_path.parent.mkdir(parents=True, exist_ok=True)

    lines = [f'ollama_host = "{_toml_escape(config.ollama_host)}"', ""]
    if config.judge_preference is not None:
        pref = config.judge_preference
        lines.append("[judge_preference]")
        lines.append(f'judge_model = "{_toml_escape(pref.judge_model)}"')
        if pref.chosen_at:
            lines.append(f'chosen_at = "{_toml_escape(pref.chosen_at)}"')
        lines.append("")

    tmp_path = cfg_path.with_suffix(cfg_path.suffix + ".tmp")
    tmp_path.write_text("\n".join(lines), encoding="utf-8")
    os.replace(tmp_path, cfg_path)
    return cfg_path
