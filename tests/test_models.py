from pathlib import Path

from quill.models import Note, parse_dt


def test_markdown_roundtrip(tmp_path: Path) -> None:
    note = Note(
        path=tmp_path / "my-note.md",
        rel_path="my-note",
        title="My Note",
        body="Hello **world**",
        pinned=True,
        tags=["a", "b"],
    )
    note.path.write_text(note.to_markdown())

    loaded = Note.from_file(note.path, tmp_path)
    assert loaded.title == "My Note"
    assert loaded.body == "Hello **world**"
    assert loaded.pinned is True
    assert loaded.tags == ["a", "b"]
    assert loaded.rel_path == "my-note"


def test_from_file_without_frontmatter(tmp_path: Path) -> None:
    path = tmp_path / "plain.md"
    path.write_text("Just some text, no frontmatter.")
    note = Note.from_file(path, tmp_path)
    assert note.title == "plain"
    assert "Just some text" in note.body
    assert note.pinned is False


def test_folder_from_rel_path(tmp_path: Path) -> None:
    note = Note(path=tmp_path / "a/b/c.md", rel_path="a/b/c", title="C")
    assert note.folder == "a/b"


def test_parse_dt_variants() -> None:
    assert parse_dt("2026-09-21T10:00:00") is not None
    assert parse_dt("2026-09-21") is not None
    assert parse_dt("") is None
    assert parse_dt("not-a-date") is None


def test_touch_updates_timestamp() -> None:
    note = Note(path=Path("x.md"), rel_path="x", title="X", updated="2000-01-01T00:00:00")
    note.touch()
    assert note.updated != "2000-01-01T00:00:00"
    assert parse_dt(note.updated) is not None
