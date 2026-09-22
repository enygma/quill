from pathlib import Path

import pytest

import quill.config as config_module
from quill.config import AIConfig, QuillConfig, load_settings, resolve_notes_dir, save_settings, set_setting


def test_load_settings_defaults_when_no_rc_file() -> None:
    cfg = load_settings()
    assert cfg.ai.provider == "anthropic"
    assert cfg.ai.enabled is True


def test_save_and_reload_roundtrip(tmp_path: Path) -> None:
    cfg = QuillConfig(notes_dir=tmp_path / "notes", ai=AIConfig(model="claude-opus-5", enabled=False))
    save_settings(cfg)
    reloaded = load_settings()
    assert reloaded.notes_dir == (tmp_path / "notes").resolve()
    assert reloaded.ai.model == "claude-opus-5"
    assert reloaded.ai.enabled is False


def test_default_history_settings() -> None:
    cfg = QuillConfig(notes_dir=Path("/nonexistent"))
    assert cfg.history_enabled is True
    assert cfg.max_revisions == 5


def test_default_notebook_is_default() -> None:
    cfg = QuillConfig(notes_dir=Path("/nonexistent"))
    assert cfg.current_notebook == "Default"


def test_current_notebook_roundtrip(tmp_path: Path) -> None:
    cfg = QuillConfig(notes_dir=tmp_path / "notes", current_notebook="Work")
    save_settings(cfg)
    reloaded = load_settings()
    assert reloaded.current_notebook == "Work"


def test_set_setting_current_notebook(tmp_path: Path) -> None:
    set_setting("current_notebook", "Personal")
    assert load_settings().current_notebook == "Personal"


def test_set_setting_current_notebook_rejects_empty() -> None:
    with pytest.raises(ValueError):
        set_setting("current_notebook", "   ")


def test_load_config_runs_migration_and_resolves_notebook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from quill.config import load_config
    from quill.storage import NoteStore

    notes_dir = tmp_path / "notes"
    store = NoteStore(notes_dir)
    store.create("Legacy Note")

    monkeypatch.delenv("QUILL_NOTES_DIR", raising=False)
    cfg = load_config(str(notes_dir), cli_notebook="Work")
    assert cfg.current_notebook == "Work"
    assert (notes_dir / "Default" / "legacy-note.md").exists()


def test_history_settings_roundtrip(tmp_path: Path) -> None:
    cfg = QuillConfig(notes_dir=tmp_path / "notes", history_enabled=False, max_revisions=10)
    save_settings(cfg)
    reloaded = load_settings()
    assert reloaded.history_enabled is False
    assert reloaded.max_revisions == 10


def test_set_setting_history_fields(tmp_path: Path) -> None:
    set_setting("history_enabled", "false")
    set_setting("max_revisions", "3")
    cfg = load_settings()
    assert cfg.history_enabled is False
    assert cfg.max_revisions == 3


def test_set_setting_notes_dir(tmp_path: Path) -> None:
    new_dir = tmp_path / "somewhere"
    set_setting("notes_dir", str(new_dir))
    assert load_settings().notes_dir == new_dir.resolve()


def test_set_setting_ai_field(tmp_path: Path) -> None:
    set_setting("ai.model", "claude-opus-5")
    set_setting("ai.enabled", "false")
    cfg = load_settings()
    assert cfg.ai.model == "claude-opus-5"
    assert cfg.ai.enabled is False


def test_set_setting_rejects_unknown_key() -> None:
    with pytest.raises(ValueError):
        set_setting("bogus", "x")
    with pytest.raises(ValueError):
        set_setting("ai.bogus", "x")


def test_resolve_notes_dir_precedence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rc_dir = tmp_path / "from-rc"
    save_settings(QuillConfig(notes_dir=rc_dir, ai=AIConfig()))

    # ~/.quillrc wins over the built-in default...
    assert resolve_notes_dir(None) == rc_dir.resolve()

    # ...but QUILL_NOTES_DIR beats the rc file...
    env_dir = tmp_path / "from-env"
    monkeypatch.setenv("QUILL_NOTES_DIR", str(env_dir))
    assert resolve_notes_dir(None) == env_dir.resolve()

    # ...and an explicit --dir beats everything.
    cli_dir = tmp_path / "from-cli"
    assert resolve_notes_dir(str(cli_dir)) == cli_dir.resolve()


def test_rc_path_is_isolated_from_real_home() -> None:
    # Guards the guard: confirms the autouse fixture in conftest.py is
    # actually diverting writes away from the real ~/.quillrc.
    assert config_module.RC_PATH.name != ".quillrc" or "pytest" in str(config_module.RC_PATH)
    assert str(config_module.RC_PATH) != str(Path.home() / ".quillrc")
