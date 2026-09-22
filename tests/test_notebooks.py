from pathlib import Path

from quill.notebooks import DEFAULT_NOTEBOOK, ensure_notebook, list_notebooks, migrate_legacy_notes
from quill.storage import NoteStore


def test_list_notebooks_empty_for_fresh_dir(tmp_path: Path) -> None:
    assert list_notebooks(tmp_path) == []


def test_list_notebooks_excludes_hidden_entries(tmp_path: Path) -> None:
    (tmp_path / "Work").mkdir()
    (tmp_path / "Personal").mkdir()
    (tmp_path / ".notebooks").touch()
    (tmp_path / ".hidden").mkdir()
    assert list_notebooks(tmp_path) == ["Personal", "Work"]


def test_ensure_notebook_creates_directory(tmp_path: Path) -> None:
    path = ensure_notebook(tmp_path, "Work")
    assert path == tmp_path / "Work"
    assert path.is_dir()


def test_ensure_notebook_is_idempotent(tmp_path: Path) -> None:
    ensure_notebook(tmp_path, "Work")
    path = ensure_notebook(tmp_path, "Work")  # should not raise
    assert path.is_dir()


def test_migrate_legacy_notes_moves_everything_into_default(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create("Top Level Note")
    store.create("Nested Note", folder="projects")
    store.create_folder("Templates")
    store.create("A Template", folder="Templates")

    migrate_legacy_notes(tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == [".notebooks", DEFAULT_NOTEBOOK]
    default_dir = tmp_path / DEFAULT_NOTEBOOK
    assert (default_dir / "top-level-note.md").exists()
    assert (default_dir / "projects" / "nested-note.md").exists()
    assert (default_dir / "Templates" / "a-template.md").exists()


def test_migrate_legacy_notes_is_a_noop_on_a_fresh_directory(tmp_path: Path) -> None:
    migrate_legacy_notes(tmp_path)
    assert list(tmp_path.iterdir()) == [tmp_path / ".notebooks"]


def test_migrate_legacy_notes_only_runs_once(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create("Original Note")
    migrate_legacy_notes(tmp_path)

    # Simulate real post-migration usage: a second notebook exists, and the
    # user has emptied out Default. A second migrate call must not disturb
    # either, or re-sweep Work's contents into Default.
    default_dir = tmp_path / DEFAULT_NOTEBOOK
    for item in default_dir.iterdir():
        if item.is_file():
            item.unlink()
    work_dir = tmp_path / "Work"
    work_store = NoteStore(work_dir)
    work_store.create("Work Note")

    migrate_legacy_notes(tmp_path)

    assert sorted(p.name for p in tmp_path.iterdir()) == [".notebooks", DEFAULT_NOTEBOOK, "Work"]
    assert (work_dir / "work-note.md").exists()
    assert list(default_dir.iterdir()) == []


def test_migrated_notebook_is_a_fully_working_notestore(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create("Original Note", body="hello")
    migrate_legacy_notes(tmp_path)

    migrated_store = NoteStore(tmp_path / DEFAULT_NOTEBOOK)
    notes = migrated_store.list_notes()
    assert len(notes) == 1
    assert notes[0].title == "Original Note"
    assert notes[0].body == "hello"
