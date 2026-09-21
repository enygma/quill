from pathlib import Path

import pytest

from quill.storage import NoteNotFoundError, NoteStore, slugify


def test_slugify() -> None:
    assert slugify("Buy Milk!") == "buy-milk"
    assert slugify("  spaced   out  ") == "spaced-out"
    assert slugify("") == "note"


def test_create_and_get(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Grocery List", body="- [ ] milk")
    assert note.rel_path == "grocery-list"
    fetched = store.get("grocery-list")
    assert fetched.title == "Grocery List"
    assert fetched.body == "- [ ] milk"


def test_create_in_folder(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Alpha", folder="projects/work")
    assert note.rel_path == "projects/work/alpha"
    assert (tmp_path / "projects" / "work" / "alpha.md").exists()


def test_duplicate_titles_get_unique_slugs(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    n1 = store.create("Same Title")
    n2 = store.create("Same Title")
    assert n1.rel_path != n2.rel_path
    assert n2.rel_path == "same-title-2"


def test_delete_removes_file_and_empty_dirs(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Alpha", folder="projects/work")
    store.delete(note.rel_path)
    assert not (tmp_path / "projects" / "work").exists()
    assert not (tmp_path / "projects").exists()
    with pytest.raises(NoteNotFoundError):
        store.delete(note.rel_path)


def test_toggle_pin(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Pin me")
    assert note.pinned is False
    pinned = store.toggle_pin(note.rel_path)
    assert pinned.pinned is True
    unpinned = store.toggle_pin(note.rel_path)
    assert unpinned.pinned is False


def test_save_updates_body_and_timestamp(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Note")
    old_updated = note.updated
    note.body = "new content"
    store.save(note)
    reloaded = store.get(note.rel_path)
    assert reloaded.body == "new content"
    assert reloaded.updated >= old_updated


def test_list_notes_skips_hidden_files(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create("Visible")
    (tmp_path / ".hidden.md").write_text("---\ntitle: Hidden\n---\n")
    notes = store.list_notes()
    assert len(notes) == 1
    assert notes[0].title == "Visible"


def test_create_folder_is_empty_but_listed(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create_folder("projects/work")
    assert (tmp_path / "projects" / "work").is_dir()
    assert "projects/work" in store.list_folders()
    assert store.list_notes() == []


def test_create_folder_idempotent(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    store.create_folder("projects")
    store.create_folder("projects")  # should not raise
    assert store.list_folders() == ["projects"]


def test_resolve_link_by_title_and_path(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Project Alpha", folder="projects")
    assert store.resolve_link("Project Alpha").rel_path == note.rel_path
    assert store.resolve_link("project alpha").rel_path == note.rel_path  # case-insensitive
    assert store.resolve_link("projects/project-alpha").rel_path == note.rel_path
    assert store.resolve_link("Nonexistent") is None


def test_root_under_a_symlink_still_resolves(tmp_path: Path) -> None:
    # Regression test: NoteStore._abs_path() resolves symlinks (e.g. macOS's
    # /tmp -> /private/tmp). If self.root weren't resolved the same way,
    # Note.from_file()'s path.relative_to(root) would raise ValueError for
    # every note as soon as it's read back.
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link_dir = tmp_path / "link"
    link_dir.symlink_to(real_dir)

    store = NoteStore(link_dir / "notes")
    note = store.create("Through A Symlink")
    fetched = store.get(note.rel_path)
    assert fetched.title == "Through A Symlink"


def test_rename_moves_file(tmp_path: Path) -> None:
    store = NoteStore(tmp_path)
    note = store.create("Old Title")
    old_path = note.path
    renamed = store.rename(note, "New Title")
    assert renamed.rel_path == "new-title"
    assert not old_path.exists()
    assert renamed.path.exists()
