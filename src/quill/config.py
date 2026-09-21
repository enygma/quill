"""Global settings for Quill, stored in ~/.quillrc (YAML)."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path

import yaml

DEFAULT_NOTES_DIR = Path.home() / ".quill"
RC_PATH = Path.home() / ".quillrc"


@dataclass
class AIConfig:
    provider: str = "anthropic"
    model: str = "claude-sonnet-5"
    api_key_env: str = "ANTHROPIC_API_KEY"
    api_key: str | None = None
    enabled: bool = True


SAVE_MODES = ("autosave", "manual")


@dataclass
class QuillConfig:
    notes_dir: Path
    ai: AIConfig = field(default_factory=AIConfig)
    save_mode: str = "autosave"  # "autosave" or "manual" (ctrl+s only)
    autosave_interval: float = 5.0  # seconds; only used when save_mode == "autosave"

    def to_dict(self) -> dict:
        return {
            "notes_dir": str(self.notes_dir),
            "ai": asdict(self.ai),
            "save_mode": self.save_mode,
            "autosave_interval": self.autosave_interval,
        }


def _default_config() -> QuillConfig:
    return QuillConfig(notes_dir=DEFAULT_NOTES_DIR.resolve(), ai=AIConfig())


def _read_rc() -> dict:
    if not RC_PATH.exists():
        return {}
    try:
        data = yaml.safe_load(RC_PATH.read_text())
    except yaml.YAMLError:
        return {}
    return data if isinstance(data, dict) else {}


def load_settings() -> QuillConfig:
    """Load settings from ~/.quillrc, falling back to defaults for anything
    unset. Does not apply CLI/env overrides for notes_dir; see resolve_notes_dir."""
    data = _read_rc()
    cfg = _default_config()

    notes_dir = data.get("notes_dir")
    if notes_dir:
        cfg.notes_dir = Path(notes_dir).expanduser().resolve()

    ai_data = data.get("ai", {}) if isinstance(data.get("ai"), dict) else {}
    valid_keys = {f.name for f in fields(AIConfig)}
    cfg.ai = AIConfig(**{k: v for k, v in ai_data.items() if k in valid_keys})

    save_mode = data.get("save_mode")
    if save_mode in SAVE_MODES:
        cfg.save_mode = save_mode

    autosave_interval = data.get("autosave_interval")
    if autosave_interval is not None:
        try:
            cfg.autosave_interval = max(1.0, float(autosave_interval))
        except (TypeError, ValueError):
            pass

    return cfg


def save_settings(cfg: QuillConfig) -> None:
    RC_PATH.write_text(yaml.safe_dump(cfg.to_dict(), sort_keys=False))


def resolve_notes_dir(cli_dir: str | None = None) -> Path:
    """Determine which directory notes should be stored/read from.

    Precedence: --dir flag > QUILL_NOTES_DIR env var > ~/.quillrc > ~/.quill
    """
    if cli_dir:
        return Path(cli_dir).expanduser().resolve()
    env_dir = os.environ.get("QUILL_NOTES_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    return load_settings().notes_dir


def load_config(cli_dir: str | None = None) -> QuillConfig:
    cfg = load_settings()
    cfg.notes_dir = resolve_notes_dir(cli_dir)
    cfg.notes_dir.mkdir(parents=True, exist_ok=True)
    if not RC_PATH.exists():
        save_settings(cfg)
    return cfg


def set_setting(dotted_key: str, value: str) -> QuillConfig:
    """Set a dotted setting key (e.g. 'notes_dir' or 'ai.model') and persist it."""
    cfg = load_settings()
    if dotted_key == "notes_dir":
        cfg.notes_dir = Path(value).expanduser().resolve()
    elif dotted_key == "save_mode":
        if value not in SAVE_MODES:
            raise ValueError(f"save_mode must be one of {SAVE_MODES}")
        cfg.save_mode = value
    elif dotted_key == "autosave_interval":
        try:
            cfg.autosave_interval = max(1.0, float(value))
        except ValueError:
            raise ValueError("autosave_interval must be a number") from None
    elif dotted_key.startswith("ai."):
        attr = dotted_key.split(".", 1)[1]
        if attr not in {f.name for f in fields(AIConfig)}:
            raise ValueError(f"Unknown AI setting: {attr}")
        if attr == "enabled":
            value = value.strip().lower() in {"1", "true", "yes", "on"}
        setattr(cfg.ai, attr, value)
    else:
        raise ValueError(f"Unknown setting: {dotted_key}")
    save_settings(cfg)
    return cfg
